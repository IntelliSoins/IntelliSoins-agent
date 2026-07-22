"""Unit tests — event store (disabled / in-memory mode, no live DB)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import _path  # noqa: F401

from voice_agent.config import VoiceConfig
from voice_agent.events import EventStore, psycopg_available


class TestEventStoreDisabled(unittest.TestCase):
    def test_from_config_without_dsn(self) -> None:
        store = EventStore.from_config(VoiceConfig(db_dsn="", db_enabled=True))
        self.assertFalse(store.is_enabled)
        self.assertEqual(store.disabled_reason, "no_dsn")

    def test_disabled_when_psycopg_missing(self) -> None:
        store = EventStore(dsn="postgresql://localhost/voice_agent", enabled=True)
        with patch("voice_agent.events._PSYCOPG_AVAILABLE", False):
            store._resolve_enabled()
        self.assertFalse(store.is_enabled)
        self.assertEqual(store.disabled_reason, "psycopg_unavailable")

    def test_memory_mode_session_turn_tools_tts(self) -> None:
        store = EventStore(dsn="", enabled=False)
        session = store.start_session("sess-1", tools_enabled=True)
        self.assertEqual(session.session_id, "sess-1")
        self.assertIsNotNone(session.session_pk)

        turn = store.start_turn(
            session, 0, user_transcript="allo", route="intake"
        )
        self.assertEqual(turn.turn_index, 0)
        store.record_tool_call(
            turn, 0, "record_consent", {"granted": True}, {"ok": True}
        )
        store.record_tts_segment(turn, 0, "Bonjour.", audio_bytes=b"wav")
        store.finish_turn(
            turn,
            answer_text="Bonjour.",
            stopped_reason="completed",
            n_tool_calls=1,
            n_tts_segments=1,
        )

        tools = store.memory_tool_calls()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["tool_name"], "record_consent")
        tts = store.memory_tts_segments()
        self.assertEqual(tts[0]["text"], "Bonjour.")
        self.assertEqual(tts[0]["audio_bytes"], b"wav")

    def test_psycopg_available_is_bool(self) -> None:
        self.assertIsInstance(psycopg_available(), bool)

    def test_enabled_path_uses_sql_when_connected(self) -> None:
        """Exercise SQL writers against a mocked connection (no live PG)."""
        store = EventStore(dsn="postgresql://localhost/voice_agent", enabled=True)
        # Force enabled even if psycopg absent in this interpreter.
        store.enabled = True
        store._disabled_reason = ""

        conn = MagicMock()
        session_row = {"id": 10}
        turn_row = {"id": 20}
        conn.execute = MagicMock(
            side_effect=[
                MagicMock(fetchone=MagicMock(return_value=session_row)),
                MagicMock(fetchone=MagicMock(return_value=turn_row)),
                MagicMock(),  # tool_call
                MagicMock(),  # tts
                MagicMock(),  # finish_turn
            ]
        )
        store._conn = conn

        session = store.start_session("s-sql")
        self.assertEqual(session.session_pk, 10)
        turn = store.start_turn(session, 1, user_transcript="hi")
        self.assertEqual(turn.turn_pk, 20)
        store.record_tool_call(turn, 0, "opt_out", {}, {"ok": True})
        store.record_tts_segment(turn, 0, "ok")
        store.finish_turn(turn, answer_text="ok", n_tool_calls=1, n_tts_segments=1)
        self.assertGreaterEqual(conn.execute.call_count, 5)
        self.assertGreaterEqual(conn.commit.call_count, 5)
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        self.assertIn("public.sessions", sqls)
        self.assertIn("public.turns", sqls)
        self.assertIn("public.tool_calls", sqls)
        self.assertIn("public.tts_segments", sqls)


if __name__ == "__main__":
    unittest.main()
