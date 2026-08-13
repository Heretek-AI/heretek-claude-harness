"""Typed exception hierarchy for android_re_core.

All public APIs in this package raise subclasses of :class:`AndroidReError`,
never bare :class:`Exception`. This makes it easy for callers (the MCP
servers, the skill runtime) to map errors to typed MCP responses.

The hierarchy:

- :class:`AndroidReError` (root)
  - :class:`APKError` (apk/dex/manifest/manifest issues)
    - :class:`APKTooLarge`
    - :class:`APKZipBomb`
    - :class:`APKNotFound`
    - :class:`APKInvalid`
    - :class:`APKAlreadyOpen`
  - :class:`ProjectError` (project lifecycle issues)
    - :class:`ProjectNotFound`
    - :class:`ProjectClosed`
  - :class:`ToolError` (external tool / subprocess issues)
    - :class:`ToolNotFound`
    - :class:`ToolTimeout`
    - :class:`ToolFailed`
  - :class:`DeviceError` (adb / device issues; Phase 3+)
  - :class:`FridaError` (frida client / server issues; Phase 3+)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "APKAlreadyOpen",
    "APKError",
    "APKInvalid",
    "APKNotFound",
    "APKTooLarge",
    "APKZipBomb",
    "AndroidReError",
    "DeviceError",
    "FridaError",
    "ProjectClosed",
    "ProjectError",
    "ProjectNotFound",
    "ToolError",
    "ToolFailed",
    "ToolNotFound",
    "ToolTimeout",
]


class AndroidReError(Exception):
    """Root of the android_re_core exception hierarchy."""

    code: str = "android_re_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details) if details else {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error for inclusion in an MCP tool response."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# APK / DEX / manifest errors
# ---------------------------------------------------------------------------


class APKError(AndroidReError):
    """An APK file could not be opened, parsed, or otherwise analyzed."""

    code = "apk_error"


class APKTooLarge(APKError):
    """The APK file exceeds the configured maximum size."""

    code = "apk_too_large"


class APKZipBomb(APKError):
    """The APK's decompression ratio exceeds the configured maximum."""

    code = "apk_zip_bomb"


class APKNotFound(APKError):
    """The APK path does not exist or is not a regular file."""

    code = "apk_not_found"


class APKInvalid(APKError):
    """The APK file is not a valid ZIP / DEX / Android package."""

    code = "apk_invalid"


class APKAlreadyOpen(APKError):
    """A project for the same APK is already registered under a different id."""

    code = "apk_already_open"


# ---------------------------------------------------------------------------
# Project lifecycle errors
# ---------------------------------------------------------------------------


class ProjectError(AndroidReError):
    """An operation referenced a project that is unknown or in a bad state."""

    code = "project_error"


class ProjectNotFound(ProjectError):
    """The requested project_id is not in the :class:`ProjectStore`."""

    code = "project_not_found"


class ProjectClosed(ProjectError):
    """The requested project has been closed and its resources released."""

    code = "project_closed"


# ---------------------------------------------------------------------------
# External tool / subprocess errors
# ---------------------------------------------------------------------------


class ToolError(AndroidReError):
    """An external tool (apktool, jadx, apksigner, …) failed."""

    code = "tool_error"


class ToolNotFound(ToolError):
    """The named tool could not be located on the host PATH or in vendor/."""

    code = "tool_not_found"


class ToolTimeout(ToolError):
    """The tool did not complete within the configured timeout."""

    code = "tool_timeout"


class ToolFailed(ToolError):
    """The tool exited with a non-zero status or wrote a parse error."""

    code = "tool_failed"


# ---------------------------------------------------------------------------
# Device / Frida errors (Phase 3+)
# ---------------------------------------------------------------------------


class DeviceError(AndroidReError):
    """A device / adb operation failed."""

    code = "device_error"


class FridaError(AndroidReError):
    """A frida client or server operation failed."""

    code = "frida_error"
