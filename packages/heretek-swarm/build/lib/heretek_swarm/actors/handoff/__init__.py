"""
Handoff subpackage — agent-to-agent handoff with context transfer, validation,
rate limiting, and strategy-based orchestration.

Deduplicates type definitions that were previously duplicated across
handoff.py and handoff_handlers.py into a single types.py module.
"""

from heretek_swarm.actors.handoff.handlers import (
    HandoffLoggingHandler,
    HandoffProcessor,
    HandoffRateLimitHandler,
    HandoffTransferHandler,
    HandoffValidationHandler,
)
from heretek_swarm.actors.handoff.orchestrator import (
    HandoffOrchestrator,
    HandoffStrategy,
    LoadBalancingStrategy,
    PerformanceStrategy,
    TaskTypeStrategy,
)
from heretek_swarm.actors.handoff.types import (
    AgentHandoff,
    HandoffContext,
    HandoffResult,
    HandoffValidator,
)

__all__ = [
    "AgentHandoff",
    "HandoffContext",
    "HandoffLoggingHandler",
    "HandoffOrchestrator",
    "HandoffProcessor",
    "HandoffRateLimitHandler",
    "HandoffResult",
    "HandoffStrategy",
    "HandoffTransferHandler",
    "HandoffValidationHandler",
    "HandoffValidator",
    "LoadBalancingStrategy",
    "PerformanceStrategy",
    "TaskTypeStrategy",
]
