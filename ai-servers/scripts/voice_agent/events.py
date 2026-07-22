"""PostgreSQL exact event log (per-call) — separate from durable memory.

Writes existing ``voice_agent`` tables:
``public.sessions``, ``public.turns``, ``public.tool_calls``, ``public.tts_segments``.

Records call traces: session/turn inserts, turn completion updates, and
idempotent upserts on ``(turn_pk, ordinal)`` for tool calls / TTS segments.
This is the exact log, not subject-scoped durable memory.

Uses ``psycopg`` only when importable and a DSN is configured; otherwise runs
in a graceful no-op disabled mode (in-memory ids for unit tests / dry runs).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

try:
    import psycopg
    from psycopg.rows import dict_row

    _PSYCOPG_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via disabled mode in tests
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    _PSYCOPG_AVAILABLE = False


def psycopg_available() -> bool:
    return _PSYCOPG_AVAILABLE


@dataclass
class SessionHandle:
    session_id: str
    session_pk: Optional[int] = None


@dataclass
class TurnHandle:
    session_id: str
    session_pk: Optional[int]
    turn_pk: Optional[int]
    turn_index: int


@dataclass
class EventStore:
    """Exact per-call event log over the existing voice_agent schema.

    Distinct from ``DurableMemoryRepository`` (subject-scoped confirmed facts).
    Turn completion uses UPDATE; tool/TTS rows use ordinal upserts.
    """

    dsn: str = ""
    enabled: bool = True
    _conn: Any = field(default=None, repr=False)
    _disabled_reason: str = field(default="", repr=False)
    _mem_session_pk: int = field(default=0, repr=False)
    _mem_turn_pk: int = field(default=0, repr=False)
    _mem_sessions: dict[str, int] = field(default_factory=dict, repr=False)
    _mem_turns: dict[int, dict[str, Any]] = field(default_factory=dict, repr=False)
    _mem_tool_calls: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _mem_tts: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @classmethod
    def from_config(cls, config: Any) -> "EventStore":
        dsn = getattr(config, "db_dsn", "") or ""
        want = bool(getattr(config, "db_enabled", True))
        store = cls(dsn=dsn, enabled=want and bool(dsn))
        if not dsn:
            store.enabled = False
            store._disabled_reason = "no_dsn"
        elif not want:
            store.enabled = False
            store._disabled_reason = "disabled_by_config"
        else:
            store._resolve_enabled()
        return store

    def _resolve_enabled(self) -> None:
        if not self.enabled:
            self._disabled_reason = self._disabled_reason or "disabled_by_config"
            return
        if not self.dsn:
            self.enabled = False
            self._disabled_reason = "no_dsn"
            return
        if not _PSYCOPG_AVAILABLE:
            self.enabled = False
            self._disabled_reason = "psycopg_unavailable"
            return

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    @property
    def disabled_reason(self) -> str:
        return "" if self.enabled else (self._disabled_reason or "disabled")

    def connect(self) -> None:
        """Open a connection when enabled; no-op when disabled."""
        self._resolve_enabled()
        if not self.enabled:
            return
        assert psycopg is not None
        self._conn = psycopg.connect(self.dsn, row_factory=dict_row)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "EventStore":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- sessions / turns -------------------------------------------------

    def start_session(
        self,
        session_id: Optional[str] = None,
        *,
        host: Optional[str] = None,
        pid: Optional[int] = None,
        tools_enabled: Optional[bool] = True,
        config: Optional[Mapping[str, Any]] = None,
        **flags: Any,
    ) -> SessionHandle:
        sid = session_id or str(uuid.uuid4())
        if not self.enabled:
            self._mem_session_pk += 1
            pk = self._mem_session_pk
            self._mem_sessions[sid] = pk
            return SessionHandle(session_id=sid, session_pk=pk)

        self._ensure_conn()
        row = self._conn.execute(
            """
            INSERT INTO public.sessions (
                session_id, host, pid, tools_enabled, agent_route,
                allow_send, barge_in, config
            ) VALUES (
                %(session_id)s, %(host)s, %(pid)s, %(tools_enabled)s,
                %(agent_route)s, %(allow_send)s, %(barge_in)s, %(config)s::jsonb
            )
            RETURNING id
            """,
            {
                "session_id": sid,
                "host": host or os.uname().nodename,
                "pid": pid if pid is not None else os.getpid(),
                "tools_enabled": tools_enabled,
                "agent_route": flags.get("agent_route"),
                "allow_send": flags.get("allow_send"),
                "barge_in": flags.get("barge_in"),
                "config": json.dumps(dict(config or {})),
            },
        ).fetchone()
        self._conn.commit()
        return SessionHandle(session_id=sid, session_pk=int(row["id"]))

    def start_turn(
        self,
        session: SessionHandle,
        turn_index: int,
        *,
        user_transcript: Optional[str] = None,
        route: Optional[str] = None,
        system_prompt: Optional[str] = None,
        input_format: str = "wav",
        input_sample_rate: Optional[int] = None,
        input_duration_s: Optional[float] = None,
        input_rms: Optional[float] = None,
        input_bytes: Optional[int] = None,
        raw: Optional[Mapping[str, Any]] = None,
    ) -> TurnHandle:
        if not self.enabled:
            self._mem_turn_pk += 1
            pk = self._mem_turn_pk
            self._mem_turns[pk] = {
                "session_id": session.session_id,
                "session_pk": session.session_pk,
                "turn_index": turn_index,
                "user_transcript": user_transcript,
            }
            return TurnHandle(
                session_id=session.session_id,
                session_pk=session.session_pk,
                turn_pk=pk,
                turn_index=turn_index,
            )

        self._ensure_conn()
        row = self._conn.execute(
            """
            INSERT INTO public.turns (
                session_pk, session_id, turn_index, user_transcript, route,
                system_prompt, input_format, input_sample_rate, input_duration_s,
                input_rms, input_bytes, raw
            ) VALUES (
                %(session_pk)s, %(session_id)s, %(turn_index)s, %(user_transcript)s,
                %(route)s, %(system_prompt)s, %(input_format)s, %(input_sample_rate)s,
                %(input_duration_s)s, %(input_rms)s, %(input_bytes)s, %(raw)s::jsonb
            )
            RETURNING id
            """,
            {
                "session_pk": session.session_pk,
                "session_id": session.session_id,
                "turn_index": turn_index,
                "user_transcript": user_transcript,
                "route": route,
                "system_prompt": system_prompt,
                "input_format": input_format,
                "input_sample_rate": input_sample_rate,
                "input_duration_s": input_duration_s,
                "input_rms": input_rms,
                "input_bytes": input_bytes,
                "raw": json.dumps(dict(raw or {})),
            },
        ).fetchone()
        self._conn.commit()
        return TurnHandle(
            session_id=session.session_id,
            session_pk=session.session_pk,
            turn_pk=int(row["id"]),
            turn_index=turn_index,
        )

    def finish_turn(
        self,
        turn: TurnHandle,
        *,
        answer_text: Optional[str] = None,
        stopped_reason: Optional[str] = None,
        error: Optional[str] = None,
        n_tool_calls: Optional[int] = None,
        n_tts_segments: Optional[int] = None,
        turn_wall_seconds: Optional[float] = None,
        rounds: Optional[int] = None,
        session_tokens: Optional[int] = None,
        cached_tokens: Optional[int] = None,
        gemma_gen_seconds: Optional[float] = None,
        raw: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            rec = self._mem_turns.get(turn.turn_pk or -1)
            if rec is not None:
                rec.update(
                    {
                        "answer_text": answer_text,
                        "stopped_reason": stopped_reason,
                        "error": error,
                        "n_tool_calls": n_tool_calls,
                        "n_tts_segments": n_tts_segments,
                    }
                )
            return

        self._ensure_conn()
        self._conn.execute(
            """
            UPDATE public.turns SET
                answer_text = COALESCE(%(answer_text)s, answer_text),
                stopped_reason = COALESCE(%(stopped_reason)s, stopped_reason),
                error = COALESCE(%(error)s, error),
                n_tool_calls = COALESCE(%(n_tool_calls)s, n_tool_calls),
                n_tts_segments = COALESCE(%(n_tts_segments)s, n_tts_segments),
                turn_wall_seconds = COALESCE(%(turn_wall_seconds)s, turn_wall_seconds),
                rounds = COALESCE(%(rounds)s, rounds),
                session_tokens = COALESCE(%(session_tokens)s, session_tokens),
                cached_tokens = COALESCE(%(cached_tokens)s, cached_tokens),
                gemma_gen_seconds = COALESCE(%(gemma_gen_seconds)s, gemma_gen_seconds),
                raw = CASE
                    WHEN %(raw)s IS NULL THEN raw
                    ELSE %(raw)s::jsonb
                END
            WHERE id = %(turn_pk)s
            """,
            {
                "turn_pk": turn.turn_pk,
                "answer_text": answer_text,
                "stopped_reason": stopped_reason,
                "error": error,
                "n_tool_calls": n_tool_calls,
                "n_tts_segments": n_tts_segments,
                "turn_wall_seconds": turn_wall_seconds,
                "rounds": rounds,
                "session_tokens": session_tokens,
                "cached_tokens": cached_tokens,
                "gemma_gen_seconds": gemma_gen_seconds,
                "raw": json.dumps(dict(raw)) if raw is not None else None,
            },
        )
        self._conn.commit()

    def record_tool_call(
        self,
        turn: TurnHandle,
        ordinal: int,
        tool_name: str,
        arguments: Any,
        result: Any,
    ) -> None:
        args_s = _as_text(arguments)
        result_s = _as_text(result)
        if not self.enabled:
            self._mem_tool_calls.append(
                {
                    "turn_pk": turn.turn_pk,
                    "ordinal": ordinal,
                    "tool_name": tool_name,
                    "arguments": args_s,
                    "result": result_s,
                }
            )
            return

        self._ensure_conn()
        self._conn.execute(
            """
            INSERT INTO public.tool_calls (turn_pk, ordinal, tool_name, arguments, result)
            VALUES (%(turn_pk)s, %(ordinal)s, %(tool_name)s, %(arguments)s, %(result)s)
            ON CONFLICT (turn_pk, ordinal) DO UPDATE SET
                tool_name = EXCLUDED.tool_name,
                arguments = EXCLUDED.arguments,
                result = EXCLUDED.result
            """,
            {
                "turn_pk": turn.turn_pk,
                "ordinal": ordinal,
                "tool_name": tool_name,
                "arguments": args_s,
                "result": result_s,
            },
        )
        self._conn.commit()

    def record_tts_segment(
        self,
        turn: TurnHandle,
        ordinal: int,
        text: str,
        *,
        audio_bytes: Optional[bytes] = None,
        sample_rate: Optional[int] = None,
        char_count: Optional[int] = None,
        synth_seconds: Optional[float] = None,
        audio_seconds: Optional[float] = None,
        ttfa_seconds: Optional[float] = None,
        rtf: Optional[float] = None,
        cfg_value: Optional[float] = None,
        inference_timesteps: Optional[int] = None,
    ) -> None:
        if not self.enabled:
            self._mem_tts.append(
                {
                    "turn_pk": turn.turn_pk,
                    "ordinal": ordinal,
                    "text": text,
                    "char_count": char_count if char_count is not None else len(text),
                    "audio_bytes": audio_bytes,
                    "sample_rate": sample_rate,
                }
            )
            return

        self._ensure_conn()
        self._conn.execute(
            """
            INSERT INTO public.tts_segments (
                turn_pk, ordinal, text, char_count, cfg_value, inference_timesteps,
                ttfa_seconds, synth_seconds, audio_seconds, rtf, sample_rate,
                output_audio
            ) VALUES (
                %(turn_pk)s, %(ordinal)s, %(text)s, %(char_count)s, %(cfg_value)s,
                %(inference_timesteps)s, %(ttfa_seconds)s, %(synth_seconds)s,
                %(audio_seconds)s, %(rtf)s, %(sample_rate)s, %(output_audio)s
            )
            ON CONFLICT (turn_pk, ordinal) DO UPDATE SET
                text = EXCLUDED.text,
                char_count = EXCLUDED.char_count,
                output_audio = EXCLUDED.output_audio
            """,
            {
                "turn_pk": turn.turn_pk,
                "ordinal": ordinal,
                "text": text,
                "char_count": char_count if char_count is not None else len(text),
                "cfg_value": cfg_value,
                "inference_timesteps": inference_timesteps,
                "ttfa_seconds": ttfa_seconds,
                "synth_seconds": synth_seconds,
                "audio_seconds": audio_seconds,
                "rtf": rtf,
                "sample_rate": sample_rate,
                "output_audio": audio_bytes,
            },
        )
        self._conn.commit()

    # --- memory-mode inspection (tests / dry-run) -------------------------

    def memory_tool_calls(self) -> Sequence[Mapping[str, Any]]:
        return list(self._mem_tool_calls)

    def memory_tts_segments(self) -> Sequence[Mapping[str, Any]]:
        return list(self._mem_tts)

    def _ensure_conn(self) -> None:
        if self._conn is None:
            self.connect()
        if self._conn is None:
            raise RuntimeError("event store connection unavailable")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)
