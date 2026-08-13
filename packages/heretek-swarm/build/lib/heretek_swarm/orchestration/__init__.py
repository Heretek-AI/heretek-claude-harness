"""
Heretek Swarm Orchestration Package

This package provides multi-agent orchestration patterns including:
- HeavySwarm 5-phase deliberation workflow
- MAKER consensus integration
- Workflow management and monitoring
"""

from heretek_swarm.orchestration.heavyswarm import (
    HeavySwarmWorkflow,
    PhaseResult,
    WorkflowPhase,
    WorkflowPhaseError,
    WorkflowResult,
)

__all__ = [
    "HeavySwarmWorkflow",
    "PhaseResult",
    "WorkflowPhase",
    "WorkflowPhaseError",
    "WorkflowResult",
]
