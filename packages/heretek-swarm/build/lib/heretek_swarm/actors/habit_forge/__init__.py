"""
Habit-Forge Module - Behavior Architecture & Pattern Optimization.

This module provides the HabitForgeAgent for habit formation and behavioral
pattern optimization. The module has been refactored into separate components:

- types.py: Type definitions (HabitStage, ReinforcementType, Habit, BehavioralPattern)
- tracking.py: Tracking helpers and mixin (HabitForgeTrackingMixin)
- streaks.py: Streak calculation helpers and mixin (HabitForgeStreaksMixin)
- agent.py: Main HabitForgeAgent class

For backward compatibility, all public exports from the original habit_forge.py
are re-exported from this module.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Re-export agent from agent.py
from heretek_swarm.actors.habit_forge.agent import HabitForgeAgent

# Re-export mixins and helpers from streaks.py
from heretek_swarm.actors.habit_forge.streaks import (
    HabitForgeStreaksMixin,
    calculate_longest_streak,
    get_stage_for_adherence,
    is_within_streak_threshold,
    should_reset_streak,
)

# Re-export mixins and helpers from tracking.py
from heretek_swarm.actors.habit_forge.tracking import (
    HabitForgeTrackingMixin,
    summarize_habit_progress,
    validate_habit_fields,
)

# Re-export types from types.py
from heretek_swarm.actors.habit_forge.types import (
    BehavioralPattern,
    Habit,
    HabitStage,
    ReinforcementType,
)

__all__ = [
    # Types (enums and data classes)
    "BehavioralPattern",
    "Habit",
    "HabitForgeAgent",
    "HabitForgeStreaksMixin",
    "HabitForgeTrackingMixin",
    "HabitStage",
    "ReinforcementType",
    # Streaks helpers
    "calculate_longest_streak",
    "get_stage_for_adherence",
    "is_within_streak_threshold",
    "should_reset_streak",
    # Tracking helpers
    "summarize_habit_progress",
    "validate_habit_fields",
]
