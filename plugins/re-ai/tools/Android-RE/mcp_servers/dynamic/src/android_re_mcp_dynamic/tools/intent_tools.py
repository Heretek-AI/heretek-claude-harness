"""Intent and clipboard tools."""

from __future__ import annotations

import shlex
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.device.adb import shell

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register intent / clipboard tools."""

    @mcp.tool(
        name="start_intent",
        description=(
            "Send an intent via ``am start``. Supports action, data URI, and string extras."
        ),
    )
    def start_intent(
        serial: Annotated[str, Field(description="Device serial")],
        action: Annotated[str, Field(description="Intent action, e.g. android.intent.action.VIEW")],
        data_uri: Annotated[
            str | None,
            Field(description="Optional data URI (e.g. https://example.com)"),
        ] = None,
        extras: Annotated[
            dict[str, str] | None,
            Field(description="Optional string extras"),
        ] = None,
        component: Annotated[
            str | None,
            Field(description="Optional explicit component (pkg/.Activity)"),
        ] = None,
    ) -> dict[str, Any]:
        argv: list[str] = ["am", "start", "-a", action]
        if data_uri:
            argv.extend(["-d", data_uri])
        if component:
            argv.extend(["-n", component])
        for k, v in (extras or {}).items():
            argv.extend(["--es", k, v])
        cmd = " ".join(shlex.quote(a) for a in argv)
        try:
            out = shell(cmd, serial=serial, timeout_s=30)
        except Exception as e:
            return {"error": {"code": "start_intent_failed", "message": str(e)}}
        return {"ok": True, "action": action, "output": out[-500:]}

    @mcp.tool(
        name="send_broadcast",
        description="Send a broadcast via ``am broadcast``.",
    )
    def send_broadcast(
        serial: Annotated[str, Field(description="Device serial")],
        action: Annotated[str, Field(description="Broadcast action")],
        extras: Annotated[
            dict[str, str] | None, Field(description="Optional string extras")
        ] = None,
        component: Annotated[str | None, Field(description="Optional target component")] = None,
    ) -> dict[str, Any]:
        argv: list[str] = ["am", "broadcast", "-a", action]
        if component:
            argv.extend(["-n", component])
        for k, v in (extras or {}).items():
            argv.extend(["--es", k, v])
        cmd = " ".join(shlex.quote(a) for a in argv)
        try:
            out = shell(cmd, serial=serial, timeout_s=30)
        except Exception as e:
            return {"error": {"code": "broadcast_failed", "message": str(e)}}
        return {"ok": True, "action": action, "output": out[-500:]}

    @mcp.tool(
        name="set_clipboard",
        description=(
            "Set the device clipboard via ``am broadcast`` to "
            "com.android.commands.sysutil.SysUtil (works on most "
            "AOSP / emulator images)."
        ),
    )
    def set_clipboard(
        serial: Annotated[str, Field(description="Device serial")],
        text: Annotated[str, Field(description="Text to place on the clipboard")],
    ) -> dict[str, Any]:
        # This is fragile — there is no stable public API for setting
        # the clipboard on Android. The approach below uses the
        # ``service call clipboard`` binder transaction, which works
        # on emulators and AOSP userdebug builds. On other images it
        # silently fails.
        escaped = text.replace("'", "'\\''")
        cmd = f"service call clipboard 2 i32 1 i32 0 i32 0 s16 com.android.shell s16 '{escaped}'"
        try:
            out = shell(cmd, serial=serial, timeout_s=15)
        except Exception as e:
            return {"error": {"code": "set_clipboard_failed", "message": str(e)}}
        return {"ok": True, "text": text, "output": out[-200:]}
