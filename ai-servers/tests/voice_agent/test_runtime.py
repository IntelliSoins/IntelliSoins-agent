from __future__ import annotations

import unittest

import _path  # noqa: F401  # test path bootstrap

from voice_agent.config import VoiceConfig
from voice_agent.runtime import VoiceRuntime


class TestVoiceRuntime(unittest.TestCase):
    def make_runtime(
        self,
        *,
        consent: bool = False,
        require_consent: bool = False,
        session_id: str = "call-1",
    ) -> VoiceRuntime:
        return VoiceRuntime.create(
            VoiceConfig(db_dsn="", db_enabled=False),
            subject_id="contact-42",
            session_id=session_id,
            explicit_consent_verified=consent,
            require_consent=require_consent,
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

        segments = runtime.store.memory_tts_segments()
        self.assertEqual(len(segments), 1)
        self.assertIsNone(segments[0]["audio_bytes"])
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
        self.assertTrue(runtime.end_requested)
        self.assertEqual(
            runtime.store.memory_outbox()[0]["event_type"],
            "urgent_human_review",
        )
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

    def test_required_consent_transitions_from_explicit_transcript(self):
        runtime = self.make_runtime(require_consent=True)
        runtime.start()
        runtime.start_user_turn("Oui, je consens")
        self.assertTrue(runtime.explicit_consent_verified)
        consent = runtime.memory.get_active("contact-42", "consent:voice_session")
        self.assertIsNotNone(consent)
        self.assertTrue(consent.fact_value["granted"])
        runtime.close()

        declined = self.make_runtime(
            require_consent=True,
            session_id="call-declined",
        )
        declined.start()
        declined.start_user_turn("Non merci")
        self.assertTrue(declined.end_requested)
        consent = declined.memory.get_active(
            "contact-42", "consent:voice_session"
        )
        self.assertFalse(consent.fact_value["granted"])
        declined.close()

    def test_callback_and_opt_out_enqueue_actions(self):
        runtime = self.make_runtime()
        runtime.start()
        runtime.start_user_turn("Rappelez-moi demain.")
        runtime.invoke_tool(
            "schedule_callback",
            {"when": "tomorrow", "reason": "follow_up"},
        )
        runtime.invoke_tool("opt_out", {"channels": ["voice"]})
        self.assertEqual(
            [item["event_type"] for item in runtime.store.memory_outbox()],
            ["callback_requested", "contact_opt_out"],
        )
        self.assertTrue(runtime.end_requested)
        runtime.close()

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
