"""
Goal System — Autonomous strategic goal proposal, voting, and persistence.

Goals are proposed by Metis (the strategic planning agent), flow through
MAKER consensus voting, and are persisted via :class:`FileGoalStore` using
atomic file writes.
"""

from .consensus import GoalConsensus
from .models import Goal, Vote
from .pipeline import run_goal_cycle
from .store import FileGoalStore

__all__ = [
    "FileGoalStore",
    "Goal",
    "GoalConsensus",
    "Vote",
    "run_goal_cycle",
]
