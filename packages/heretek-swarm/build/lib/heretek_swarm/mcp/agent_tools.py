"""
Agent Tool Injection — MCP tools as OpenAI function-calling tools for swarms.Agent.

Provides two conversion functions that bridge CoreMCPTools' MCPToolDefinition
entries into the format swarms.Agent needs:

1. ``build_tools_list_dictionary()`` — OpenAI function-calling schemas
2. ``build_tool_handlers()`` — synchronous callable wrappers around async handlers

Usage (post-spawn injection)::

    from heretek_swarm.mcp.agent_tools import (
        build_tools_list_dictionary,
        build_tool_handlers,
    )

    registry = self.mcp_tools.get_registry()
    actor.swarms_agent.tools_list_dictionary = build_tools_list_dictionary(registry)
    actor.swarms_agent.tools = list(build_tool_handlers(registry).values())
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

    from heretek_swarm.tools.mcp_tools import MCPToolRegistry as ToolsMCPToolRegistry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# OpenAI function-calling schema builder
# ---------------------------------------------------------------------------


def build_tools_list_dictionary(
    registry: ToolsMCPToolRegistry,
) -> list[dict[str, Any]]:
    """
    Convert all tools in *registry* to OpenAI function-calling schemas.

    Each tool's ``input_schema`` maps directly to the ``parameters`` field
    of the OpenAI function schema::

        {
            "type": "function",
            "function": {
                "name": "<tool_name>",
                "description": "<tool_description>",
                "parameters": <input_schema>,
            },
        }

    Only enabled tools are included.  If the registry has no tools an empty
    list is returned.

    Args:
        registry: A ``MCPToolRegistry`` (from ``tools/mcp_tools.py``)
                  whose ``list_tools()`` returns ``MCPToolDefinition`` entries
                  as dicts, and whose ``get_tool()`` returns the definition.

    Returns:
        A list of OpenAI function-calling dicts suitable for setting on
        ``swarms.Agent.tools_list_dictionary``.
    """
    tool_defs = registry.list_tools(category=None)
    schemas: list[dict[str, Any]] = []

    for tool_dict in tool_defs:
        name = tool_dict.get("name", "")
        if not name:
            continue

        # Look up the full definition for description and input_schema.
        tool_def = registry.get_tool(name)
        if tool_def is None:
            logger.warning("agent_tools_schema_not_found", tool_name=name)
            continue

        schema = {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.input_schema,
            },
        }
        schemas.append(schema)

    if not schemas:
        logger.warning(
            "agent_tools_schema_empty", message="No MCP tools converted to OpenAI schemas"
        )

    logger.debug("agent_tools_schema_built", tool_count=len(schemas))
    return schemas


# ---------------------------------------------------------------------------
# Synchronous handler wrapper builder
# ---------------------------------------------------------------------------


def build_tool_handlers(
    registry: ToolsMCPToolRegistry,
) -> dict[str, Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]]]:
    """
    Build synchronous callable wrappers for all tools in *registry*.

    The original handlers are ``async def`` functions with the signature::

        handler(arguments: dict[str, Any], context: dict[str, Any] | None)
            -> dict[str, Any] | Awaitable[dict[str, Any]]

    Each returned wrapper is a synchronous function that calls ``asyncio.run()``
    on the async handler.  This is safe because swarms.Agent executes tool calls
    inside ``asyncio.to_thread()`` — there is no running event loop conflict in
    the thread pool.

    The returned dict keys are tool names, matching the ``name`` field in the
    OpenAI schemas produced by ``build_tools_list_dictionary()``.  The swarms
    Agent's ``BaseTool`` dispatches by matching function names, so the dict
    keys must match the schema names exactly.

    Args:
        registry: A ``MCPToolRegistry`` (from ``tools/mcp_tools.py``)
                  whose ``get_tool()`` returns ``MCPToolDefinition`` entries.

    Returns:
        A dict mapping ``tool_name -> sync_callable`` where each callable
        has the signature ``(arguments: dict, context: dict | None) -> dict``.
    """
    handlers: dict[str, Callable] = {}

    tool_defs = registry.list_tools(category=None)
    for tool_dict in tool_defs:
        name = tool_dict.get("name", "")
        if not name:
            continue

        tool_def = registry.get_tool(name)
        if tool_def is None:
            logger.warning("agent_tools_handler_not_found", tool_name=name)
            continue

        original_handler = tool_def.handler

        # Build a synchronous wrapper.
        # If the handler is an async function, use asyncio.run() to bridge
        # the sync‑to‑async gap.  If it is a plain sync function, call it  # noqa: RUF003
        # directly.  This is safe because swarms.Agent executes tools
        # inside asyncio.to_thread() — no overlapping event loop conflict.
        def _make_wrapper(handler):
            def _sync_wrapper(
                arguments: dict[str, Any],
                context: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                try:
                    candidate = handler(arguments, context)
                    if asyncio.iscoroutine(candidate):
                        return asyncio.run(candidate)
                    return candidate
                except Exception as exc:
                    logger.error(
                        "agent_tool_handler_error",
                        tool_name=name,  # noqa: B023
                        error=str(exc),
                    )
                    return {"error": str(exc), "success": False}

            return _sync_wrapper

        handlers[name] = _make_wrapper(original_handler)

    logger.debug("agent_tools_handlers_built", handler_count=len(handlers))
    return handlers
