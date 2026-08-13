"""Android emulator management.

Wraps the ``emulator`` CLI for headless start / list / kill. Used
by the dynamic MCP server's ``start_emulator`` tool (Phase 3+) and
by CI to spin up an emulator for the device test matrix.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import ToolFailed, ToolNotFound, ToolTimeout

__all__ = [
    "EmulatorInfo",
    "kill_emulator",
    "list_avds",
    "start_emulator",
    "wait_for_boot",
]


@dataclass(frozen=True)
class EmulatorInfo:
    """A single AVD (Android Virtual Device) entry."""

    name: str
    path: Path | None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "path": str(self.path) if self.path else None}


def _find_emulator() -> str:
    """Locate the ``emulator`` binary via $ANDROID_HOME or $PATH."""
    for sdk_root in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(sdk_root)
        if not root:
            continue
        candidate = Path(root) / "emulator" / ("emulator.exe" if os.name == "nt" else "emulator")
        if candidate.exists():
            return str(candidate)
    which = shutil.which("emulator")
    if which:
        return which
    raise ToolNotFound(
        "emulator",
        details={"hint": "Install via Android Studio SDK Manager."},
    )


def list_avds() -> list[EmulatorInfo]:
    """List available AVDs."""
    binary = _find_emulator()
    proc = subprocess.run(
        [binary, "-list-avds"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    out: list[EmulatorInfo] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or "Name:" not in line:
            continue
        # Format: "Name: <name>" or "Name: <name> Path: <path> Device: ..."
        parts = line.split(" Path: ")
        name = parts[0].split("Name: ", 1)[1].strip()
        path_str = parts[1].split(" ")[0].strip() if len(parts) > 1 else None
        out.append(EmulatorInfo(name=name, path=Path(path_str) if path_str else None))
    return out


def start_emulator(
    avd: str,
    *,
    headless: bool = True,
    no_audio: bool = True,
    no_anim: bool = True,
    no_snapshot: bool = True,
    gpu_mode: str = "swiftshader_indirect",
    timeout_s: int = 180,
) -> str:
    """Start an Android emulator in the background.

    Returns the adb serial of the new emulator (e.g.
    ``"emulator-5554"``).

    Args:
        avd: Name of the AVD.
        headless: If true, run without a window (for CI).
        no_audio: Disable audio output.
        no_anim: Disable boot animation (faster boot).
        no_snapshot: Do not auto-load a saved snapshot.
        gpu_mode: GPU backend (``swiftshader_indirect`` is the
            headless-friendly default).
        timeout_s: Maximum time to wait for the emulator to appear
            in ``adb devices``.
    """
    binary = _find_emulator()
    args: list[str] = [
        f"@{avd}",
        "-no-snapshot-load" if no_snapshot else "-snapshot-load",
        "-no-audio" if no_audio else "-audio",
        "-no-boot-anim" if no_anim else "-boot-anim",
    ]
    if headless:
        args.extend(["-no-window", "-gpu", gpu_mode])

    # Start in a new process group so we can kill the whole tree
    proc = subprocess.Popen(
        [binary, *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for the device to appear in adb devices
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            from .adb import list_devices

            for d in list_devices():
                if d.serial.startswith("emulator-"):
                    return d.serial
        except Exception:
            pass
        time.sleep(1.0)
    # Could not find it; clean up.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        pass
    raise ToolTimeout(
        f"Emulator did not appear in adb devices within {timeout_s}s",
        details={"avd": avd},
    )


def kill_emulator(serial: str, *, timeout_s: int = 30) -> None:
    """Kill an emulator by adb serial."""
    from .adb import run_adb

    try:
        run_adb(["-s", serial, "emu", "kill"], timeout_s=timeout_s)
    except ToolFailed as e:
        raise ToolFailed(f"emulator kill failed: {e}", details=e.details) from e


def wait_for_boot(serial: str, *, timeout_s: int = 300, poll_s: float = 2.0) -> bool:
    """Poll ``getprop sys.boot_completed`` until it's ``1``."""
    from .adb import getprop

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            value = getprop("sys.boot_completed", serial=serial)
        except Exception:
            value = ""
        if value.strip() == "1":
            return True
        time.sleep(poll_s)
    return False


_ = field  # silence linter
