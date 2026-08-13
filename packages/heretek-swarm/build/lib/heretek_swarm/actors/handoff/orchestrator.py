"""
Handoff orchestration — strategy-based handoff evaluation and execution.

Extracted from the original actors/handoff.py minus the type definitions
(HandoffContext, HandoffResult, HandoffValidator, AgentHandoff) which now
live in heretek_swarm.actors.handoff.types.
"""

from abc import ABC, abstractmethod
from typing import Any

import structlog

from heretek_swarm.actors.handoff.types import AgentHandoff, HandoffResult
from heretek_swarm.actors.mixins import DeliberationMixin, LearningMixin, MemoryMixin, PatternMixin

logger = structlog.get_logger(__name__)


# =============================================================================
# Handoff Strategies
# =============================================================================


class HandoffStrategy(ABC):
    """Base class for handoff strategies"""

    @abstractmethod
    async def should_handoff(self, context: dict[str, Any]) -> bool:
        """Determine if handoff should occur"""

    @abstractmethod
    async def select_destination(self, context: dict[str, Any]) -> str:
        """Select destination agent for handoff"""


class TaskTypeStrategy(HandoffStrategy):
    """Handoff based on task type"""

    TASK_AGENTS = {  # noqa: RUF012
        "code_generation": "coder",
        "analysis": "alpha",
        "validation": "beta",
        "research": "explorer",
        "creative": "dreamer",
        "memory": "historian",
        "safety": "sentinel",
    }

    async def should_handoff(self, context: dict[str, Any]) -> bool:
        """Check if task type matches a specialized agent"""
        task_type = context.get("task_type")
        return task_type in self.TASK_AGENTS

    async def select_destination(self, context: dict[str, Any]) -> str:
        """Select destination based on task type"""
        task_type = context.get("task_type")
        return self.TASK_AGENTS.get(task_type, "steward")


class PerformanceStrategy(HandoffStrategy):
    """Handoff based on agent performance metrics"""

    PERFORMANCE_THRESHOLD = 0.7  # 70% success rate threshold

    async def should_handoff(self, context: dict[str, Any]) -> bool:
        """Check if agent performance is below threshold"""
        success_rate = context.get("success_rate", 1.0)
        return success_rate < self.PERFORMANCE_THRESHOLD

    async def select_destination(self, context: dict[str, Any]) -> str:
        """Select best performing agent"""
        agent_performance = context.get("agent_performance", {})

        # P1-5 fix: Handle empty dict
        if not agent_performance:
            logger.warning("No agent performance data available, defaulting to steward")
            return "steward"

        # Find agent with highest success rate
        best_agent = max(agent_performance.items(), key=lambda x: x[1].get("success_rate", 0.0))

        return best_agent[0] if best_agent else "steward"


class LoadBalancingStrategy(HandoffStrategy):
    """Handoff based on current agent load"""

    MAX_CONCURRENT_TASKS = 5

    async def should_handoff(self, context: dict[str, Any]) -> bool:
        """Check if agent is overloaded"""
        current_tasks = context.get("current_tasks", 0)
        return current_tasks >= self.MAX_CONCURRENT_TASKS

    async def select_destination(self, context: dict[str, Any]) -> str:
        """Select least loaded agent"""
        agent_load = context.get("agent_load", {})

        # P1-5 fix: Handle empty dict
        if not agent_load:
            logger.warning("No agent load data available, defaulting to steward")
            return "steward"

        # Find agent with lowest task count
        least_loaded = min(agent_load.items(), key=lambda x: x[1].get("task_count", 0))

        return least_loaded[0] if least_loaded else "steward"


class HandoffOrchestrator(PatternMixin, DeliberationMixin, MemoryMixin, LearningMixin):
    """
    Orchestrates agent handoffs using configurable strategies.

    Manages the handoff lifecycle and ensures proper context transfer.
    """

    def __init__(self, handoff: AgentHandoff):
        """
        Initialize orchestrator.

        Args:
            handoff: AgentHandoff instance
        """
        self.handoff = handoff
        self.strategy: HandoffStrategy | None = None
        self._strategy_map = {
            "task_type": TaskTypeStrategy(),
            "performance": PerformanceStrategy(),
            "load_balancing": LoadBalancingStrategy(),
        }

    def set_strategy(self, strategy_name: str) -> bool:
        """
        Set the handoff strategy.

        Args:
            strategy_name: Name of strategy to use

        Returns:
            True if strategy was set successfully
        """
        if strategy_name not in self._strategy_map:
            logger.warning(
                "strategy_not_found",
                strategy=strategy_name,
                available=list(self._strategy_map.keys()),
            )
            return False

        self.strategy = self._strategy_map[strategy_name]
        logger.info("strategy_set", strategy=strategy_name)
        return True

    async def evaluate_and_handoff(
        self, from_agent_id: str, context: dict[str, Any], reason: str = "automatic"
    ) -> HandoffResult | None:
        """
        Evaluate if handoff is needed and execute if so.

        Args:
            from_agent_id: Current agent ID
            context: Current execution context
            reason: Reason for handoff evaluation

        Returns:
            HandoffResult if handoff was executed, None otherwise
        """
        if not self.strategy:
            logger.warning("no_strategy_set")
            return None

        # Evaluate if handoff should occur
        should_handoff = await self.strategy.should_handoff(context)

        if not should_handoff:
            return None

        # Select destination agent
        to_agent_id = await self.strategy.select_destination(context)

        if to_agent_id == from_agent_id:
            logger.warning("handoff_same_agent", agent_id=from_agent_id)
            return None

        # Execute handoff
        return await self.handoff.execute_handoff(
            from_agent_id=from_agent_id, to_agent_id=to_agent_id, context=context, reason=reason
        )
