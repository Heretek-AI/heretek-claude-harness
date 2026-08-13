"""MCP server entry point for re-gdb."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_gdb import gdb_mi

logger = logging.getLogger("re_gdb")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-gdb")


@mcp.tool()
def check_gdb() -> dict:
    """Return gdb version + whether GEF is configured."""
    return gdb_mi.check_gdb()


@mcp.tool()
def start_session(
    path: str = "",
    gdb_args: list[str] | None = None,
    session: str = "default",
) -> dict:
    """Open (or reuse) a GDB session. Optionally load a binary."""
    return gdb_mi.start_session(path, gdb_args, session)


@mcp.tool()
def end_session(session: str) -> dict:
    """Tear down a GDB session."""
    return gdb_mi.end_session_tool(session)


@mcp.tool()
def run_to_breakpoint(session: str, target: str, condition: str = "") -> dict:
    """Set a breakpoint at *target* and run to it."""
    return gdb_mi.run_to_breakpoint(session, target, condition)


@mcp.tool()
def step_count(session: str, count: int = 1) -> dict:
    """Single-step *count* times, return register state after."""
    return gdb_mi.step_count(session, count)


@mcp.tool()
def read_memory(
    session: str, addr: str, count: int = 16, fmt: str = "hex"
) -> dict:
    """Read *count* memory units at *addr*."""
    return gdb_mi.read_memory(session, addr, count, fmt)


@mcp.tool()
def gef_heap(session: str) -> dict:
    """GEF: heap chunks (glibc malloc bins)."""
    return gdb_mi.gef_heap(session)


@mcp.tool()
def gef_canary(session: str) -> dict:
    """GEF: stack canary check."""
    return gdb_mi.gef_canary(session)


@mcp.tool()
def gef_registers(session: str) -> dict:
    """GEF: registers (extended view)."""
    return gdb_mi.gef_registers(session)


@mcp.tool()
def gef_vmmap(session: str) -> dict:
    """GEF: vmmap (mapped regions with perms)."""
    return gdb_mi.gef_vmmap(session)


@mcp.tool()
def gef_nearpc(session: str, n: int = 8) -> dict:
    """GEF: nearpc (look ahead N instructions from PC)."""
    return gdb_mi.gef_nearpc(session, n)


@mcp.tool()
def gef_pattern_create(length: int) -> dict:
    """Create a cyclic pattern of *length* bytes (for offset-finding)."""
    return gdb_mi.gef_pattern_create(length)


@mcp.tool()
def gef_pattern_offset(value: str) -> dict:
    """Find the offset of *value* in a cyclic pattern."""
    return gdb_mi.gef_pattern_offset(value)


@mcp.tool()
def attach_pid(session: str, pid: int) -> dict:
    """Attach to a running process by PID."""
    return gdb_mi.attach_pid(session, pid)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
