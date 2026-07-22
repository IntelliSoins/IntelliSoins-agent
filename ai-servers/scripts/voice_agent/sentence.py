"""Sentence chunking for streaming TTS (shared with Pipecat wrappers later)."""

from __future__ import annotations

import re

_SENTENCE_RE = re.compile(r"[^.!?…]+[.!?…]+[\"»”']?\s*")
_MD_CLEAN_RE = (
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"\*([^*]+)\*"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"^#+\s*", re.MULTILINE), ""),
    (re.compile(r"^[\-\*•]\s+", re.MULTILINE), ""),
    (re.compile(r"^\d+\.\s+", re.MULTILINE), ""),
    (re.compile(r"[#*`_]+"), ""),
    (re.compile(r"\s+"), " "),
)


def for_tts(text: str) -> str:
    """Strip markdown / list markers so TTS gets plain oral text."""
    t = (text or "").strip()
    for pattern, repl in _MD_CLEAN_RE:
        t = pattern.sub(repl, t)
    return t.strip()


def pop_sentences(
    buffer: str, *, first_done: bool, min_chars: int = 90
) -> tuple[list[str], str]:
    """Extract complete sentences from a streaming buffer.

    The first sentence is emitted as soon as a terminator appears; later
    sentences are merged until ``min_chars`` to reduce TTS round-trips.
    """
    sentences: list[str] = []
    pos = 0
    for match in _SENTENCE_RE.finditer(buffer):
        if match.start() != pos:
            break
        candidate = match.group(0).strip()
        if not first_done or len(candidate) >= min_chars or not sentences:
            sentences.append(candidate)
        else:
            sentences[-1] = f"{sentences[-1]} {candidate}"
        pos = match.end()
        first_done = True
    return sentences, buffer[pos:]


def flush_remainder(buffer: str) -> list[str]:
    """Emit any trailing non-terminated text as a final chunk."""
    rest = (buffer or "").strip()
    return [rest] if rest else []
