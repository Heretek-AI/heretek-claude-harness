"""Structured tribunal verdict aggregation.

Replaces the fragile string-keyword matching in
``runtime/steward_pulse._convene_tribunal_on_anomaly`` (formerly
``steward_pulse.py:419-428``) with a Pydantic-validated structured
output. The LLM is asked to emit JSON; if the JSON parses and
matches the schema, it is used with high confidence. If parsing
fails, the legacy keyword fallback fires with low confidence so
the swarm's behavior degrades gracefully (does not break).

This is the G-02 fix from PLAN.md.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

VerdictLabel = Literal["emergent", "threat", "inconclusive"]


class RulingVerdict(BaseModel):
    verdict: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""


_THREAT_KEYWORDS = ("threat", "danger", "malicious", "attack", "block", "critical")
_EMERGENT_KEYWORDS = ("emergent", "beneficial", "breakthrough", "novel", "innovative")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_candidate(text: str) -> str | None:
    """Return the first balanced JSON object in ``text``, or None."""
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = _JSON_FENCE_RE.search(stripped)
    if match:
        return match.group(1)
    start = stripped.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(stripped)):
            if stripped[end] == "{":
                depth += 1
            elif stripped[end] == "}":
                depth -= 1
                if depth == 0:
                    return stripped[start : end + 1]
        start = stripped.find("{", start + 1)
    return None


def parse_agent_verdict(output: str) -> RulingVerdict | None:
    candidate = _extract_json_candidate(output or "")
    if candidate is None:
        return None
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return RulingVerdict.model_validate(data)
    except Exception:
        return None


def keyword_fallback_verdict(output: str) -> RulingVerdict:
    text = (output or "").lower()
    is_threat = any(k in text for k in _THREAT_KEYWORDS)
    is_emergent = any(k in text for k in _EMERGENT_KEYWORDS)
    if is_emergent and not is_threat:
        return RulingVerdict(verdict="emergent", confidence=0.5, reasoning="keyword fallback: emergent")
    if is_threat:
        return RulingVerdict(verdict="threat", confidence=0.5, reasoning="keyword fallback: threat")
    return RulingVerdict(verdict="inconclusive", confidence=0.5, reasoning="keyword fallback: no match")


def aggregate_triad_ruling(alpha: str, beta: str, charlie: str) -> RulingVerdict:
    verdicts: list[RulingVerdict] = []
    for output in (alpha, beta, charlie):
        parsed = parse_agent_verdict(output)
        verdicts.append(parsed if parsed is not None else keyword_fallback_verdict(output))

    counts: dict[str, list[float]] = {"emergent": [], "threat": [], "inconclusive": []}
    for v in verdicts:
        counts[v.verdict].append(v.confidence)

    def _score(label: str) -> tuple[float, int]:
        bucket = counts[label]
        if not bucket:
            return (0.0, 0)
        return (sum(bucket) / len(bucket), len(bucket))

    best = max(counts.keys(), key=_score)
    mean_confidence = sum(counts[best]) / max(len(counts[best]), 1)
    reasoning = (
        f"aggregated from {len(verdicts)} verdicts: "
        f"emergent={len(counts['emergent'])}, "
        f"threat={len(counts['threat'])}, "
        f"inconclusive={len(counts['inconclusive'])}"
    )
    return RulingVerdict(verdict=best, confidence=mean_confidence, reasoning=reasoning)
