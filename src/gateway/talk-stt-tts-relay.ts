// Gateway Talk STT-TTS relay.
// Bridges browser Talk audio sessions with offline STT and TTS providers.
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { resolveExpiresAtMsFromDurationMs } from "@openclaw/normalization-core/number-coercion";
import { dispatchInboundMessage } from "../auto-reply/dispatch.js";
import { createReplyDispatcher } from "../auto-reply/reply/reply-dispatcher.js";
import type { MsgContext } from "../auto-reply/templating.js";
import { resolveSessionFilePath } from "../config/sessions.js";
import { appendSessionTranscriptMessage } from "../config/sessions/transcript-append.js";
import { transcribeAudioFile } from "../media-understanding/runtime.js";
import { recordTalkObservabilityEvent } from "../talk/observability.js";
import {
  type TalkEvent,
  type TalkSessionController,
  createTalkSessionController,
} from "../talk/talk-session-controller.js";
import { synthesizeSpeech } from "../tts/tts.js";
import { appendInjectedAssistantMessageToTranscript } from "./server-methods/chat-transcript-inject.js";
import type { GatewayRequestContext } from "./server-methods/shared-types.js";
import { loadSessionEntry } from "./session-utils.js";
import {
  closeExpiredTalkRelaySessions,
  requireActiveTalkRelaySession,
} from "./talk-relay-session-lifecycle.js";
import { forgetUnifiedTalkSession } from "./talk-session-registry.js";

const STT_TTS_SESSION_TTL_MS = 30 * 60 * 1000;
const MAX_AUDIO_BASE64_BYTES = 512 * 1024;
const MAX_STT_TTS_SESSIONS_PER_CONN = 2;
const MAX_STT_TTS_SESSIONS_GLOBAL = 64;
const TALK_EVENT = "talk.event";

// We use 24kHz PCM16 for maximum audio quality with Kokoro/VibeVoice
const RELAY_INPUT_ENCODING = "pcm16";
const RELAY_INPUT_SAMPLE_RATE_HZ = 24000;
const RELAY_OUTPUT_ENCODING = "pcm16";
const RELAY_OUTPUT_SAMPLE_RATE_HZ = 24000;

// VAD Constants
const VAD_RMS_THRESHOLD = 0.015;
const VAD_SILENCE_DURATION_MS = 1000;

export type SttTtsRelaySession = {
  id: string;
  connId: string;
  context: GatewayRequestContext;
  talk: TalkSessionController;
  sessionKey: string;
  agentId?: string;
  expiresAtMs: number;
  cleanupTimer: ReturnType<typeof setTimeout>;
  closed: boolean;

  // Audio state
  audioChunks: Buffer[];
  isSpeaking: boolean;
  silenceDurationMs: number;
  chunkCount: number;

  // Active run state
  activeRunAbortController?: AbortController;
  isPlayingAudio: boolean;
};

export type CreateTalkSttTtsRelaySessionParams = {
  context: GatewayRequestContext;
  connId: string;
  sessionKey: string;
  agentId?: string;
  provider?: string;
};

export type TalkSttTtsRelaySessionResult = {
  provider: string;
  transport: "gateway-relay";
  relaySessionId: string;
  audio: {
    inputEncoding: "pcm16";
    inputSampleRateHz: 24000;
    outputEncoding: "pcm16";
    outputSampleRateHz: 24000;
  };
  expiresAt: number;
};

type TalkSttTtsRelayEventPayload =
  | { relaySessionId: string; type: "ready" }
  | { relaySessionId: string; type: "inputAudio"; byteLength: number }
  | { relaySessionId: string; type: "speechStart" }
  | { relaySessionId: string; type: "audio"; audioBase64: string }
  | { relaySessionId: string; type: "clear" }
  | {
      relaySessionId: string;
      type: "transcript";
      role: "user" | "assistant";
      text: string;
      final: boolean;
    }
  | { relaySessionId: string; type: "error"; message: string }
  | { relaySessionId: string; type: "close"; reason: "completed" | "error" };

type TalkSttTtsRelayEvent = TalkSttTtsRelayEventPayload & {
  talkEvent?: TalkEvent;
};

const sttTtsSessions = new Map<string, SttTtsRelaySession>();

function broadcastToOwner(
  context: GatewayRequestContext,
  connId: string,
  event: TalkSttTtsRelayEvent,
): void {
  context.broadcastToConnIds(TALK_EVENT, event, new Set([connId]), { dropIfSlow: true });
}

function writeWavHeader(samplesLength: number, sampleRate: number): Buffer {
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + samplesLength * 2, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(1, 22); // Mono
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(samplesLength * 2, 40);
  return header;
}

function calculateRms(buffer: Buffer): number {
  let sumSquares = 0;
  const samplesCount = Math.floor(buffer.length / 2);
  for (let i = 0; i < samplesCount; i++) {
    const sample = buffer.readInt16LE(i * 2) / 32768;
    sumSquares += sample * sample;
  }
  return samplesCount > 0 ? Math.sqrt(sumSquares / samplesCount) : 0;
}

function ensureSttTtsTurn(session: SttTtsRelaySession): string {
  const turn = session.talk.ensureTurn();
  if (turn.event) {
    broadcastToOwner(session.context, session.connId, {
      relaySessionId: session.id,
      type: "speechStart",
      talkEvent: turn.event,
    });
  }
  return turn.turnId;
}

function closeSttTtsSession(session: SttTtsRelaySession, reason: "completed" | "error"): void {
  if (session.closed) {
    return;
  }
  session.closed = true;
  sttTtsSessions.delete(session.id);
  forgetUnifiedTalkSession(session.id);
  clearTimeout(session.cleanupTimer);

  if (session.activeRunAbortController) {
    session.activeRunAbortController.abort();
  }

  broadcastToOwner(session.context, session.connId, {
    relaySessionId: session.id,
    type: "close",
    reason,
    talkEvent: session.talk.emit({
      type: "session.closed",
      payload: { reason },
      final: true,
    }),
  });
}

function pruneExpiredSttTtsSessions(nowMs = Date.now()): void {
  closeExpiredTalkRelaySessions({
    sessions: sttTtsSessions.values(),
    closeSession: (session) => closeSttTtsSession(session, "completed"),
    nowMs,
  });
}

function countSttTtsSessionsForConn(connId: string): number {
  let count = 0;
  for (const session of sttTtsSessions.values()) {
    if (session.connId === connId) {
      count += 1;
    }
  }
  return count;
}

function enforceSttTtsSessionLimits(connId: string): void {
  pruneExpiredSttTtsSessions();
  if (sttTtsSessions.size >= MAX_STT_TTS_SESSIONS_GLOBAL) {
    throw new Error("Too many active STT-TTS Talk sessions");
  }
  if (countSttTtsSessionsForConn(connId) >= MAX_STT_TTS_SESSIONS_PER_CONN) {
    throw new Error("Too many active STT-TTS Talk sessions for this connection");
  }
}

/** Creates a local STT-TTS relay session and registers it. */
export function createTalkSttTtsRelaySession(
  params: CreateTalkSttTtsRelaySessionParams,
): TalkSttTtsRelaySessionResult {
  enforceSttTtsSessionLimits(params.connId);

  const relaySessionId = randomUUID();
  const expiresAtMs = resolveExpiresAtMsFromDurationMs(STT_TTS_SESSION_TTL_MS);
  if (expiresAtMs === undefined) {
    throw new Error("STT-TTS relay session expiry is outside the supported Date range");
  }

  const talk = createTalkSessionController(
    {
      sessionId: relaySessionId,
      mode: "stt-tts",
      transport: "gateway-relay",
      brain: "agent-consult",
      provider: params.provider ?? "openai",
    },
    { onEvent: recordTalkObservabilityEvent },
  );

  const relay: SttTtsRelaySession = {
    id: relaySessionId,
    connId: params.connId,
    context: params.context,
    talk,
    sessionKey: params.sessionKey,
    agentId: params.agentId,
    expiresAtMs,
    cleanupTimer: setTimeout(() => {
      const active = sttTtsSessions.get(relaySessionId);
      if (active) {
        closeSttTtsSession(active, "completed");
      }
    }, STT_TTS_SESSION_TTL_MS),
    closed: false,
    audioChunks: [],
    isSpeaking: false,
    silenceDurationMs: 0,
    chunkCount: 0,
    isPlayingAudio: false,
  };

  relay.cleanupTimer.unref?.();
  sttTtsSessions.set(relaySessionId, relay);

  // Instantly signal ready status for local offline use
  setTimeout(() => {
    broadcastToOwner(params.context, params.connId, {
      relaySessionId,
      type: "ready",
      talkEvent: talk.emit({ type: "session.ready", payload: null }),
    });
  }, 10);

  return {
    provider: params.provider ?? "openai",
    transport: "gateway-relay",
    relaySessionId,
    audio: {
      inputEncoding: RELAY_INPUT_ENCODING,
      inputSampleRateHz: RELAY_INPUT_SAMPLE_RATE_HZ,
      outputEncoding: RELAY_OUTPUT_ENCODING,
      outputSampleRateHz: RELAY_OUTPUT_SAMPLE_RATE_HZ,
    },
    expiresAt: Math.floor(expiresAtMs / 1000),
  };
}

function getSttTtsSession(relaySessionId: string, connId: string): SttTtsRelaySession {
  return requireActiveTalkRelaySession({
    sessions: sttTtsSessions,
    sessionId: relaySessionId,
    connId,
    closeSession: (session) => closeSttTtsSession(session, "completed"),
    unknownSessionMessage: "Unknown STT-TTS Talk session",
  });
}

/** Receives audio base64, runs RMS-based VAD, and schedules transcription at speech end. */
export function sendTalkSttTtsRelayAudio(params: {
  relaySessionId: string;
  connId: string;
  audioBase64: string;
}): void {
  if (params.audioBase64.length > MAX_AUDIO_BASE64_BYTES) {
    throw new Error("STT-TTS Talk audio frame is too large");
  }
  const session = getSttTtsSession(params.relaySessionId, params.connId);
  if (session.closed) {
    return;
  }

  const chunk = Buffer.from(params.audioBase64, "base64");
  const turnId = ensureSttTtsTurn(session);

  // If agent is playing voice back and user starts speaking, trigger barge-in interrupt
  const rms = calculateRms(chunk);
  if (rms >= VAD_RMS_THRESHOLD && session.isPlayingAudio) {
    cancelTalkSttTtsRelayTurn({
      relaySessionId: session.id,
      connId: session.connId,
      reason: "barge-in",
    });
  }

  session.audioChunks.push(chunk);

  broadcastToOwner(session.context, session.connId, {
    relaySessionId: session.id,
    type: "inputAudio",
    byteLength: chunk.byteLength,
    talkEvent: session.talk.emit({
      type: "input.audio.delta",
      turnId,
      payload: { byteLength: chunk.byteLength },
    }),
  });

  // Calculate duration of chunk in ms: samples / sampleRate * 1000
  const chunkDurationMs = (chunk.length / 2 / RELAY_INPUT_SAMPLE_RATE_HZ) * 1000;

  session.chunkCount = (session.chunkCount || 0) + 1;
  if (session.chunkCount % 20 === 0) {
    console.log(
      `[VAD] Monitoring audio: RMS = ${rms.toFixed(5)} (speaking = ${session.isSpeaking})`,
    );
  }

  if (rms >= VAD_RMS_THRESHOLD) {
    if (!session.isSpeaking) {
      console.log(
        `[VAD] Speech START detected (RMS: ${rms.toFixed(5)} >= threshold: ${VAD_RMS_THRESHOLD})`,
      );
      session.isSpeaking = true;
    }
    session.silenceDurationMs = 0;
  } else if (session.isSpeaking) {
    session.silenceDurationMs += chunkDurationMs;
    if (session.silenceDurationMs >= VAD_SILENCE_DURATION_MS) {
      console.log(
        `[VAD] Speech END detected after ${session.silenceDurationMs}ms of silence. Processing turn...`,
      );
      // User finished speaking, process!
      void processSpeechAndQueryAgent(session, turnId);
    }
  }
}

async function processSpeechAndQueryAgent(
  session: SttTtsRelaySession,
  turnId: string,
): Promise<void> {
  if (session.audioChunks.length === 0) {
    return;
  }
  const chunks = [...session.audioChunks];
  session.audioChunks = [];
  session.isSpeaking = false;
  session.silenceDurationMs = 0;

  const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
  const totalSamples = totalLength / 2;
  const wavHeader = writeWavHeader(totalSamples, RELAY_INPUT_SAMPLE_RATE_HZ);
  const wavBuffer = Buffer.concat([wavHeader, ...chunks]);

  const cfg = session.context.getRuntimeConfig();
  const tmpFilePath = path.join(os.tmpdir(), `openclaw-talk-${randomUUID()}.wav`);
  fs.writeFileSync(tmpFilePath, wavBuffer);

  try {
    console.log(`[STT] Transcribing audio file: ${tmpFilePath}`);
    // 1. Transcription (STT)
    const sttResult = await transcribeAudioFile({
      filePath: tmpFilePath,
      cfg,
      mime: "audio/wav",
    });

    const text = sttResult.text?.trim();
    console.log(`[STT] Transcription result: "${text}"`);
    if (!text) {
      console.log("[STT] Empty transcription, ending turn.");
      session.talk.endTurn({ turnId, payload: {} });
      return;
    }

    // Emit final user transcription
    broadcastToOwner(session.context, session.connId, {
      relaySessionId: session.id,
      type: "transcript",
      role: "user",
      text,
      final: true,
      talkEvent: session.talk.emit({
        type: "transcript.done",
        turnId,
        payload: { text },
        final: true,
      }),
    });

    // 2. Append user message to the session file
    const { entry } = loadSessionEntry(session.sessionKey, { agentId: session.agentId });
    const sessionId = entry?.sessionId || session.id;
    const sessionFile = resolveSessionFilePath(sessionId, entry, { agentId: session.agentId });
    await appendSessionTranscriptMessage({
      transcriptPath: sessionFile,
      message: {
        role: "user",
        content: [{ type: "text", text }],
        timestamp: Date.now(),
      },
      now: Date.now(),
      useRawWhenLinear: true,
      config: cfg,
    });

    // 3. Dispatch to agent (LLM)
    console.log(`[Agent] Querying agent with text: "${text}"`);
    const runId = randomUUID();
    const abortController = new AbortController();
    session.activeRunAbortController = abortController;

    const ctx: MsgContext = {
      Body: text,
      BodyForAgent: text,
      RawBody: text,
      SessionKey: session.sessionKey,
      AgentId: session.agentId,
      Provider: "talk",
      Surface: "talk",
      ChatType: "direct",
    };

    let responseText = "";
    const dispatcher = createReplyDispatcher({
      deliver: async (payload, _info) => {
        if (payload.text) {
          responseText += payload.text;
          // Emit assistant transcript delta
          broadcastToOwner(session.context, session.connId, {
            relaySessionId: session.id,
            type: "transcript",
            role: "assistant",
            text: responseText,
            final: false,
            talkEvent: session.talk.emit({
              type: "transcript.delta",
              turnId,
              payload: { text: payload.text },
            }),
          });
        }
      },
      onError: (err) => {
        console.error("STT-TTS Agent dispatch error:", err);
      },
    });

    await dispatchInboundMessage({
      ctx,
      cfg,
      dispatcher,
      replyOptions: {
        runId,
        abortSignal: abortController.signal,
      },
    });

    session.activeRunAbortController = undefined;
    console.log(`[Agent] Reply received: "${responseText}"`);

    if (abortController.signal.aborted || !responseText.trim()) {
      console.log("[Agent] Run aborted or empty response, ending turn.");
      session.talk.endTurn({ turnId, payload: {} });
      return;
    }

    // Emit final assistant transcript
    broadcastToOwner(session.context, session.connId, {
      relaySessionId: session.id,
      type: "transcript",
      role: "assistant",
      text: responseText,
      final: true,
      talkEvent: session.talk.emit({
        type: "transcript.done",
        turnId,
        payload: { text: responseText },
        final: true,
      }),
    });

    // 4. Synthesize reply (TTS)
    session.isPlayingAudio = true;
    console.log(`[TTS] Synthesizing speech for: "${responseText}"`);
    const ttsResult = await synthesizeSpeech({
      text: responseText,
      cfg,
      overrides: {
        responseFormat: "wav",
      } as unknown as Record<string, unknown>,
      disableFallback: true,
    });

    if (ttsResult.success && ttsResult.audioBuffer && ttsResult.audioBuffer.length > 44) {
      // Find dynamic "data" WAV segment offset
      const dataOffset = ttsResult.audioBuffer.indexOf("data");
      const pcmAudio =
        dataOffset !== -1
          ? ttsResult.audioBuffer.slice(dataOffset + 8)
          : ttsResult.audioBuffer.slice(44);

      console.log(
        `[TTS] Synthesis successful. Streaming ${pcmAudio.length} bytes of PCM16 audio...`,
      );
      // Stream PCM chunks to client
      const chunkSize = 8192;
      for (let i = 0; i < pcmAudio.length; i += chunkSize) {
        if (!sttTtsSessions.has(session.id) || session.closed || !session.isPlayingAudio) {
          console.log("[TTS] Audio playback interrupted or session closed.");
          break;
        }
        const chunk = pcmAudio.slice(i, i + chunkSize);
        broadcastToOwner(session.context, session.connId, {
          relaySessionId: session.id,
          type: "audio",
          audioBase64: chunk.toString("base64"),
        });

        // Sleep to throttle audio streaming to real playback speed
        await new Promise<void>((resolve) => {
          setTimeout(resolve, 40);
        });
      }
      console.log("[TTS] Audio streaming completed.");
    } else {
      console.error("[TTS] Speech synthesis failed or returned empty buffer:", ttsResult);
    }

    session.isPlayingAudio = false;

    // 5. Append assistant reply to session database file
    await appendInjectedAssistantMessageToTranscript({
      transcriptPath: sessionFile,
      sessionKey: session.sessionKey,
      agentId: session.agentId,
      message: responseText,
      config: cfg,
    });

    session.talk.endTurn({ turnId, payload: {} });
  } catch (error) {
    console.error("STT-TTS processing failure:", error);
    broadcastToOwner(session.context, session.connId, {
      relaySessionId: session.id,
      type: "error",
      message: error instanceof Error ? error.message : String(error),
    });
  } finally {
    try {
      fs.unlinkSync(tmpFilePath);
    } catch {}
  }
}

/** Aborts active agent run or audio playback. */
export function cancelTalkSttTtsRelayTurn(params: {
  relaySessionId: string;
  connId: string;
  reason?: string;
}): void {
  const session = getSttTtsSession(params.relaySessionId, params.connId);

  if (session.activeRunAbortController) {
    session.activeRunAbortController.abort();
    session.activeRunAbortController = undefined;
  }

  session.isPlayingAudio = false;
  session.audioChunks = [];
  session.isSpeaking = false;
  session.silenceDurationMs = 0;

  broadcastToOwner(session.context, session.connId, {
    relaySessionId: session.id,
    type: "clear",
    talkEvent: session.talk.emit({
      type: "output.audio.done",
      turnId: session.talk.ensureTurn().turnId,
      payload: { reason: params.reason ?? "cancel" },
      final: true,
    }),
  });
}

/** Closes the session. */
export function stopTalkSttTtsRelaySession(params: {
  relaySessionId: string;
  connId: string;
}): void {
  const session = getSttTtsSession(params.relaySessionId, params.connId);
  closeSttTtsSession(session, "completed");
}
