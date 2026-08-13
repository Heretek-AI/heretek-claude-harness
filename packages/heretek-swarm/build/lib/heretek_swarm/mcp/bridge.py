"""
MCP Registry Bridge

Bridges the dual MCPToolRegistry problem: CoreMCPTools (tools/mcp_tools.py)
registers tool definitions into its own MCPToolRegistry class, while the
mcp/server.py HTTP API uses a global get_registry() that returns a different
MCPToolRegistry from mcp/registry.py.

This module provides a sync function that reads tool definitions from the
tools-layer registry and registers them into the mcp/ registry so the HTTP
API can serve them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from heretek_swarm.mcp.registry import MCPToolMetadata, ToolProviderType
from heretek_swarm.mcp.server import get_registry, set_registry

if TYPE_CHECKING:
    from heretek_swarm.tools.mcp_tools import CoreMCPTools

logger = structlog.get_logger(__name__)


def sync_mcp_registries(core_tools: CoreMCPTools | None) -> int:
    """
    Bridge tools from CoreMCPTools' registry into the mcp/ server registry.

    Reads all tool definitions from the tools-layer MCPToolRegistry (inside
    CoreMCPTools), converts each to MCPToolMetadata, and registers it into
    the mcp/ MCPToolRegistry (the one served by the HTTP API).

    Args:
        core_tools: An initialized ``CoreMCPTools`` instance whose internal
                    registry contains ``MCPToolDefinition`` entries.  May be
                    ``None`` — returns 0 immediately in that case.

    Returns:
        The number of tools successfully bridged.

    Raises:
        ValueError: If a tool name already exists in the mcp/ registry
                    (renamed from tools-layer tool to avoid conflict).
    """
    # None-guard: if CoreMCPTools was not initialized, there is nothing to
    # bridge.
    if core_tools is None:
        logger.info("mcp_bridge_skipped_no_core_tools")
        return 0

    # Read all tool definitions from the tools-layer registry.
    # CoreMCPTools.get_registry() returns the tools-layer MCPToolRegistry.
    tools_registry = core_tools.get_registry()
    tool_defs = tools_registry.list_tools(category=None)

    if not tool_defs:
        logger.warning(
            "mcp_bridge_empty_tools", message="No tool definitions found in CoreMCPTools registry"
        )
        return 0

    # Get the mcp/ registry (the one served by the HTTP API).
    mcp_registry = get_registry()

    bridged_count = 0
    skipped_count = 0

    for tool_dict in tool_defs:
        tool_name = tool_dict.get("name", "")
        if not tool_name:
            skipped_count += 1
            continue

        # Look up the original MCPToolDefinition to access its handler.
        tool_def = tools_registry.get_tool(tool_name)
        if tool_def is None:
            logger.warning("mcp_bridge_handler_not_found", name=tool_name)
            skipped_count += 1
            continue

        # Convert MCPToolDefinition (tools-layer) → MCPToolMetadata (mcp-layer).
        metadata = MCPToolMetadata(
            name=tool_def.name,
            description=tool_def.description,
            input_schema=tool_def.input_schema,
            output_schema=None,  # tools-layer has no output_schema
            category=tool_def.category,
            version=tool_def.version,
            provider=ToolProviderType.LOCAL,
            tags=[],
            enabled=tool_def.enabled,
        )

        # Register into the mcp/ registry, passing the same handler through.
        # Both registries use the same handler calling convention:
        #   handler(arguments: dict, context: dict | None) -> dict
        try:
            mcp_registry.register_tool(metadata, tool_def.handler)
            bridged_count += 1
            logger.debug("mcp_tool_bridged", name=tool_name, category=tool_def.category)
        except ValueError:
            # Tool already registered — skip silently (idempotent bridge).
            skipped_count += 1

    # Sync the global so the HTTP API sees all bridged tools.
    set_registry(mcp_registry)

    # ------------------------------------------------------------------
    # Apply persisted tool states from tools_state.json.
    #
    # After all tools are registered, load the persisted enabled/disabled
    # states and apply them.  This ensures that tools disabled via the
    # dashboard survive daemon restarts — the bridge never overwrites a
    # user-disabled tool back to enabled.
    # ------------------------------------------------------------------
    persisted_states = mcp_registry._load_tool_states()  # noqa: SLF001
    applied_count = 0
    orphan_count = 0
    for tool_name, persisted_enabled in persisted_states.items():
        tool = mcp_registry._tools.get(tool_name)  # noqa: SLF001
        if tool is not None:
            tool.enabled = persisted_enabled
            applied_count += 1
        else:
            orphan_count += 1
            logger.warning(
                "mcp_bridge_orphan_state",
                tool_name=tool_name,
                message="Persisted state references tool not in registry",
            )

    logger.info(
        "mcp_bridge_complete",
        total_tools=len(mcp_registry.list_tools()),
        bridged=bridged_count,
        skipped=skipped_count,
        persisted_states_applied=applied_count,
        orphan_states=orphan_count,
    )
    return bridged_count
