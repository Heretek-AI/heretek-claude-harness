"""
Coder subpackage - Code Implementation & Debugging Specialist.
"""

from heretek_swarm.actors.coder.agent import CoderAgent
from heretek_swarm.actors.coder.types import (
    CodeLanguage,
    CodeReview,
    CodeSnippet,
    CodeTask,
    DebugSession,
    ImplementationTask,
    ReviewIssue,
    ReviewSeverity,
)

__all__ = [
    "CodeLanguage",
    "CodeReview",
    "CodeSnippet",
    "CodeTask",
    "CoderAgent",
    "DebugSession",
    "ImplementationTask",
    "ReviewIssue",
    "ReviewSeverity",
]
