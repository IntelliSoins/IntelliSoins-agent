"""Async batch Whisper client (OpenAI-compatible ``/v1/audio/transcriptions``)."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import httpx

from ..config import VoiceConfig


class WhisperClient:
    """Batch speech-to-text against Spark Whisper (``VOICE_WHISPER_URL``)."""

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

    async def __aenter__(self) -> "WhisperClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def transcribe(
        self,
        wav_bytes: bytes,
        *,
        filename: str = "voice.wav",
        language: Optional[str] = None,
        extra_fields: Optional[Mapping[str, Any]] = None,
        cancel_event: Optional[Any] = None,
    ) -> str:
        """POST a WAV blob; return transcript text (stripped).

        ``cancel_event`` is any object with ``.is_set()`` (e.g. ``asyncio.Event``).
        """
        self._raise_if_cancelled(cancel_event)
        data: dict[str, Any] = {
            "language": language or self._config.whisper_language,
            "response_format": "json",
            "temperature": "0",
        }
        prompt = self._config.whisper_prompt
        if prompt:
            data["prompt"] = prompt
        if extra_fields:
            data.update(dict(extra_fields))

        timeout = httpx.Timeout(self._config.whisper_timeout_s, connect=10.0)
        resp = await self._client.post(
            self._config.whisper_url,
            files={"file": (filename, wav_bytes, "audio/wav")},
            data=data,
            timeout=timeout,
        )
        self._raise_if_cancelled(cancel_event)
        resp.raise_for_status()
        payload = resp.json()
        return (payload.get("text") or "").strip()

    @staticmethod
    def _raise_if_cancelled(cancel_event: Optional[Any]) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio_cancelled()


def asyncio_cancelled() -> BaseException:
    """Import-safe cancellation error."""
    import asyncio

    return asyncio.CancelledError("voice_agent whisper cancelled")
