"""Deterministic red-flag scanning — independent of the LLM.

Intake / routing only. Never diagnoses, never recommends treatment.
Matches are keyword/phrase heuristics for escalation routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class RedFlagMatch:
    code: str
    label: str
    severity: str  # critical | high | moderate
    matched_span: str
    # Explicit non-clinical disclaimer for callers / logs.
    action: str = "route_to_human"
    diagnosis: None = None  # always None — never diagnose


@dataclass(frozen=True)
class RedFlagScanResult:
    text: str
    matches: tuple[RedFlagMatch, ...] = field(default_factory=tuple)

    @property
    def triggered(self) -> bool:
        return bool(self.matches)

    @property
    def max_severity(self) -> str:
        order = {"moderate": 1, "high": 2, "critical": 3}
        if not self.matches:
            return "none"
        return max(self.matches, key=lambda m: order.get(m.severity, 0)).severity

    def as_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "max_severity": self.max_severity,
            "matches": [
                {
                    "code": m.code,
                    "label": m.label,
                    "severity": m.severity,
                    "matched_span": m.matched_span,
                    "action": m.action,
                    "diagnosis": None,
                }
                for m in self.matches
            ],
            "disclaimer": (
                "Intake/routing signals only. Not a diagnosis. "
                "Escalate to a qualified human."
            ),
        }


# (code, label, severity, compiled pattern)
_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "suicidality",
        "suicidal ideation / self-harm language",
        "critical",
        re.compile(
            r"\b(suicid\w*|me\s+tuer|me\s+suicider|kill\s+myself|"
            r"end\s+my\s+life|je\s+veux\s+mourir|self[-\s]?harm)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "chest_pain_acute",
        "acute chest pain language",
        "critical",
        re.compile(
            r"\b(douleur\s+(dans\s+la\s+|au\s+)?poitrine|chest\s+pain|"
            r"serrage\s+(dans\s+la\s+)?poitrine|heart\s+attack|"
            r"crise\s+cardiaque|infarctus)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "breathing_difficulty",
        "severe breathing difficulty language",
        "critical",
        re.compile(
            r"\b(je\s+(ne\s+)?(peux|arrive)\s+pas\s+(à\s+|a\s+)?respirer|"
            r"can'?t\s+breathe|difficulty\s+breathing|"
            r"essoufflement\s+s[eé]v[eè]re|asphyxi\w*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stroke_signs",
        "stroke-sign language",
        "critical",
        re.compile(
            r"\b(face\s+drooping|bras\s+(qui\s+)?(tombe|pend)|"
            r"speech\s+slurr\w*|avc|stroke\s+symptoms?|"
            r"paralys\w+\s+(d['’]?un|du)\s+(c[oô]t[eé]|visage|bras))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "severe_bleeding",
        "severe bleeding language",
        "high",
        re.compile(
            r"\b(saigne\s+beaucoup|severe\s+bleeding|h[eé]morrag\w*|"
            r"bleeding\s+won'?t\s+stop|sang\s+qui\s+ne\s+s['’]?arr[eê]te\s+pas)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "overdose",
        "overdose / poisoning language",
        "critical",
        re.compile(
            r"\b(overdose|surdose|empoisonn\w*|poisoning|"
            r"took\s+too\s+many\s+pills|trop\s+de\s+(comprim[eé]s|m[eé]dicaments))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "violence_threat",
        "violence / harm-to-others language",
        "high",
        re.compile(
            r"\b(tuer\s+quelqu['’]?un|kill\s+(him|her|them|someone)|"
            r"menace\s+de\s+mort|hurt\s+someone)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "unresponsive",
        "unresponsive / loss of consciousness language",
        "critical",
        re.compile(
            r"\b(inconscient|unresponsive|passed\s+out|ne\s+r[eé]pond\s+plus|"
            r"perte\s+de\s+connaissance|collapsed)\b",
            re.IGNORECASE,
        ),
    ),
)


def scan_red_flags(text: str) -> RedFlagScanResult:
    """Scan free text for escalation signals. Never returns a diagnosis."""
    source = text or ""
    matches: list[RedFlagMatch] = []
    seen: set[str] = set()
    for code, label, severity, pattern in _PATTERNS:
        found = pattern.search(source)
        if not found or code in seen:
            continue
        seen.add(code)
        matches.append(
            RedFlagMatch(
                code=code,
                label=label,
                severity=severity,
                matched_span=found.group(0),
                action="route_to_human",
                diagnosis=None,
            )
        )
    return RedFlagScanResult(text=source, matches=tuple(matches))


def scan_many(texts: Sequence[str]) -> RedFlagScanResult:
    """Scan multiple utterances; merge unique codes (highest severity wins)."""
    order = {"moderate": 1, "high": 2, "critical": 3}
    best: dict[str, RedFlagMatch] = {}
    joined = "\n".join(t for t in texts if t)
    for text in texts:
        for match in scan_red_flags(text).matches:
            prev = best.get(match.code)
            if prev is None or order.get(match.severity, 0) > order.get(
                prev.severity, 0
            ):
                best[match.code] = match
    return RedFlagScanResult(text=joined, matches=tuple(best.values()))
