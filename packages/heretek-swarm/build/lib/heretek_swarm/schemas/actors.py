"""
schemas.actors — consolidated Pydantic models for inter-actor messages.

This module re-exports all Pydantic models from the validation layer so that
external callers can use a stable import path::

    from heretek_swarm.schemas.actors import ActorMessage, MessageType, MESSAGE_TYPES

The internal dataclass ActorMessage in actors/base/core.py is NOT re-exported here;
it remains an internal implementation detail.
"""

from __future__ import annotations

from typing import Any

from heretek_swarm.validation.agent_messages import (
    MESSAGE_TYPES,
    ActorMessage,
    AgentMessageBase,
    CodeExecutionRequest,
    ConsensusProposal,
    ConsensusVote,
    CoordinationRequest,
    ErrorMessage,
    MessagePriority,
    MessageType,
    StateUpdate,
    TaskMessage,
    ToolRequest,
    ToolResponse,
    create_actor_message,
    create_state_update,
    create_tool_request,
    create_tool_response,
    validate_message,
)

# Re-export everything for external callers.
__all__ = [
    # Registry
    "MESSAGE_TYPES",
    # Message models
    "ActorMessage",
    # Base
    "AgentMessageBase",
    "CodeExecutionRequest",
    "ConsensusProposal",
    "ConsensusVote",
    "CoordinationRequest",
    "ErrorMessage",
    "MessagePriority",
    # Enums
    "MessageType",
    "StateUpdate",
    "TaskMessage",
    "ToolRequest",
    "ToolResponse",
    "create_actor_message",
    "create_state_update",
    "create_tool_request",
    "create_tool_response",
    # Factory / helpers
    "validate_message",
]

# Names listed in the task plan that do not yet exist in agent_messages.py.
# They are documented here so future slices can implement and wire them.
_PLAN_REFERENCED_MISSING = {
    "DeliberationRequest",
    "MemoryStoreRequest",
    "AnalysisRequest",
    "ValidationRequest",
    "QueryRequest",
    "LineageRequest",
    "HealthCheckRequest",
    "SuspendResumeRequest",
    "TerminateRequest",
    "CollectiveTaskRequest",
    "DependencyRequest",
    "IMMUTABLE_RULES",
    "BASELINE_CONFIG",
}


def __getattr__(name: str) -> Any:
    """Re-export from agent_messages; raise DeprecationWarning for legacy paths."""
    if name in _PLAN_REFERENCED_MISSING:
        raise AttributeError(
            f"heretek_swarm.schemas.actors.{name} is not yet implemented "
            f"(planned for a future slice)."
        )

    # Redirect known exports through the module namespace.
    if name in __all__:
        return globals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
