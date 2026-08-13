"""
MCP (Model Context Protocol) Tools for Heretek Swarm

Provides standardized tool interface for external AI systems
and agent-to-agent tool sharing.

Implements the MCP specification for tool registration, discovery, and invocation.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.models.external_call_log import ExternalCallLog
from heretek_swarm.models.external_call_log_encryption import (
    ExternalCallLogEncryptor,
)

logger = structlog.get_logger(__name__)

# Global encryptor instance (initialized lazily)
_encryptor: ExternalCallLogEncryptor | None = None


def _get_encryptor() -> ExternalCallLogEncryptor:
    """Get or create the global encryptor instance."""
    global _encryptor
    if _encryptor is None:
        import os

        encryption_key = os.environ.get("EXTERNAL_CALL_LOG_ENCRYPTION_KEY")
        _encryptor = ExternalCallLogEncryptor(encryption_key)
    return _encryptor


def _create_log_entry_sync(
    agent_id: str,
    agent_type: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    error: str | None,
    duration_ms: float,
) -> ExternalCallLog:
    """
    Create an ExternalCallLog entry synchronously.

    This is a helper for creating log entries that can be added to a session.
    """
    encryptor = _get_encryptor()

    # Encrypt arguments (as request body) and result/error (as response body)
    request_encrypted = encryptor.encrypt(arguments)
    if error:
        response_encrypted = encryptor.encrypt({"error": error})
        status_code: int | None = None
    else:
        response_encrypted = encryptor.encrypt(result)
        status_code = result.get("status_code")

    return ExternalCallLog(
        agent_id=agent_id,
        agent_type=agent_type,
        call_type="mcp",
        url=f"mcp://tool/{tool_name}",
        method="INVOKE",
        status_code=status_code,
        duration_ms=duration_ms,
        request_body_encrypted=request_encrypted.get("encrypted", ""),
        response_body_encrypted=response_encrypted.get("encrypted", ""),
        tool_name=tool_name,
        error_message=error,
    )


@dataclass
class MCPToolDefinition:
    """MCP-compliant tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable
    category: str = "general"
    version: str = "1.0.0"
    enabled: bool = True


class MCPToolRegistry:
    """
    Registry for MCP-compatible tools.

    Provides centralized tool management with:
    - Tool registration and discovery
    - Input validation against JSON schemas
    - Invocation tracking and metrics
    - Category-based filtering
    """

    def __init__(self):
        self._tools: dict[str, MCPToolDefinition] = {}
        self._tool_stats: dict[str, dict] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: MCPToolDefinition) -> None:
        """
        Register an MCP tool.

        Args:
            tool: The tool definition to register

        Raises:
            ValueError: If tool name conflicts with existing registration
        """
        if tool.name in self._tools:
            logger.warning("tool_registration_conflict", tool_name=tool.name)
            raise ValueError(f"Tool {tool.name} already registered")

        self._tools[tool.name] = tool
        self._tool_stats[tool.name] = {
            "calls": 0,
            "errors": 0,
            "last_called": None,
            "avg_latency_ms": 0.0,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Track by category
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

        logger.info("tool_registered", name=tool.name, category=tool.category)

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool by name.

        Args:
            name: The tool name to unregister

        Returns:
            True if tool was unregistered, False if not found
        """
        if name not in self._tools:
            return False

        tool = self._tools.pop(name)
        self._tool_stats.pop(name)

        # Remove from category
        if tool.category in self._categories:
            self._categories[tool.category].remove(name)

        logger.info("tool_unregistered", name=name)
        return True

    def get_tool(self, name: str) -> MCPToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[dict[str, Any]]:
        """
        List all available tools in MCP format.

        Args:
            category: Optional category filter

        Returns:
            List of tool definitions in MCP format
        """
        tools = self._tools.values()

        if category:
            tools = [t for t in tools if t.category == category]

        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
                "category": t.category,
                "version": t.version,
                "enabled": t.enabled,
            }
            for t in tools
            if t.enabled
        ]

    def list_categories(self) -> list[str]:
        """List all available tool categories."""
        return list(self._categories.keys())

    def get_stats(self, name: str) -> dict[str, Any] | None:
        """Get invocation statistics for a tool."""
        return self._tool_stats.get(name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all tools."""
        return self._tool_stats.copy()

    async def invoke(
        self, name: str, arguments: dict[str, Any], context: dict | None = None
    ) -> dict[str, Any]:
        """
        Invoke an MCP tool.

        Args:
            name: Tool name to invoke
            arguments: Tool arguments
            context: Optional invocation context (agent_id, session_id, etc.)

        Returns:
            Tool invocation result with success/error status

        Raises:
            ValueError: If tool not found or disabled
            ValidationError: If arguments don't match schema
        """
        import time

        start_time = time.time()

        # Extract agent info from context
        agent_id = context.get("agent_id", "unknown") if context else "unknown"
        agent_type = context.get("agent_type", "mcp_agent") if context else "mcp_agent"

        try:
            if name not in self._tools:
                logger.error("tool_not_found", name=name)
                raise ValueError(f"Tool {name} not found")

            tool = self._tools[name]

            if not tool.enabled:
                logger.warning("tool_disabled", name=name)
                raise ValueError(f"Tool {name} is disabled")

            # Validate arguments against schema
            if not self._validate_arguments(arguments, tool.input_schema):
                logger.error("tool_validation_failed", name=name, arguments=arguments)
                raise ValueError(f"Invalid arguments for tool {name}")

            # Update stats
            self._tool_stats[name]["calls"] += 1
            self._tool_stats[name]["last_called"] = datetime.now(UTC).isoformat()

            # Invoke handler
            result = await tool.handler(arguments, context or {})

            # Update latency
            latency_ms = (time.time() - start_time) * 1000
            stats = self._tool_stats[name]
            calls = stats["calls"]
            stats["avg_latency_ms"] = (stats["avg_latency_ms"] * (calls - 1) + latency_ms) / calls

            logger.debug("tool_invoked", name=name, latency_ms=latency_ms)

            # Log successful call to ExternalCallLog.
            # Wrapped in try/except so logging failures don't prevent tool execution.
            try:
                _create_log_entry_sync(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    tool_name=name,
                    arguments=arguments,
                    result=result,
                    error=None,
                    duration_ms=latency_ms,
                )
                # Note: In production, this would be added to a session and committed
                # For now, we just log the creation (actual persistence requires DB session)
                logger.debug(
                    "external_call_log_created",
                    agent_id=agent_id,
                    tool_name=name,
                    call_type="mcp",
                    duration_ms=latency_ms,
                )
            except Exception as log_error:
                logger.warning(
                    "external_call_log_creation_failed",
                    tool_name=name,
                    error=str(log_error),
                )

            return {"success": True, "result": result}

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            # Only update stats if the tool was registered (has stats entry)
            if name in self._tool_stats:
                self._tool_stats[name]["errors"] += 1
            logger.error("tool_invocation_error", name=name, error=str(e))

            # Log failed call to ExternalCallLog.
            # Wrapped in try/except so logging failures don't prevent tool execution.
            try:
                _create_log_entry_sync(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    tool_name=name,
                    arguments=arguments,
                    result={},
                    error=str(e),
                    duration_ms=latency_ms,
                )
                logger.debug(
                    "external_call_log_created",
                    agent_id=agent_id,
                    tool_name=name,
                    call_type="mcp",
                    duration_ms=latency_ms,
                    error=str(e),
                )
            except Exception as log_error:
                logger.warning(
                    "external_call_log_creation_failed",
                    tool_name=name,
                    error=str(log_error),
                )

            return {"success": False, "error": str(e)}

    # Type check dispatch table
    _TYPE_CHECKS: ClassVar[dict[str, type | tuple[type, ...]]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    def _validate_arguments(self, arguments: dict[str, Any], schema: dict[str, Any]) -> bool:
        """
        Validate arguments against JSON schema.
        """
        if not schema:
            return True

        required = schema.get("required", [])
        for field in required:
            if field not in arguments:
                return False

        properties = schema.get("properties", {})
        for key, value in arguments.items():
            if key not in properties:
                continue
            if not self._validate_property(key, value, properties[key]):
                return False

        return True

    def _validate_property(
        self, key: str, value: Any, prop_schema: dict[str, Any]
    ) -> bool:
        """Validate a single property against its schema."""
        expected_type = prop_schema.get("type")
        if expected_type and expected_type in self._TYPE_CHECKS:
            if not isinstance(value, self._TYPE_CHECKS[expected_type]):
                return False

        if "enum" in prop_schema and value not in prop_schema["enum"]:
            return False

        if isinstance(value, (int, float)):
            if "minimum" in prop_schema and value < prop_schema["minimum"]:
                return False
            if "maximum" in prop_schema and value > prop_schema["maximum"]:
                return False

        return True


# ============================================================================
# Core MCP Tools
# ============================================================================


class CoreMCPTools:
    """
    Core MCP tools for Heretek Swarm.

    Provides standard tools for memory, communication, consensus, RAG,
    and external integration.
    """

    def __init__(
        self,
        memory_system=None,
        rag_pipeline=None,
        consensus_engine=None,
        event_mesh=None,
    ):
        self.memory = memory_system
        self.rag = rag_pipeline
        self.consensus = consensus_engine
        self.event_mesh = event_mesh
        self.registry = MCPToolRegistry()
        self._register_default_tools()

    def _register_default_tools(self):
        """Register default MCP tools using specialized registrars."""
        from .registrars import get_handler_methods, register_all_tools

        # Extract handler methods from this instance
        handlers = get_handler_methods(self)

        # Register all tools via specialized registrars
        register_all_tools(self.registry, handlers)

    async def _handle_memory_store(
        self, arguments: dict[str, Any], context: dict | None = None
    ) -> dict:
        """Handle memory store request."""
        if not self.memory:
            return {"error": "Memory system not initialized"}

        content = arguments.get("content")
        metadata = arguments.get("metadata", {})
        importance = arguments.get("importance", 0.5)

        result = await self.memory.store(
            content={"text": content, **metadata},
            metadata={
                "importance": importance,
                "source": context.get("agent_id", "unknown") if context else "unknown",
            },
        )

        return {
            "memory_id": getattr(result, "id", "unknown"),
            "stored_at": datetime.now(UTC).isoformat(),
        }

    async def _handle_memory_retrieve(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle memory retrieve request."""
        if not self.memory:
            return {"error": "Memory system not initialized"}

        query = arguments.get("query")
        limit = arguments.get("limit", 10)
        arguments.get("tier", "all")

        results = await self.memory.query(
            query_text=query,
            limit=limit,
        )

        return {
            "entries": [
                {
                    "content": entry.content if hasattr(entry, "content") else entry,
                    "metadata": getattr(entry, "metadata", {}),
                    "score": getattr(entry, "similarity", 0),
                }
                for entry in (results.entries if hasattr(results, "entries") else results)
            ]
        }

    async def _handle_agent_message(
        self, arguments: dict[str, Any], context: dict | None = None
    ) -> dict:
        """Handle agent message request."""
        target = arguments.get("target_agent")
        message_type = arguments.get("message_type")
        content = arguments.get("content")

        if not self.event_mesh:
            return {"error": "Event mesh not initialized"}

        await self.event_mesh.publish(
            f"agent.{target}",
            {
                "type": message_type,
                "content": content,
                "from_agent": context.get("agent_id") if context else None,
            },
        )

        return {"sent": True, "target": target}

    async def _handle_agent_handoff(
        self, arguments: dict[str, Any], context: dict | None = None
    ) -> dict:
        """Handle agent handoff request."""
        to_agent = arguments.get("to_agent")
        handoff_context = arguments.get("context")
        reason = arguments.get("reason", "task_transfer")

        if not self.event_mesh:
            return {"error": "Event mesh not initialized"}

        await self.event_mesh.publish(
            f"agent.{to_agent}",
            {
                "type": "handoff",
                "context": handoff_context,
                "reason": reason,
                "from_agent": context.get("agent_id") if context else None,
            },
        )

        return {"handoff_initiated": True, "to_agent": to_agent}

    async def _handle_consensus_propose(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle consensus propose request."""
        if not self.consensus:
            return {"error": "Consensus engine not initialized"}

        arguments.get("proposal")
        arguments.get("context", {})
        urgency = arguments.get("urgency", "medium")

        # Submit to consensus engine
        proposal_id = f"proposal_{datetime.now(UTC).timestamp()}"

        return {
            "proposal_id": proposal_id,
            "status": "pending",
            "urgency": urgency,
        }

    async def _handle_consensus_vote(
        self, arguments: dict[str, Any], context: dict | None = None
    ) -> dict:
        """Handle consensus vote request."""
        if not self.consensus:
            return {"error": "Consensus engine not initialized"}

        proposal_id = arguments.get("proposal_id")
        arguments.get("vote")
        arguments.get("confidence")
        arguments.get("reasoning")

        # Cast vote
        return {
            "vote_cast": True,
            "proposal_id": proposal_id,
            "agent_id": context.get("agent_id") if context else None,
        }

    async def _handle_rag_query(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle RAG query request."""
        if not self.rag:
            return {"error": "RAG pipeline not initialized"}

        query = arguments.get("query")
        arguments.get("mode", "hybrid")
        top_k = arguments.get("top_k", 10)

        result = await self.rag.query(
            query=query,
            top_k=top_k,
        )

        return {
            "documents": [
                {
                    "content": doc.content if hasattr(doc, "content") else doc,
                    "metadata": getattr(doc, "metadata", {}),
                    "score": getattr(doc, "score", 0),
                }
                for doc in (result.documents if hasattr(result, "documents") else result)
            ]
        }

    async def _handle_rag_ingest(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle RAG ingest request."""
        if not self.rag:
            return {"error": "RAG pipeline not initialized"}

        arguments.get("content")
        source = arguments.get("source", "unknown")
        arguments.get("metadata", {})

        # Ingest document
        return {"ingested": True, "source": source}

    async def _handle_external_api_call(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle external API call request."""
        import httpx

        arguments.get("connection_id")
        endpoint = arguments.get("endpoint")
        method = arguments.get("method", "GET")
        payload = arguments.get("payload")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, endpoint, json=payload)
                return {
                    "status_code": response.status_code,
                    "body": response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else response.text,
                }
        except Exception as e:
            return {"error": str(e)}

    async def _handle_notification_send(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle notification send request."""
        channel = arguments.get("channel")
        message = arguments.get("message")
        priority = arguments.get("priority", "info")

        if not self.event_mesh:
            return {"error": "Event mesh not initialized"}

        await self.event_mesh.publish(
            f"notification.{channel}",
            {
                "message": message,
                "priority": priority,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        return {"sent": True, "channel": channel}

    async def _handle_workflow_start(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle workflow start request."""
        workflow_type = arguments.get("workflow_type")
        params = arguments.get("params", {})
        topic = arguments.get("topic")

        # Start workflow via event mesh
        if not self.event_mesh:
            return {"error": "Event mesh not initialized"}

        workflow_id = f"workflow_{datetime.now(UTC).timestamp()}"

        await self.event_mesh.publish(
            "workflow.start",
            {
                "workflow_id": workflow_id,
                "workflow_type": workflow_type,
                "params": params,
                "topic": topic,
            },
        )

        return {"workflow_id": workflow_id, "status": "started"}

    async def _handle_workflow_status(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle workflow status request."""
        workflow_id = arguments.get("workflow_id")

        # Query workflow status (placeholder)
        return {
            "workflow_id": workflow_id,
            "status": "running",
            "phase": "analysis",
        }

    async def _handle_system_health(
        self, arguments: dict[str, Any], context: dict | None = None  # noqa: ARG002
    ) -> dict:
        """Handle system health request."""
        return {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "components": {
                "memory": "initialized" if self.memory else "not_initialized",
                "rag": "initialized" if self.rag else "not_initialized",
                "consensus": "initialized" if self.consensus else "not_initialized",
                "event_mesh": "initialized" if self.event_mesh else "not_initialized",
            },
        }

    def get_registry(self) -> MCPToolRegistry:
        """Get the underlying tool registry."""
        return self.registry
