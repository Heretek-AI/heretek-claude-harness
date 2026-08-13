"""
Coordinator Module - Multi-Agent Coordination Specialist

This module provides coordination capabilities for multi-agent systems including:
- Task synchronization across multiple agents
- Dependency resolution and sequencing
- Parallel execution orchestration
- Resource contention management
- Collective task progress tracking

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Re-export types for backward compatibility
from heretek_swarm.actors.coordinator.agent import CoordinatorAgent
from heretek_swarm.actors.coordinator.strategies import (
    DependencyResolutionStrategy,
    ParallelExecutionStrategy,
    ResourceAllocationStrategy,
)
from heretek_swarm.actors.coordinator.types import (
    AgentState,
    CoordinatedTask,
    DependencyType,
    TaskStatus,
)

__all__ = [
    "AgentState",
    "CoordinatedTask",
    # Main agent class
    "CoordinatorAgent",
    # Strategy classes
    "DependencyResolutionStrategy",
    "DependencyType",
    "ParallelExecutionStrategy",
    "ResourceAllocationStrategy",

    "TaskStatus",
]
