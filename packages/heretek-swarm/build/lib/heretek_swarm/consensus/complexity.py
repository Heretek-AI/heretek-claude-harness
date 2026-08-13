"""
Complexity heuristic for automatic consensus routing.

Determines whether a question needs MAKER consensus (complex, multi-faceted)
vs simple triad deliberation.  Pure keyword + length scoring — no LLM calls,
deterministic, <1ms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

logger = logging.getLogger("complexity_heuristic")

# ── Keyword banks ──────────────────────────────────────────────────────
# Each entry maps to a category label used in the explanation string.

_TRADEOFF_KEYWORDS: list[tuple[str, str]] = [
    ("tradeoff", "tradeoff"),
    ("trade-off", "tradeoff"),
    ("trade off", "tradeoff"),
    ("pros and cons", "pros/cons"),
    ("pros vs cons", "pros/cons"),
    ("pros vs", "pros/cons"),
    ("advantages and disadvantages", "pros/cons"),
    ("costs and benefits", "cost/benefit"),
    ("cost benefit", "cost/benefit"),
    ("benefits and risks", "risk/benefit"),
]

_ANALYSIS_KEYWORDS: list[tuple[str, str]] = [
    ("compare", "comparison"),
    ("comparison", "comparison"),
    ("versus", "comparison"),
    (" vs ", "comparison"),
    ("evaluate", "evaluation"),
    ("evaluation", "evaluation"),
    ("assess", "evaluation"),
    ("assessment", "evaluation"),
    ("analyze", "analysis"),
    ("analyse", "analysis"),
    ("analysis", "analysis"),
    ("should we", "decision"),
    ("should i", "decision"),
    ("should the", "decision"),
    ("is it worth", "decision"),
    ("do we need", "decision"),
    ("weigh", "weighing"),
    ("weighing", "weighing"),
    ("consider", "consideration"),
    ("consideration", "consideration"),
    ("implications", "implications"),
    ("consequences", "consequences"),
    ("impact of", "impact"),
    ("impact on", "impact"),
    ("risk", "risk"),
    ("risks", "risk"),
    ("downside", "risk"),
    ("upside", "risk"),
]


@dataclass
class ComplexityResult:
    """Result of a complexity assessment."""

    score: float  # 0.0 – 1.0  # noqa: RUF003
    is_complex: bool  # True ⇒ route to MAKER consensus
    matched_keywords: list[str] = field(default_factory=list)
    length_trigger: bool = False
    keyword_trigger: bool = False

    @property
    def routing_mode(self) -> str:
        """Human-readable routing label: 'consensus' or 'triad'."""
        return "consensus" if self.is_complex else "triad"

    def explanation(self) -> str:
        """One-line explanation suitable for structured logging."""
        parts: list[str] = []
        if self.keyword_trigger:
            cats = sorted(set(self.matched_keywords))
            parts.append(f"keywords={','.join(cats)}")
        if self.length_trigger:
            parts.append("long_question")
        detail = " ".join(parts) if parts else "simple"
        return f"complexity={self.score:.2f} mode={self.routing_mode} {detail}"


class ComplexityHeuristic:
    """Determines whether a question needs MAKER consensus routing.

    Scoring rules (additive):
      • +0.4 if question length > ``length_threshold`` characters
      • +0.5 per matched keyword category (capped at 3 categories → +0.9)
      • Score is clamped to [0.0, 1.0]
      • ``is_complex`` is True when score >= ``complex_threshold``

    Defaults (threshold=0.5) mean:
      • A single analysis keyword (0.5) is enough to trigger consensus
      • Length alone (0.4) is NOT enough → needs ≥1 keyword
      • 2+ keyword categories (1.0, capped at 0.9) always trigger
    """

    def __init__(
        self,
        length_threshold: int = 50,
        complex_threshold: float = 0.5,
        length_weight: float = 0.4,
        keyword_weight: float = 0.5,
        max_keyword_score: float = 0.9,
    ) -> None:
        self.length_threshold = length_threshold
        self.complex_threshold = complex_threshold
        self.length_weight = length_weight
        self.keyword_weight = keyword_weight
        self.max_keyword_score = max_keyword_score

    # ── Public API ─────────────────────────────────────────────────────

    def assess(self, question: str) -> ComplexityResult:
        """Score *question* and return a :class:`ComplexityResult`."""
        normalized = question.lower().strip()

        # Length component
        length_trigger = len(normalized) > self.length_threshold

        # Keyword component — collect unique category labels
        matched_categories: set[str] = set()

        for keyword, category in _TRADEOFF_KEYWORDS:
            if keyword in normalized:
                matched_categories.add(category)
        for keyword, category in _ANALYSIS_KEYWORDS:
            if keyword in normalized:
                matched_categories.add(category)

        keyword_trigger = len(matched_categories) > 0

        # Compute score
        score = 0.0
        if length_trigger:
            score += self.length_weight
        keyword_score = min(
            len(matched_categories) * self.keyword_weight,
            self.max_keyword_score,
        )
        score += keyword_score
        score = min(score, 1.0)

        is_complex = score >= self.complex_threshold

        result = ComplexityResult(
            score=round(score, 4),
            is_complex=is_complex,
            matched_keywords=sorted(matched_categories),
            length_trigger=length_trigger,
            keyword_trigger=keyword_trigger,
        )

        logger.info("Complexity assessment: %s", result.explanation())
        return result

    def is_complex(self, question: str) -> bool:
        """Convenience: returns True when question needs MAKER consensus."""
        return self.assess(question).is_complex

    def score(self, question: str) -> float:
        """Convenience: returns raw complexity score 0.0–1.0."""  # noqa: RUF002
        return self.assess(question).score
