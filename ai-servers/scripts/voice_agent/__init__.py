"""Voice agent core (P0/P1) — dependency-light, Pipecat-ready.

Exact per-call event log (``sessions``/``turns``/``tool_calls``/``tts_segments``)
is kept separate from subject-scoped durable memory (``durable_facts``). Contact
identity (``subject_id``) comes from trusted runtime context, never LLM args.

Healthcare scope: intake / routing / structured notes only — never diagnose.
"""

from __future__ import annotations

from .config import VoiceConfig, load_config
from .events import EventStore
from .memory import DurableMemoryRepository
from .tools.registry import ToolRegistry, build_default_registry

__all__ = [
    "VoiceConfig",
    "load_config",
    "EventStore",
    "DurableMemoryRepository",
    "ToolRegistry",
    "build_default_registry",
]

__version__ = "0.1.0"
