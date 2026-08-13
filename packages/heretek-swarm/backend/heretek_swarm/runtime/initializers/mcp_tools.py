"""
MCP-tools initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_mcp_tools` free function wires the
CoreMCPTools instance and bridges the registries. The
main_loop ``_initialize_mcp_tools`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_mcp_tools`` is preserved as a
thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = logging.getLogger("heretek_swarm.runtime.initializers.mcp_tools")


async def initialize_mcp_tools(swarm: "AutonomousSwarm") -> None:
    """Wire the MCP tools and bridge the registries on ``swarm``.

    On any failure, ``swarm.mcp_tools`` is set to ``None`` and
    a ``mcp_tools_init_failed`` warning is logged. The swarm
    stays bootable; agents that depend on MCP tools just run
    without them.
    """
    try:
        from heretek_swarm.mcp.bridge import sync_mcp_registries
        from heretek_swarm.mcp.core import CoreMCPTools

        swarm.mcp_tools = CoreMCPTools(
            cognee_reader=swarm._cognee_reader,
            cognee_writer=swarm._cognee_writer,
            rag_retriever=swarm.rag,
            consensus_engine=swarm.consensus,
            event_mesh=swarm.event_mesh,
        )
        bridged = sync_mcp_registries(swarm.mcp_tools)
        logger.info(
            "mcp_tools_initialized",
            tool_count=len(swarm.mcp_tools.get_registry().list_tools()),
            bridged_count=bridged,
        )
    except Exception as exc:
        logger.warning("mcp_tools_init_failed", error=str(exc))
        swarm.mcp_tools = None


__all__ = ["initialize_mcp_tools"]
