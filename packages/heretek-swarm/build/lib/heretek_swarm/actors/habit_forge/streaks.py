"""
Habit-Forge Streaks - Streak Calculation Helpers and Mixin.

Contains streak-related logic extracted from habit_forge.py, including
the HabitForgeStreaksMixin for cooperative multiple inheritance.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from heretek_swarm.actors.habit_forge.types import Habit


# Streak break threshold in days
STREAK_BREAK_THRESHOLD_DAYS = 2

# Sentinel value for repeated UTC suffix literal
_UTC_SUFFIX = "+00:00"


class HabitForgeStreaksMixin:
    """
    Mixin providing streak calculation and tracking helper methods.

    This mixin provides cooperative inheritance support through super().__init__().
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize and forward MRO chain (cooperative inheritance)."""
        super().__init__(*args, **kwargs)

    def check_stage_progression(self, habit: Habit) -> tuple[str, str] | None:
        """
        Check and determine habit stage based on adherence.

        Args:
            habit: Habit to check for progression

        Returns:
            Tuple of (old_stage, new_stage) if changed, None otherwise
        """
        from heretek_swarm.actors.habit_forge.types import HabitStage

        old_stage = habit.stage.value

        # Stage progression logic based on adherence rate
        if habit.adherence_rate >= 0.9 and habit.streak_current >= 60:
            new_stage = HabitStage.MAINTENANCE
        elif habit.adherence_rate >= 0.8 and habit.streak_current >= 30:
            new_stage = HabitStage.AUTOMATICITY
        elif habit.adherence_rate >= 0.7 and habit.streak_current >= 21:
            new_stage = HabitStage.CONSOLIDATION
        elif habit.adherence_rate >= 0.5 and habit.streak_current >= 7:
            new_stage = HabitStage.ACQUISITION
        elif habit.adherence_rate >= 0.3:
            new_stage = HabitStage.INITIATION
        else:
            new_stage = HabitStage.AWARENESS

        if new_stage.value != old_stage:
            return (old_stage, new_stage.value)
        return None

    def get_streak_status(self, habit: Habit) -> dict[str, Any]:
        """
        Get detailed streak status for a habit.

        Args:
            habit: Habit instance

        Returns:
            Dictionary with streak status information
        """
        return {
            "current_streak": habit.streak_current,
            "longest_streak": habit.streak_longest,
            "days_since_completion": (
                (datetime.now(UTC) - habit.last_completion).days if habit.last_completion else None
            ),
            "streak_at_risk": (
                habit.last_completion is not None
                and (datetime.now(UTC) - habit.last_completion).days >= 1
            ),
        }

    def is_streak_active(self, habit: Habit) -> bool:
        """
        Check if a habit's streak is still active.

        Args:
            habit: Habit instance to check

        Returns:
            True if streak is active (completed within threshold), False otherwise
        """
        if habit.streak_current == 0:
            return False

        if not habit.last_completion:
            return False

        days_since = (datetime.now(UTC) - habit.last_completion).days
        return days_since < STREAK_BREAK_THRESHOLD_DAYS

    def calculate_streak_probability(
        self,
        _habit: Habit,
        completion_history: list[datetime],
    ) -> float:
        """
        Calculate probability of maintaining streak based on history.

        Args:
            habit: Habit instance
            completion_history: List of completion timestamps

        Returns:
            Probability score (0.0 to 1.0)
        """
        if len(completion_history) < 2:
            return 0.5  # Insufficient data

        # Calculate average gap between completions
        gaps = []
        sorted_history = sorted(completion_history)
        for i in range(1, len(sorted_history)):
            gap = (sorted_history[i] - sorted_history[i - 1]).days
            gaps.append(gap)

        avg_gap = sum(gaps) / len(gaps)

        # Calculate consistency score
        consistency = 1.0 - (min(avg_gap - 1, 2) / 3)  # Penalize gaps > 1 day
        return max(0.0, min(1.0, consistency))


# Standalone utility functions for use without a class instance


def is_within_streak_threshold(
    last_completion: datetime | None,
    threshold_days: int = STREAK_BREAK_THRESHOLD_DAYS,
) -> bool:
    """
    Check if a completion is within the streak threshold.

    Args:
        last_completion: Last completion timestamp
        threshold_days: Number of days allowed between completions

    Returns:
        True if within threshold, False otherwise
    """
    if last_completion is None:
        return False

    return (datetime.now(UTC) - last_completion).days < threshold_days


def should_reset_streak(
    last_completion: datetime | None,
    current_time: datetime | None = None,
    threshold_days: int = STREAK_BREAK_THRESHOLD_DAYS,
) -> bool:
    """
    Determine if streak should be reset due to missed days.

    Args:
        last_completion: Last completion timestamp
        current_time: Current time (defaults to now)
        threshold_days: Number of days allowed between completions

    Returns:
        True if streak should be reset, False otherwise
    """
    if current_time is None:
        current_time = datetime.now(UTC)

    if last_completion is None:
        return True

    days_since = (current_time - last_completion).days
    return days_since >= threshold_days


def get_stage_for_adherence(
    adherence_rate: float,
    streak_current: int,
) -> str:
    """
    Determine habit stage based on adherence rate and streak.

    Args:
        adherence_rate: Current adherence rate (0.0-1.0)
        streak_current: Current streak count

    Returns:
        Habit stage string value
    """
    from heretek_swarm.actors.habit_forge.types import HabitStage

    if adherence_rate >= 0.9 and streak_current >= 60:
        return HabitStage.MAINTENANCE.value
    if adherence_rate >= 0.8 and streak_current >= 30:
        return HabitStage.AUTOMATICITY.value
    if adherence_rate >= 0.7 and streak_current >= 21:
        return HabitStage.CONSOLIDATION.value
    if adherence_rate >= 0.5 and streak_current >= 7:
        return HabitStage.ACQUISITION.value
    if adherence_rate >= 0.3:
        return HabitStage.INITIATION.value
    return HabitStage.AWARENESS.value


def calculate_longest_streak(completions: list[dict[str, Any]]) -> int:
    """
    Calculate the longest streak from a list of completions.

    Args:
        completions: List of completion records with 'timestamp' field

    Returns:
        Longest streak count
    """
    if not completions:
        return 0

    # Sort completions by timestamp
    sorted_completions = sorted(
        completions,
        key=lambda x: datetime.fromisoformat(x["timestamp"].replace("Z", _UTC_SUFFIX)),
    )

    longest = 1
    current = 1

    for i in range(1, len(sorted_completions)):
        prev_time = datetime.fromisoformat(
            sorted_completions[i - 1]["timestamp"].replace("Z", _UTC_SUFFIX)
        )
        curr_time = datetime.fromisoformat(
            sorted_completions[i]["timestamp"].replace("Z", _UTC_SUFFIX)
        )

        days_diff = (curr_time - prev_time).days

        if days_diff < STREAK_BREAK_THRESHOLD_DAYS:
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    return longest
