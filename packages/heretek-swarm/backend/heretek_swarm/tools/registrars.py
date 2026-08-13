"""Tool registration helpers by category.

This module provides specialized registrars for organizing MCP tool
registrations into maintainable, focused components.
"""

from collections.abc import Callable
from typing import Any

import structlog

from .mcp_tools import MCPToolDefinition, MCPToolRegistry

logger = structlog.get_logger(__name__)


class BaseToolRegistrar:
    """Base class for tool registrars."""

    def __init__(self, registry: MCPToolRegistry, handlers: dict[str, Callable]):
        self._registry = registry
        self._handlers = handlers

    def register(self) -> None:
        """Register all tools in this category."""
        for handler in self._handlers.values():
            handler()


class MemoryToolsRegistrar(BaseToolRegistrar):
    """Register memory-related MCP tools."""

    def register(self) -> None:
        """Register all memory tools."""
        self._registry.register(
            MCPToolDefinition(
                name="memory_store",
                description="Store information in collective memory with optional metadata and importance weighting",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to store"},
                        "metadata": {"type": "object", "description": "Additional metadata"},
                        "importance": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "default": 0.5,
                        },
                    },
                    "required": ["content"],
                },
                handler=self._handlers.get("_handle_memory_store"),
                category="memory",
            )
        )

        self._registry.register(
            MCPToolDefinition(
                name="memory_retrieve",
                description="Retrieve relevant memories by semantic query",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                        "tier": {
                            "type": "string",
                            "enum": ["ephemeral", "persistent", "all"],
                            "default": "all",
                        },
                    },
                    "required": ["query"],
                },
                handler=self._handlers.get("_handle_memory_retrieve"),
                category="memory",
            )
        )


class CommunicationToolsRegistrar(BaseToolRegistrar):
    """Register communication-related MCP tools."""

    def register(self) -> None:
        """Register all communication tools."""
        self._registry.register(
            MCPToolDefinition(
                name="agent_message",
                description="Send a message to another agent",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_agent": {"type": "string", "description": "Target agent ID"},
                        "message_type": {"type": "string", "description": "Message type"},
                        "content": {"type": "object", "description": "Message content"},
                        "reply_expected": {"type": "boolean", "default": False},
                    },
                    "required": ["target_agent", "message_type", "content"],
                },
                handler=self._handlers.get("_handle_agent_message"),
                category="communication",
            )
        )

        self._registry.register(
            MCPToolDefinition(
                name="agent_handoff",
                description="Transfer task context to another agent",
                input_schema={
                    "type": "object",
                    "properties": {
                        "to_agent": {"type": "string", "description": "Target agent ID"},
                        "context": {"type": "object", "description": "Task context"},
                        "reason": {"type": "string", "description": "Handoff reason"},
                    },
                    "required": ["to_agent", "context"],
                },
                handler=self._handlers.get("_handle_agent_handoff"),
                category="communication",
            )
        )


class ConsensusToolsRegistrar(BaseToolRegistrar):
    """Register consensus-related MCP tools."""

    def register(self) -> None:
        """Register all consensus tools."""
        self._registry.register(
            MCPToolDefinition(
                name="consensus_propose",
                description="Submit a proposal for collective decision via MAKER consensus",
                input_schema={
                    "type": "object",
                    "properties": {
                        "proposal": {"type": "string", "description": "Proposal text"},
                        "context": {"type": "object", "description": "Proposal context"},
                        "urgency": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "default": "medium",
                        },
                    },
                    "required": ["proposal"],
                },
                handler=self._handlers.get("_handle_consensus_propose"),
                category="consensus",
            )
        )

        self._registry.register(
            MCPToolDefinition(
                name="consensus_vote",
                description="Cast a vote on an active proposal",
                input_schema={
                    "type": "object",
                    "properties": {
                        "proposal_id": {"type": "string", "description": "Proposal ID"},
                        "vote": {"type": "string", "description": "Vote value"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence level",
                        },
                        "reasoning": {"type": "string", "description": "Vote reasoning"},
                    },
                    "required": ["proposal_id", "vote", "confidence"],
                },
                handler=self._handlers.get("_handle_consensus_vote"),
                category="consensus",
            )
        )


class RAGToolsRegistrar(BaseToolRegistrar):
    """Register RAG-related MCP tools."""

    def register(self) -> None:
        """Register all RAG tools."""
        self._registry.register(
            MCPToolDefinition(
                name="rag_query",
                description="Query the RAG knowledge base",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "mode": {
                            "type": "string",
                            "enum": ["vector", "keyword", "hybrid"],
                            "default": "hybrid",
                        },
                        "top_k": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    },
                    "required": ["query"],
                },
                handler=self._handlers.get("_handle_rag_query"),
                category="knowledge",
            )
        )

        self._registry.register(
            MCPToolDefinition(
                name="rag_ingest",
                description="Ingest a document into the RAG system",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Document content"},
                        "source": {"type": "string", "description": "Document source"},
                        "metadata": {"type": "object", "description": "Document metadata"},
                    },
                    "required": ["content"],
                },
                handler=self._handlers.get("_handle_rag_ingest"),
                category="knowledge",
            )
        )


class IntegrationToolsRegistrar(BaseToolRegistrar):
    """Register integration-related MCP tools."""

    def register(self) -> None:
        """Register all integration tools."""
        self._registry.register(
            MCPToolDefinition(
                name="external_api_call",
                description="Make an authenticated external API call",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection_id": {"type": "string", "description": "Connection ID"},
                        "endpoint": {"type": "string", "description": "API endpoint"},
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        },
                        "payload": {"type": "object", "description": "Request payload"},
                    },
                    "required": ["connection_id", "endpoint", "method"],
                },
                handler=self._handlers.get("_handle_external_api_call"),
                category="integration",
            )
        )

        self._registry.register(
            MCPToolDefinition(
                name="notification_send",
                description="Send a notification to external channels",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "enum": ["discord", "slack", "telegram", "all"],
                            "description": "Notification channel",
                        },
                        "message": {"type": "string", "description": "Notification message"},
                        "priority": {
                            "type": "string",
                            "enum": ["info", "warning", "error", "critical"],
                            "default": "info",
                        },
                    },
                    "required": ["channel", "message"],
                },
                handler=self._handlers.get("_handle_notification_send"),
                category="integration",
            )
        )


class WorkflowToolsRegistrar(BaseToolRegistrar):
    """Register workflow-related MCP tools."""

    def register(self) -> None:
        """Register all workflow tools."""
        self._registry.register(
            MCPToolDefinition(
                name="workflow_start",
                description="Start a new workflow execution",
                input_schema={
                    "type": "object",
                    "properties": {
                        "workflow_type": {
                            "type": "string",
                            "description": "Workflow type (e.g., 'heavyswarm')",
                        },
                        "params": {"type": "object", "description": "Workflow parameters"},
                        "topic": {"type": "string", "description": "Workflow topic"},
                    },
                    "required": ["workflow_type"],
                },
                handler=self._handlers.get("_handle_workflow_start"),
                category="workflow",
            )
        )

        self._registry.register(
            MCPToolDefinition(
                name="workflow_status",
                description="Get the status of a running workflow",
                input_schema={
                    "type": "object",
                    "properties": {"workflow_id": {"type": "string", "description": "Workflow ID"}},
                    "required": ["workflow_id"],
                },
                handler=self._handlers.get("_handle_workflow_status"),
                category="workflow",
            )
        )


class SystemToolsRegistrar(BaseToolRegistrar):
    """Register system-related MCP tools."""

    def register(self) -> None:
        """Register all system tools."""
        self._registry.register(
            MCPToolDefinition(
                name="system_health",
                description="Get system health status",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=self._handlers.get("_handle_system_health"),
                category="system",
            )
        )


# Registry of all registrars for easy iteration
TOOL_REGISTRARS = [
    MemoryToolsRegistrar,
    CommunicationToolsRegistrar,
    ConsensusToolsRegistrar,
    RAGToolsRegistrar,
    IntegrationToolsRegistrar,
    WorkflowToolsRegistrar,
    SystemToolsRegistrar,
]


def get_handler_methods(obj: Any) -> dict[str, Callable]:
    """Extract all handler methods from an object.

    Args:
        obj: The object containing handler methods

    Returns:
        Dict mapping method names to method references
    """
    return {
        name: getattr(obj, name)
        for name in dir(obj)
        if name.startswith("_handle_") and callable(getattr(obj, name))
    }


def register_all_tools(registry: MCPToolRegistry, handlers: dict[str, Callable]) -> None:
    """Register all default tools using specialized registrars.

    Args:
        registry: The MCP tool registry to register with
        handlers: Dict of handler method references
    """
    for registrar_class in TOOL_REGISTRARS:
        registrar = registrar_class(registry, handlers)
        registrar.register()
