"""Allowlisted tool handlers — intake/routing/notes only, idempotent.

Contact identity (``subject_id``) and consent verification come only from
``ToolContext`` (trusted runtime). LLM tool arguments never set identity,
phone numbers, or consent-verified flags.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ..memory import DurableMemoryRepository
from .red_flags import scan_red_flags


@dataclass
class ToolContext:
    """Per-invocation context from trusted runtime (not LLM-controlled)."""

    session_id: str
    subject_id: str
    memory: DurableMemoryRepository
    turn_pk: Optional[int] = None
    user_text: str = ""
    # Runtime must set True only after an explicit, verified consent interaction.
    explicit_consent_verified: bool = False


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    name: str
    data: dict[str, Any]
    idempotent_replay: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "name": self.name,
            "data": self.data,
            "idempotent_replay": self.idempotent_replay,
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, default=str)


def _idem(arguments: Mapping[str, Any], name: str) -> str:
    """Build an idempotency key.

    Prefer an explicit client key; otherwise SHA-256 digest of stable payload
    fields so note bodies / PII are never stored in the index key.
    """
    key = arguments.get("idempotency_key") or arguments.get("id")
    if key:
        material = f"{name}:explicit:{key}"
    else:
        payload = {
            k: arguments[k]
            for k in sorted(arguments)
            if k not in ("raw", "idempotency_key", "id")
        }
        material = (
            f"{name}:payload:"
            f"{json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)}"
        )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{name}:{digest}"


def _confirm(
    ctx: ToolContext,
    *,
    fact_key: str,
    value: Mapping[str, Any],
    category: str,
    tool_name: str,
    idempotency_key: str,
) -> tuple[dict[str, Any], bool]:
    existing = ctx.memory.get_by_idempotency(ctx.subject_id, idempotency_key)
    if existing is not None:
        return {
            "fact_key": existing.fact_key,
            "fact_value": existing.fact_value,
            "fact_id": existing.id,
            "subject_id": existing.subject_id,
            "source_session_id": existing.source_session_id,
        }, True
    fact = ctx.memory.confirm_fact(
        ctx.subject_id,
        fact_key,
        value,
        source_session_id=ctx.session_id,
        category=category,
        source_turn_pk=ctx.turn_pk,
        source_tool=tool_name,
        idempotency_key=idempotency_key,
    )
    return {
        "fact_key": fact.fact_key,
        "fact_value": fact.fact_value,
        "fact_id": fact.id,
        "subject_id": fact.subject_id,
        "source_session_id": fact.source_session_id,
    }, False


def record_consent(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    granted_value = arguments.get("granted")
    if not isinstance(granted_value, bool):
        return ToolResult(
            ok=False,
            name="record_consent",
            data={"error": "granted_must_be_boolean"},
        )
    granted = granted_value
    if granted and not ctx.explicit_consent_verified:
        return ToolResult(
            ok=False,
            name="record_consent",
            data={"error": "explicit_consent_required"},
        )
    scope = str(arguments.get("scope") or "voice_session")
    idem = _idem(arguments, "record_consent")
    data, replay = _confirm(
        ctx,
        fact_key=f"consent:{scope}",
        value={"granted": granted, "scope": scope},
        category="consent",
        tool_name="record_consent",
        idempotency_key=idem,
    )
    return ToolResult(ok=True, name="record_consent", data=data, idempotent_replay=replay)


def save_call_note(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    """Store a structured call note (intake/routing only — not clinical charting)."""
    note_type = str(arguments.get("note_type") or "general")
    body = str(arguments.get("body") or arguments.get("note") or "").strip()
    tags = arguments.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    if not body:
        return ToolResult(
            ok=False,
            name="save_call_note",
            data={"error": "body_required"},
        )
    idem = _idem(arguments, "save_call_note")
    data, replay = _confirm(
        ctx,
        fact_key=f"note:{idem}",
        value={
            "note_type": note_type,
            "body": body,
            "tags": tags,
            "kind": "structured_note",
        },
        category="note",
        tool_name="save_call_note",
        idempotency_key=idem,
    )
    return ToolResult(ok=True, name="save_call_note", data=data, idempotent_replay=replay)


def record_reminder_outcome(
    ctx: ToolContext, arguments: Mapping[str, Any]
) -> ToolResult:
    reminder_id = str(arguments.get("reminder_id") or "unknown")
    outcome = str(arguments.get("outcome") or "unknown")
    idem = _idem(arguments, "record_reminder_outcome")
    data, replay = _confirm(
        ctx,
        fact_key=f"reminder_outcome:{reminder_id}",
        value={"reminder_id": reminder_id, "outcome": outcome},
        category="reminder",
        tool_name="record_reminder_outcome",
        idempotency_key=idem,
    )
    return ToolResult(
        ok=True, name="record_reminder_outcome", data=data, idempotent_replay=replay
    )


def capture_followup(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    summary = str(arguments.get("summary") or "").strip()
    when = arguments.get("when")
    channel = str(arguments.get("channel") or "callback")
    if not summary:
        return ToolResult(
            ok=False, name="capture_followup", data={"error": "summary_required"}
        )
    idem = _idem(arguments, "capture_followup")
    data, replay = _confirm(
        ctx,
        fact_key=f"followup:{idem}",
        value={"summary": summary, "when": when, "channel": channel},
        category="followup",
        tool_name="capture_followup",
        idempotency_key=idem,
    )
    return ToolResult(
        ok=True, name="capture_followup", data=data, idempotent_replay=replay
    )


def capture_triage_intake(
    ctx: ToolContext, arguments: Mapping[str, Any]
) -> ToolResult:
    """Capture structured triage *intake* fields for routing — never diagnoses."""
    chief_concern = str(
        arguments.get("chief_concern") or arguments.get("concern") or ""
    ).strip()
    urgency_self = arguments.get("urgency_self")
    symptoms = arguments.get("symptoms") or []
    if not isinstance(symptoms, list):
        symptoms = [str(symptoms)]
    if not chief_concern:
        return ToolResult(
            ok=False,
            name="capture_triage_intake",
            data={"error": "chief_concern_required"},
        )
    idem = _idem(arguments, "capture_triage_intake")
    data, replay = _confirm(
        ctx,
        fact_key="triage_intake",
        value={
            "chief_concern": chief_concern,
            "urgency_self": urgency_self,
            "symptoms": symptoms,
            "scope": "intake_routing_only",
            "diagnosis": None,
        },
        category="triage_intake",
        tool_name="capture_triage_intake",
        idempotency_key=idem,
    )
    data["disclaimer"] = "Intake/routing only. Not a diagnosis."
    return ToolResult(
        ok=True, name="capture_triage_intake", data=data, idempotent_replay=replay
    )


def detect_red_flags(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    """Run deterministic red-flag scan (also invokable as a tool by the LLM)."""
    text = str(arguments.get("text") or ctx.user_text or "")
    result = scan_red_flags(text)
    payload = result.as_dict()
    idem = _idem({"text": text, **dict(arguments)}, "detect_red_flags")
    if result.triggered:
        stored, replay = _confirm(
            ctx,
            fact_key="red_flags_last",
            value=payload,
            category="safety",
            tool_name="detect_red_flags",
            idempotency_key=idem,
        )
        payload["stored"] = stored
        return ToolResult(
            ok=True,
            name="detect_red_flags",
            data=payload,
            idempotent_replay=replay,
        )
    return ToolResult(ok=True, name="detect_red_flags", data=payload)


def schedule_callback(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    """Request a callback; outbound number comes from trusted contact records."""
    when = arguments.get("when")
    reason = str(arguments.get("reason") or "follow_up").strip()
    if not when:
        return ToolResult(
            ok=False, name="schedule_callback", data={"error": "when_required"}
        )
    idem = _idem(arguments, "schedule_callback")
    data, replay = _confirm(
        ctx,
        fact_key=f"callback:{idem}",
        value={
            "when": when,
            "reason": reason,
            "subject_id": ctx.subject_id,
            "status": "requested",
        },
        category="callback",
        tool_name="schedule_callback",
        idempotency_key=idem,
    )
    return ToolResult(
        ok=True, name="schedule_callback", data=data, idempotent_replay=replay
    )


def opt_out(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    channels = arguments.get("channels") or ["voice"]
    if not isinstance(channels, list):
        channels = [str(channels)]
    reason = arguments.get("reason")
    idem = _idem(arguments, "opt_out")
    data, replay = _confirm(
        ctx,
        fact_key="opt_out",
        value={"channels": channels, "reason": reason, "active": True},
        category="consent",
        tool_name="opt_out",
        idempotency_key=idem,
    )
    data["should_end"] = True
    return ToolResult(ok=True, name="opt_out", data=data, idempotent_replay=replay)


def end_call(ctx: ToolContext, arguments: Mapping[str, Any]) -> ToolResult:
    reason = str(arguments.get("reason") or "user_request")
    summary = str(arguments.get("summary") or "").strip()
    idem = _idem(arguments, "end_call")
    data, replay = _confirm(
        ctx,
        fact_key="call_end",
        value={"reason": reason, "summary": summary, "ended": True},
        category="session",
        tool_name="end_call",
        idempotency_key=idem,
    )
    data["should_end"] = True
    return ToolResult(ok=True, name="end_call", data=data, idempotent_replay=replay)


HANDLERS = {
    "record_consent": record_consent,
    "save_call_note": save_call_note,
    "record_reminder_outcome": record_reminder_outcome,
    "capture_followup": capture_followup,
    "capture_triage_intake": capture_triage_intake,
    "detect_red_flags": detect_red_flags,
    "schedule_callback": schedule_callback,
    "opt_out": opt_out,
    "end_call": end_call,
}
