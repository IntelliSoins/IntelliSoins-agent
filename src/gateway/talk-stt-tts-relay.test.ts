import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dispatchInboundMessage } from "../auto-reply/dispatch.js";
import { transcribeAudioFile } from "../media-understanding/runtime.js";
import { synthesizeSpeech } from "../tts/tts.js";
import { createTalkSttTtsRelaySession, sendTalkSttTtsRelayAudio } from "./talk-stt-tts-relay.js";

vi.mock("../media-understanding/runtime.js", () => ({
  transcribeAudioFile: vi.fn(),
}));

vi.mock("../tts/tts.js", () => ({
  synthesizeSpeech: vi.fn(),
}));

vi.mock("../auto-reply/dispatch.js", () => ({
  dispatchInboundMessage: vi.fn(),
}));

vi.mock("../config/sessions/transcript-append.js", () => ({
  appendSessionTranscriptMessage: vi.fn(),
}));

vi.mock("./server-methods/chat-transcript-inject.js", () => ({
  appendInjectedAssistantMessageToTranscript: vi.fn(),
}));

describe("STT-TTS local offline voice relay", () => {
  let context: any;

  beforeEach(() => {
    context = {
      getRuntimeConfig: vi.fn(() => ({})),
      broadcastToConnIds: vi.fn(),
    };
    vi.mocked(transcribeAudioFile).mockResolvedValue({ text: "hello", provider: "openai" });
    vi.mocked(synthesizeSpeech).mockResolvedValue({
      success: true,
      audioBuffer: Buffer.alloc(100),
      provider: "openai",
    });
    vi.mocked(dispatchInboundMessage).mockImplementation(async (params: any) => {
      // Simulate assistant response
      await params.dispatcher.sendFinalReply({ text: "hi there" });
      return {} as any;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should create and register a session successfully", () => {
    const session = createTalkSttTtsRelaySession({
      context,
      connId: "conn-123",
      sessionKey: "session-key",
      agentId: "agent-id",
    });

    expect(session.relaySessionId).toBeDefined();
    expect(session.transport).toBe("gateway-relay");
  });

  it("should run VAD logic and trigger agent on silence", async () => {
    const sessionResult = createTalkSttTtsRelaySession({
      context,
      connId: "conn-123",
      sessionKey: "session-key",
      agentId: "agent-id",
    });

    // 1. Send silence -> should not trigger speaking
    const silentChunk = Buffer.alloc(9600); // 9600 bytes = 4800 samples = 200ms at 24kHz
    sendTalkSttTtsRelayAudio({
      relaySessionId: sessionResult.relaySessionId,
      connId: "conn-123",
      audioBase64: silentChunk.toString("base64"),
    });

    // 2. Send active speech (sine wave) -> should trigger speaking
    const speechChunk = Buffer.alloc(9600);
    for (let i = 0; i < speechChunk.length / 2; i++) {
      speechChunk.writeInt16LE(Math.sin(i) * 16384, i * 2);
    }
    sendTalkSttTtsRelayAudio({
      relaySessionId: sessionResult.relaySessionId,
      connId: "conn-123",
      audioBase64: speechChunk.toString("base64"),
    });

    // 3. Send silence to trigger silence timeout (need 1000ms total, send 5 chunks of 200ms)
    for (let k = 0; k < 6; k++) {
      sendTalkSttTtsRelayAudio({
        relaySessionId: sessionResult.relaySessionId,
        connId: "conn-123",
        audioBase64: silentChunk.toString("base64"),
      });
    }

    // Allow async VAD processing to resolve
    await new Promise<void>((resolve) => {
      setTimeout(resolve, 100);
    });

    expect(transcribeAudioFile).toHaveBeenCalled();
    expect(dispatchInboundMessage).toHaveBeenCalled();
    expect(synthesizeSpeech).toHaveBeenCalled();
  });
});
