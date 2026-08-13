"""
LearningMixin - Collective learning status reporting.

Provides a single method for reporting the overall status of
collective learning, consensus, and memory optimization.
"""

from enum import Enum
from typing import Any


class LearningState(Enum):
    """Learning state enumeration for adaptive learning."""

    IDLE = "idle"
    LEARNING = "learning"
    CONVERGED = "converged"
    STAGNANT = "stagnant"
    DIVERGENT = "divergent"
    UNKNOWN = "unknown"


class LearningMixin:
    """
    Mixin providing collective learning status reporting.

    Requires the host actor to have:
        - pattern_extractor: PatternExtractor | None
        - deliberation_engine: SwarmDeliberationEngine | None
        - _active_deliberations: dict[str, str]
        - access_analyzer: AccessPatternAnalyzer | None

    Methods:
        get_learning_status: Get status of all learning systems
    """

    pattern_extractor: Any = None
    deliberation_engine: Any = None
    _active_deliberations: dict[str, str] = None
    access_analyzer: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Override __init__ to continue the MRO chain."""
        # Pass both positional and keyword args to continue the chain
        # Each mixin in the chain extracts what it needs and passes the rest
        super().__init__(*args, **kwargs)

    def get_learning_status(self) -> dict[str, Any]:
        """
        Get collective learning and memory optimization status.

        Returns:
            Dictionary containing status of all learning subsystems
        """
        return {
            "agent_id": self.agent_id,
            "collective_learning": {
                "patterns_extracted": (
                    len(self.pattern_extractor._validated_patterns) if self.pattern_extractor else 0  # noqa: SLF001
                ),
                "message_cache_size": (
                    len(self.pattern_extractor._message_cache) if self.pattern_extractor else 0  # noqa: SLF001
                ),
            },
            "consensus": {
                "active_deliberations": len(self._active_deliberations or {}),
                "deliberation_engine_stats": (
                    self.deliberation_engine.get_statistics() if self.deliberation_engine else {}
                ),
            },
            "memory_optimization": {
                "access_statistics": (
                    self.access_analyzer.get_statistics().to_dict() if self.access_analyzer else {}
                ),
            },
        }
