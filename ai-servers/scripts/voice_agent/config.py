"""VOICE_* environment configuration for Spark Whisper / Qwen / VoxCPM bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


def _env(name: str, default: str, environ: Optional[Mapping[str, str]] = None) -> str:
    src = os.environ if environ is None else environ
    return (src.get(name) or default).strip()


def _env_float(
    name: str, default: float, environ: Optional[Mapping[str, str]] = None
) -> float:
    raw = _env(name, str(default), environ)
    return float(raw)


def _env_int(
    name: str, default: int, environ: Optional[Mapping[str, str]] = None
) -> int:
    raw = _env(name, str(default), environ)
    return int(raw)


def _env_bool(
    name: str, default: bool, environ: Optional[Mapping[str, str]] = None
) -> bool:
    raw = _env(name, "1" if default else "0", environ).lower()
    return raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class VoiceConfig:
    """Runtime endpoints and knobs for the voice-agent core.

    Defaults target the current Spark mesh layout:
    Whisper ``:2022``, Qwen ``:8000``, VoxCPM Mac bridge ``:8884``.
    """

    whisper_url: str = "http://10.0.1.1:2022/v1/audio/transcriptions"
    whisper_language: str = "fr"
    whisper_prompt: str = ""
    whisper_timeout_s: float = 20.0

    llm_url: str = "http://10.0.1.1:8000/v1/chat/completions"
    llm_model: str = "qwen3.5-4b-finetunev2"
    llm_key: str = ""
    llm_timeout_s: float = 60.0
    max_tokens: int = 280
    temperature: float = 0.3
    repetition_penalty: float = 1.15

    tts_url: str = "http://127.0.0.1:8884/v1/audio/speech"
    tts_model: str = "michael-v8"
    tts_timeout_s: float = 45.0
    tts_min_chars: int = 90
    tts_gap_ms: int = 120

    # DSN for event store + durable memory. Empty → store disabled.
    db_dsn: str = ""
    db_enabled: bool = True
    store_tts_audio: bool = False

    extra: dict[str, Any] = field(default_factory=dict)

    def llm_headers(self) -> dict[str, str]:
        if not self.llm_key:
            return {}
        return {"Authorization": f"Bearer {self.llm_key}"}


def load_config(environ: Optional[Mapping[str, str]] = None) -> VoiceConfig:
    """Load config from ``VOICE_*`` environment variables."""
    env = os.environ if environ is None else environ
    dsn = _env(
        "VOICE_DB_DSN",
        _env("VOICE_DATABASE_URL", "", env),
        env,
    )
    if not dsn:
        # Convention: postgresql://…/voice_agent on local Homebrew PG.
        dsn = _env("DATABASE_URL", "", env)
    return VoiceConfig(
        whisper_url=_env(
            "VOICE_WHISPER_URL",
            "http://10.0.1.1:2022/v1/audio/transcriptions",
            env,
        ),
        whisper_language=_env("VOICE_WHISPER_LANGUAGE", "fr", env),
        whisper_prompt=_env("VOICE_WHISPER_PROMPT", "", env),
        whisper_timeout_s=_env_float("VOICE_WHISPER_TIMEOUT_S", 20.0, env),
        llm_url=_env(
            "VOICE_LLM_URL",
            "http://10.0.1.1:8000/v1/chat/completions",
            env,
        ),
        llm_model=_env("VOICE_LLM_MODEL", "qwen3.5-4b-finetunev2", env),
        llm_key=_env("VOICE_LLM_KEY", "", env),
        llm_timeout_s=_env_float("VOICE_LLM_TIMEOUT_S", 60.0, env),
        max_tokens=_env_int("VOICE_MAX_TOKENS", 280, env),
        temperature=_env_float("VOICE_TEMPERATURE", 0.3, env),
        repetition_penalty=_env_float("VOICE_REPETITION_PENALTY", 1.15, env),
        tts_url=_env(
            "VOICE_TTS_URL",
            "http://127.0.0.1:8884/v1/audio/speech",
            env,
        ),
        tts_model=_env("VOICE_TTS_MODEL", "michael-v8", env),
        tts_timeout_s=_env_float("VOICE_TTS_TIMEOUT_S", 45.0, env),
        tts_min_chars=_env_int("VOICE_TTS_MIN_CHARS", 90, env),
        tts_gap_ms=_env_int("VOICE_TTS_GAP_MS", 120, env),
        db_dsn=dsn,
        db_enabled=_env_bool("VOICE_DB_ENABLED", True, env) and bool(dsn),
        store_tts_audio=_env_bool("VOICE_STORE_TTS_AUDIO", False, env),
    )
