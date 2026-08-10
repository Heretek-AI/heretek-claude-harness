"""Issue-to-path classifier.

Pure function: takes an IssueRef + body and returns one of five paths:
fix, investigate, spec, break-down, skip. Heuristic-based, no LLM.
"""

from __future__ import annotations

import re
from typing import Literal

from .ledger import IssueRef

Path = Literal["fix", "investigate", "spec", "break-down", "skip"]

_FILE_LINE_RE = re.compile(r"`?[\w./\-]+\.[A-Za-z]+:\d+`?")
_FIX_KEYWORDS = re.compile(
    r"\b(fix|patch|replace|use\s+\w+\s+instead)\b", re.IGNORECASE
)
_SPEC_KEYWORDS = re.compile(
    r"\b(research|audit|design|plugin|skill|system)\b", re.IGNORECASE
)
_BREAKDOWN_KEYWORDS = re.compile(
    r"\b(split|decompose|sub-?tasks?|phase)\b", re.IGNORECASE
)
_SKIP_KEYWORDS = re.compile(
    r"\b(duplicate|won'?t\s+fix|by\s+design|not\s+applicable)\b", re.IGNORECASE
)


def classify(issue: IssueRef, body: str = "") -> Path:
    """Heuristic route from issue to a processing path."""
    text = f"{issue.title} {body}".lower()
    has_anchor = bool(_FILE_LINE_RE.search(issue.title)) or bool(
        _FILE_LINE_RE.search(body)
    )

    if _SKIP_KEYWORDS.search(text):
        return "skip"
    if has_anchor and _FIX_KEYWORDS.search(text):
        return "fix"
    if _SPEC_KEYWORDS.search(text) and not has_anchor:
        return "spec"
    if _BREAKDOWN_KEYWORDS.search(text):
        return "break-down"
    return "investigate"
