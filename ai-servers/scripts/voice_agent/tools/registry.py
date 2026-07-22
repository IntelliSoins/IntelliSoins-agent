"""Allowlisted, idempotent tool registry for the voice-agent core."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from . import handlers
from .handlers import ToolContext, ToolResult
from .red_flags import RedFlagScanResult, scan_red_flags

ToolHandler = Callable[[ToolContext, Mapping[str, Any]], ToolResult]


# OpenAI-style tool schemas (intake/routing only — no diagnostic verbs).
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "record_consent": {
        "type": "function",
        "function": {
            "name": "record_consent",
            "description": "Record user consent for this voice session (scope-limited).",
            "parameters": {
                "type": "object",
                "properties": {
                    "granted": {"type": "boolean"},
                    "scope": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["granted"],
            },
        },
    },
    "save_call_note": {
        "type": "function",
        "function": {
            "name": "save_call_note",
            "description": (
                "Save a structured call note for intake/routing. "
                "Not a clinical chart entry; never diagnose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "body": {"type": "string"},
                    "note_type": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["body"],
            },
        },
    },
    "record_reminder_outcome": {
        "type": "function",
        "function": {
            "name": "record_reminder_outcome",
            "description": "Record the outcome of a reminder interaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string"},
                    "outcome": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["reminder_id", "outcome"],
            },
        },
    },
    "capture_followup": {
        "type": "function",
        "function": {
            "name": "capture_followup",
            "description": "Capture a follow-up action item (non-clinical).",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "when": {"type": "string"},
                    "channel": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["summary"],
            },
        },
    },
    "capture_triage_intake": {
        "type": "function",
        "function": {
            "name": "capture_triage_intake",
            "description": (
                "Capture structured triage intake fields for routing only. "
                "Never diagnose or recommend treatment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chief_concern": {"type": "string"},
                    "urgency_self": {"type": "string"},
                    "symptoms": {"type": "array", "items": {"type": "string"}},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["chief_concern"],
            },
        },
    },
    "detect_red_flags": {
        "type": "function",
        "function": {
            "name": "detect_red_flags",
            "description": (
                "Run deterministic red-flag scan on text for escalation routing. "
                "Does not diagnose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
            },
        },
    },
    "schedule_callback": {
        "type": "function",
        "function": {
            "name": "schedule_callback",
            "description": (
                "Request a callback slot (routing only). "
                "Outbound number is resolved from trusted contact records, "
                "not from tool arguments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "when": {"type": "string"},
                    "reason": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["when"],
            },
        },
    },
    "opt_out": {
        "type": "function",
        "function": {
            "name": "opt_out",
            "description": "Record an opt-out from one or more contact channels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channels": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
            },
        },
    },
    "end_call": {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "End the current voice call cleanly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "summary": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
            },
        },
    },
}


@dataclass
class ToolRegistry:
    """Hard allowlist — unknown tool names are rejected."""

    handlers: dict[str, ToolHandler] = field(default_factory=dict)
    schemas: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register(
        self,
        name: str,
        handler: ToolHandler,
        schema: Optional[dict[str, Any]] = None,
    ) -> None:
        if name in self.handlers:
            raise ValueError(f"tool already registered: {name}")
        self.handlers[name] = handler
        if schema is not None:
            self.schemas[name] = schema
        elif name in TOOL_SCHEMAS:
            self.schemas[name] = TOOL_SCHEMAS[name]

    def allowlisted(self) -> frozenset[str]:
        return frozenset(self.handlers)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [self.schemas[n] for n in sorted(self.schemas) if n in self.handlers]

    def invoke(
        self,
        name: str,
        arguments: Mapping[str, Any] | str | None,
        ctx: ToolContext,
    ) -> ToolResult:
        if name not in self.handlers:
            return ToolResult(
                ok=False,
                name=name,
                data={"error": "tool_not_allowlisted", "tool": name},
            )
        args = _strip_untrusted_identity(_parse_arguments(arguments))
        return self.handlers[name](ctx, args)

    def invoke_openai_tool_call(
        self, tool_call: Mapping[str, Any], ctx: ToolContext
    ) -> ToolResult:
        fn = tool_call.get("function") or {}
        name = fn.get("name") or tool_call.get("name") or ""
        arguments = fn.get("arguments") or tool_call.get("arguments") or {}
        return self.invoke(str(name), arguments, ctx)

    def scan_red_flags_independent(self, text: str) -> RedFlagScanResult:
        """Deterministic safety scan — does not go through the LLM."""
        return scan_red_flags(text)


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name, handler in handlers.HANDLERS.items():
        registry.register(name, handler, TOOL_SCHEMAS.get(name))
    return registry


# Never accepted from the model — identity, numbers, and consent gates are
# supplied only via trusted ToolContext / contact records.
_UNTRUSTED_ARG_KEYS = frozenset(
    {
        "subject_id",
        "contact_id",
        "session_id",
        "phone",
        "phone_number",
        "outbound_number",
        "explicit_consent_verified",
    }
)


def _parse_arguments(
    arguments: Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        text = arguments.strip()
        if not text:
            return {}
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
        return dict(loaded) if isinstance(loaded, dict) else {"value": loaded}
    return dict(arguments)


def _strip_untrusted_identity(arguments: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in arguments.items() if k not in _UNTRUSTED_ARG_KEYS}
