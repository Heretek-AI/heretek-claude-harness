"""FastMCP server for the triage orchestrator."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

from android_re_core.store.sqlite import TriageStore

_STORE: TriageStore = TriageStore()


def get_store() -> TriageStore:
    return _STORE


def build_server() -> FastMCP:
    """Build and return a fresh :class:`FastMCP` instance with all tools registered."""
    mcp = FastMCP(
        name="android-re-triage",
        instructions=(
            "Android-RE triage orchestrator. Opens long-running, "
            "checkpointable multi-step analyses against an APK, "
            "composes the static / native / dynamic results into a "
            "MASVS-aligned report, and persists state to SQLite. "
            "Use the triage_id returned by start_triage for all "
            "subsequent calls."
        ),
    )

    from .tools import (
        control_tools,
        finding_tools,
        lifecycle_tools,
        report_tools,
    )

    lifecycle_tools.register(mcp)
    finding_tools.register(mcp)
    control_tools.register(mcp)
    report_tools.register(mcp)

    return mcp
