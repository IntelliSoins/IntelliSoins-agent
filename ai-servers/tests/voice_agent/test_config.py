"""Unit tests — VoiceConfig / VOICE_* env."""

from __future__ import annotations

import unittest

import _path  # noqa: F401

from voice_agent.config import load_config


class TestVoiceConfig(unittest.TestCase):
    def test_defaults_target_spark_ports(self) -> None:
        cfg = load_config({})
        self.assertIn(":2022", cfg.whisper_url)
        self.assertIn(":8000", cfg.llm_url)
        self.assertIn(":8884", cfg.tts_url)
        self.assertEqual(cfg.llm_model, "qwen3.5-4b-finetunev2")
        self.assertFalse(cfg.db_enabled)

    def test_voice_env_overrides(self) -> None:
        env = {
            "VOICE_WHISPER_URL": "http://10.0.0.5:2022/v1/audio/transcriptions",
            "VOICE_LLM_URL": "http://10.0.0.5:8000/v1/chat/completions",
            "VOICE_TTS_URL": "http://127.0.0.1:8884/v1/audio/speech",
            "VOICE_LLM_MODEL": "qwen-test",
            "VOICE_LLM_KEY": "secret",
            "VOICE_MAX_TOKENS": "100",
            "VOICE_TTS_MIN_CHARS": "40",
            "VOICE_DB_DSN": "postgresql://localhost/voice_agent",
            "VOICE_DB_ENABLED": "1",
        }
        cfg = load_config(env)
        self.assertEqual(cfg.whisper_url, env["VOICE_WHISPER_URL"])
        self.assertEqual(cfg.llm_url, env["VOICE_LLM_URL"])
        self.assertEqual(cfg.tts_url, env["VOICE_TTS_URL"])
        self.assertEqual(cfg.llm_model, "qwen-test")
        self.assertEqual(cfg.max_tokens, 100)
        self.assertEqual(cfg.tts_min_chars, 40)
        self.assertTrue(cfg.db_enabled)
        self.assertEqual(cfg.llm_headers()["Authorization"], "Bearer secret")

    def test_db_disabled_without_dsn(self) -> None:
        cfg = load_config({"VOICE_DB_ENABLED": "1"})
        self.assertFalse(cfg.db_enabled)

    def test_db_explicitly_disabled(self) -> None:
        cfg = load_config(
            {
                "VOICE_DB_DSN": "postgresql://localhost/voice_agent",
                "VOICE_DB_ENABLED": "0",
            }
        )
        self.assertFalse(cfg.db_enabled)


if __name__ == "__main__":
    unittest.main()
