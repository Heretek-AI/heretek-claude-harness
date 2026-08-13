"""
A2A (Agent-to-Agent) Protocol Infrastructure.

Provides structured communication between agents using the Agent-to-Agent protocol.
Based on JSON-RPC 2.0 specification with extensions for swarm coordination.
"""

from heretek_swarm.infrastructure.a2a.protocol import (
    A2AMessage,
    A2AMessageType,
    A2AProtocol,
    AgentCapability,
    MessagePriority,
    create_consensus_message,
    create_delegation_message,
    create_task_request,
    create_task_response,
)

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
]
