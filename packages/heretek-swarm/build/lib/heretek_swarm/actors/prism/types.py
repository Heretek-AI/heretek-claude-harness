"""
Prism Types - Type definitions for multi-perspective analysis.

This module contains all type definitions used by the Prism agent:
- Enums: PerspectiveType, BiasType, AnalyticalFramework
- Dataclasses: Perspective, BiasDetection

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PerspectiveType(StrEnum):
    """Types of perspectives Prism can generate."""

    TECHNICAL = "technical"
    USER = "user"
    BUSINESS = "business"
    SECURITY = "security"
    ETHICAL = "ethical"
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    STAKEHOLDER = "stakeholder"
    SYSTEMS = "systems"
    FIRST_PRINCIPLES = "first_principles"


class BiasType(StrEnum):
    """Cognitive biases Prism can detect."""

    CONFIRMATION = "confirmation_bias"
    ANCHORING = "anchoring_bias"
    AVAILABILITY = "availability_heuristic"
    SURVIVORSHIP = "survivorship_bias"
    SUNK_COST = "sunk_cost_fallacy"
    OVERCONFIDENCE = "overconfidence_bias"
    GROUP_THINK = "group_think"
    RECENTCY = "recency_bias"
    SELECTION = "selection_bias"
    ATTRIBUTION = "attribution_error"


class AnalyticalFramework(StrEnum):
    """Analytical frameworks Prism can apply."""

    FIRST_PRINCIPLES = "first_principles"
    SYSTEMS_THINKING = "systems_thinking"
    PRE_MORTEM = "pre_mortem"
    STAKEHOLDER_IMPACT = "stakeholder_impact"
    COST_BENEFIT = "cost_benefit"
    SWOT = "swot_analysis"
    FIVE_WHY = "five_whys"
    ROOT_CAUSE = "root_cause_analysis"


class Perspective:
    """Represents a single perspective on an issue."""

    def __init__(
        self,
        perspective_type: PerspectiveType,
        viewpoint: str,
        key_insights: list[str],
        assumptions: list[str],
        blind_spots: list[str],
        confidence: float = 0.0,
    ) -> None:
        self.perspective_type = perspective_type
        self.viewpoint = viewpoint
        self.key_insights = key_insights
        self.assumptions = assumptions
        self.blind_spots = blind_spots
        self.confidence = confidence
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert perspective to dictionary."""
        return {
            "perspective_type": self.perspective_type.value,
            "viewpoint": self.viewpoint,
            "key_insights": self.key_insights,
            "assumptions": self.assumptions,
            "blind_spots": self.blind_spots,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


class BiasDetection:
    """Represents a detected cognitive bias."""

    def __init__(
        self,
        bias_type: BiasType,
        description: str,
        evidence: list[str],
        severity: str = "medium",
        recommendation: str | None = None,
    ) -> None:
        self.bias_type = bias_type
        self.description = description
        self.evidence = evidence
        self.severity = severity
        self.recommendation = recommendation
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert bias detection to dictionary."""
        return {
            "bias_type": self.bias_type.value,
            "description": self.description,
            "evidence": self.evidence,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp.isoformat(),
        }


__all__ = [
    "AnalyticalFramework",
    "BiasDetection",
    "BiasType",
    "Perspective",
    "PerspectiveType",
]
