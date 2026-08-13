"""Process-tree utilities for Wine on POSIX.

Wineserver holds an exclusive ``flock`` on the prefix dir. Killing
only the .exe leaves the wineserver alive and the prefix locked,
which breaks the next Wine invocation from any other prefix. This
module provides:

- ``find_child_pids`` — list of PIDs in a process tree
- ``kill_process_tree`` — SIGTERM, then SIGKILL after a grace period
- ``wineserver_kill`` — stop the wineserver for a specific prefix;
  refuses to operate on the user's default ``~/.wine``

On Windows hosts every function returns a structured error — Wine
is not available there, and ``re-winedbg`` reports this at
``check_winedbg`` time.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


_DEFAULT_WINE_PREFIX = str(Path.home() / ".wine")
_RE_AI_WINE_CACHE_ROOT = str(Path.home() / ".cache" / "re-ai-wine")


def _is_windows_host() -> bool:
    return sys.platform == "win32"


def _read_proc_status(pid: int) -> dict[str, str] | None:
    """Read ``/proc/<pid>/status`` fields. Returns ``None`` on
    permission-denied, missing process, or any other read failure."""
    try:
        text = Path(f"/proc/{pid}/status").read_text(
            encoding="utf-8", errors="replace"
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def find_child_pids(parent_pid: int) -> list[int]:
    """Return the list of descendant PIDs of *parent_pid*, recursively.

    Uses ``/proc`` on Linux. On macOS or any other POSIX without
    ``/proc``, returns ``[]`` (the caller must rely on the process
    being a single-PID wine wrapper, which is true on macOS).
    """
    if not Path("/proc").exists():
        return []
    children: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        status = _read_proc_status(pid)
        if status is None:
            continue
        try:
            ppid = int(status.get("PPid", "0"))
        except ValueError:
            continue
        if ppid == parent_pid:
            children.append(pid)
    result = list(children)
    for c in children:
        result.extend(find_child_pids(c))
    return result


def kill_process_tree(pid: int, grace_s: float = 2.0) -> list[int]:
    """Send ``SIGTERM`` to *pid* and its descendants, then ``SIGKILL``
    after *grace_s* to any survivors. Returns the list of PIDs that
    were signalled (best-effort; survivors are not reported)."""
    pids = [pid] + find_child_pids(pid)
    signalled: list[int] = []
    for p in pids:
        try:
            os.kill(p, signal.SIGTERM)
            signalled.append(p)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    time.sleep(grace_s)
    for p in pids:
        try:
            os.kill(p, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    return signalled


def wineserver_kill(
    prefix: str,
    wineserver_path: str = "wineserver",
    grace_s: float = 2.0,
) -> dict[str, Any]:
    """Stop the wineserver for *prefix*.

    Refuses to operate on the user's default ``~/.wine`` — only kills
    servers for prefixes under ``~/.cache/re-ai-wine/`` that this
    server created. Returns a structured status dict.
    """
    if _is_windows_host():
        return {"status": "ERROR", "error": "host_not_supported"}
    if not prefix:
        return {"status": "ERROR", "error": "empty_prefix"}
    if prefix == _DEFAULT_WINE_PREFIX:
        return {
            "status": "ERROR",
            "error": "refusing_to_kill_global_wineserver",
            "hint": "use a per-session WINEPREFIX under ~/.cache/re-ai-wine/",
        }
    if not prefix.startswith(_RE_AI_WINE_CACHE_ROOT):
        return {
            "status": "ERROR",
            "error": "refusing_to_kill_external_wineserver",
            "hint": f"prefix must be under {_RE_AI_WINE_CACHE_ROOT}",
        }
    try:
        proc = subprocess.run(
            [wineserver_path, "-k"],
            env={**os.environ, "WINEPREFIX": prefix},
            capture_output=True,
            text=True,
            timeout=grace_s + 5,
            check=False,
        )
        return {
            "status": "OK" if proc.returncode == 0 else "WARN",
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError:
        return {"status": "WARN", "error": "wineserver not on PATH"}
    except subprocess.TimeoutExpired:
        return {"status": "WARN", "error": "wineserver -k timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "error": str(exc)}
