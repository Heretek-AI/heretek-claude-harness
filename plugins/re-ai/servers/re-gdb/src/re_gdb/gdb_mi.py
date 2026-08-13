"""Persistent GDB subprocess driver.

One GDB instance per "session" string. We drive GDB via its MI (machine
interface) commands and parse the structured responses. On Windows,
pexpect is unavailable; we fall back to subprocess pipes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Try to import pexpect; on Windows it's not available, but pywinpty can
# wrap a console process. We pick whichever works.
_HAS_PEXPECT = False
_HAS_WINPTY = False
try:
    import pexpect  # type: ignore
    _HAS_PEXPECT = True
except ImportError:
    try:
        import winpty  # type: ignore
        _HAS_WINPTY = True
    except ImportError:
        pass


def get_gdb_path() -> str:
    return os.environ.get("GDB_PATH") or shutil.which("gdb") or "gdb"


def get_gef_path() -> str:
    return os.environ.get("GEF_PATH") or str(Path.home() / ".gdb" / "gef.py")


# ── Session management ─────────────────────────────────────────────────


class GDBSession:
    """One persistent GDB subprocess. Thread-safe send/recv."""

    def __init__(self, session_id: str, gdb_args: list[str] | None = None) -> None:
        self.session_id = session_id
        self.gdb_args = gdb_args or ["--quiet", "--nx", "--nh"]
        # Auto-source GEF if available
        gef = get_gef_path()
        if Path(gef).exists():
            self.gdb_args = list(self.gdb_args) + ["-ex", f"source {gef}"]
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_token = 1
        self._output: list[str] = []
        self._reader_thread: threading.Thread | None = None
        self._open()

    def _open(self) -> None:
        cmd = [get_gdb_path(), "--interpreter=mi3"] + self.gdb_args
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            # Windows: avoid spawning a console window
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # Drain the initial banner / prompt.
        time.sleep(0.2)
        self._drain()

    def _drain(self) -> None:
        """Read and discard any pending output (non-blocking)."""
        assert self.proc and self.proc.stdout
        # Cycle 2 fix: Python 3.14 renamed TextIOWrapper.setblocking to
        # set_blocking; the prior `getattr(..., "set_blocking", None) or
        # .setblocking` chain raised AttributeError on 3.14 because
        # setblocking is gone. Probe each name via getattr(default=None)
        # and only call the one that exists.
        set_nonblock = (
            getattr(self.proc.stdout, "set_blocking", None)
            or getattr(self.proc.stdout, "setblocking", None)
        )
        if set_nonblock is not None:
            set_nonblock(False)
        try:
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    break
                self._output.append(line)
        except (BlockingIOError, OSError):
            pass
        finally:
            set_nonblock(True)

    def send(self, command: str) -> dict[str, Any]:
        """Send a CLI command (not MI) to GDB, return raw output."""
        with self._lock:
            assert self.proc and self.proc.stdin and self.proc.stdout
            token = str(self._next_token)
            self._next_token += 1
            self.proc.stdin.write(f"{command}\n")
            self.proc.stdin.flush()
            # Read until we see the prompt "(gdb) "
            buf: list[str] = []
            deadline = time.time() + 30
            while time.time() < deadline:
                line = self.proc.stdout.readline()
                if not line:
                    break
                buf.append(line.rstrip())
                # A2 fix (v2.8.0): MI3 prompt is literally "(gdb) \n"
                # (with trailing space). rstrip() strips both \n and the
                # trailing space, leaving "(gdb)" — so a prior check of
                # endswith("(gdb) ") could never match and every send()
                # blocked the full 30s deadline. Compare against the
                # rstripped form. Confirmed via xxd of `gdb --interpreter=mi3`
                # output: byte sequence `28 67 64 62 29 20 0a`.
                if line.rstrip().endswith("(gdb)"):
                    break
            return {"session": self.session_id, "command": command, "output": "\n".join(buf)}

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write("-gdb-exit\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                self.proc.terminate()
        self.proc = None


# Global session registry, keyed by an arbitrary session-id string.
_SESSIONS: dict[str, GDBSession] = {}
_SESSIONS_LOCK = threading.Lock()


def get_session(session_id: str) -> GDBSession:
    with _SESSIONS_LOCK:
        s = _SESSIONS.get(session_id)
        if s is None:
            s = GDBSession(session_id)
            _SESSIONS[session_id] = s
        return s


def end_session(session_id: str) -> None:
    with _SESSIONS_LOCK:
        s = _SESSIONS.pop(session_id, None)
    if s is not None:
        s.close()


# ── Tool implementations ────────────────────────────────────────────────


def check_gdb() -> dict[str, Any]:
    """Return gdb version + whether GEF is loaded."""
    info: dict[str, Any] = {"gdb": None, "gef": None, "status": "OK"}
    try:
        proc = subprocess.run(
            [get_gdb_path(), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            info["gdb"] = (proc.stdout or "").strip().splitlines()[0]
    except Exception as exc:  # noqa: BLE001
        info["gdb"] = f"NOT FOUND: {exc}"
        info["status"] = "WARN"
    gef = get_gef_path()
    info["gef"] = str(gef) if Path(gef).exists() else f"NOT FOUND at {gef}"
    return info


def start_session(
    path: str = "",
    gdb_args: list[str] | None = None,
    session: str = "default",
) -> dict[str, Any]:
    """Open a GDB session. Optionally load a binary."""
    s = get_session(session)
    out: list[dict[str, Any]] = []
    if path:
        out.append(s.send(f"-file-exec-and-symbols {path}"))
    out.append(s.send("info functions"))
    return {"session": session, "steps": out}


def end_session_tool(session: str) -> dict[str, Any]:
    end_session(session)
    return {"session": session, "status": "ended"}


def run_to_breakpoint(
    session: str, target: str, condition: str = ""
) -> dict[str, Any]:
    """Set a breakpoint at *target* (function name or ``*addr``) and run."""
    s = get_session(session)
    out = [
        s.send(f"break {target}"),
        s.send(f"condition 1 {condition}" if condition else "condition 1"),
        s.send("run"),
    ]
    return {"session": session, "target": target, "steps": out}


def step_count(session: str, count: int = 1) -> dict[str, Any]:
    s = get_session(session)
    out = [s.send(f"stepi {count}"), s.send("info registers")]
    return {"session": session, "count": count, "steps": out}


def read_memory(
    session: str, addr: str, count: int = 16, fmt: str = "hex"
) -> dict[str, Any]:
    s = get_session(session)
    out = s.send(f"x/{count}{fmt[0]} {addr}")
    return {"session": session, "addr": addr, "count": count, "fmt": fmt, "output": out}


# ── GEF convenience commands ──────────────────────────────────────────


def gef_command(session: str, command: str) -> dict[str, Any]:
    """Run a GEF command (heap, canary, registers, vmmap, nearpc, etc.)."""
    s = get_session(session)
    return {"session": session, "command": command, "output": s.send(command)}


def gef_heap(session: str) -> dict[str, Any]:
    return gef_command(session, "heap chunks")


def gef_canary(session: str) -> dict[str, Any]:
    return gef_command(session, "canary")


def gef_registers(session: str) -> dict[str, Any]:
    return gef_command(session, "registers")


def gef_vmmap(session: str) -> dict[str, Any]:
    return gef_command(session, "vmmap")


def gef_nearpc(session: str, n: int = 8) -> dict[str, Any]:
    return gef_command(session, f"nearpc {n}")


def gef_pattern_create(length: int) -> dict[str, Any]:
    """Generate a cyclic pattern of *length* bytes (for offset-finding)."""
    # GDB's pattern_create doesn't exist; we use a python one-liner.
    import string

    charset = string.ascii_letters + string.digits
    out = []
    for a in range(len(charset)):
        for b in range(len(charset)):
            for c in range(len(charset)):
                if len("".join(out)) >= length:
                    return {"pattern": "".join(out)[:length], "length": length}
                out.append(charset[a] + charset[b] + charset[c])
    return {"pattern": "".join(out)[:length], "length": length}


def gef_pattern_offset(value: str) -> dict[str, Any]:
    """Find the offset of *value* in the cyclic pattern."""
    if len(value) < 4:
        return {"error": "value must be at least 4 bytes"}
    pat = gef_pattern_create(1024 * 1024)["pattern"]
    idx = pat.find(value)
    if idx == -1:
        return {"value": value, "offset": -1, "found": False}
    return {"value": value, "offset": idx, "found": True}


def attach_pid(session: str, pid: int) -> dict[str, Any]:
    s = get_session(session)
    return {"session": session, "pid": pid, "output": s.send(f"attach {pid}")}
