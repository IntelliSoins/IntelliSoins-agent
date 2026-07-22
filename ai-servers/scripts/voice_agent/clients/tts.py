"""Async TTS client with sentence chunking and cancellation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import httpx

from ..config import VoiceConfig
from ..sentence import flush_remainder, for_tts, pop_sentences


@dataclass(frozen=True)
class TtsSegment:
    """One synthesized audio segment for a sentence (or merged sentences)."""

    ordinal: int
    text: str
    audio_bytes: bytes
    char_count: int


class TtsClient:
    """Sentence-chunked speech synthesis via VoxCPM bridge (``VOICE_TTS_URL``)."""

    def __init__(
        self,
        config: VoiceConfig,
        *,
        client: Optional[httpx.AsyncClient] = None,
        owns_client: bool = False,
    ) -> None:
        self._config = config
        self._owns_client = owns_client or client is None
        self._client = client or httpx.AsyncClient()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "TtsClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def synthesize(
        self,
        text: str,
        *,
        model: Optional[str] = None,
        cancel_event: Optional[Any] = None,
    ) -> bytes:
        """Synthesize a single text chunk; return audio bytes (WAV or provider format)."""
        oral = for_tts(text)
        if not oral:
            return b""
        self._raise_if_cancelled(cancel_event)
        timeout = httpx.Timeout(self._config.tts_timeout_s, connect=10.0)
        resp = await self._client.post(
            self._config.tts_url,
            json={
                "model": model or self._config.tts_model,
                "input": oral,
                "stream": False,
            },
            timeout=timeout,
        )
        self._raise_if_cancelled(cancel_event)
        resp.raise_for_status()
        return resp.content

    async def synthesize_streamed_text(
        self,
        text_deltas: AsyncIterator[str],
        *,
        model: Optional[str] = None,
        cancel_event: Optional[Any] = None,
        flush_tail: bool = True,
    ) -> AsyncIterator[TtsSegment]:
        """Chunk streamed LLM text into sentences and synthesize each."""
        buffer = ""
        first_done = False
        ordinal = 0
        min_chars = self._config.tts_min_chars

        async for delta in text_deltas:
            self._raise_if_cancelled(cancel_event)
            if not delta:
                continue
            buffer += delta
            sentences, buffer = pop_sentences(
                buffer, first_done=first_done, min_chars=min_chars
            )
            for sentence in sentences:
                first_done = True
                audio = await self.synthesize(
                    sentence, model=model, cancel_event=cancel_event
                )
                if not audio:
                    continue
                oral = for_tts(sentence)
                yield TtsSegment(
                    ordinal=ordinal,
                    text=oral,
                    audio_bytes=audio,
                    char_count=len(oral),
                )
                ordinal += 1

        if flush_tail:
            self._raise_if_cancelled(cancel_event)
            for sentence in flush_remainder(buffer):
                audio = await self.synthesize(
                    sentence, model=model, cancel_event=cancel_event
                )
                if not audio:
                    continue
                oral = for_tts(sentence)
                yield TtsSegment(
                    ordinal=ordinal,
                    text=oral,
                    audio_bytes=audio,
                    char_count=len(oral),
                )
                ordinal += 1

    @staticmethod
    def _raise_if_cancelled(cancel_event: Optional[Any]) -> None:
        if cancel_event is not None and cancel_event.is_set():
            import asyncio

            raise asyncio.CancelledError("voice_agent tts cancelled")
