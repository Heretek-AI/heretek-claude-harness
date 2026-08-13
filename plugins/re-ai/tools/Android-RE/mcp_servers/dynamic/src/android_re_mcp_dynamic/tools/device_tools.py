"""Device management tools: list, connect, install, launch."""

from __future__ import annotations

import json
import shlex
import time
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.device.adb import list_devices as adb_list_devices
from android_re_core.errors import ToolNotFound
from android_re_mcp_dynamic.server import (
    get_session_store,
)

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register device-management tools."""

    @mcp.tool(
        name="list_devices",
        description=(
            "List every device visible via ADB. Returns serial + state. "
            "Use the serial for the ``serial`` argument on other tools."
        ),
    )
    def list_devices() -> dict[str, Any]:
        try:
            devs = adb_list_devices()
        except ToolNotFound as e:
            return {"error": {"code": e.code, "message": e.message, "hint": e.details.get("hint")}}
        return {
            "count": len(devs),
            "devices": [d.to_dict() for d in devs],
        }

    @mcp.tool(
        name="connect_device",
        description=(
            "Set the active device for subsequent dynamic tools. "
            "Returns the active serial. Idempotent."
        ),
    )
    def connect_device(
        serial: Annotated[str, Field(description="ADB device serial (e.g. 'emulator-5554')")],
    ) -> dict[str, Any]:
        # Validate the device is reachable
        from android_re_core.device.adb import get_state, run_adb

        try:
            run_adb(["-s", serial, "wait-for-device"], timeout_s=15)
            state = get_state(serial=serial)
        except Exception as e:
            return {"error": {"code": "device_unreachable", "message": str(e)}}
        return {"serial": serial, "state": state}

    @mcp.tool(
        name="pair_device",
        description=(
            "Pair with a wireless ADB device. Requires the pairing code "
            "shown on the device's developer options screen."
        ),
    )
    def pair_device(
        ip: Annotated[str, Field(description="Device IP (e.g. '192.168.1.42')")],
        port: Annotated[int, Field(ge=1, le=65535, description="Pairing port")],
        pairing_code: Annotated[str, Field(description="6-digit pairing code")],
    ) -> dict[str, Any]:
        from android_re_core.device.adb import run_adb

        try:
            proc = run_adb(["pair", f"{ip}:{port}", pairing_code], timeout_s=30)
        except Exception as e:
            return {"error": {"code": "pair_failed", "message": str(e)}}
        return {"ok": True, "output": proc.stdout[-500:]}

    @mcp.tool(
        name="disconnect_device",
        description=("Disconnect a wireless ADB endpoint. No-op for USB devices."),
    )
    def disconnect_device(
        endpoint: Annotated[str, Field(description="ip:port to disconnect")],
    ) -> dict[str, Any]:
        from android_re_core.device.adb import run_adb

        try:
            run_adb(["disconnect", endpoint], timeout_s=10)
        except Exception as e:
            return {"error": {"code": "disconnect_failed", "message": str(e)}}
        return {"ok": True, "endpoint": endpoint}

    @mcp.tool(
        name="install_apk",
        description=(
            "Install an APK on a device via the SDK-34+ aware install "
            "ladder. On API level < 34 the one-shot ``adb install`` is "
            "the primary path; on API 34+ the ladder escalates through "
            "a push-to-/data/local/tmp/ + ``pm install`` path, and as a "
            "last-resort fallback the staged ``pm install-create`` / "
            "``-write`` / ``-commit`` flow. REQUIRES confirm=true. "
            "Destructive: replaces the package if already installed."
        ),
    )
    def install_apk(
        serial: Annotated[str, Field(description="Device serial")],
        apk_path: Annotated[str, Field(description="Path to the .apk on the host")],
        replace: Annotated[bool, Field(description="Reinstall / replace existing")] = True,
        allow_downgrade: Annotated[bool, Field(description="Allow version downgrade")] = False,
        confirm: Annotated[bool, Field(description="Must be true to install")] = False,
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Optional override for the dry-run summary path. "
                    "Defaults to "
                    "``Output/<apk-basename>-<short-sha>/dynamic/install-attempt.dry-run.json``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        if not confirm:
            from android_re_core.paths import output_dir_for

            apk_path_resolved = Path(apk_path)
            out = (
                Path(output_path)
                if output_path
                else output_dir_for(apk_path_resolved) / "dynamic" / "install-attempt.dry-run.json"
            )
            summary = {
                "dry_run": True,
                "serial": serial,
                "apk_path": str(apk_path_resolved),
                "replace": replace,
                "allow_downgrade": allow_downgrade,
                "strategy_ladder": [
                    "adb_install (pre-34 fast path; tried first on API 34+ too)",
                    "push_then_pm_install (API 34+ primary escalation)",
                    "staged_install (API 34+ last-resort fallback)",
                ],
                "would_write_summary_to": str(out),
            }
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(summary, indent=2))
            return {
                "error": {
                    "code": "confirm_required",
                    "message": "install_apk requires confirm=true",
                    "dry_run_summary": summary,
                }
            }
        from android_re_core.device.adb_install import install_apk as _core_install

        try:
            result = _core_install(
                serial=serial,
                apk_path=apk_path,
                replace=replace,
                allow_downgrade=allow_downgrade,
            )
        except Exception as e:
            return {"error": {"code": "install_failed", "message": str(e)}}
        return result.to_dict()

    @mcp.tool(
        name="uninstall_apk",
        description=("Uninstall a package from a device. REQUIRES confirm=true. Destructive."),
    )
    def uninstall_apk(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier (e.g. com.example)")],
        keep_data: Annotated[bool, Field(description="Keep /data/data/<pkg> on disk")] = False,
        confirm: Annotated[bool, Field(description="Must be true to uninstall")] = False,
    ) -> dict[str, Any]:
        if not confirm:
            return {
                "error": {
                    "code": "confirm_required",
                    "message": "uninstall_apk requires confirm=true",
                }
            }
        from android_re_core.device.adb import run_adb

        args = ["-s", serial, "uninstall"]
        if keep_data:
            args.append("-k")
        args.append(package)
        try:
            proc = run_adb(args, timeout_s=60)
        except Exception as e:
            return {"error": {"code": "uninstall_failed", "message": str(e)}}
        return {"ok": True, "package": package, "output": proc.stdout[-500:]}

    @mcp.tool(
        name="launch_app",
        description=(
            "Launch an app on a device via ``am start``. Returns the "
            "spawned PID (or None if launch-by-intent)."
        ),
    )
    def launch_app(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier")],
        activity: Annotated[
            str | None,
            Field(
                description="Fully-qualified activity (e.g. com.example/.MainActivity); defaults to the MAIN/LAUNCHER"
            ),
        ] = None,
        extras: Annotated[
            dict[str, str] | None,
            Field(description="Optional intent extras as string->string"),
        ] = None,
        wait_ms: Annotated[int, Field(ge=0, le=60000)] = 0,
    ) -> dict[str, Any]:
        from android_re_core.device.adb import shell_argv

        component = (
            activity if activity and "." in activity else f"{package}/{activity or '.MainActivity'}"
        )
        argv = ["am", "start", "-n", component]
        for k, v in (extras or {}).items():
            argv.extend(["--es", k, v])
        try:
            out = shell_argv(argv, serial=serial, timeout_s=30)
        except Exception as e:
            return {"error": {"code": "launch_failed", "message": str(e)}}
        if wait_ms:
            time.sleep(wait_ms / 1000.0)
        # Try to capture the PID via pidof
        pid: int | None = None
        try:
            from android_re_core.device.adb import shell

            out2 = shell(f"pidof {shlex.quote(package)}", serial=serial).strip()
            if out2.isdigit():
                pid = int(out2)
        except Exception:
            pass
        return {
            "serial": serial,
            "package": package,
            "component": component,
            "pid": pid,
            "output": out[-500:],
        }

    @mcp.tool(
        name="force_stop",
        description="Force-stop a running app via ``am force-stop``.",
    )
    def force_stop(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier")],
    ) -> dict[str, Any]:
        from android_re_core.device.adb import shell

        out = shell(f"am force-stop {shlex.quote(package)}", serial=serial)
        return {"ok": True, "output": out[-500:]}

    @mcp.tool(
        name="list_processes",
        description=(
            "Enumerate running processes on a device. Optionally filter by name substring."
        ),
    )
    def list_processes(
        serial: Annotated[str, Field(description="Device serial")],
        name_substring: Annotated[
            str | None,
            Field(description="Optional substring filter on process name"),
        ] = None,
    ) -> dict[str, Any]:
        from android_re_core.device.adb import shell

        out = shell("ps -A", serial=serial)
        procs: list[dict[str, Any]] = []
        # `ps -A` on Android: USER PID PPID VSZ RSS WCHAN ADDR S NAME
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            name = parts[-1]
            if name_substring and name_substring not in name:
                continue
            try:
                pid = int(parts[1])
            except ValueError:
                continue
            procs.append({"pid": pid, "name": name})
        return {"serial": serial, "count": len(procs), "processes": procs}

    _ = get_session_store  # available for downstream tools
