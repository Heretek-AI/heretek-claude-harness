"""MCP-server-specific errors.

These are distinct from the :mod:`android_re_core.errors` hierarchy
because they need to round-trip through the MCP tool response format
in a specific way (string code + human message + optional hint).
"""

from __future__ import annotations

from typing import Any


class McpServerError(Exception):
    """Base class for MCP-server-specific errors."""

    code: str = "mcp_error"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.hint:
            out["hint"] = self.hint
        return out


class ToolNotInstalled(McpServerError):
    """A third-party tool (quark, androwarn, apkleaks, …) is not on PATH."""

    code = "tool_not_installed"
