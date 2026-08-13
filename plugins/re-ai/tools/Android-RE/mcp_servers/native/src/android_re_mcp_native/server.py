"""FastMCP server definition for the native binary analysis MCP.

The :func:`build_server` factory returns a :class:`FastMCP` instance
with all 19 tools registered. Like the static server, the native
server is transport-agnostic; ``__main__`` wires it to stdio.

The server shares its :class:`~android_re_core.project.ProjectStore`
with the static server so a single MCP client (Claude Code) can hold
multiple servers in the same process and they cooperate on the same
projects. For the v0.2.0 release, the static and native servers run
in their own processes by default (registered as separate MCP
servers), but the store API is identical.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

from android_re_core.project import ProjectStore

_STORE: ProjectStore = ProjectStore()


def get_store() -> ProjectStore:
    """Return the process-wide :class:`ProjectStore`."""
    return _STORE


def build_server() -> FastMCP:
    """Build and return a fresh :class:`FastMCP` instance with all tools registered."""
    mcp = FastMCP(
        name="android-re-native",
        instructions=(
            "Native Android binary analysis: parse ELF / OAT / VDEX / "
            "ART shared libraries from an APK, extract sections, "
            "symbols, imports, exports, strings, and security "
            "features, disassemble functions, and generate Frida "
            "native-hook templates. Use the project_id returned by "
            "android-re-static's open_project (or call open_project "
            "here directly)."
        ),
    )

    from .tools import (
        binary_tools,
        disasm_tools,
        hooks_tools,
        project_tools,
        report_tools,
        sig_tools,
        string_tools,
    )

    binary_tools.register(mcp)
    disasm_tools.register(mcp)
    string_tools.register(mcp)
    sig_tools.register(mcp)
    hooks_tools.register(mcp)
    report_tools.register(mcp)
    project_tools.register(mcp)

    return mcp
