"""Derived durable memory repository (confirmed facts only).

Separate from the exact event log (``EventStore`` / sessions·turns·tool_calls·
tts_segments). Stores promoted, confirmed facts in ``public.durable_facts``
(see ``migrations/001_durable_memory.sql``).

Facts are keyed by ``subject_id`` (trusted contact identity) so memory survives
across calls. ``source_session_id`` is audit-only (which call wrote the fact).
Identity must come from trusted runtime context — never from LLM tool args.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from .events import EventStore, psycopg_available

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


class SubjectIdRequired(ValueError):
    """Raised when durable memory is invoked without a contact identity."""


@dataclass
class DurableFact:
    subject_id: str
    fact_key: str
    fact_value: dict[str, Any]
    source_session_id: Optional[str] = None
    category: str = "general"
    source_turn_pk: Optional[int] = None
    source_tool: Optional[str] = None
    idempotency_key: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class DurableMemoryRepository:
    """Subject-scoped confirmed facts, separate from the exact event log."""

    dsn: str = ""
    enabled: bool = True
    _conn: Any = field(default=None, repr=False)
    _disabled_reason: str = field(default="", repr=False)
    # subject_id -> fact_key -> DurableFact
    _mem: dict[str, dict[str, DurableFact]] = field(default_factory=dict, repr=False)
    # (subject_id, idempotency_key) -> DurableFact
    _mem_by_idem: dict[tuple[str, str], DurableFact] = field(
        default_factory=dict, repr=False
    )
    _next_id: int = field(default=0, repr=False)

    @classmethod
    def from_event_store(cls, store: EventStore) -> "DurableMemoryRepository":
        repo = cls(dsn=store.dsn, enabled=store.is_enabled)
        if not store.is_enabled:
            repo.enabled = False
            repo._disabled_reason = store.disabled_reason
        else:
            repo._resolve_enabled()
        return repo

    @classmethod
    def from_config(cls, config: Any) -> "DurableMemoryRepository":
        dsn = getattr(config, "db_dsn", "") or ""
        want = bool(getattr(config, "db_enabled", True))
        repo = cls(dsn=dsn, enabled=want and bool(dsn))
        if not dsn:
            repo.enabled = False
            repo._disabled_reason = "no_dsn"
        elif not want:
            repo.enabled = False
            repo._disabled_reason = "disabled_by_config"
        else:
            repo._resolve_enabled()
        return repo

    def _resolve_enabled(self) -> None:
        if not self.enabled:
            self._disabled_reason = self._disabled_reason or "disabled_by_config"
            return
        if not self.dsn:
            self.enabled = False
            self._disabled_reason = "no_dsn"
            return
        if not psycopg_available():
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
        self._resolve_enabled()
        if not self.enabled:
            return
        assert psycopg is not None
        self._conn = psycopg.connect(self.dsn, row_factory=dict_row)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DurableMemoryRepository":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def confirm_fact(
        self,
        subject_id: str,
        fact_key: str,
        fact_value: Mapping[str, Any],
        *,
        source_session_id: Optional[str] = None,
        category: str = "general",
        source_turn_pk: Optional[int] = None,
        source_tool: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> DurableFact:
        """Confirm a fact for a contact (idempotent on subject + idempotency_key)."""
        sid = _require_subject_id(subject_id)
        value = dict(fact_value)
        now = datetime.now(timezone.utc)

        if idempotency_key:
            existing = self.get_by_idempotency(sid, idempotency_key)
            if existing is not None:
                return existing

        if not self.enabled:
            return self._mem_confirm(
                sid,
                fact_key,
                value,
                source_session_id=source_session_id,
                category=category,
                source_turn_pk=source_turn_pk,
                source_tool=source_tool,
                idempotency_key=idempotency_key,
                confirmed_at=now,
            )

        self._ensure_conn()
        self._conn.execute(
            """
            UPDATE public.durable_facts
            SET superseded_at = now()
            WHERE subject_id = %(subject_id)s
              AND fact_key = %(fact_key)s
              AND superseded_at IS NULL
            """,
            {"subject_id": sid, "fact_key": fact_key},
        )
        row = self._conn.execute(
            """
            INSERT INTO public.durable_facts (
                subject_id, source_session_id, fact_key, fact_value, category,
                source_turn_pk, source_tool, idempotency_key, meta
            ) VALUES (
                %(subject_id)s, %(source_session_id)s, %(fact_key)s,
                %(fact_value)s::jsonb, %(category)s, %(source_turn_pk)s,
                %(source_tool)s, %(idempotency_key)s, %(meta)s::jsonb
            )
            RETURNING id, confirmed_at
            """,
            {
                "subject_id": sid,
                "source_session_id": source_session_id,
                "fact_key": fact_key,
                "fact_value": json.dumps(value),
                "category": category,
                "source_turn_pk": source_turn_pk,
                "source_tool": source_tool,
                "idempotency_key": idempotency_key,
                "meta": json.dumps(dict(meta or {})),
            },
        ).fetchone()
        self._conn.commit()
        return DurableFact(
            id=int(row["id"]),
            subject_id=sid,
            source_session_id=source_session_id,
            fact_key=fact_key,
            fact_value=value,
            category=category,
            source_turn_pk=source_turn_pk,
            source_tool=source_tool,
            idempotency_key=idempotency_key,
            confirmed_at=row["confirmed_at"],
        )

    def get_active(self, subject_id: str, fact_key: str) -> Optional[DurableFact]:
        sid = _require_subject_id(subject_id)
        if not self.enabled:
            return self._mem.get(sid, {}).get(fact_key)

        self._ensure_conn()
        row = self._conn.execute(
            """
            SELECT id, subject_id, source_session_id, fact_key, fact_value, category,
                   source_turn_pk, source_tool, idempotency_key, confirmed_at
            FROM public.durable_facts
            WHERE subject_id = %(subject_id)s
              AND fact_key = %(fact_key)s
              AND superseded_at IS NULL
            """,
            {"subject_id": sid, "fact_key": fact_key},
        ).fetchone()
        if not row:
            return None
        return _row_to_fact(row)

    def get_by_idempotency(
        self, subject_id: str, idempotency_key: str
    ) -> Optional[DurableFact]:
        sid = _require_subject_id(subject_id)
        if not self.enabled:
            return self._mem_by_idem.get((sid, idempotency_key))

        self._ensure_conn()
        row = self._conn.execute(
            """
            SELECT id, subject_id, source_session_id, fact_key, fact_value, category,
                   source_turn_pk, source_tool, idempotency_key, confirmed_at
            FROM public.durable_facts
            WHERE subject_id = %(subject_id)s
              AND idempotency_key = %(idempotency_key)s
            ORDER BY confirmed_at DESC
            LIMIT 1
            """,
            {"subject_id": sid, "idempotency_key": idempotency_key},
        ).fetchone()
        if not row:
            return None
        return _row_to_fact(row)

    def list_active(
        self, subject_id: str, *, category: Optional[str] = None
    ) -> Sequence[DurableFact]:
        sid = _require_subject_id(subject_id)
        if not self.enabled:
            facts = list(self._mem.get(sid, {}).values())
            if category:
                facts = [f for f in facts if f.category == category]
            return facts

        self._ensure_conn()
        if category:
            rows = self._conn.execute(
                """
                SELECT id, subject_id, source_session_id, fact_key, fact_value,
                       category, source_turn_pk, source_tool, idempotency_key,
                       confirmed_at
                FROM public.durable_facts
                WHERE subject_id = %(subject_id)s
                  AND category = %(category)s
                  AND superseded_at IS NULL
                ORDER BY confirmed_at
                """,
                {"subject_id": sid, "category": category},
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT id, subject_id, source_session_id, fact_key, fact_value,
                       category, source_turn_pk, source_tool, idempotency_key,
                       confirmed_at
                FROM public.durable_facts
                WHERE subject_id = %(subject_id)s
                  AND superseded_at IS NULL
                ORDER BY confirmed_at
                """,
                {"subject_id": sid},
            ).fetchall()
        return [_row_to_fact(r) for r in rows]

    def _mem_confirm(
        self,
        subject_id: str,
        fact_key: str,
        value: dict[str, Any],
        *,
        source_session_id: Optional[str],
        category: str,
        source_turn_pk: Optional[int],
        source_tool: Optional[str],
        idempotency_key: Optional[str],
        confirmed_at: datetime,
    ) -> DurableFact:
        self._next_id += 1
        fact = DurableFact(
            id=self._next_id,
            subject_id=subject_id,
            source_session_id=source_session_id,
            fact_key=fact_key,
            fact_value=value,
            category=category,
            source_turn_pk=source_turn_pk,
            source_tool=source_tool,
            idempotency_key=idempotency_key,
            confirmed_at=confirmed_at,
        )
        self._mem.setdefault(subject_id, {})[fact_key] = fact
        if idempotency_key:
            self._mem_by_idem[(subject_id, idempotency_key)] = fact
        return fact

    def _ensure_conn(self) -> None:
        if self._conn is None:
            self.connect()
        if self._conn is None:
            raise RuntimeError("durable memory connection unavailable")


def _require_subject_id(subject_id: str) -> str:
    sid = (subject_id or "").strip()
    if not sid:
        raise SubjectIdRequired("subject_id is required (trusted runtime identity)")
    return sid


def _row_to_fact(row: Mapping[str, Any]) -> DurableFact:
    value = row["fact_value"]
    if isinstance(value, str):
        value = json.loads(value)
    return DurableFact(
        id=int(row["id"]),
        subject_id=row["subject_id"],
        source_session_id=row.get("source_session_id"),
        fact_key=row["fact_key"],
        fact_value=dict(value or {}),
        category=row.get("category") or "general",
        source_turn_pk=row.get("source_turn_pk"),
        source_tool=row.get("source_tool"),
        idempotency_key=row.get("idempotency_key"),
        confirmed_at=row.get("confirmed_at"),
    )
