"""
Habit-Forge Tracking - Habit Tracking Helpers and Mixin.

Contains tracking-related helper methods and the HabitForgeTrackingMixin
for cooperative multiple inheritance.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from heretek_swarm.actors.habit_forge.types import Habit


class HabitForgeTrackingMixin:
    """
    Mixin providing habit tracking helper methods.

    This mixin provides cooperative inheritance support through super().__init__().
    All methods here operate on Habit instances and can be reused across the codebase.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize and forward MRO chain (cooperative inheritance)."""
        super().__init__(*args, **kwargs)

    def validate_habit_request(self, content: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate habit creation/modification request.

        Args:
            content: Message content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["name", "trigger", "routine", "reward"]
        for field in required_fields:
            if field not in content:
                return False, f"Missing required field: {field}"
            if not isinstance(content[field], str):
                return False, f"Field '{field}' must be a string"
            if len(content[field]) > 5000:
                return False, f"Field '{field}' exceeds maximum length"
        return True, ""

    def calculate_adherence_rate(
        self,
        habit: Habit,
    ) -> float:
        """
        Calculate adherence rate for a habit.

        Args:
            habit: Habit instance to calculate adherence for

        Returns:
            Adherence rate as float between 0.0 and 1.0
        """
        if not habit.completions:
            return 0.0

        from datetime import UTC, datetime

        days_active = (datetime.now(UTC) - habit.created_at).days
        if days_active == 0:
            days_active = 1

        if habit.target_frequency == "daily":
            expected = days_active
        elif habit.target_frequency == "weekly":
            expected = days_active / 7
        else:
            expected = days_active

        return min(len(habit.completions) / expected, 1.0)

    def get_habit_summary(self, habit: Habit) -> dict[str, Any]:
        """
        Get a summary of habit progress.

        Args:
            habit: Habit instance to summarize

        Returns:
            Dictionary with habit summary data
        """
        return {
            "habit_id": habit.habit_id,
            "name": habit.name,
            "stage": habit.stage.value,
            "adherence_rate": habit.adherence_rate,
            "streak_current": habit.streak_current,
            "streak_longest": habit.streak_longest,
            "total_completions": len(habit.completions),
            "created_at": habit.created_at.isoformat(),
            "last_completion": habit.last_completion.isoformat() if habit.last_completion else None,
        }


# Standalone utility functions for use without a class instance


def validate_habit_fields(
    name: str,
    trigger: str,
    routine: str,
    reward: str,
) -> tuple[bool, str]:
    """
    Standalone validation of habit fields.

    Args:
        name: Habit name
        trigger: Habit trigger
        routine: Habit routine
        reward: Habit reward

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "name must be a non-empty string"
    if not trigger or not isinstance(trigger, str):
        return False, "trigger must be a non-empty string"
    if not routine or not isinstance(routine, str):
        return False, "routine must be a non-empty string"
    if not reward or not isinstance(reward, str):
        return False, "reward must be a non-empty string"

    if len(name) > 5000:
        return False, "name exceeds maximum length"
    if len(trigger) > 5000:
        return False, "trigger exceeds maximum length"
    if len(routine) > 5000:
        return False, "routine exceeds maximum length"
    if len(reward) > 5000:
        return False, "reward exceeds maximum length"

    return True, ""


def summarize_habit_progress(
    name: str,
    stage: str,
    adherence_rate: float,
    streak_current: int,
    streak_longest: int,
    completions_count: int,
    created_at: str,
    last_completion: str | None = None,
) -> dict[str, Any]:
    """
    Create a habit progress summary dictionary.

    Args:
        name: Habit name
        stage: Current habit stage
        adherence_rate: Adherence rate (0.0-1.0)
        streak_current: Current streak count
        streak_longest: Longest streak achieved
        completions_count: Total number of completions
        created_at: ISO timestamp of creation
        last_completion: ISO timestamp of last completion or None

    Returns:
        Dictionary with habit summary
    """
    return {
        "name": name,
        "stage": stage,
        "adherence_rate": adherence_rate,
        "streak_current": streak_current,
        "streak_longest": streak_longest,
        "total_completions": completions_count,
        "created_at": created_at,
        "last_completion": last_completion,
    }
