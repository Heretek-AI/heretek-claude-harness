"""android_re_mcp_native — FastMCP server for native Android binary analysis.

Backed by :mod:`android_re_core.native` (LIEF 0.17.6 wrapper).
"""

from __future__ import annotations

from .server import build_server

__all__ = ["build_server"]
