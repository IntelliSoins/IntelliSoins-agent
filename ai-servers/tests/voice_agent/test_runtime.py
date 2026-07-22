from __future__ import annotations

import unittest

import _path  # noqa: F401  # test path bootstrap

from voice_agent.config import VoiceConfig
from voice_agent.runtime import VoiceRuntime


class TestVoiceRuntime(unittest.TestCase):
    def make_runtime(
        self, *, consent: bool = False, session_id: str = "call-1"
    ) -> VoiceRuntime:
        return VoiceRuntime.create(
            VoiceConfig(db_dsn="", db_enabled=False),
            subject_id="contact-42",
            session_id=session_id,
            explicit_consent_verified=consent,
        )

    def test_requires_trusted_subject(self):
        with self.assertRaises(ValueError):
            VoiceRuntime.create(
                VoiceConfig(db_enabled=False),
                subject_id="",
                session_id="call-1",
            )

    def test_exact_turn_and_tts_are_recorded(self):
        runtime = self.make_runtime()
        runtime.start()
        safety = runtime.start_user_turn("Bonjour, voici mon suivi.")
        self.assertFalse(safety.triggered)

        runtime.record_tts(
            "Merci pour le suivi.",
            b"RIFF-audio",
            sample_rate=24000,
            synth_seconds=0.2,
            audio_seconds=1.0,
        )
        runtime.finish_turn()

        self.assertEqual(len(runtime.store.memory_tts_segments()), 1)
        self.assertIsNone(runtime.current_turn)
        runtime.close()

    def test_red_flag_scan_is_automatic_and_logged(self):
        runtime = self.make_runtime()
        runtime.start()
        safety = runtime.start_user_turn("J'ai une douleur à la poitrine.")

        self.assertTrue(safety.triggered)
        calls = runtime.store.memory_tool_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool_name"], "detect_red_flags")
        runtime.close()

    def test_consent_gate_uses_runtime_flag_only(self):
        runtime = self.make_runtime(consent=False)
        runtime.start()
        runtime.start_user_turn("Oui, je consens à cet appel.")
        denied = runtime.invoke_tool(
            "record_consent",
            {"granted": True, "explicit_consent_verified": True},
        )
        self.assertFalse(denied.ok)
        self.assertEqual(denied.data["error"], "explicit_consent_required")
        runtime.close()

        verified = self.make_runtime(consent=True, session_id="call-2")
        verified.start()
        verified.start_user_turn("Oui, je consens à cet appel.")
        accepted = verified.invoke_tool("record_consent", {"granted": True})
        self.assertTrue(accepted.ok)
        verified.close()

    def test_memory_is_subject_scoped_across_calls(self):
        first = self.make_runtime()
        first.start()
        first.start_user_turn("Rappelle-moi demain.")
        saved = first.invoke_tool(
            "capture_followup",
            {"summary": "Rappeler demain", "when": "demain"},
        )
        self.assertTrue(saved.ok)

        second = self.make_runtime(session_id="call-2")
        second.memory = first.memory
        facts = second.active_facts()
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].subject_id, "contact-42")


if __name__ == "__main__":
    unittest.main()
