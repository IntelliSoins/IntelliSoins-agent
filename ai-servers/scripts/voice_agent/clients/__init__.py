"""HTTP client package (Whisper / LLM / TTS)."""

from __future__ import annotations

from .llm import ChatChunk, LlmClient
from .tts import TtsClient, TtsSegment
from .whisper import WhisperClient

__all__ = [
    "WhisperClient",
    "LlmClient",
    "ChatChunk",
    "TtsClient",
    "TtsSegment",
]
