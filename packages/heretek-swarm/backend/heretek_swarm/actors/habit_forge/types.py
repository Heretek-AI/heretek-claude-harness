"""
Habit-Forge Types - Data Models and Enums for Behavior Architecture.

Contains all type definitions extracted from habit_forge.py:
- HabitStage: Stages of habit formation
- ReinforcementType: Types of reinforcement strategies
- Habit: Core habit data model
- BehavioralPattern: Detected behavior pattern model

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class HabitStage(StrEnum):
    """Stages of habit formation."""

    AWARENESS = "awareness"
    INITIATION = "initiation"
    ACQUISITION = "acquisition"
    CONSOLIDATION = "consolidation"
    AUTOMATICITY = "automaticity"
    MAINTENANCE = "maintenance"


class ReinforcementType(StrEnum):
    """Types of reinforcement strategies."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    SOCIAL = "social"
    MATERIAL = "material"
    INTRINSIC = "intrinsic"


class Habit:
    """Represents a tracked habit."""

    def __init__(
        self,
        habit_id: str,
        name: str,
        description: str,
        trigger: str,
        routine: str,
        reward: str,
        target_frequency: str = "daily",
        stage: HabitStage = HabitStage.INITIATION,
    ) -> None:
        self.habit_id = habit_id
        self.name = name
        self.description = description
        self.trigger = trigger
        self.routine = routine
        self.reward = reward
        self.target_frequency = target_frequency
        self.stage = stage
        self.created_at = datetime.now(UTC)

        # Tracking metrics
        self.completions: list[dict[str, Any]] = []
        self.adherence_rate: float = 0.0
        self.streak_current: int = 0
        self.streak_longest: int = 0
        self.last_completion: datetime | None = None

    def record_completion(self, context: str | None = None) -> None:
        """Record a habit completion."""
        completion_time = datetime.now(UTC)
        self.completions.append(
            {
                "timestamp": completion_time.isoformat(),
                "context": context,
            }
        )
        self.last_completion = completion_time

        # Update streak
        if self.streak_current == 0 or (
            self.last_completion and completion_time - self.last_completion < timedelta(days=2)
        ):
            self.streak_current += 1
        else:
            self.streak_current = 1

        if self.streak_current > self.streak_longest:
            self.streak_longest = self.streak_current

        # Calculate adherence rate
        self._calculate_adherence()

    def _calculate_adherence(self) -> None:
        """Calculate adherence rate based on completions."""
        if not self.completions:
            self.adherence_rate = 0.0
            return

        # Calculate expected completions based on frequency
        days_active = (datetime.now(UTC) - self.created_at).days
        if days_active == 0:
            days_active = 1

        if self.target_frequency == "daily":
            expected = days_active
        elif self.target_frequency == "weekly":
            expected = days_active / 7
        else:
            expected = days_active

        self.adherence_rate = min(len(self.completions) / expected, 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert habit to dictionary."""
        return {
            "habit_id": self.habit_id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "routine": self.routine,
            "reward": self.reward,
            "target_frequency": self.target_frequency,
            "stage": self.stage.value,
            "adherence_rate": self.adherence_rate,
            "streak_current": self.streak_current,
            "streak_longest": self.streak_longest,
            "completions_count": len(self.completions),
            "created_at": self.created_at.isoformat(),
            "last_completion": self.last_completion.isoformat() if self.last_completion else None,
        }


class BehavioralPattern:
    """Represents a detected behavioral pattern."""

    def __init__(
        self,
        pattern_id: str,
        pattern_type: Any,  # PatternType from collective.learning
        description: str,
        triggers: list[str],
        behaviors: list[str],
        outcomes: list[str],
        frequency: str = "unknown",
        impact_score: float = 0.0,
        evidence: list[dict[str, Any]] | None = None,
        category: str | None = None,
        confidence: float | None = None,
    ) -> None:
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type
        self.description = description
        self.triggers = triggers
        self.behaviors = behaviors
        self.outcomes = outcomes
        self.frequency = frequency
        self.impact_score = impact_score
        self.evidence = evidence or []
        self.category = category
        self.confidence = confidence
        self.detected_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "triggers": self.triggers,
            "behaviors": self.behaviors,
            "outcomes": self.outcomes,
            "frequency": self.frequency,
            "impact_score": self.impact_score,
            "evidence": self.evidence,
            "category": self.category,
            "confidence": self.confidence,
            "detected_at": self.detected_at.isoformat(),
        }
