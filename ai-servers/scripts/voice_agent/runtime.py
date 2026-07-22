"""Per-call runtime joining exact events, derived memory, tools, and safety.

The runtime deliberately keeps two storage contracts separate:

* :class:`EventStore` records the exact per-call trace.
* :class:`DurableMemoryRepository` stores confirmed, subject-scoped facts.

The contact identity and consent-verification flag are trusted inputs supplied
by the caller adapter. They are never accepted from LLM tool arguments.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from .config import VoiceConfig
from .events import EventStore, SessionHandle, TurnHandle
from .memory import DurableFact, DurableMemoryRepository
from .tools.handlers import ToolContext, ToolResult
from .tools.red_flags import RedFlagScanResult
from .tools.registry import ToolRegistry, build_default_registry


@dataclass
class VoiceRuntime:
    """State and persistence for one WebRTC or telephony call."""

    config: VoiceConfig
    subject_id: str
    session_id: str
    explicit_consent_verified: bool = False
    require_consent: bool = False
    consent_scope: str = "voice_session"
    channel: str = "webrtc"
    barge_in: bool = False
    end_requested: bool = field(default=False, init=False)
    store: EventStore = field(default_factory=EventStore)
    memory: DurableMemoryRepository = field(default_factory=DurableMemoryRepository)
    registry: ToolRegistry = field(default_factory=build_default_registry)
    _session: Optional[SessionHandle] = field(default=None, init=False, repr=False)
    _turn: Optional[TurnHandle] = field(default=None, init=False, repr=False)
    _turn_started_monotonic: float = field(default=0.0, init=False, repr=False)
    _turn_index: int = field(default=0, init=False, repr=False)
    _tool_count: int = field(default=0, init=False, repr=False)
    _tts_count: int = field(default=0, init=False, repr=False)
    _answer_parts: list[str] = field(default_factory=list, init=False, repr=False)
    _user_text: str = field(default="", init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    @classmethod
    def create(
        cls,
        config: VoiceConfig,
        *,
        subject_id: str,
        session_id: str,
        explicit_consent_verified: bool = False,
        require_consent: bool = False,
        consent_scope: str = "voice_session",
        channel: str = "webrtc",
        barge_in: bool = False,
    ) -> "VoiceRuntime":
        """Construct a runtime without opening database connections."""
        trusted_subject = subject_id.strip()
        if not trusted_subject:
            raise ValueError("trusted subject_id is required")
        trusted_session = session_id.strip()
        if not trusted_session:
            raise ValueError("session_id is required")
        store = EventStore.from_config(config)
        memory = DurableMemoryRepository.from_config(config)
        return cls(
            config=config,
            subject_id=trusted_subject,
            session_id=trusted_session,
            explicit_consent_verified=explicit_consent_verified,
            require_consent=require_consent,
            consent_scope=consent_scope,
            channel=channel,
            barge_in=barge_in,
            store=store,
            memory=memory,
        )

    @property
    def session(self) -> Optional[SessionHandle]:
        return self._session

    @property
    def current_turn(self) -> Optional[TurnHandle]:
        return self._turn

    def start(self) -> SessionHandle:
        """Open stores and create the exact session record."""
        with self._lock:
            self.store.connect()
            self.memory.connect()
            if self.channel.startswith("telephony"):
                opt_out = self.memory.get_active(self.subject_id, "opt_out")
                if opt_out and opt_out.fact_value.get("active"):
                    raise PermissionError(
                        f"outbound contact blocked by active opt-out for {self.subject_id}"
                    )
            self._session = self.store.start_session(
                self.session_id,
                host=os.uname().nodename,
                pid=os.getpid(),
                tools_enabled=True,
                config={
                    "channel": self.channel,
                    "subject_id": self.subject_id,
                    "db_enabled": self.store.is_enabled,
                    "llm_model": self.config.llm_model,
                    "tts_model": self.config.tts_model,
                    "require_consent": self.require_consent,
                },
                agent_route=True,
                allow_send=False,
                barge_in=self.barge_in,
            )
            return self._session

    def close(self, *, stopped_reason: str = "session_closed") -> None:
        """Finish any open turn and close both database connections."""
        with self._lock:
            self.finish_turn(stopped_reason=stopped_reason)
            self.memory.close()
            self.store.close()

    def start_user_turn(
        self,
        transcript: str,
        *,
        raw: Optional[Mapping[str, Any]] = None,
    ) -> RedFlagScanResult:
        """Start an exact turn and run deterministic safety scanning."""
        text = transcript.strip()
        if not text:
            raise ValueError("non-empty transcript is required")
        with self._lock:
            if self._session is None:
                self.start()
            if self._turn is not None:
                self.finish_turn(stopped_reason="interrupted_by_user")

            self._turn_index += 1
            self._tool_count = 0
            self._tts_count = 0
            self._answer_parts = []
            self._user_text = text
            self._turn_started_monotonic = time.monotonic()
            assert self._session is not None
            consent_decision = self._observe_consent(text)
            stored_transcript = text
            if self.require_consent and not self.explicit_consent_verified:
                stored_transcript = "[consent response withheld]"
            self._turn = self.store.start_turn(
                self._session,
                self._turn_index,
                user_transcript=stored_transcript,
                route=self.channel,
                input_format="pcm_s16le",
                input_sample_rate=16000,
                raw=raw,
            )

            if consent_decision is not None:
                self.invoke_tool(
                    "record_consent",
                    {
                        "granted": consent_decision,
                        "scope": self.consent_scope,
                        "idempotency_key": (
                            f"consent:{self.session_id}:{self._turn_index}"
                        ),
                    },
                )
                if not consent_decision:
                    self.end_requested = True

            safety = self.registry.scan_red_flags_independent(text)
            if safety.triggered:
                self.invoke_tool(
                    "detect_red_flags",
                    {
                        "text": text,
                        "idempotency_key": (
                            f"safety:{self.session_id}:{self._turn_index}"
                        ),
                    },
                )
            return safety

    def invoke_tool(
        self, name: str, arguments: Mapping[str, Any] | str | None
    ) -> ToolResult:
        """Invoke one allowlisted tool and record its exact input/output."""
        with self._lock:
            if self._turn is None:
                raise RuntimeError("tool call requires an active turn")
            ordinal = self._tool_count
            self._tool_count += 1
            self.store.record_tool_call(
                self._turn,
                ordinal,
                name,
                arguments,
                {"status": "started"},
            )
            ctx = ToolContext(
                session_id=self.session_id,
                subject_id=self.subject_id,
                memory=self.memory,
                turn_pk=self._turn.turn_pk,
                user_text=self._user_text,
                explicit_consent_verified=self.explicit_consent_verified,
            )
            try:
                result = self.registry.invoke(name, arguments, ctx)
            except Exception as exc:
                self.store.record_tool_call(
                    self._turn,
                    ordinal,
                    name,
                    arguments,
                    {"status": "failed", "error": str(exc)},
                )
                raise

            action_type = self._action_type(name, result)
            if action_type:
                outbox_id = self.store.enqueue_action(
                    event_type=action_type,
                    subject_id=self.subject_id,
                    session_id=self.session_id,
                    turn_pk=self._turn.turn_pk,
                    idempotency_key=(
                        f"{self.session_id}:{self._turn.turn_index}:{ordinal}"
                    ),
                    payload=result.as_dict(),
                )
                result.data["outbox_id"] = outbox_id
            if result.data.get("should_end") or action_type == "urgent_human_review":
                self.end_requested = True

            self.store.record_tool_call(
                self._turn,
                ordinal,
                name,
                arguments,
                result.as_dict(),
            )
            return result

    def record_tts(
        self,
        text: str,
        audio_bytes: bytes,
        *,
        sample_rate: int,
        synth_seconds: Optional[float] = None,
        audio_seconds: Optional[float] = None,
        ttfa_seconds: Optional[float] = None,
    ) -> None:
        """Record a synthesized segment and accumulate the spoken answer."""
        spoken = text.strip()
        if not spoken:
            return
        with self._lock:
            if self._turn is None:
                return
            self.store.record_tts_segment(
                self._turn,
                self._tts_count,
                spoken,
                audio_bytes=audio_bytes if self.config.store_tts_audio else None,
                sample_rate=sample_rate,
                char_count=len(spoken),
                synth_seconds=synth_seconds,
                audio_seconds=audio_seconds,
                ttfa_seconds=ttfa_seconds,
                rtf=(
                    synth_seconds / audio_seconds
                    if synth_seconds is not None and audio_seconds
                    else None
                ),
            )
            self._tts_count += 1
            self._answer_parts.append(spoken)

    def finish_turn(
        self,
        *,
        stopped_reason: str = "completed",
        error: Optional[str] = None,
    ) -> None:
        """Finalize the current exact turn, if any."""
        with self._lock:
            if self._turn is None:
                return
            elapsed = (
                time.monotonic() - self._turn_started_monotonic
                if self._turn_started_monotonic
                else None
            )
            self.store.finish_turn(
                self._turn,
                answer_text=" ".join(self._answer_parts).strip() or None,
                stopped_reason=stopped_reason,
                error=error,
                n_tool_calls=self._tool_count,
                n_tts_segments=self._tts_count,
                turn_wall_seconds=elapsed,
                raw={"subject_id": self.subject_id, "channel": self.channel},
            )
            self._turn = None
            self._turn_started_monotonic = 0.0
            self._user_text = ""
            self._answer_parts = []

    def active_facts(
        self, *, categories: Optional[Sequence[str]] = None
    ) -> Sequence[DurableFact]:
        """Return active confirmed facts for this trusted subject."""
        facts = list(self.memory.list_active(self.subject_id))
        if categories is None:
            return facts
        allowed = set(categories)
        return [fact for fact in facts if fact.category in allowed]

    def memory_context(self, *, max_chars: int = 3000) -> str:
        """Render confirmed memory as bounded, always-valid JSON."""
        facts = self.active_facts()
        payload: list[dict[str, Any]] = []
        for fact in facts:
            candidate = {
                "key": fact.fact_key,
                "category": fact.category,
                "value": fact.fact_value,
                "confirmed_at": (
                    fact.confirmed_at.isoformat() if fact.confirmed_at else None
                ),
            }
            encoded = json.dumps(
                [*payload, candidate], ensure_ascii=False, default=str
            )
            if len(encoded) > max_chars:
                break
            payload.append(candidate)
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _observe_consent(self, text: str) -> Optional[bool]:
        """Recognize only a narrow explicit response when consent is required."""
        if not self.require_consent or self.explicit_consent_verified:
            return None
        normalized = re.sub(r"[^\wàâçéèêëîïôûùüÿœ'’ -]", "", text.lower()).strip()
        affirmative = (
            r"^(oui|oui j['’]accepte|j['’]accepte|"
            r"oui je consens|je consens|vous avez mon consentement)$"
        )
        negative = (
            r"^(non|non merci|je refuse|je ne consens pas|"
            r"je n['’]accepte pas|arrêtez l['’]appel|arretez l['’]appel)$"
        )
        if re.fullmatch(affirmative, normalized):
            self.explicit_consent_verified = True
            return True
        if re.fullmatch(negative, normalized):
            return False
        return None

    @staticmethod
    def _action_type(name: str, result: ToolResult) -> Optional[str]:
        if not result.ok:
            return None
        if name == "detect_red_flags" and result.data.get("triggered"):
            return "urgent_human_review"
        return {
            "schedule_callback": "callback_requested",
            "opt_out": "contact_opt_out",
            "end_call": "call_end_requested",
        }.get(name)
