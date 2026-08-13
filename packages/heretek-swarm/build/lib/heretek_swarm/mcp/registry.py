"""
MCP Tool Registry

Provides centralized tool management for MCP protocol:
- Tool registration and discovery
- Metadata management with input/output schemas
- Tool execution with proper error handling
- Statistics tracking
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Persisted tool state
# ---------------------------------------------------------------------------

TOOLS_STATE_FILE = Path.home() / ".heretek-swarm" / "tools_state.json"
"""Path to per-user persistence file for tool enabled/disabled states.

Using ``Path.home()`` so the same file is used regardless of which directory
the daemon is started from.  Tests override this by patching the module-level
constant or setting ``HEREKET_CONFIG_DIR`` before import.
"""


class ToolProviderType(StrEnum):
    """Source of the tool."""

    LOCAL = "local"
    EXTERNAL = "external"
    PROXIED = "proxied"


class ToolStatus(StrEnum):
    """Tool execution status."""

    READY = "ready"
    RUNNING = "running"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class MCPToolMetadata:
    """MCP tool metadata."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    category: str = "general"
    version: str = "1.0.0"
    provider: ToolProviderType = ToolProviderType.LOCAL
    server_id: str | None = None
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MCPToolInvocation:
    """Record of a tool invocation."""

    invocation_id: UUID
    tool_name: str
    arguments: dict[str, Any]
    context: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None = None
    success: bool | None = None
    result: Any = None
    error: str | None = None


class MCPToolRegistry:
    """
    Registry for MCP tools.

    Provides centralized tool management with:
    - Tool registration and discovery
    - Input validation against JSON schemas
    - Invocation tracking and metrics
    - Category-based filtering
    """

    def __init__(self) -> None:
        self._tools: dict[str, MCPToolMetadata] = {}
        self._handlers: dict[str, Any] = {}
        self._invocations: dict[UUID, MCPToolInvocation] = {}
        self._stats: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        metadata: MCPToolMetadata,
        handler: Any,
    ) -> None:
        """
        Register an MCP tool.

        Args:
            metadata: Tool metadata including name, description, schemas
            handler: Callable that executes the tool

        Raises:
            ValueError: If tool name conflicts with existing registration
        """
        if metadata.name in self._tools:
            logger.warning("mcp_tool_registration_conflict", tool_name=metadata.name)
            raise ValueError(f"Tool {metadata.name} already registered")

        self._tools[metadata.name] = metadata
        self._handlers[metadata.name] = handler
        self._stats[metadata.name] = {
            "calls": 0,
            "errors": 0,
            "last_called": None,
            "avg_latency_ms": 0.0,
            "created_at": datetime.now(UTC).isoformat(),
        }

        logger.info(
            "mcp_tool_registered",
            name=metadata.name,
            category=metadata.category,
            provider=metadata.provider.value,
        )

    # ------------------------------------------------------------------
    # Tool state persistence
    # ------------------------------------------------------------------

    def _load_tool_states(self) -> dict[str, bool]:
        """Load persisted tool enabled/disabled states from disk.

        Returns a ``dict`` mapping tool name → enabled flag, or an empty
        ``dict`` when the file is missing, unparseable, or an OS error occurs.
        """
        try:
            raw = TOOLS_STATE_FILE.read_text(encoding="utf-8")
        except OSError:
            return {}

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "tools_state_load_failed",
                error=str(exc),
                path=str(TOOLS_STATE_FILE),
            )
            return {}

        tool_states: dict[str, bool] = {}
        states = data.get("tool_states", {})
        for name, val in states.items():
            if isinstance(val, bool):
                tool_states[name] = val  # noqa: PERF403
        return tool_states

    def _save_tool_states(self) -> None:
        """Persist current tool enabled/disabled states to disk atomically.

        Writes to a ``.tmp`` file, flushes, fsyncs, and then atomically
        replaces the real file so a crash mid-write never corrupts
        ``tools_state.json``.
        """
        payload: dict[str, Any] = {
            "version": "1.0.0",
            "tool_states": {name: meta.enabled for name, meta in self._tools.items()},
        }

        tmp_path = Path(str(TOOLS_STATE_FILE) + ".tmp")

        try:
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(payload, indent=2, sort_keys=True)
            tmp_path.write_text(raw, encoding="utf-8")
            tmp_fd = os.open(str(tmp_path), os.O_RDWR)
            try:
                os.fsync(tmp_fd)
            finally:
                os.close(tmp_fd)
            os.replace(str(tmp_path), str(TOOLS_STATE_FILE))  # noqa: PTH105
        except OSError as exc:
            logger.error(
                "tools_state_save_failed",
                error=str(exc),
                path=str(TOOLS_STATE_FILE),
            )
            # Best-effort cleanup of the temp file.
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)

    def set_tool_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a registered tool by name.

        Returns ``True`` if the tool was found and the state was persisted,
        ``False`` if the tool name is unknown (persistence is skipped).
        """
        tool = self._tools.get(name)
        if tool is None:
            return False

        tool.enabled = enabled
        self._save_tool_states()
        logger.info(
            "mcp_tool_toggled",
            name=name,
            enabled=enabled,
        )
        return True

    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool by name.

        Args:
            name: The tool name to unregister

        Returns:
            True if tool was unregistered, False if not found
        """
        if name not in self._tools:
            return False

        self._tools.pop(name)
        self._handlers.pop(name)
        self._stats.pop(name)

        logger.info("mcp_tool_unregistered", name=name)
        return True

    def get_tool(self, name: str) -> MCPToolMetadata | None:
        """Get tool metadata by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> Any | None:
        """Get tool handler by name."""
        return self._handlers.get(name)

    def list_tools(
        self,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[MCPToolMetadata]:
        """
        List all available tools.

        Args:
            category: Optional category filter
            enabled_only: If True, only return enabled tools

        Returns:
            List of tool metadata
        """
        tools = self._tools.values()

        if category:
            tools = [t for t in tools if t.category == category]

        if enabled_only:
            tools = [t for t in tools if t.enabled]

        return list(tools)

    def list_tool_summaries(
        self,
        enabled_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List tools in MCP protocol format.

        Args:
            enabled_only: If True (default), only enabled tools are included.
                Set to False to include disabled tools (with ``"enabled": false``)
                for dashboard / admin views.
        """
        tools = self._tools.values()
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
                "outputSchema": t.output_schema,
                "category": t.category,
                "version": t.version,
                "provider": t.provider.value,
                "serverId": t.server_id,
                "enabled": t.enabled,
            }
            for t in tools
        ]

    def get_stats(self, name: str) -> dict[str, Any] | None:
        """Get invocation statistics for a tool."""
        return self._stats.get(name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all tools."""
        return self._stats.copy()

    def invoke_sync(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Synchronously invoke an MCP tool.

        Args:
            name: Tool name to invoke
            arguments: Tool arguments
            context: Optional invocation context

        Returns:
            Tool invocation result
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a new task
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.invoke(name, arguments, context))
                    return future.result()
            return loop.run_until_complete(self.invoke(name, arguments, context))
        except RuntimeError:
            # No event loop in current thread, create new one
            return asyncio.run(self.invoke(name, arguments, context))

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
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
        """
        import time

        start_time = time.time()
        invocation_id = uuid4()

        invocation = MCPToolInvocation(
            invocation_id=invocation_id,
            tool_name=name,
            arguments=arguments,
            context=context,
            started_at=datetime.now(UTC),
        )
        self._invocations[invocation_id] = invocation

        # Resolve tool and validate preconditions
        precheck = self._resolve_tool_for_invocation(name, invocation)
        if precheck is not None:
            return precheck

        tool = self._tools[name]

        # Validate arguments
        if not self._validate_arguments(arguments, tool.input_schema):
            self._record_invocation_error(invocation, f"Invalid arguments for tool {name}")
            logger.error("mcp_tool_validation_failed", name=name, arguments=arguments)
            return {"success": False, "error": f"Invalid arguments for tool {name}"}

        # Update stats
        self._stats[name]["calls"] += 1
        self._stats[name]["last_called"] = datetime.now(UTC).isoformat()

        # Execute handler and record outcome
        return await self._execute_handler_and_record(
            name, invocation, arguments, context or {}, start_time
        )

    def _resolve_tool_for_invocation(
        self,
        name: str,
        invocation: MCPToolInvocation,
    ) -> dict[str, Any] | None:
        """
        Resolve tool and check preconditions before invocation.

        Returns:
            Error dict if precondition fails, None if tool is ready to invoke.
        """
        if name not in self._tools:
            logger.error("mcp_tool_not_found", name=name)
            self._record_invocation_error(invocation, f"Tool {name} not found")
            return {"success": False, "error": f"Tool {name} not found"}

        tool = self._tools[name]

        if not tool.enabled:
            logger.warning("mcp_tool_disabled", name=name)
            self._record_invocation_error(invocation, f"Tool {name} is disabled")
            return {"success": False, "error": f"Tool {name} is disabled"}

        return None

    def _record_invocation_error(
        self,
        invocation: MCPToolInvocation,
        error_message: str,
    ) -> None:
        """Record an error on an invocation record."""
        invocation.error = error_message
        invocation.completed_at = datetime.now(UTC)

    async def _execute_handler_and_record(
        self,
        name: str,
        invocation: MCPToolInvocation,
        arguments: dict[str, Any],
        context: dict[str, Any],
        start_time: float,
    ) -> dict[str, Any]:
        """Execute the tool handler and record the invocation outcome."""
        import time

        try:
            handler = self._handlers[name]
            result = handler(arguments, context)
            if asyncio.iscoroutine(result):
                result = await result

            latency_ms = (time.time() - start_time) * 1000
            self._update_success_stats(name, latency_ms)
            self._record_invocation_success(invocation, result)
            logger.debug("mcp_tool_invoked", name=name, latency_ms=latency_ms)
            return {"success": True, "result": result}

        except Exception as e:
            self._stats[name]["errors"] += 1
            invocation.success = False
            invocation.error = str(e)
            invocation.completed_at = datetime.now(UTC)
            logger.error("mcp_tool_invocation_error", name=name, error=str(e))
            return {"success": False, "error": str(e)}

    def _record_invocation_success(
        self,
        invocation: MCPToolInvocation,
        result: Any,
    ) -> None:
        """Record a successful result on an invocation record."""
        invocation.success = True
        invocation.result = result
        invocation.completed_at = datetime.now(UTC)

    def _update_success_stats(self, name: str, latency_ms: float) -> None:
        """Update latency statistics after a successful invocation."""
        stats = self._stats[name]
        calls = stats["calls"]
        stats["avg_latency_ms"] = (stats["avg_latency_ms"] * (calls - 1) + latency_ms) / calls

    def _validate_arguments(
        self,
        arguments: dict[str, Any],
        schema: dict[str, Any],
    ) -> bool:
        """
        Validate arguments against JSON schema.

        Args:
            arguments: Arguments to validate
            schema: JSON schema to validate against

        Returns:
            True if valid, False otherwise
        """
        if not schema:
            return True

        if not self._validate_required_fields(arguments, schema):
            return False

        return self._validate_all_properties(arguments, schema)

    def _validate_required_fields(
        self,
        arguments: dict[str, Any],
        schema: dict[str, Any],
    ) -> bool:
        """Check that all required fields are present."""
        required = schema.get("required", [])
        return all(field_name in arguments for field_name in required)

    def _validate_all_properties(
        self,
        arguments: dict[str, Any],
        schema: dict[str, Any],
    ) -> bool:
        """Validate all argument properties against their schemas."""
        properties = schema.get("properties", {})
        for key, value in arguments.items():
            if key in properties:
                prop_schema = properties[key]
                if not self._validate_single_property(value, prop_schema):
                    return False
        return True

    def _validate_single_property(
        self,
        value: Any,
        prop_schema: dict[str, Any],
    ) -> bool:
        """Validate a single property against its schema."""
        if not self._check_type_constraint(value, prop_schema):
            return False
        if not self._check_enum_constraint(value, prop_schema):
            return False
        if not self._check_numeric_bounds(value, prop_schema):
            return False
        return self._check_string_length(value, prop_schema)

    def _check_type_constraint(
        self,
        value: Any,
        prop_schema: dict[str, Any],
    ) -> bool:
        """Validate value type matches the schema type."""
        expected_type = prop_schema.get("type")
        if expected_type is None:
            return True

        type_checks = (
            (expected_type == "string", str),
            (expected_type == "integer", int),
            (expected_type == "number", (int, float)),
            (expected_type == "boolean", bool),
            (expected_type == "array", list),
            (expected_type == "object", dict),
        )
        for matches, expected in type_checks:
            if matches:
                return isinstance(value, expected)
        return True

    def _check_enum_constraint(
        self,
        value: Any,
        prop_schema: dict[str, Any],
    ) -> bool:
        """Validate value is one of the allowed enum values."""
        if "enum" not in prop_schema:
            return True
        return value in prop_schema["enum"]

    def _check_numeric_bounds(
        self,
        value: Any,
        prop_schema: dict[str, Any],
    ) -> bool:
        """Validate numeric value is within min/max bounds."""
        if not isinstance(value, (int, float)):
            return True
        if "minimum" in prop_schema and value < prop_schema["minimum"]:
            return False
        return not ("maximum" in prop_schema and value > prop_schema["maximum"])

    def _check_string_length(
        self,
        value: Any,
        prop_schema: dict[str, Any],
    ) -> bool:
        """Validate string length is within min/max bounds."""
        if not isinstance(value, str):
            return True
        if "minLength" in prop_schema and len(value) < prop_schema["minLength"]:
            return False
        return not ("maxLength" in prop_schema and len(value) > prop_schema["maxLength"])


class MCPServerRegistry:
    """
    Registry for MCP servers.

    Manages external MCP server connections and proxies tools
    from external servers into the local registry.
    """

    def __init__(self) -> None:
        self._servers: dict[str, dict[str, Any]] = {}
        self._server_clients: dict[str, Any] = {}

    def register_server(
        self,
        server_id: str,
        name: str,
        base_url: str,
        auth_token: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Register an MCP server connection.

        Args:
            server_id: Unique server identifier
            name: Human-readable server name
            base_url: Server base URL
            auth_token: Optional authentication token
            metadata: Additional server metadata
        """
        if server_id in self._servers:
            raise ValueError(f"Server {server_id} already registered")

        self._servers[server_id] = {
            "server_id": server_id,
            "name": name,
            "base_url": base_url,
            "auth_token": auth_token,
            "metadata": metadata or {},
            "status": "disconnected",
            "registered_at": datetime.now(UTC).isoformat(),
        }

        logger.info("mcp_server_registered", server_id=server_id, name=name)

    def unregister_server(self, server_id: str) -> bool:
        """Unregister an MCP server."""
        if server_id not in self._servers:
            return False

        self._servers.pop(server_id)
        self._server_clients.pop(server_id, None)

        logger.info("mcp_server_unregistered", server_id=server_id)
        return True

    def get_server(self, server_id: str) -> dict[str, Any] | None:
        """Get server configuration."""
        return self._servers.get(server_id)

    def list_servers(self) -> list[dict[str, Any]]:
        """List all registered servers."""
        return [
            {
                "server_id": s["server_id"],
                "name": s["name"],
                "base_url": s["base_url"],
                "status": s["status"],
                "metadata": s["metadata"],
            }
            for s in self._servers.values()
        ]

    def update_server_status(
        self,
        server_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update server connection status."""
        if server_id in self._servers:
            self._servers[server_id]["status"] = status
            self._servers[server_id]["last_error"] = error
            self._servers[server_id]["last_updated"] = datetime.now(UTC).isoformat()

    def set_client(self, server_id: str, client: Any) -> None:
        """Set the client instance for a server."""
        self._server_clients[server_id] = client

    def get_client(self, server_id: str) -> Any | None:
        """Get the client instance for a server."""
        return self._server_clients.get(server_id)
