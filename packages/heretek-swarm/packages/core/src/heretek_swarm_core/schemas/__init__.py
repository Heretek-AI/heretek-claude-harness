"""schemas — Pydantic validation schemas for stable import paths.

Re-exports actor message models and external call log schemas so external
callers use a single stable entry point:

    from heretek_swarm_core.schemas import ActorMessage, ExternalCallLogResponse
"""

from heretek_swarm_core.schemas.actors import (
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
from heretek_swarm_core.schemas.external_call_log import (
    ExternalCallLogBase,
    ExternalCallLogCreate,
    ExternalCallLogListItem,
    ExternalCallLogListResponse,
    ExternalCallLogResponse,
    extract_domain,
)

__all__ = [
    # Actors
    "MESSAGE_TYPES",
    "ActorMessage",
    "AgentMessageBase",
    "CodeExecutionRequest",
    "ConsensusProposal",
    "ConsensusVote",
    "CoordinationRequest",
    "ErrorMessage",
    "MessagePriority",
    "MessageType",
    "StateUpdate",
    "TaskMessage",
    "ToolRequest",
    "ToolResponse",
    "create_actor_message",
    "create_state_update",
    "create_tool_request",
    "create_tool_response",
    "validate_message",
    # External call logs
    "ExternalCallLogBase",
    "ExternalCallLogCreate",
    "ExternalCallLogListItem",
    "ExternalCallLogListResponse",
    "ExternalCallLogResponse",
    "extract_domain",
]
