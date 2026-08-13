"""android_re_mcp_static — FastMCP server for static Android APK analysis.

This package registers a FastMCP server with the 11 first-phase tools.
Subsequent phases add native binary analysis, secrets scanning, SARIF
reporting, and the repackage round-trip.

The server is transport-agnostic; ``__main__`` wires it to stdio for
the v0.1.0 release.
"""

from __future__ import annotations

from .server import build_server

__all__ = ["build_server"]


def __getattr__(name: str) -> object:  # pragma: no cover - convenience
    if name == "server":
        from . import server

        return server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
