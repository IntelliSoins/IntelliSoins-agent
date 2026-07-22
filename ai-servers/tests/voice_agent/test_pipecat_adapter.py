from __future__ import annotations

import asyncio
import importlib.util
import io
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock

import _path  # noqa: F401

PIPECAT_AVAILABLE = importlib.util.find_spec("pipecat") is not None


@unittest.skipUnless(PIPECAT_AVAILABLE, "pipecat is installed in its dedicated venv")
class TestPipecatAdapter(unittest.TestCase):
    def test_pcm_wav_roundtrip(self):
        from voice_agent.pipecat_adapter import decode_wav, pcm_s16le_to_wav

        pcm = b"\x00\x00\x01\x00" * 160
        wav_bytes = pcm_s16le_to_wav(pcm, sample_rate=16000)
        sample_rate, channels, decoded, duration = decode_wav(wav_bytes)

        self.assertEqual(sample_rate, 16000)
        self.assertEqual(channels, 1)
        self.assertEqual(decoded, pcm)
        self.assertGreater(duration, 0)

    def test_decode_rejects_non_s16_wav(self):
        from voice_agent.pipecat_adapter import decode_wav

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(1)
            wav.setframerate(16000)
            wav.writeframes(b"\x00" * 160)
        with self.assertRaises(ValueError):
            decode_wav(buf.getvalue())

    def test_tool_schema_handler_uses_trusted_runtime(self):
        from voice_agent.config import VoiceConfig
        from voice_agent.pipecat_adapter import build_function_schemas
        from voice_agent.runtime import VoiceRuntime

        runtime = VoiceRuntime.create(
            VoiceConfig(db_enabled=False),
            subject_id="trusted-contact",
            session_id="webrtc-1",
        )
        runtime.start()
        runtime.start_user_turn("Rappelle-moi demain.")
        schema = next(
            item
            for item in build_function_schemas(runtime)
            if item.name == "capture_followup"
        )
        callback = AsyncMock()
        params = SimpleNamespace(
            arguments={
                "summary": "Rappeler demain",
                "subject_id": "attacker-controlled",
            },
            result_callback=callback,
        )

        asyncio.run(schema.handler(params))

        callback.assert_awaited_once()
        payload = callback.await_args.args[0]
        self.assertTrue(payload["ok"])
        fact = runtime.active_facts()[0]
        self.assertEqual(fact.subject_id, "trusted-contact")
        runtime.close()

    def test_services_use_segmented_stt_and_tts_lifecycle(self):
        from pipecat.services.stt_service import SegmentedSTTService

        from voice_agent.config import VoiceConfig
        from voice_agent.pipecat_adapter import (
            SparkVoxCPMTTSService,
            SparkWhisperSTTService,
        )
        from voice_agent.runtime import VoiceRuntime

        config = VoiceConfig(db_enabled=False)
        runtime = VoiceRuntime.create(
            config,
            subject_id="trusted-contact",
            session_id="webrtc-2",
        )
        stt = SparkWhisperSTTService(config)
        tts = SparkVoxCPMTTSService(config, runtime)
        self.assertIsInstance(stt, SegmentedSTTService)
        self.assertTrue(stt._audio_passthrough)
        self.assertTrue(tts._push_start_frame)
        self.assertTrue(tts._push_stop_frames)
        asyncio.run(stt.cleanup())
        asyncio.run(tts.cleanup())

    def test_openai_base_url(self):
        from voice_agent_pipecat import SparkOpenAILLMService, _openai_base_url

        self.assertEqual(
            _openai_base_url("http://10.0.0.5:8000/v1/chat/completions"),
            "http://10.0.0.5:8000/v1",
        )
        llm = SparkOpenAILLMService(
            request_timeout_s=7,
            api_key="test",
            base_url="http://127.0.0.1:1/v1",
            settings=SparkOpenAILLMService.Settings(
                model="test",
                extra={"extra_body": {"repetition_penalty": 1.15}},
            ),
        )
        self.assertEqual(
            llm._settings.extra,
            {"extra_body": {"repetition_penalty": 1.15}},
        )
        self.assertEqual(llm._client.timeout, 7)
        asyncio.run(llm._client.close())


if __name__ == "__main__":
    unittest.main()
