import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { runFfmpeg } from "openclaw/plugin-sdk/media-runtime";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type {
  RealtimeVoiceProviderPlugin,
  RealtimeVoiceBridge,
  RealtimeVoiceBridgeCreateRequest,
} from "openclaw/plugin-sdk/realtime-voice";
import { REALTIME_VOICE_AUDIO_FORMAT_PCM16_24KHZ } from "openclaw/plugin-sdk/realtime-voice";

// Helper to convert PCM to WAV
function pcmToWav(pcmBuffer: Buffer, sampleRate: number): Buffer {
  const wavHeader = Buffer.alloc(44);
  wavHeader.write("RIFF", 0);
  wavHeader.writeUInt32LE(36 + pcmBuffer.length, 4);
  wavHeader.write("WAVE", 8);
  wavHeader.write("fmt ", 12);
  wavHeader.writeUInt32LE(16, 16);
  wavHeader.writeUInt16LE(1, 20); // raw PCM
  wavHeader.writeUInt16LE(1, 22); // mono
  wavHeader.writeUInt32LE(sampleRate, 24);
  wavHeader.writeUInt32LE(sampleRate * 2, 28); // byte rate
  wavHeader.writeUInt16LE(2, 32); // block align
  wavHeader.writeUInt16LE(16, 34); // bits per sample
  wavHeader.write("data", 36);
  wavHeader.writeUInt32LE(pcmBuffer.length, 40);
  return Buffer.concat([wavHeader, pcmBuffer]);
}

class LocalVoiceBridge implements RealtimeVoiceBridge {
  private connected = false;
  private accumulatedAudio: Buffer[] = [];
  private isUserSpeaking = false;
  private silenceDurationMs = 0;
  private activeInterval: ReturnType<typeof setInterval> | null = null;
  private processing = false;

  constructor(private readonly req: RealtimeVoiceBridgeCreateRequest) {}

  async connect(): Promise<void> {
    this.connected = true;
    this.req.onReady?.();
  }

  sendAudio(audio: Buffer): void {
    if (!this.connected) {
      return;
    }

    // Energy calculation
    let sumSquares = 0;
    const samplesCount = audio.length / 2;
    for (let i = 0; i < audio.length; i += 2) {
      if (i + 1 < audio.length) {
        const sample = audio.readInt16LE(i);
        sumSquares += sample * sample;
      }
    }
    const rms = Math.sqrt(sumSquares / samplesCount);
    const normalizedRms = rms / 32768;

    // Threshold (0.015)
    const threshold = 0.015;
    const chunkDurationMs = (samplesCount / 24000) * 1000;

    if (normalizedRms > threshold) {
      this.isUserSpeaking = true;
      this.silenceDurationMs = 0;
      this.accumulatedAudio.push(audio);
    } else if (this.isUserSpeaking) {
      this.silenceDurationMs += chunkDurationMs;
      this.accumulatedAudio.push(audio);

      const maxSilence = (this.req.providerConfig.silenceDurationMs as number) || 800;
      if (this.silenceDurationMs >= maxSilence) {
        this.isUserSpeaking = false;
        void this.processSpeech();
      }
    }
  }

  private async processSpeech(): Promise<void> {
    if (this.processing || this.accumulatedAudio.length === 0) {
      return;
    }
    this.processing = true;

    try {
      const pcmBuffer = Buffer.concat(this.accumulatedAudio);
      this.accumulatedAudio = [];

      // Avoid triggering on very short sounds (< 0.4s)
      if (pcmBuffer.length < 24000 * 2 * 0.4) {
        this.processing = false;
        return;
      }

      const wavBuffer = pcmToWav(pcmBuffer, 24000);

      // Call Whisper STT
      const formData = new FormData();
      const blob = new Blob([wavBuffer as unknown as BlobPart], { type: "audio/wav" });
      formData.append("file", blob, "speech.wav");
      formData.append("response_format", "json");
      const sttModel = (this.req.providerConfig.sttModel as string) || "whisper-stt";
      formData.append("model", sttModel);

      const sttPort = (this.req.providerConfig.sttPort as number) || 2022;
      const headers: Record<string, string> = {};
      const apiKey =
        (this.req.providerConfig.apiKey as string) || (this.req.providerConfig.token as string);
      if (apiKey) {
        headers["Authorization"] = `Bearer ${apiKey}`;
      }

      const response = await fetch(`http://127.0.0.1:${sttPort}/v1/audio/transcriptions`, {
        method: "POST",
        headers,
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Whisper STT failed with status ${response.status}`);
      }

      const data = (await response.json()) as { text: string };
      const text = data.text?.trim();

      if (text) {
        this.req.onTranscript?.("user", text, true);
      }
    } catch (error) {
      this.req.onError?.(error instanceof Error ? error : new Error(String(error)));
    } finally {
      this.processing = false;
    }
  }

  sendUserMessage(text: string): void {
    if (!this.connected) {
      return;
    }

    this.req.onTranscript?.("assistant", text, true);

    this.sendUserMessageAsync(text).catch((error: unknown) => {
      this.req.onError?.(error instanceof Error ? error : new Error(String(error)));
    });
  }

  private async sendUserMessageAsync(text: string): Promise<void> {
    try {
      // Call vibevoice-tts
      const ttsPort = (this.req.providerConfig.ttsPort as number) || 8882;
      const voice = (this.req.providerConfig.voice as string) || "fr-Spk0_man";
      const model = (this.req.providerConfig.model as string) || "vibevoice-tts";

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const apiKey =
        (this.req.providerConfig.apiKey as string) || (this.req.providerConfig.token as string);
      if (apiKey) {
        headers["Authorization"] = `Bearer ${apiKey}`;
      }

      const response = await fetch(`http://127.0.0.1:${ttsPort}/v1/audio/speech`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          model,
          input: text,
          voice,
        }),
      });

      if (!response.ok) {
        throw new Error(`VibeVoice TTS failed with status ${response.status}`);
      }

      const arrayBuffer = await response.arrayBuffer();
      const audioBuffer = Buffer.from(arrayBuffer);

      // Convert synthesized audio to raw PCM16 24kHz mono using ffmpeg
      const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "openclaw-local-voice-"));
      const inputPath = path.join(tempDir, "input.mp3");
      const outputPath = path.join(tempDir, "output.raw");

      fs.writeFileSync(inputPath, audioBuffer);

      await runFfmpeg([
        "-y",
        "-i",
        inputPath,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "24000",
        "-ac",
        "1",
        outputPath,
      ]);

      const pcmOutput = fs.readFileSync(outputPath);

      try {
        fs.unlinkSync(inputPath);
        fs.unlinkSync(outputPath);
        fs.rmdirSync(tempDir);
      } catch {
        // ignore cleanup errors
      }

      // Stream the audio chunks back to the client
      if (this.activeInterval) {
        clearInterval(this.activeInterval);
      }

      const chunkSize = 4096;
      const delayMs = Math.round((chunkSize / 2 / 24000) * 1000); // ~85ms
      let offset = 0;

      this.activeInterval = setInterval(() => {
        if (offset >= pcmOutput.length || !this.connected) {
          if (this.activeInterval) {
            clearInterval(this.activeInterval);
            this.activeInterval = null;
          }
          this.req.onMark?.("audio-done");
          return;
        }

        const chunk = pcmOutput.subarray(offset, offset + chunkSize);
        offset += chunkSize;
        this.req.onAudio(chunk);
      }, delayMs);
    } catch (error) {
      this.req.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  }

  handleBargeIn(): void {
    if (this.activeInterval) {
      clearInterval(this.activeInterval);
      this.activeInterval = null;
    }
    this.req.onClearAudio();
  }

  setMediaTimestamp(): void {}
  acknowledgeMark(): void {}
  submitToolResult(): void {}

  close(): void {
    this.connected = false;
    if (this.activeInterval) {
      clearInterval(this.activeInterval);
      this.activeInterval = null;
    }
    this.req.onClose?.("completed");
  }

  isConnected(): boolean {
    return this.connected;
  }
}

const localVoiceProvider: RealtimeVoiceProviderPlugin = {
  id: "local-voice",
  label: "Local STT-TTS Voice",
  defaultModel: "local-voice",
  autoSelectOrder: 1,
  capabilities: {
    transports: ["gateway-relay"],
    inputAudioFormats: [REALTIME_VOICE_AUDIO_FORMAT_PCM16_24KHZ],
    outputAudioFormats: [REALTIME_VOICE_AUDIO_FORMAT_PCM16_24KHZ],
    supportsBrowserSession: false,
    supportsBargeIn: true,
    supportsToolCalls: false,
  },
  resolveConfig: ({ rawConfig }) => rawConfig,
  isConfigured: () => true,
  createBridge: (req) => new LocalVoiceBridge(req),
};

export default definePluginEntry({
  id: "my-speech-service",
  name: "My Speech Service Plugin",
  description: "Custom OpenClaw SST-TTS plugin",
  register(api) {
    api.registerRealtimeVoiceProvider(localVoiceProvider);
  },
});
