"""Unit tests — durable memory repository (in-memory / disabled mode)."""

from __future__ import annotations

import unittest
from pathlib import Path

import _path  # noqa: F401

from voice_agent.events import EventStore
from voice_agent.memory import DurableMemoryRepository, SubjectIdRequired


class TestDurableMemory(unittest.TestCase):
    def test_migration_is_subject_scoped(self) -> None:
        path = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "voice_agent"
            / "migrations"
            / "001_durable_memory.sql"
        )
        self.assertTrue(path.is_file())
        sql = path.read_text(encoding="utf-8")
        self.assertIn("durable_facts", sql)
        self.assertIn("subject_id", sql)
        self.assertIn("source_session_id", sql)
        self.assertIn("(subject_id, fact_key)", sql)
        self.assertIn("(subject_id, idempotency_key)", sql)
        self.assertNotIn("(session_id, fact_key)", sql)

    def test_action_outbox_migration_exists(self) -> None:
        path = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "voice_agent"
            / "migrations"
            / "002_action_outbox.sql"
        )
        sql = path.read_text(encoding="utf-8")
        self.assertIn("action_outbox", sql)
        self.assertIn("status = 'pending'", sql)
        self.assertIn("UNIQUE (subject_id, event_type, idempotency_key)", sql)

    def test_confirm_and_idempotent_replay(self) -> None:
        store = EventStore(dsn="", enabled=False)
        mem = DurableMemoryRepository.from_event_store(store)
        self.assertFalse(mem.is_enabled)

        first = mem.confirm_fact(
            "contact-a",
            "consent:voice_session",
            {"granted": True},
            source_session_id="sess-1",
            category="consent",
            idempotency_key="consent-1",
        )
        second = mem.confirm_fact(
            "contact-a",
            "consent:voice_session",
            {"granted": False},
            source_session_id="sess-2",
            category="consent",
            idempotency_key="consent-1",
        )
        self.assertEqual(first.id, second.id)
        self.assertTrue(second.fact_value["granted"])
        self.assertEqual(second.source_session_id, "sess-1")

        active = mem.get_active("contact-a", "consent:voice_session")
        assert active is not None
        self.assertTrue(active.fact_value["granted"])
        self.assertEqual(active.subject_id, "contact-a")

    def test_memory_survives_across_sessions(self) -> None:
        mem = DurableMemoryRepository(dsn="", enabled=False)
        mem.confirm_fact(
            "contact-x",
            "opt_out",
            {"active": True, "channels": ["voice"]},
            source_session_id="call-1",
            category="consent",
            idempotency_key="opt-1",
        )
        # Later call, same contact — fact still active.
        active = mem.get_active("contact-x", "opt_out")
        assert active is not None
        self.assertEqual(active.source_session_id, "call-1")

        # New write from a different call supersedes and audits the new session.
        mem.confirm_fact(
            "contact-x",
            "opt_out",
            {"active": True, "channels": ["voice", "sms"]},
            source_session_id="call-2",
            category="consent",
            idempotency_key="opt-2",
        )
        active2 = mem.get_active("contact-x", "opt_out")
        assert active2 is not None
        self.assertEqual(active2.source_session_id, "call-2")
        self.assertEqual(active2.fact_value["channels"], ["voice", "sms"])

    def test_subject_id_required(self) -> None:
        mem = DurableMemoryRepository(dsn="", enabled=False)
        with self.assertRaises(SubjectIdRequired):
            mem.confirm_fact("", "k", {"v": 1})
        with self.assertRaises(SubjectIdRequired):
            mem.get_active("   ", "k")

    def test_supersede_on_new_key_write_memory_mode(self) -> None:
        mem = DurableMemoryRepository(dsn="", enabled=False)
        mem.confirm_fact(
            "s",
            "triage_intake",
            {"chief_concern": "a"},
            source_session_id="c1",
            category="triage",
        )
        mem.confirm_fact(
            "s",
            "triage_intake",
            {"chief_concern": "b"},
            source_session_id="c2",
            category="triage",
        )
        active = mem.get_active("s", "triage_intake")
        assert active is not None
        self.assertEqual(active.fact_value["chief_concern"], "b")
        self.assertEqual(active.source_session_id, "c2")

    def test_list_active_by_category(self) -> None:
        mem = DurableMemoryRepository(dsn="", enabled=False)
        mem.confirm_fact("s", "note:1", {"body": "x"}, category="note")
        mem.confirm_fact("s", "opt_out", {"active": True}, category="consent")
        notes = mem.list_active("s", category="note")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].fact_key, "note:1")
        self.assertEqual(notes[0].subject_id, "s")


if __name__ == "__main__":
    unittest.main()
