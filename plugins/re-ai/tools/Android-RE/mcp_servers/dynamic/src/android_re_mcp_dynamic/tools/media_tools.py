"""Media tools: screenshot, screenrecord."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.device.adb import run_adb

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register media tools."""

    @mcp.tool(
        name="take_screenshot",
        description=(
            "Capture a PNG screenshot of the current device screen. "
            "Returns the host path of the saved file. Defaults to "
            "``$ANDROID_RE_OUTPUT_DIR/dynamic/screenshot-<ts>.png`` "
            "(typically ``Output/dynamic/screenshot-<ts>.png``); "
            "override with ``output_path``."
        ),
    )
    def take_screenshot(
        serial: Annotated[str, Field(description="Device serial")],
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write the PNG to. Defaults to "
                    "``$ANDROID_RE_OUTPUT_DIR/dynamic/screenshot-<ts>.png``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        if not output_path:
            base = Path(os.environ.get("ANDROID_RE_OUTPUT_DIR", "./Output")) / "dynamic"
            base.mkdir(parents=True, exist_ok=True)
            output_path = str(base / f"screenshot-{int(time.time())}.png")
        output_path = os.path.expanduser(output_path)
        # Capture to the device first, then pull
        remote = "/sdcard/screenshot.png"
        try:
            run_adb(["-s", serial, "shell", "screencap", "-p", remote], timeout_s=15)
        except Exception as e:
            return {"error": {"code": "screencap_failed", "message": str(e)}}
        try:
            run_adb(["-s", serial, "pull", remote, output_path], timeout_s=30)
        except Exception as e:
            return {"error": {"code": "pull_failed", "message": str(e)}}
        try:
            os.path.getsize(output_path)
        except OSError:
            pass
        try:
            run_adb(["-s", serial, "shell", "rm", remote], timeout_s=5)
        except Exception:
            pass
        return {"ok": True, "output_path": output_path}

    @mcp.tool(
        name="screenrecord",
        description=(
            "Record the screen to an MP4. Returns the host path after "
            "the recording completes (or the timeout elapses). "
            "Defaults to ``$ANDROID_RE_OUTPUT_DIR/dynamic/screenrecord-<ts>.mp4``; "
            "override with ``output_path``."
        ),
    )
    def screenrecord(
        serial: Annotated[str, Field(description="Device serial")],
        duration_s: Annotated[
            int, Field(ge=1, le=180, description="Recording length in seconds")
        ] = 10,
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write the MP4 to. Defaults to "
                    "``$ANDROID_RE_OUTPUT_DIR/dynamic/screenrecord-<ts>.mp4``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        if not output_path:
            base = Path(os.environ.get("ANDROID_RE_OUTPUT_DIR", "./Output")) / "dynamic"
            base.mkdir(parents=True, exist_ok=True)
            output_path = str(base / f"screenrecord-{int(time.time())}.mp4")
        output_path = os.path.expanduser(output_path)
        remote = "/sdcard/screenrecord.mp4"
        # Run screenrecord on the device with a time limit
        from android_re_core.device.adb import run_adb

        try:
            run_adb(
                ["-s", serial, "shell", "screenrecord", "--time-limit", str(duration_s), remote],
                timeout_s=duration_s + 30,
            )
        except Exception as e:
            return {"error": {"code": "screenrecord_failed", "message": str(e)}}
        try:
            run_adb(["-s", serial, "pull", remote, output_path], timeout_s=60)
        except Exception as e:
            return {"error": {"code": "pull_failed", "message": str(e)}}
        try:
            run_adb(["-s", serial, "shell", "rm", remote], timeout_s=5)
        except Exception:
            pass
        return {
            "ok": True,
            "output_path": output_path,
            "duration_s": duration_s,
        }

    _ = Path  # silence linter
