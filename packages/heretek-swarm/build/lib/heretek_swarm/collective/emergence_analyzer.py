"""Analyzer for emergent patterns and collective behaviors."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from .emergent_detection import EmergentPatternDetector

logger = structlog.get_logger(__name__)


class EmergenceAnalyzer:
    """Analyzer for emergent patterns and collective behaviors."""

    def __init__(self, detector: EmergentPatternDetector):
        self.detector = detector
        logger.info("emergence_analyzer_initialized")

    def analyze_emergence_trends(self) -> dict[str, Any]:
        patterns = self.detector._emergent_patterns  # noqa: SLF001

        if len(patterns) < 5:
            return {"trend": "insufficient_data"}

        mid = len(patterns) // 2
        early = patterns[:mid]
        recent = patterns[mid:]

        early_avg = sum(p.emergence_score for p in early) / len(early)
        recent_avg = sum(p.emergence_score for p in recent) / len(recent)

        trend = "increasing" if recent_avg > early_avg else "decreasing"
        change = abs(recent_avg - early_avg)

        return {
            "trend": trend,
            "early_avg_score": early_avg,
            "recent_avg_score": recent_avg,
            "change": change,
            "early_count": len(early),
            "recent_count": len(recent),
        }

    def identify_key_contributors(self) -> list[dict[str, Any]]:
        agent_contributions: dict[str, int] = defaultdict(int)

        for pattern in self.detector._emergent_patterns:  # noqa: SLF001
            for agent_id in pattern.participating_agents:
                agent_contributions[agent_id] += 1

        contributors = [
            {"agent_id": aid, "contribution_count": count}
            for aid, count in sorted(agent_contributions.items(), key=lambda x: x[1], reverse=True)
        ]

        return contributors[:10]

    def analyze_pattern_correlations(self) -> dict[str, Any]:
        patterns = self.detector._emergent_patterns  # noqa: SLF001

        if len(patterns) < 10:
            return {"correlations": "insufficient_data"}

        class_cooccurrences: dict[tuple[str, str], int] = defaultdict(int)

        for pattern in patterns:
            class1 = pattern.pattern_class.value
            for other in patterns:
                if other.pattern_id != pattern.pattern_id:
                    class2 = other.pattern_class.value
                    key = tuple(sorted([class1, class2]))
                    class_cooccurrences[key] += 1

        return {
            "cooccurrences": dict(class_cooccurrences),
            "most_correlated": max(class_cooccurrences.items(), key=lambda x: x[1])[0]
            if class_cooccurrences
            else None,
        }

    def get_emergence_timeline(self) -> list[dict[str, Any]]:
        timeline = []

        for pattern in sorted(self.detector._emergent_patterns, key=lambda p: p.timestamp):  # noqa: SLF001
            timeline.append(  # noqa: PERF401
                {
                    "timestamp": pattern.timestamp,
                    "pattern_class": pattern.pattern_class.value,
                    "emergence_level": pattern.emergence_level.value,
                    "emergence_score": pattern.emergence_score,
                    "agent_count": len(pattern.participating_agents),
                }
            )

        return timeline
