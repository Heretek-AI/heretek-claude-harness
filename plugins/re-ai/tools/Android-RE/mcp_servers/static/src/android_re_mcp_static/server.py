"""FastMCP server definition for the static analysis MCP.

This module wires together the tool functions from
:mod:`android_re_mcp_static.tools` into a single :class:`FastMCP` instance.
The :func:`build_server` factory is used by:

- ``__main__.py`` for the production stdio entry point.
- Tests, which build a server and connect to it via an in-memory
  :class:`mcp.Client` to assert tool schemas and responses.

Adding a new tool:

1. Implement the tool function in the relevant topic module under
   :mod:`android_re_mcp_static.tools` (e.g., :file:`tools/manifest.py`).
2. Import the topic module here (its ``register(mcp)`` is called).
3. Add a contract test in :file:`tests/test_mcp_static.py`.
4. Update :file:`docs/mcp-tool-reference.md`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

from android_re_core.project import ProjectStore

# A module-level store is shared by every tool. A single MCP server
# process is expected to handle one or a handful of analysis sessions
# at a time; this in-memory store is sufficient.
_STORE: ProjectStore = ProjectStore()


def get_store() -> ProjectStore:
    """Return the process-wide :class:`ProjectStore`."""
    return _STORE


def build_server() -> FastMCP:
    """Build and return a fresh :class:`FastMCP` instance with all tools registered.

    Each call returns a new instance, which is what tests want.
    """
    mcp = FastMCP(
        name="android-re-static",
        instructions=(
            "Static Android APK analysis: open APKs, read manifests, list "
            "components and permissions, find classes/methods, decompile "
            "individual classes and methods via jadx (with deobfuscation "
            "and Kotlin output), enumerate the decompiled source tree, "
            "and inspect signing certificates. Use the project_id returned "
            "by open_project for all subsequent calls. Always close a "
            "project with close_project when done."
        ),
    )

    # Register every topic module. Each module exposes ``register(mcp)``
    # which uses the @mcp.tool decorator.
    from .tools import (
        certs,
        cleanup_tools,
        decompile_tools,
        dex_tools,
        gradle_tools,
        manifest_tools,
        native_tools,
        project_tools,
        reporting_tools,
        secrets_tools,
        smali_tools,
    )

    project_tools.register(mcp)
    manifest_tools.register(mcp)
    dex_tools.register(mcp)
    certs.register(mcp)
    native_tools.register(mcp)
    smali_tools.register(mcp)
    decompile_tools.register(mcp)
    cleanup_tools.register(mcp)
    gradle_tools.register(mcp)
    secrets_tools.register(mcp)
    reporting_tools.register(mcp)

    return mcp
