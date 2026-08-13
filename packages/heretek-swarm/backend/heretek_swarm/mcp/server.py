"""
MCP (Model Context Protocol) Server Implementation

Provides HTTP server implementing MCP protocol handlers:
- GET /tools/list - List available tools
- POST /tools/call - Execute a tool
- GET /tools/{name} - Get tool details
- GET /health - Server health check

Uses FastAPI/Starlette for HTTP handling with proper
async support and structured logging.
"""

from __future__ import annotations

import time as _time_module
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.mcp.registry import MCPToolRegistry

logger = structlog.get_logger("mcp.server")

# Global registry instance
_registry: MCPToolRegistry | None = None


def get_registry() -> MCPToolRegistry:
    """Get the global MCP tool registry."""
    global _registry
    if _registry is None:
        _registry = MCPToolRegistry()
    return _registry


def set_registry(registry: MCPToolRegistry) -> None:
    """Set the global MCP tool registry."""
    global _registry
    _registry = registry


# =============================================================================
# MCP Request/Response Models
# =============================================================================


class ToolCallRequest(BaseModel):
    """Request to call an MCP tool."""

    name: str = Field(..., description="Tool name to invoke")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    context: dict[str, Any] | None = Field(default=None, description="Invocation context")


class ToolCallResponse(BaseModel):
    """Response from tool invocation."""

    success: bool
    result: Any | None = None
    error: str | None = None
    invocation_id: str | None = None
    latency_ms: float | None = None


class ToolListItem(BaseModel):
    """Tool in list response."""

    name: str
    description: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any] | None = None
    category: str
    version: str
    enabled: bool


class ToolListResponse(BaseModel):
    """Response listing available tools."""

    tools: list[ToolListItem]
    total: int
    categories: list[str]


class ToolDetailResponse(BaseModel):
    """Detailed tool information."""

    name: str
    description: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any] | None = None
    category: str
    version: str
    provider: str
    tags: list[str]
    enabled: bool
    stats: dict[str, Any] | None = None


class ToolToggleRequest(BaseModel):
    """Request body for toggling a tool's enabled state."""

    enabled: bool = Field(..., description="New enabled state for the tool")


class HealthResponse(BaseModel):
    """Server health response."""

    status: str
    timestamp: str
    registry: dict[str, Any]


class ServerInfo(BaseModel):
    """MCP server information."""

    name: str = "heretek-swarm-mcp"
    version: str = "1.0.0"
    protocol_version: str = "2024-11-05"


# =============================================================================
# MCP Router
# =============================================================================

router = APIRouter(prefix="/api/mcp", tags=["mcp"], dependencies=[Depends(verify_auth)])


# =============================================================================
# Tool Endpoints
# =============================================================================


@router.get("/tools")
async def list_tools(category: str | None = None) -> ToolListResponse:
    """
    List all available MCP tools.

    Args:
        category: Optional category filter

    Returns:
        List of tools with metadata
    """
    registry = get_registry()
    tools = registry.list_tools(category=category)
    categories = list({t.category for t in tools})

    return ToolListResponse(
        tools=[
            ToolListItem(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
                outputSchema=t.output_schema,
                category=t.category,
                version=t.version,
                enabled=t.enabled,
            )
            for t in tools
        ],
        total=len(tools),
        categories=categories,
    )


@router.get("/tools/{tool_name}")
async def get_tool(tool_name: str) -> ToolDetailResponse:
    """
    Get details for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Detailed tool information
    """
    registry = get_registry()
    tool = registry.get_tool(tool_name)

    if not tool:
        raise HTTPException(404, f"Tool {tool_name} not found")

    stats = registry.get_stats(tool_name)

    return ToolDetailResponse(
        name=tool.name,
        description=tool.description,
        inputSchema=tool.input_schema,
        outputSchema=tool.output_schema,
        category=tool.category,
        version=tool.version,
        provider=tool.provider.value,
        tags=tool.tags,
        enabled=tool.enabled,
        stats=stats,
    )


@router.post("/tools/call")
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """
    Invoke an MCP tool.

    Args:
        request: Tool call request with name and arguments

    Returns:
        Tool invocation result
    """
    import time

    start_time = time.time()
    registry = get_registry()

    result = await registry.invoke(
        name=request.name,
        arguments=request.arguments,
        context=request.context,
    )

    latency_ms = (time.time() - start_time) * 1000

    return ToolCallResponse(
        success=result.get("success", False),
        result=result.get("result"),
        error=result.get("error"),
        latency_ms=latency_ms,
    )


@router.put("/tools/toggle/{tool_name}")
async def toggle_tool(
    tool_name: str,
    body: ToolToggleRequest,
    request: Request,
) -> dict[str, Any]:
    """
    Toggle a tool's enabled state.

    Args:
        tool_name: Name of the tool to toggle
        body: Request body with ``enabled: bool``

    Returns:
        ``{"name": ..., "enabled": ..., "success": True}`` on success,
        or raises 404 when the tool name is unknown.
    """
    start_ts = _time_module.time()
    registry = get_registry()

    ok = registry.set_tool_enabled(tool_name, body.enabled)
    if not ok:
        raise HTTPException(
            404,
            f"Tool '{tool_name}' not found. Use GET /mcp/tools to list available tools.",
        )

    duration_ms = (_time_module.time() - start_ts) * 1000

    # Structured audit log
    caller_ip = request.client.host if request.client else "unknown"
    logger.info(
        "mcp_tool_toggle_endpoint",
        endpoint="/api/mcp/tools/toggle/{name}",
        method="PUT",
        caller_ip=caller_ip,
        tool_name=tool_name,
        enabled=body.enabled,
        duration_ms=round(duration_ms, 3),
    )

    return {"name": tool_name, "enabled": body.enabled, "success": True}


@router.get("/tools/{tool_name}/stats")
async def get_tool_stats(tool_name: str) -> dict[str, Any]:
    """
    Get statistics for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool statistics
    """
    registry = get_registry()
    stats = registry.get_stats(tool_name)

    if stats is None:
        raise HTTPException(404, f"Tool {tool_name} not found")

    return stats


# =============================================================================
# Health Endpoints
# =============================================================================


@router.get("/health")
async def health_check() -> HealthResponse:
    """
    Check MCP server health.

    Returns:
        Server health status
    """
    registry = get_registry()
    all_stats = registry.get_all_stats()

    total_calls = sum(s.get("calls", 0) for s in all_stats.values())
    total_errors = sum(s.get("errors", 0) for s in all_stats.values())

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
        registry={
            "total_tools": len(registry.list_tools()),
            "total_calls": total_calls,
            "total_errors": total_errors,
        },
    )


@router.get("/info")
async def get_server_info() -> ServerInfo:
    """
    Get MCP server information.

    Returns:
        Server metadata
    """
    return ServerInfo()


# =============================================================================
# MCP Server Class
# =============================================================================


class MCPServer:
    """
    MCP Server for Heretek Swarm.

    Manages tool registry and provides MCP protocol endpoints
    for dynamic tool loading and execution.
    """

    def __init__(self) -> None:
        self._registry = MCPToolRegistry()
        self._running = False

    @property
    def registry(self) -> MCPToolRegistry:
        """Get the tool registry."""
        return self._registry

    @property
    def router(self) -> APIRouter:
        """Get the FastAPI router."""
        return router

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Any,
        output_schema: dict[str, Any] | None = None,
        category: str = "general",
        version: str = "1.0.0",
        tags: list[str] | None = None,
    ) -> None:
        """
        Register a tool with the MCP server.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON schema for tool input
            handler: Callable that executes the tool
            output_schema: JSON schema for tool output
            category: Tool category
            version: Tool version
            tags: Optional tags
        """
        from heretek_swarm.mcp.registry import MCPToolMetadata, ToolProviderType

        metadata = MCPToolMetadata(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            category=category,
            version=version,
            provider=ToolProviderType.LOCAL,
            tags=tags or [],
        )

        self._registry.register_tool(metadata, handler)
        logger.info("mcp_server_tool_registered", name=name, category=category)

    async def start(self) -> None:
        """Start the MCP server."""
        set_registry(self._registry)
        self._running = True
        logger.info("mcp_server_started")

    async def stop(self) -> None:
        """Stop the MCP server."""
        self._running = False
        logger.info("mcp_server_stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
