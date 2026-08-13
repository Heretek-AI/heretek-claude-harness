"""Thin typed wrapper around the ``adb`` CLI.

Used by the dynamic MCP server for low-level device control.
The mcp_bridge TypeScript server uses adbkit (an async connection-
pooled client) for the same job, but at a different layer. Both
share the same ADB binary and the same device list.

The wrapper is intentionally read-only: it does not install, push,
or pull files. Those operations go through the dynamic MCP server
with explicit ``confirm: bool`` gates.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

from ..errors import ToolFailed, ToolNotFound, ToolTimeout
from ..paths import find_adb

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "AdbDevice",
    "dumpsys",
    "get_state",
    "getprop",
    "list_devices",
    "run_adb",
    "shell",
]


#: Default subprocess timeout for ``adb`` calls (seconds).
DEFAULT_TIMEOUT_S: int = 30


@dataclass(frozen=True)
class AdbDevice:
    """A single device reported by ``adb devices``."""

    serial: str
    state: str  # "device" | "offline" | "unauthorized" | "no permissions"

    def to_dict(self) -> dict[str, Any]:
        return {"serial": self.serial, "state": self.state}


def run_adb(
    args: list[str],
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    serial: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an ``adb`` subprocess with a timeout and structured errors.

    Args:
        args: Arguments to pass after ``adb``.
        timeout_s: Subprocess timeout in seconds.
        serial: Optional device serial. When set, ``-s <serial>`` is
            prepended to the command.

    Returns:
        The completed :class:`subprocess.CompletedProcess`.

    Raises:
        ToolNotFound: adb is not on PATH.
        ToolTimeout: adb did not complete in time.
        ToolFailed: adb exited with a non-zero status.
    """
    binary = find_adb()
    cmd: list[str] = [str(binary)]
    if serial is not None:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ToolTimeout(
            f"adb timed out after {timeout_s}s",
            details={"cmd": cmd},
        ) from e
    except FileNotFoundError as e:
        raise ToolNotFound(
            "adb",
            details={"hint": "Install Android Platform Tools and set ANDROID_HOME."},
        ) from e
    if proc.returncode != 0:
        raise ToolFailed(
            f"adb failed (exit {proc.returncode})",
            details={
                "cmd": cmd,
                "stdout": proc.stdout[-1000:],
                "stderr": proc.stderr[-1000:],
            },
        )
    return proc


def list_devices() -> list[AdbDevice]:
    """Run ``adb devices -l`` and parse the output."""
    proc = run_adb(["devices", "-l"])
    out: list[AdbDevice] = []
    for line in proc.stdout.splitlines()[1:]:  # skip header
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        out.append(AdbDevice(serial=serial, state=state))
    return out


def get_state(serial: str | None = None) -> str:
    """Return the device state (e.g. ``"device"``, ``"offline"``)."""
    proc = run_adb(["get-state"], serial=serial)
    return proc.stdout.strip()


def shell(
    command: str,
    *,
    serial: str | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Run ``adb shell <command>`` and return stdout.

    The command is passed as a single string; it is **not** tokenized.
    Use ``shell_argv`` for that.
    """
    proc = run_adb(["shell", command], serial=serial, timeout_s=timeout_s)
    return proc.stdout


def shell_argv(
    argv: list[str],
    *,
    serial: str | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Run ``adb shell <args...>`` with explicit argv.

    The args are joined with ``shlex.quote`` so spaces and shell
    metacharacters are preserved across the adb boundary.
    """
    quoted = " ".join(shlex.quote(a) for a in argv)
    return shell(quoted, serial=serial, timeout_s=timeout_s)


def getprop(prop: str, *, serial: str | None = None) -> str:
    """Read a system property via ``adb shell getprop``."""
    return shell(f"getprop {shlex.quote(prop)}", serial=serial).strip()


def dumpsys(
    service: str,
    *,
    args: list[str] | None = None,
    serial: str | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Run ``adb shell dumpsys <service> [args...]``."""
    argv = ["dumpsys", service, *(args or [])]
    return shell_argv(argv, serial=serial, timeout_s=timeout_s)


# Internal helper to silence unused-import warnings.
_ = os
