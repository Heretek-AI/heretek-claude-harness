"""
Actors base package - re-exports from base.py wrapper for backwards compatibility.
"""

# Import directly from core module to avoid circular import via base.py wrapper
# Trigger monkey-patch side-effects (message handlers, state management, etc.)
from heretek_swarm.actors.base import (
    message_handling,
    state_management,
)
from heretek_swarm.actors.base.core import (
    ActorMessage,
    ActorState,
    ActorStatus,
    AgentActor,
)

__all__ = ["ActorMessage", "ActorState", "ActorStatus", "AgentActor"]
