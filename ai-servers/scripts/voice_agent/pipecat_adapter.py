"""Pipecat adapters for the existing Spark STT/LLM/TTS endpoints.

This module is imported only by the Pipecat service. The dependency-light core
(``events``, ``memory``, ``runtime``, ``tools``) remains testable without
Pipecat installed.
"""

from __future__ import annotations

import asyncio
import io
import time
import wave
from collections.abc import AsyncGenerator
from typing import Any, Awaitable, Callable, Mapping, Optional

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    CancelFrame,
    ErrorFrame,
    Frame,
    LLMContextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.settings import STTSettings, TTSSettings
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.services.tts_service import TTSService, TextAggregationMode
from pipecat.utils.time import time_now_iso8601

from .clients.tts import TtsClient
from .clients.whisper import WhisperClient
from .config import VoiceConfig
from .runtime import VoiceRuntime

SAFETY_ESCALATION_TEXT = (
    "Ce que vous décrivez peut nécessiter une aide urgente. "
    "Je ne peux pas établir de diagnostic. Si le danger est immédiat, "
    "appelez le 911 ou rendez-vous à l'urgence. "
    "Je dois interrompre le triage automatisé maintenant."
)
CONSENT_DECLINED_TEXT = (
    "Je respecte votre refus. Aucune information additionnelle ne sera recueillie "
    "et l'échange automatisé se termine maintenant."
)


def pcm_s16le_to_wav(audio: bytes, *, sample_rate: int, channels: int = 1) -> bytes:
    """Wrap raw signed 16-bit PCM in a WAV container for Spark Whisper."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio)
    return buf.getvalue()


def decode_wav(audio: bytes) -> tuple[int, int, bytes, float]:
    """Return sample rate, channels, PCM bytes, and duration from a WAV blob."""
    with wave.open(io.BytesIO(audio), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError(f"unsupported TTS sample width: {wav.getsampwidth()}")
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        frames = wav.getnframes()
        pcm = wav.readframes(frames)
    duration = frames / sample_rate if sample_rate else 0.0
    return sample_rate, channels, pcm, duration


class SparkWhisperSTTService(SegmentedSTTService):
    """Pipecat STT service using the existing batch Whisper endpoint."""

    def __init__(
        self,
        config: VoiceConfig,
        *,
        client: Optional[WhisperClient] = None,
        sample_rate: int = 16000,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sample_rate=sample_rate,
            audio_passthrough=True,
            ttfs_p99_latency=config.whisper_timeout_s,
            settings=STTSettings(
                model="whisper-michael-ft",
                language=config.whisper_language,
            ),
            **kwargs,
        )
        self._config = config
        self._client = client or WhisperClient(config)
        self._owns_client = client is None
        self._closed = False

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        try:
            await self.start_processing_metrics()
            wav = pcm_s16le_to_wav(audio, sample_rate=self.sample_rate)
            text = await self._client.transcribe(wav)
            await self.stop_processing_metrics()
            if text:
                yield TranscriptionFrame(
                    text=text,
                    user_id=self._user_id,
                    timestamp=time_now_iso8601(),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield ErrorFrame(error=f"Spark Whisper error: {exc}")

    async def stop(self, frame: Frame) -> None:
        await super().stop(frame)
        await self._close_client()

    async def cancel(self, frame: CancelFrame) -> None:
        await super().cancel(frame)
        await self._close_client()

    async def cleanup(self) -> None:
        await self._close_client()
        await super().cleanup()

    async def _close_client(self) -> None:
        if self._owns_client and not self._closed:
            self._closed = True
            await self._client.aclose()


class SparkVoxCPMTTSService(TTSService):
    """Pipecat TTS service using the VoxCPM bridge's WAV response."""

    def __init__(
        self,
        config: VoiceConfig,
        runtime: VoiceRuntime,
        *,
        client: Optional[TtsClient] = None,
        sample_rate: int = 48000,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sample_rate=sample_rate,
            text_aggregation_mode=TextAggregationMode.SENTENCE,
            push_text_frames=True,
            push_start_frame=True,
            push_stop_frames=True,
            stop_frame_timeout_s=0.2,
            settings=TTSSettings(
                model=config.tts_model,
                voice=config.tts_model,
                language="fr",
            ),
            **kwargs,
        )
        self._config = config
        self._runtime = runtime
        self._client = client or TtsClient(config)
        self._owns_client = client is None
        self._closed = False

    async def run_tts(
        self, text: str, context_id: str
    ) -> AsyncGenerator[Frame | None, None]:
        started = time.monotonic()
        try:
            await self.start_ttfb_metrics()
            wav_bytes = await self._client.synthesize(text)
            first_audio = time.monotonic()
            await self.stop_ttfb_metrics()
            if not wav_bytes:
                return
            sample_rate, channels, pcm, duration = decode_wav(wav_bytes)
            synth_seconds = first_audio - started
            await self.start_tts_usage_metrics(text)
            bytes_per_20ms = max(2 * channels, int(sample_rate * channels * 2 * 0.02))
            for offset in range(0, len(pcm), bytes_per_20ms):
                chunk = pcm[offset : offset + bytes_per_20ms]
                if chunk:
                    yield TTSAudioRawFrame(
                        chunk,
                        sample_rate,
                        channels,
                        context_id=context_id,
                    )
            try:
                await asyncio.to_thread(
                    self._runtime.record_tts,
                    text,
                    wav_bytes,
                    sample_rate=sample_rate,
                    synth_seconds=synth_seconds,
                    audio_seconds=duration,
                    ttfa_seconds=synth_seconds,
                )
            except Exception:
                logger.exception("Failed to persist TTS segment after audio delivery")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield ErrorFrame(error=f"Spark VoxCPM error: {exc}")

    async def stop(self, frame: Frame) -> None:
        await super().stop(frame)
        await self._close_client()

    async def cancel(self, frame: CancelFrame) -> None:
        await super().cancel(frame)
        await self._close_client()

    async def cleanup(self) -> None:
        await self._close_client()
        await super().cleanup()

    async def _close_client(self) -> None:
        if self._owns_client and not self._closed:
            self._closed = True
            await self._client.aclose()


class SafetyGateProcessor(FrameProcessor):
    """Start persisted turns and bypass the LLM on deterministic red flags."""

    def __init__(self, runtime: VoiceRuntime, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._runtime = runtime
        self._last_message_count = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
            messages = frame.context.get_messages()
            count = len(messages)
            if count > self._last_message_count:
                self._last_message_count = count
                user_text = _latest_user_text(messages)
                if user_text:
                    safety = await asyncio.to_thread(
                        self._runtime.start_user_turn,
                        user_text,
                        raw={"safety_scanned": True},
                    )
                    if safety.triggered:
                        await self.push_frame(
                            TTSSpeakFrame(SAFETY_ESCALATION_TEXT), direction
                        )
                        return
                    if self._runtime.end_requested:
                        await self.push_frame(
                            TTSSpeakFrame(CONSENT_DECLINED_TEXT), direction
                        )
                        return
        await self.push_frame(frame, direction)


class TurnFinalizerProcessor(FrameProcessor):
    """Finalize persisted turns when Pipecat finishes bot playback."""

    def __init__(
        self,
        runtime: VoiceRuntime,
        *,
        end_callback: Optional[Callable[[], Awaitable[None]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._runtime = runtime
        self.end_callback = end_callback

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if isinstance(frame, BotStoppedSpeakingFrame):
            await asyncio.to_thread(self._runtime.finish_turn)
            if self._runtime.end_requested and self.end_callback is not None:
                await self.end_callback()


def build_function_schemas(runtime: VoiceRuntime) -> list[FunctionSchema]:
    """Convert the core allowlist into Pipecat schemas with persisted handlers."""
    schemas: list[FunctionSchema] = []
    for schema in runtime.registry.openai_tools():
        function = schema["function"]
        parameters = function.get("parameters") or {}
        name = function["name"]

        async def handler(params: Any, *, _name: str = name) -> None:
            result = await asyncio.to_thread(
                runtime.invoke_tool,
                _name,
                params.arguments,
            )
            await params.result_callback(result.as_dict())
            if result.data.get("should_end"):
                await params.pipeline_worker.cancel()

        schemas.append(
            FunctionSchema(
                name=name,
                description=function.get("description") or "",
                properties=dict(parameters.get("properties") or {}),
                required=list(parameters.get("required") or []),
                handler=handler,
            )
        )
    return schemas


def _latest_user_text(messages: list[Mapping[str, Any]]) -> str:
    if not messages or messages[-1].get("role") != "user":
        return ""
    content = messages[-1].get("content")
    if isinstance(content, str):
        return content.strip()
    return ""
