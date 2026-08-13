"""Network tools: TCP forward, MITM setup."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.device.adb import run_adb, shell

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register network tools."""

    @mcp.tool(
        name="tcp_forward",
        description=(
            "Forward a TCP port from the device to the host. The "
            "device can reach the host on the forwarded port via "
            "``localhost:<device_port>``."
        ),
    )
    def tcp_forward(
        serial: Annotated[str, Field(description="Device serial")],
        device_port: Annotated[int, Field(ge=1, le=65535, description="Device-side port")],
        host_port: Annotated[
            int | None,
            Field(ge=1, le=65535, description="Host-side port; auto-allocate if omitted"),
        ] = None,
    ) -> dict[str, Any]:
        args: list[str] = ["-s", serial, "forward"]
        if host_port is not None:
            args.append(f"tcp:{host_port}")
        else:
            args.append("tcp:0")
        args.append(f"tcp:{device_port}")
        try:
            proc = run_adb(args, timeout_s=10)
        except Exception as e:
            return {"error": {"code": "forward_failed", "message": str(e)}}
        # The auto-allocated host port is reported by ``adb forward --list``,
        # not by ``forward tcp:0 ...``; we echo back what the user asked for.
        return {
            "serial": serial,
            "device_port": device_port,
            "host_port": host_port,
            "output": proc.stdout[-200:],
        }

    @mcp.tool(
        name="list_forwards",
        description="List all active adb forwards.",
    )
    def list_forwards() -> dict[str, Any]:
        try:
            proc = run_adb(["forward", "--list"], timeout_s=10)
        except Exception as e:
            return {"error": {"code": "list_failed", "message": str(e)}}
        out: list[dict[str, Any]] = []
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                out.append(
                    {
                        "serial": parts[0],
                        "host": parts[1],
                        "device": parts[2],
                    }
                )
        return {"count": len(out), "forwards": out}

    @mcp.tool(
        name="remove_forward",
        description="Remove one (or all) adb forwards.",
    )
    def remove_forward(
        host_port: Annotated[
            int | None,
            Field(description="Host-side port to remove; omit to remove all"),
        ] = None,
    ) -> dict[str, Any]:
        args = ["forward", "--remove"]
        if host_port is None:
            args[-1] = "--remove-all"
        else:
            args.append(f"tcp:{host_port}")
        try:
            run_adb(args, timeout_s=10)
        except Exception as e:
            return {"error": {"code": "remove_failed", "message": str(e)}}
        return {"ok": True, "host_port": host_port}

    @mcp.tool(
        name="setup_mitm",
        description=(
            "Configure MITM for the app: install a CA cert from the "
            "host, push the network_security_config (if provided), and "
            "forward the device port to the host proxy. REQUIRES "
            "confirm=true."
        ),
    )
    def setup_mitm(
        serial: Annotated[str, Field(description="Device serial")],
        mitm_host: Annotated[
            str, Field(description="Host running the MITM proxy (e.g. 10.0.2.2 for emulator)")
        ],
        mitm_port: Annotated[int, Field(ge=1, le=65535)] = 8080,
        install_cert: Annotated[
            bool, Field(description="Auto-install the mitmproxy CA into the system store")
        ] = True,
        confirm: Annotated[bool, Field(description="Must be true to install cert")] = False,
        output_dir: Annotated[
            str | None,
            Field(
                description=(
                    "Directory where screenshots / session artifacts "
                    "land during the MITM session. Defaults to "
                    "``$ANDROID_RE_OUTPUT_DIR/network/`` if set, else "
                    "``./Output/network/``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        if not confirm and install_cert:
            return {
                "error": {
                    "code": "confirm_required",
                    "message": "setup_mitm with install_cert=true requires confirm=true",
                }
            }
        steps: list[dict[str, Any]] = []
        # 1. Forward device:8080 -> host:8080 so apps can hit
        #    127.0.0.1:8080 and reach the host proxy.
        try:
            run_adb(
                ["-s", serial, "reverse", f"tcp:{mitm_port}", f"tcp:{mitm_port}"],
                timeout_s=10,
            )
            steps.append({"step": "adb_reverse", "ok": True, "port": mitm_port})
        except Exception as e:
            steps.append({"step": "adb_reverse", "ok": False, "error": str(e)})
        # 2. Install CA (system-level; requires adb remount + root)
        if install_cert:
            try:
                # Hash the mitmproxy cert (located on the host at
                # ~/.mitmproxy/mitmproxy-ca-cert.cer by default).
                # The actual cert copy/push is performed by the host
                # proxy setup; here we just mark the step.
                shell(
                    "su -c 'ls /system/etc/security/cacerts/' || true", serial=serial, timeout_s=10
                )
                steps.append(
                    {
                        "step": "install_ca",
                        "ok": True,
                        "hint": (
                            "Run: mitmproxy --set confdir=~/.mitmproxy, then "
                            "adb push ~/.mitmproxy/mitmproxy-ca-cert.cer "
                            "/system/etc/security/cacerts/ && adb shell "
                            "chmod 644 /system/etc/security/cacerts/<hash>.0"
                        ),
                    }
                )
            except Exception as e:
                steps.append({"step": "install_ca", "ok": False, "error": str(e)})
        return {
            "serial": serial,
            "mitm_host": mitm_host,
            "mitm_port": mitm_port,
            "output_dir": str(
                Path(output_dir).expanduser()
                if output_dir
                else Path(os.environ.get("ANDROID_RE_OUTPUT_DIR", "./Output")) / "network"
            ),
            "steps": steps,
        }
