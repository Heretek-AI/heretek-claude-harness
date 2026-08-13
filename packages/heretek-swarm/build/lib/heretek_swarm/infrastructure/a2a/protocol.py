"""
A2A Protocol Implementation.

Agent-to-Agent communication protocol based on JSON-RPC 2.0 with swarm extensions.
Supports task delegation, consensus messages, capability discovery, and streaming.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class A2AMessageType(Enum):
    """A2A message types extending JSON-RPC 2.0."""

    # Core JSON-RPC
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"

    # Task messages
    TASK_PROPOSE = "task/propose"
    TASK_ACCEPT = "task/accept"
    TASK_REJECT = "task/reject"
    TASK_COMPLETE = "task/complete"
    TASK_PROGRESS = "task/progress"

    # Delegation messages
    DELEGATE = "delegate"
    DELEGATION_ACCEPT = "delegate/accept"
    DELEGATION_REJECT = "delegate/reject"
    DELEGATION_COMPLETE = "delegate/complete"

    # Consensus messages
    CONSENSUS_PROPOSE = "consensus/propose"
    CONSENSUS_VOTE = "consensus/vote"
    CONSENSUS_COMMIT = "consensus/commit"

    # Capability discovery
    CAPABILITY_QUERY = "capability/query"
    CAPABILITY_ANNOUNCE = "capability/announce"

    # Streaming
    STREAM_START = "stream/start"
    STREAM_CHUNK = "stream/chunk"
    STREAM_END = "stream/end"


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3
    CRITICAL = 4


@dataclass
class AgentCapability:
    """Describes an agent capability."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class A2AMessage:
    """
    A2A message structure (JSON-RPC 2.0 + extensions).

    Fields:
        jsonrpc: JSON-RPC version (always "2.0")
        id: Message correlation ID
        method: Message type/method
        params: Message parameters
        result: Response result (for response messages)
        error: Error info (for error messages)
    """

    jsonrpc: str = "2.0"
    id: str = field(default_factory=lambda: str(uuid4()))
    method: A2AMessageType = A2AMessageType.REQUEST
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: dict[str, Any] | None = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    correlation_id: str | None = None
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        msg = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
        }

        if self.params:
            msg["params"] = self.params
        if self.result is not None:
            msg["result"] = self.result
        if self.error:
            msg["error"] = self.error
        if self.correlation_id:
            msg["correlation_id"] = self.correlation_id
        if self.trace_id:
            msg["trace_id"] = self.trace_id

        return msg

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2AMessage":
        """Parse from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id", str(uuid4())),
            method=A2AMessageType(data.get("method", "request")),
            params=data.get("params", {}),
            result=data.get("result"),
            error=data.get("error"),
            priority=MessagePriority(data.get("priority", 1)),
            timestamp=data.get("timestamp", datetime.now(tz=UTC).isoformat()),
            correlation_id=data.get("correlation_id"),
            trace_id=data.get("trace_id"),
        )


# =============================================================================
# Message Factory Functions
# =============================================================================


def create_task_request(
    task_id: str,
    task_type: str,
    description: str,
    source_agent: str,
    target_agent: str | None = None,
    priority: MessagePriority = MessagePriority.NORMAL,
    params: dict[str, Any] | None = None,
) -> A2AMessage:
    """Create a task request message."""
    return A2AMessage(
        method=A2AMessageType.TASK_PROPOSE,
        params={
            "task_id": task_id,
            "task_type": task_type,
            "description": description,
            "source_agent": source_agent,
            "target_agent": target_agent,
            **(params or {}),
        },
        priority=priority,
    )


def create_task_response(
    task_id: str,
    accepted: bool,
    response_message: str,
    agent_id: str,
    result: Any = None,
    correlation_id: str | None = None,
) -> A2AMessage:
    """Create a task response message."""
    return A2AMessage(
        method=A2AMessageType.TASK_ACCEPT if accepted else A2AMessageType.TASK_REJECT,
        params={
            "task_id": task_id,
            "accepted": accepted,
            "response_message": response_message,
            "agent_id": agent_id,
            "result": result,
        },
        correlation_id=correlation_id,
    )


def create_delegation_message(
    task_id: str,
    source_agent: str,
    target_agent: str,
    delegation_type: str,
    context: dict[str, Any] | None = None,
    priority: MessagePriority = MessagePriority.NORMAL,
) -> A2AMessage:
    """Create a task delegation message."""
    return A2AMessage(
        method=A2AMessageType.DELEGATE,
        params={
            "task_id": task_id,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "delegation_type": delegation_type,
            "context": context or {},
        },
        priority=priority,
    )


def create_consensus_message(
    topic: str,
    message_type: str,
    proposer: str,
    payload: dict[str, Any],
    term: int = 0,
    priority: MessagePriority = MessagePriority.HIGH,
) -> A2AMessage:
    """Create a consensus-related message."""
    return A2AMessage(
        method=A2AMessageType.CONSENSUS_PROPOSE,
        params={
            "topic": topic,
            "message_type": message_type,
            "proposer": proposer,
            "payload": payload,
            "term": term,
        },
        priority=priority,
    )


# =============================================================================
# A2A Protocol Handler
# =============================================================================


class A2AProtocol:
    """
    A2A Protocol handler for agent communication.

    Handles:
    - Message validation and routing
    - Capability negotiation
    - Protocol compliance checking
    - Error handling
    """

    SUPPORTED_METHODS: ClassVar[set[str]] = {method.value for method in A2AMessageType}

    def __init__(self):
        self._registered_agents: dict[str, list[AgentCapability]] = {}
        self._message_history: list[A2AMessage] = []
        self._max_history = 1000

    def register_agent(
        self,
        agent_id: str,
        capabilities: list[AgentCapability],
    ) -> None:
        """Register an agent with its capabilities."""
        self._registered_agents[agent_id] = capabilities
        logger.info(
            "agent_registered",
            agent_id=agent_id,
            capability_count=len(capabilities),
        )

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self._registered_agents:
            del self._registered_agents[agent_id]
            logger.info("agent_unregistered", agent_id=agent_id)
            return True
        return False

    def get_agent_capabilities(self, agent_id: str) -> list[AgentCapability] | None:
        """Get capabilities for an agent."""
        return self._registered_agents.get(agent_id)

    def validate_message(self, message: A2AMessage) -> tuple[bool, str | None]:
        """
        Validate an A2A message.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check JSON-RPC version
        if message.jsonrpc != "2.0":
            return False, f"Invalid JSON-RPC version: {message.jsonrpc}"

        # Check method is supported
        if message.method.value not in self.SUPPORTED_METHODS:
            return False, f"Unsupported method: {message.method.value}"

        # Check required params for request messages
        if (
            message.method
            in {
                A2AMessageType.TASK_PROPOSE,
                A2AMessageType.DELEGATE,
                A2AMessageType.CONSENSUS_PROPOSE,
            }
            and not message.params
        ):
            return False, "Missing required params"

        return True, None

    def route_message(
        self,
        message: A2AMessage,
    ) -> str | None:
        """
        Determine routing for a message based on target and type.

        Returns:
            Target agent ID or None for broadcast
        """
        if message.method in {
            A2AMessageType.CAPABILITY_QUERY,
            A2AMessageType.CONSENSUS_PROPOSE,
        }:
            return None  # Broadcast

        # Check for explicit target
        target = message.params.get("target_agent")
        if target:
            return target

        return None

    def process_message(self, message: A2AMessage) -> A2AMessage | None:
        """
        Process an incoming message and generate response.

        Returns:
            Response message or None
        """
        is_valid, error = self.validate_message(message)

        if not is_valid:
            return A2AMessage(
                method=A2AMessageType.ERROR,
                params={},
                error={
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": error,
                },
                correlation_id=message.id,
            )

        # Store in history
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history :]

        # Log message
        logger.debug(
            "a2a_message_processed",
            method=message.method.value,
            id=message.id,
            priority=message.priority.name,
        )

        return None  # Actual processing done by agents

    def get_capable_agents(
        self,
        capability_name: str,
        min_version: str | None = None,
    ) -> list[str]:
        """Find agents with a specific capability."""
        capable: list[str] = []
        for agent_id, capabilities in self._registered_agents.items():
            if self._agent_has_capability(agent_id, capabilities, capability_name, min_version):
                capable.append(agent_id)
        return capable

    def _agent_has_capability(
        self,
        agent_id: str,  # noqa: ARG002
        capabilities: list[Any],
        capability_name: str,
        min_version: str | None,
    ) -> bool:
        for cap in capabilities:
            if cap.name != capability_name:
                continue
            if min_version is None:
                return True
            if self._version_at_least(cap.version, min_version):
                return True
        return False

    def _version_at_least(self, version: str, min_version: str) -> bool:
        """Check if version meets minimum requirement."""
        v1_parts = [int(x) for x in version.split(".")]
        v2_parts = [int(x) for x in min_version.split(".")]

        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            if v1 > v2:
                return True
            if v1 < v2:
                return False
        return True


# Global protocol instance
_protocol: A2AProtocol | None = None


def get_protocol() -> A2AProtocol:
    """Get the global A2A protocol instance."""
    global _protocol
    if _protocol is None:
        _protocol = A2AProtocol()
    return _protocol


__all__ = [
    "A2AMessage",
    "A2AMessageType",
    "A2AProtocol",
    "AgentCapability",
    "MessagePriority",
    "create_consensus_message",
    "create_delegation_message",
    "create_task_request",
    "create_task_response",
    "get_protocol",
]
