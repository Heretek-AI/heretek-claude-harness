"""FastMCP server definition for the dynamic analysis MCP.

The :func:`build_server` factory returns a :class:`FastMCP` instance
with all 30+ tools registered. The server shares a process-wide
:class:`~android_re_core.frida.session.SessionStore` and
:class:`~android_re_core.frida.scripts.ScriptStore` so a single MCP
client (Claude Code) can hold multiple sessions and scripts in
flight.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

from android_re_core.frida.scripts import ScriptStore
from android_re_core.frida.session import SessionStore
from android_re_core.project import ProjectStore

# Project store: for cross-MCP cooperation (a project opened by the
# static server can be operated on by the dynamic server if both
# servers happen to share the same in-memory store — typically each
# runs in its own process, so the dynamic server mostly operates on
# frida sessions rather than projects).
_PROJECT_STORE: ProjectStore = ProjectStore()
_SESSION_STORE: SessionStore = SessionStore()
_SCRIPT_STORE: ScriptStore = ScriptStore()


def get_project_store() -> ProjectStore:
    return _PROJECT_STORE


def get_session_store() -> SessionStore:
    return _SESSION_STORE


def get_script_store() -> ScriptStore:
    return _SCRIPT_STORE


def build_server() -> FastMCP:
    """Build and return a fresh :class:`FastMCP` instance with all tools registered."""
    mcp = FastMCP(
        name="android-re-dynamic",
        instructions=(
            "Dynamic Android instrumentation: enumerate Frida devices, "
            "spawn/attach to processes, load Frida scripts and call "
            "RPC methods, capture logcat and screenshots, install and "
            "launch APKs, dump heap, and route traffic through a "
            "MITM proxy. Destructive tools require confirm: bool. "
            "Use the session_id returned by frida_spawn / frida_attach "
            "for all subsequent calls."
        ),
    )

    from .tools import (
        device_tools,
        file_tools,
        frida_tools,
        intent_tools,
        logcat_tools,
        media_tools,
        network_tools,
        report_tools,
    )

    device_tools.register(mcp)
    frida_tools.register(mcp)
    logcat_tools.register(mcp)
    file_tools.register(mcp)
    intent_tools.register(mcp)
    media_tools.register(mcp)
    network_tools.register(mcp)
    report_tools.register(mcp)

    return mcp
