"""Unit tests — allowlisted idempotent tool registry."""

from __future__ import annotations

import re
import unittest

import _path  # noqa: F401

from voice_agent.memory import DurableMemoryRepository
from voice_agent.tools.handlers import ToolContext, _idem
from voice_agent.tools.registry import build_default_registry


EXPECTED_TOOLS = frozenset(
    {
        "record_consent",
        "save_call_note",
        "record_reminder_outcome",
        "capture_followup",
        "capture_triage_intake",
        "detect_red_flags",
        "schedule_callback",
        "opt_out",
        "end_call",
    }
)


class TestToolRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_default_registry()
        self.memory = DurableMemoryRepository(dsn="", enabled=False)
        self.ctx = ToolContext(
            session_id="sess-tools",
            subject_id="contact-tools",
            memory=self.memory,
            turn_pk=1,
            user_text="",
            explicit_consent_verified=True,
        )

    def test_allowlist_exact(self) -> None:
        self.assertEqual(self.registry.allowlisted(), EXPECTED_TOOLS)
        names = {t["function"]["name"] for t in self.registry.openai_tools()}
        self.assertEqual(names, EXPECTED_TOOLS)

    def test_unknown_tool_rejected(self) -> None:
        result = self.registry.invoke("diagnose_patient", {"x": 1}, self.ctx)
        self.assertFalse(result.ok)
        self.assertEqual(result.data["error"], "tool_not_allowlisted")

    def test_record_consent_requires_explicit_verification(self) -> None:
        unverified = ToolContext(
            session_id="sess-tools",
            subject_id="contact-tools",
            memory=self.memory,
            explicit_consent_verified=False,
        )
        result = self.registry.invoke(
            "record_consent",
            {"granted": True, "idempotency_key": "c0"},
            unverified,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.data["error"], "explicit_consent_required")
        self.assertIsNone(self.memory.get_active("contact-tools", "consent:voice_session"))

    def test_record_consent_idempotent(self) -> None:
        a = self.registry.invoke(
            "record_consent",
            {"granted": True, "idempotency_key": "c1"},
            self.ctx,
        )
        b = self.registry.invoke(
            "record_consent",
            {"granted": True, "idempotency_key": "c1"},
            self.ctx,
        )
        self.assertTrue(a.ok)
        self.assertTrue(b.ok)
        self.assertFalse(a.idempotent_replay)
        self.assertTrue(b.idempotent_replay)
        self.assertEqual(a.data["fact_id"], b.data["fact_id"])
        self.assertEqual(a.data["subject_id"], "contact-tools")
        self.assertEqual(a.data["source_session_id"], "sess-tools")

    def test_llm_cannot_set_identity_or_consent_flag(self) -> None:
        other = ToolContext(
            session_id="sess-real",
            subject_id="contact-real",
            memory=self.memory,
            explicit_consent_verified=True,
        )
        result = self.registry.invoke(
            "opt_out",
            {
                "channels": ["voice"],
                "subject_id": "attacker-subject",
                "session_id": "attacker-session",
                "explicit_consent_verified": False,
                "idempotency_key": "o-attack",
            },
            other,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["subject_id"], "contact-real")
        self.assertEqual(result.data["source_session_id"], "sess-real")
        self.assertIsNone(self.memory.get_active("attacker-subject", "opt_out"))

    def test_idem_fallback_is_sha256_digest(self) -> None:
        body = "Patient name Jean Dupont 555-1234"
        key = _idem({"body": body, "note_type": "routing"}, "save_call_note")
        self.assertNotIn("Jean", key)
        self.assertNotIn("Dupont", key)
        self.assertNotIn("555", key)
        self.assertNotIn(body, key)
        prefix, digest = key.split(":", 1)
        self.assertEqual(prefix, "save_call_note")
        self.assertRegex(digest, re.compile(r"^[0-9a-f]{64}$"))

    def test_save_call_note_structured(self) -> None:
        result = self.registry.invoke(
            "save_call_note",
            {
                "body": "Prefers morning callbacks",
                "note_type": "routing",
                "tags": ["callback"],
            },
            self.ctx,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["fact_value"]["kind"], "structured_note")
        # Fact key embeds digest, not the note body.
        self.assertNotIn("Prefers", result.data["fact_key"])
        self.assertNotIn("morning", result.data["fact_key"])

    def test_capture_triage_intake_no_diagnosis(self) -> None:
        result = self.registry.invoke(
            "capture_triage_intake",
            {
                "chief_concern": "fatigue",
                "symptoms": ["tired"],
                "idempotency_key": "t1",
            },
            self.ctx,
        )
        self.assertTrue(result.ok)
        self.assertIsNone(result.data["fact_value"]["diagnosis"])
        self.assertIn("Not a diagnosis", result.data["disclaimer"])

    def test_detect_red_flags_tool_and_independent(self) -> None:
        independent = self.registry.scan_red_flags_independent(
            "Je veux me suicider"
        )
        self.assertTrue(independent.triggered)

        result = self.registry.invoke(
            "detect_red_flags",
            {"text": "Je veux me suicider", "idempotency_key": "rf1"},
            self.ctx,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.data["triggered"])
        for match in result.data["matches"]:
            self.assertIsNone(match["diagnosis"])

    def test_end_call_and_opt_out(self) -> None:
        end = self.registry.invoke(
            "end_call",
            {"reason": "done", "idempotency_key": "e1"},
            self.ctx,
        )
        self.assertTrue(end.data["should_end"])
        opt = self.registry.invoke(
            "opt_out",
            {"channels": ["voice", "sms"], "idempotency_key": "o1"},
            self.ctx,
        )
        self.assertTrue(opt.ok)
        self.assertTrue(opt.data["fact_value"]["active"])

    def test_schedule_callback_no_phone(self) -> None:
        schema = self.registry.schemas["schedule_callback"]
        props = schema["function"]["parameters"]["properties"]
        self.assertNotIn("phone", props)

        result = self.registry.invoke_openai_tool_call(
            {
                "id": "call_x",
                "type": "function",
                "function": {
                    "name": "schedule_callback",
                    "arguments": (
                        '{"when":"2026-07-23T10:00:00","phone":"+15551212",'
                        '"idempotency_key":"cb1"}'
                    ),
                },
            },
            self.ctx,
        )
        self.assertTrue(result.ok)
        value = result.data["fact_value"]
        self.assertEqual(value["status"], "requested")
        self.assertNotIn("phone", value)
        self.assertEqual(value["subject_id"], "contact-tools")

    def test_facts_shared_across_call_sessions(self) -> None:
        call1 = ToolContext(
            session_id="call-1",
            subject_id="contact-shared",
            memory=self.memory,
            explicit_consent_verified=True,
        )
        call2 = ToolContext(
            session_id="call-2",
            subject_id="contact-shared",
            memory=self.memory,
            explicit_consent_verified=True,
        )
        self.registry.invoke(
            "record_consent",
            {"granted": True, "idempotency_key": "shared-consent"},
            call1,
        )
        active = self.memory.get_active("contact-shared", "consent:voice_session")
        assert active is not None
        self.assertEqual(active.source_session_id, "call-1")

        # Same idempotency key on a later call is a replay, still subject-scoped.
        replay = self.registry.invoke(
            "record_consent",
            {"granted": True, "idempotency_key": "shared-consent"},
            call2,
        )
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.data["source_session_id"], "call-1")

    def test_remaining_safe_tools(self) -> None:
        reminder = self.registry.invoke(
            "record_reminder_outcome",
            {
                "reminder_id": "r1",
                "outcome": "acknowledged",
                "idempotency_key": "rm1",
            },
            self.ctx,
        )
        follow = self.registry.invoke(
            "capture_followup",
            {
                "summary": "Send brochure",
                "when": "tomorrow",
                "idempotency_key": "f1",
            },
            self.ctx,
        )
        self.assertTrue(reminder.ok)
        self.assertTrue(follow.ok)


if __name__ == "__main__":
    unittest.main()
