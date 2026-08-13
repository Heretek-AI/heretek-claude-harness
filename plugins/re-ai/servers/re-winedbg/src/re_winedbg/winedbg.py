"""Wine winedbg-gdbserver + gdb-client orchestration.

This module owns:

- the ``WinedbgSession`` dataclass (one per MCP session-id)
- the module-level ``_SESSIONS`` / ``_SESSIONS_LOCK`` registry
- the 19 tool implementations (one per ``@mcp.tool()`` in server.py)

The gdb-client side delegates to ``re_gdb.gdb_mi.GDBSession`` so we
get the persistent subprocess, the prompt-sentinel read loop, and
the per-session lock for free. The winedbg gdbserver and the wine
process are managed here, alongside a per-module base-address cache
populated from ``info sharedlibrary`` on first attach.

Vendor-neutral by design. Tool names and docstrings use only
generic debugger vocabulary — no commercial product, publisher, or
game title appears anywhere in this file.
"""

from __future__ import annotations

import base64
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from re_gdb.gdb_mi import GDBSession, get_gdb_path

from re_winedbg import gdb_text, process_tree


# ── env-var-aware binary locators ───────────────────────────────────────


def _env_or_path(env_var: str, default: str) -> str:
    return os.environ.get(env_var) or shutil.which(default) or default


def _wine_path() -> str:
    return _env_or_path("WINE_PATH", "wine")


def _winedbg_path() -> str:
    return _env_or_path("WINEDBG_PATH", "winedbg")


def _wineserver_path() -> str:
    return _env_or_path("WINESERVER_PATH", "wineserver")


# ── Wine version detection (A1 fix; v2.8.0) ─────────────────────────────


_WINE_VERSION_CACHE: tuple[int, int] | None = None


def _wine_major_version() -> int:
    """Return the major component of the installed Wine version.

    Wine 11.0 changed ``winedbg --gdb <exe>`` to run gdb interactively
    over stdin/stdout instead of binding a TCP port. The
    ``attach_winedbg_gdbserver`` tool dispatches on this value:
    Wine >= 11 uses the stdio path; Wine <= 10 keeps the TCP path.

    Cached after the first call. Returns ``0`` if Wine is not
    installed or the version can't be parsed (the caller will
    surface an ERROR through ``check_winedbg``).
    """
    global _WINE_VERSION_CACHE
    if _WINE_VERSION_CACHE is None:
        try:
            proc = subprocess.run(
                [_wine_path(), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            raw = (proc.stdout or proc.stderr or "").strip()
            # Examples:
            #   "wine-11.0 (Staging)"
            #   "wine-10.4"
            #   "wine-9.0"
            import re

            m = re.search(r"wine-(\d+)\.(\d+)", raw)
            if m:
                _WINE_VERSION_CACHE = (int(m.group(1)), int(m.group(2)))
            else:
                _WINE_VERSION_CACHE = (0, 0)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _WINE_VERSION_CACHE = (0, 0)
    return _WINE_VERSION_CACHE[0]


# ── Wine 11+ stdio gdb-client shim (A1 fix; v2.8.0) ─────────────────────


class WinedbgStdioClient:
    """Wine 11+ ``winedbg --gdb <exe>`` runs gdb interactively over the
    parent's stdin / stdout — no TCP port is bound. This shim wraps the
    existing winedbg subprocess and exposes a ``send()`` method matching
    ``re_gdb.gdb_mi.GDBSession.send()``'s signature, so downstream tools
    (``set_breakpoint``, ``continue_execution``, ``read_memory``, etc.)
    work without any further modification — they call
    ``client.send(cmd)`` and get back ``{session, command, output}``.

    The prompt sentinel is ``Wine-gdb> `` (not ``(gdb) ``) — verified
    via interactive launch of ``winedbg --gdb /path/to/cmd.exe`` on
    Wine 11.0 Staging.

    POSIX-only: uses ``select`` + ``os.read`` on the stdout fileno.
    Safe because ``start_winedbg_gdbserver`` never reads from the
    subprocess's stdout (only stderr, for port parsing), so Python's
    BufferedReader hasn't pre-buffered any bytes.
    """

    PROMPT_BYTES = b"Wine-gdb> "

    def __init__(self, session_id: str, proc: subprocess.Popen) -> None:
        self.session_id = session_id
        self.proc = proc
        self._lock = threading.Lock()
        self._buf = b""
        # Drain the winedbg startup banner up to the first prompt.
        # On Wine 11.0 Staging this includes the gdb version banner,
        # "Reading symbols from <exe>...", the entry-point disassembly,
        # and the debuginfod opt-in question (which we let answer "n").
        self._drain_to_prompt(timeout=15.0)

    def _drain_to_prompt(self, timeout: float) -> str:
        """Read until ``Wine-gdb> `` appears or the deadline passes."""
        import select

        deadline = time.time() + timeout
        if not self.proc.stdout:
            return ""
        fd = self.proc.stdout.fileno()
        captured = bytearray()
        while time.time() < deadline:
            if self.PROMPT_BYTES in self._buf:
                idx = self._buf.index(self.PROMPT_BYTES) + len(
                    self.PROMPT_BYTES
                )
                captured.extend(self._buf[:idx])
                self._buf = self._buf[idx:]
                break
            r, _, _ = select.select([fd], [], [], 0.2)
            if not r:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            self._buf += chunk
        # If we time out, return whatever we captured (caller will
        # surface a partial output to the agent rather than hanging).
        if not captured and self._buf:
            captured.extend(self._buf)
            self._buf = b""
        return captured.decode("utf-8", errors="replace")

    def send(self, command: str) -> dict[str, Any]:
        """Send a CLI command to the Wine-gdb interactive session and
        return the raw output up to the next prompt.

        Matches ``GDBSession.send()``'s return shape so downstream
        tools don't need to know which client is in play.
        """
        with self._lock:
            if not self.proc.stdin:
                return {
                    "session": self.session_id,
                    "command": command,
                    "output": "",
                    "error": "stdin_closed",
                }
            try:
                self.proc.stdin.write((command + "\n").encode("utf-8"))
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                return {
                    "session": self.session_id,
                    "command": command,
                    "output": "",
                    "error": f"write_failed: {exc}",
                }
            output = self._drain_to_prompt(timeout=30.0)
            return {
                "session": self.session_id,
                "command": command,
                "output": output,
            }

    def close(self) -> None:
        """Send ``quit`` and reap the winedbg subprocess. Idempotent."""
        if self.proc.poll() is None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(b"quit\n")
                    self.proc.stdin.flush()
                self.proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                try:
                    self.proc.terminate()
                except Exception:  # noqa: BLE001
                    pass


# ── free-port picker ────────────────────────────────────────────────────


def _pick_free_port() -> int:
    """Bind to port 0, read the OS-assigned port, close. Race-prone in
    theory (the port may be re-bound by another process before
    winedbg opens it) but in practice fine for a single-user
    workstation. A subsequent bind failure inside winedbg will
    surface as a clear error to the agent."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── session model ───────────────────────────────────────────────────────


@dataclass
class WinedbgSession:
    """One Wine debug session. Registered in ``_SESSIONS`` by
    session-id. ``_lock`` guards *all* state and serializes gdb
    commands; the inner ``GDBSession._lock`` is acquired as part
    of each gdb-client call (no deadlock — the outer lock is
    always held first)."""

    session_id: str
    wine_prefix: str
    exe: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    host_pid: int | None = None  # wine wrapper PID (if launched)
    gdbserver_proc: subprocess.Popen | None = None
    gdbserver_port: int | None = None
    gdb_client: GDBSession | WinedbgStdioClient | None = None
    gdb_attached: bool = False
    module_bases: dict[str, int] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)


_SESSIONS: dict[str, WinedbgSession] = {}
_SESSIONS_LOCK = threading.Lock()


def get_session(session_id: str) -> WinedbgSession:
    with _SESSIONS_LOCK:
        s = _SESSIONS.get(session_id)
        if s is None:
            s = WinedbgSession(
                session_id=session_id,
                wine_prefix="",
                exe="",
            )
            _SESSIONS[session_id] = s
        return s


def _teardown_locked(s: WinedbgSession) -> None:
    """Tear down a session's process tree. Caller must hold
    ``s._lock``. Idempotent."""
    if s.gdb_client is not None:
        try:
            s.gdb_client.close()
        except Exception:  # noqa: BLE001
            pass
        s.gdb_client = None
    if s.gdbserver_proc is not None and s.gdbserver_proc.poll() is None:
        try:
            s.gdbserver_proc.terminate()
            s.gdbserver_proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                s.gdbserver_proc.kill()
            except Exception:  # noqa: BLE001
                pass
    s.gdbserver_proc = None
    if s.host_pid is not None:
        try:
            process_tree.kill_process_tree(s.host_pid)
        except Exception:  # noqa: BLE001
            pass
    s.host_pid = None
    if s.wine_prefix:
        process_tree.wineserver_kill(s.wine_prefix, _wineserver_path())


# ── tool: check_winedbg ─────────────────────────────────────────────────


def check_winedbg() -> dict[str, Any]:
    """Return wine + winedbg + gdb availability. Never raises."""
    if sys.platform == "win32":
        return {
            "status": "ERROR",
            "error": "host_not_supported",
            "hint": "re-winedbg requires Wine (Linux/macOS). On Windows use the native debuggers.",
        }
    info: dict[str, Any] = {
        "status": "OK",
        "wine_path": None,
        "winedbg_path": None,
        "wine_version": None,
        "winedbg_version": None,
        "gdb_path": None,
        "gdb_version": None,
    }
    try:
        proc = subprocess.run(
            [_wine_path(), "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if proc.returncode == 0:
            info["wine_path"] = shutil.which(_wine_path()) or _wine_path()
            info["wine_version"] = (proc.stdout or "").strip().splitlines()[0]
        else:
            info["status"] = "WARN"
            info["wine_path"] = "NOT FOUND"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["status"] = "WARN"
        info["wine_path"] = "NOT FOUND"
    try:
        proc = subprocess.run(
            [_winedbg_path(), "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if proc.returncode == 0:
            info["winedbg_path"] = shutil.which(_winedbg_path()) or _winedbg_path()
            info["winedbg_version"] = (proc.stdout or "").strip().splitlines()[0]
        else:
            info["status"] = "WARN"
            info["winedbg_path"] = "NOT FOUND"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["status"] = "WARN"
        info["winedbg_path"] = "NOT FOUND"
    try:
        proc = subprocess.run(
            [get_gdb_path(), "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if proc.returncode == 0:
            info["gdb_path"] = get_gdb_path()
            info["gdb_version"] = (proc.stdout or "").strip().splitlines()[0]
        else:
            info["status"] = "WARN"
            info["gdb_path"] = "NOT FOUND"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["status"] = "WARN"
        info["gdb_path"] = "NOT FOUND"
    return info


# ── tool: launch_under_wine ─────────────────────────────────────────────


def launch_under_wine(
    exe: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    wine_prefix: str | None = None,
    wait_ms: int = 0,
    session: str = "default",
) -> dict[str, Any]:
    """Run ``wine <exe> [args...]`` in a tracked process. Returns the
    host-side PID. The session is registered (and the process
    tracked) so ``end_session`` can kill it later.

    If ``wine_prefix`` is not provided, a fresh random directory is
    created under ``~/.cache/re-ai-wine/<session>/``.
    """
    if sys.platform == "win32":
        return {"status": "ERROR", "error": "host_not_supported"}
    if not exe or not Path(exe).exists():
        return {"status": "ERROR", "error": "exe_not_found", "exe": exe}
    args = args or []
    env = env or {}
    s = get_session(session)
    with s._lock:
        if not wine_prefix:
            cache_root = Path.home() / ".cache" / "re-ai-wine"
            cache_root.mkdir(parents=True, exist_ok=True)
            wine_prefix = tempfile.mkdtemp(prefix=f"{session}-", dir=str(cache_root))
        s.wine_prefix = wine_prefix
        s.exe = exe
        s.args = list(args)
        s.env = dict(env)
        run_env = {**os.environ, "WINEPREFIX": wine_prefix, **env}
        cmd = [_wine_path(), exe, *args]
        try:
            proc = subprocess.Popen(
                cmd,
                env=run_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # On Windows we wouldn't be here; on Linux we want no
                # console window, on macOS no special flag needed.
                **({"creationflags": subprocess.CREATE_NO_WINDOW}
                   if sys.platform == "win32" else {}),
            )
        except FileNotFoundError:
            return {"status": "ERROR", "error": "wine_not_found"}
        s.host_pid = proc.pid
        if wait_ms > 0:
            try:
                proc.wait(timeout=wait_ms / 1000.0)
            except subprocess.TimeoutExpired:
                pass
        return {
            "session": session,
            "status": "started",
            "pid": proc.pid,
            "exe": exe,
            "args": list(args),
            "wine_prefix": wine_prefix,
            "command_line": " ".join(cmd),
        }


# ── tool: start_winedbg_gdbserver ───────────────────────────────────────


def start_winedbg_gdbserver(
    exe: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    wine_prefix: str | None = None,
    port: int = 0,
    session: str = "default",
) -> dict[str, Any]:
    """Spawn ``winedbg --gdb <cmdline>``. The .exe is paused at its
    entry point. If ``port`` is 0, a free TCP port is chosen and
    winedbg's actual bound port is parsed from its stderr (or 0 if
    not detectable; the caller can fall back to the requested port
    via :func:`attach_winedbg_gdbserver`).

    Cycle 1 / T1.3 fix: the prior implementation constructed
    ``winedbg --gdb <port> <exe>`` which winedbg rejected — modern
    winedbg expects the WHOLE cmdline after ``--gdb`` and
    auto-selects the bound port. This implementation now:
      1. Peeks a free port (for the response field + attach fallback)
      2. Spawns ``winedbg --gdb <exe> [args]`` (port is dropped)
      3. Reads stderr for a bound-port line (best-effort)
      4. Falls back to the peeked port if the line can't be parsed
    """
    if sys.platform == "win32":
        return {"status": "ERROR", "error": "host_not_supported"}
    if not exe or not Path(exe).exists():
        return {"status": "ERROR", "error": "exe_not_found", "exe": exe}
    args = args or []
    env = env or {}
    s = get_session(session)
    with s._lock:
        if not wine_prefix:
            cache_root = Path.home() / ".cache" / "re-ai-wine"
            cache_root.mkdir(parents=True, exist_ok=True)
            wine_prefix = tempfile.mkdtemp(prefix=f"{session}-", dir=str(cache_root))
        s.wine_prefix = wine_prefix
        s.exe = exe
        s.args = list(args)
        s.env = dict(env)
        # Peek a free port for the response field. On Wine < 11.0
        # winedbg auto-binds that port and the gdbclient attaches
        # over TCP. On Wine >= 11.0 winedbg's gdbserver starts on
        # stdin/stdout (no TCP bind) — the peeked port is still
        # reported in the response for the caller's diagnostic, but
        # the actual gdbserver protocol runs over the stdio pipes.
        if port == 0:
            port = _pick_free_port()
        run_env = {**os.environ, "WINEPREFIX": wine_prefix, **env}
        # Cycle 2 fix: `stdin=PIPE` (was DEVNULL). Wine 11.0 winedbg's
        # gdbserver runs over stdio; DEVNULL breaks that path entirely
        # (gdbserver sees EOF on stdin and exits before attach).
        cmd = [_winedbg_path(), "--gdb", exe, *args]
        try:
            proc = subprocess.Popen(
                cmd,
                env=run_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            return {"status": "ERROR", "error": "winedbg_not_found"}
        s.gdbserver_proc = proc
        # Best-effort: peek at the actual bound port from winedbg's
        # stderr. winedbg --gdb emits `gdb: <port>` on stdout/stderr
        # on most Wine versions. If we can't parse it, fall back to
        # the peeked port (the gdbclient attach will then either bind
        # to that or fail loudly).
        actual_port = _read_winedbg_bound_port(proc, fallback=port, timeout=2.0)
        s.gdbserver_port = actual_port or port
        return {
            "session": session,
            "status": "started",
            "port": s.gdbserver_port,
            "requested_port": port,
            "actual_port_source": "stderr" if actual_port else "fallback",
            "exe": exe,
            "args": list(args),
            "wine_prefix": wine_prefix,
            "gdbserver_pid": proc.pid,
            "command_line": " ".join(cmd),
        }


def _read_winedbg_bound_port(
    proc: subprocess.Popen, fallback: int, timeout: float = 2.0
) -> int | None:
    """Parse winedbg's bound port from its stderr, best-effort.

    Wine's winedbg emits a line like ``gdb: 12345`` (or the
    ``Remote debugging using ... 12345`` form) when the gdbserver
    binds a port. This helper reads stderr in a background thread
    for up to *timeout* seconds and returns the first integer it
    finds in a line that looks like a port announcement.

    Returns None if no parseable line is seen before the deadline.
    """
    import re
    import select
    import threading

    port_pattern = re.compile(r"(?:gdb:?\s+|Remote debugging using\s+\S+\s+)(\d{2,5})\b")
    captured: list[int] = []
    found = threading.Event()

    def _reader() -> None:
        try:
            # Poll stderr without blocking the main thread.
            fd = proc.stderr.fileno() if proc.stderr else -1
            buf = b""
            deadline = time.time() + timeout
            while time.time() < deadline and not found.is_set():
                if fd < 0 or not proc.stderr:
                    # No fileno — fall back to a blocking read with a
                    # short timeout via select (POSIX-only).
                    chunk = proc.stderr.read(256) if proc.stderr else b""
                else:
                    r, _, _ = select.select([fd], [], [], 0.2)
                    if not r:
                        continue
                    chunk = os.read(fd, 256)
                if not chunk:
                    break
                buf += chunk
                # Try to find a port announcement in what we have.
                # We only need the first hit; the loop is conservative.
                m = port_pattern.search(buf.decode("utf-8", errors="replace"))
                if m:
                    captured.append(int(m.group(1)))
                    found.set()
                    return
        except Exception:  # noqa: BLE001
            pass
        finally:
            found.set()  # unblock the main thread even on error

    if not proc.stderr:
        return None
    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    # If winedbg dies quickly, the reader thread will exit; poll
    # until the event is set or the process is gone.
    while not found.wait(timeout=0.2):
        if proc.poll() is not None and time.time() > _safe_deadline():
            break
    # Give the reader a moment to finalize; if it already returned
    # with a port, we're done.
    found.wait(timeout=0.5)
    return captured[0] if captured else None


def _safe_deadline() -> float:
    """Return a wall-clock deadline 5 seconds in the future (helper for the reader loop)."""
    return time.time() + 5.0


# ── tool: attach_winedbg_gdbserver ──────────────────────────────────────


def attach_winedbg_gdbserver(
    session: str,
    host: str = "127.0.0.1",
    port: int = 0,
    exe: str = "",
) -> dict[str, Any]:
    """Open a GDB client subprocess and ``target remote`` the
    gdbserver. The ``exe`` path is used to load symbol information
    (``file <exe>``) so addresses resolve to function names.

    A1 fix (v2.8.0): on Wine >= 11.0 ``winedbg --gdb`` runs gdb over
    its OWN stdin/stdout (no TCP bind). This function now dispatches:
    Wine >= 11 → ``WinedbgStdioClient`` wrapping the existing winedbg
    subprocess (host/port arguments are ignored); Wine <= 10 → the
    original TCP path with a separate ``GDBSession`` client.
    """
    s = get_session(session)
    with s._lock:
        if s.gdbserver_proc is None or s.gdbserver_proc.poll() is not None:
            return {
                "status": "ERROR",
                "error": "gdbserver_not_running",
                "hint": "call start_winedbg_gdbserver first",
            }
        wine_major = _wine_major_version()
        if wine_major >= 11:
            # Wine 11+ stdio path: drive the existing winedbg
            # subprocess directly. No separate gdb client; no TCP.
            client = WinedbgStdioClient(
                session_id=f"winedbg-stdio-{session}-{uuid.uuid4().hex[:8]}",
                proc=s.gdbserver_proc,
            )
            s.gdb_client = client
            steps: list[dict[str, Any]] = []
            # debuginfod prompt may be pending; accept-or-decline.
            # Most installs answer "n" by default — try and move on.
            steps.append(client.send("set pagination off"))
            # The Wine 11 winedbg-gdb has the file already loaded;
            # don't issue ``file <exe>`` (it would re-read symbols and
            # may hang on large IL2CPP-style binaries). If the caller
            # passed a path that differs from the spawned exe, ignore
            # it on the stdio path (the wine-gdb already has the right
            # symbols).
            steps.append(client.send("info sharedlibrary"))
            shared_out = steps[-1].get("output", "")
            s.module_bases = gdb_text.parse_sharedlibrary(shared_out)
            s.gdb_attached = True
            return {
                "session": session,
                "status": "attached",
                "transport": "stdio",
                "wine_major_version": wine_major,
                "module_count": len(s.module_bases),
                "modules": dict(sorted(s.module_bases.items())),
                "steps": steps,
            }

        # Wine <= 10 TCP path (legacy; preserved verbatim from v2.7.0).
        if port == 0:
            port = s.gdbserver_port or 0
        if port == 0:
            return {"status": "ERROR", "error": "no_port_specified"}
        client = GDBSession(
            session_id=f"winedbg-{session}-{uuid.uuid4().hex[:8]}"
        )
        s.gdb_client = client
        steps = []
        steps.append(client.send("set pagination off"))
        if exe:
            steps.append(client.send(f"file {exe}"))
        steps.append(client.send(f"target remote {host}:{port}"))
        steps.append(client.send("info sharedlibrary"))
        shared_out = steps[-1].get("output", "")
        s.module_bases = gdb_text.parse_sharedlibrary(shared_out)
        s.gdb_attached = True
        return {
            "session": session,
            "status": "attached",
            "transport": "tcp",
            "wine_major_version": wine_major,
            "host": host,
            "port": port,
            "exe": exe,
            "module_count": len(s.module_bases),
            "modules": dict(sorted(s.module_bases.items())),
            "steps": steps,
        }


# ── tool: set_breakpoint ────────────────────────────────────────────────


def _resolve_target_to_address(s: WinedbgSession, target: str) -> str:
    """Translate a user-supplied breakpoint target into a
    ``*<absolute-address>`` GDB breakpoint spec. Accepts:

    - ``*0xADDR`` — already absolute; pass through
    - ``0xADDR`` — same, prefix the ``*`` for GDB
    - ``Symbol`` — pass through (GDB resolves to its own symbol table)
    - ``Module.dll+0xRVA`` — resolve RVA via the module base cache
    - ``Module+0xRVA`` — same, with optional .dll / .exe suffix
    """
    target = target.strip()
    if target.startswith("*"):
        return target
    if target.startswith("0x") or target.startswith("0X"):
        return f"*{target}"
    # RVA form: ModuleName+0xRVA
    if "+" in target:
        mod, _, rva_str = target.partition("+")
        mod = mod.strip()
        # strip a .dll / .exe suffix for cache lookup; the cache
        # uses the basename so this is just normalisation.
        base = s.module_bases.get(mod)
        if base is None:
            for cached_name, cached_base in s.module_bases.items():
                if cached_name.lower() == mod.lower() or \
                   cached_name.lower().startswith(mod.lower() + "."):
                    base = cached_base
                    break
        if base is None:
            return target  # let GDB try — it may still know it
        try:
            rva = int(rva_str.strip(), 16)
        except ValueError:
            return target
        return f"*{hex(base + rva)}"
    return target


def set_breakpoint(
    session: str,
    target: str,
    condition: str = "",
) -> dict[str, Any]:
    """Set a breakpoint at *target* (symbol, ``*<addr>``, or
    ``<module>+0x<RVA>``) and optionally attach a *condition*.
    """
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        resolved = _resolve_target_to_address(s, target)
        steps = [s.gdb_client.send(f"break {resolved}")]
        bp_id = _parse_breakpoint_id(steps[-1].get("output", ""))
        if condition:
            steps.append(s.gdb_client.send(f"condition {bp_id} {condition}"))
        return {
            "session": session,
            "target": target,
            "resolved": resolved,
            "breakpoint_id": bp_id,
            "steps": steps,
        }


def _parse_breakpoint_id(text: str) -> int | None:
    """Extract ``Breakpoint N`` from a GDB ``break`` response."""
    import re
    m = re.search(r"Breakpoint\s+(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def remove_breakpoint(session: str, breakpoint_id: int) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send(f"delete {breakpoint_id}")
        return {
            "session": session,
            "breakpoint_id": breakpoint_id,
            "output": out,
        }


# ── tool: continue_execution ────────────────────────────────────────────


def continue_execution(session: str, timeout_s: int = 5) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send("continue")
        text = out.get("output", "")
        return {
            "session": session,
            "event": gdb_text.parse_stopped(text),
            "raw": text,
        }


# ── tools: step_* ───────────────────────────────────────────────────────


def step_into(session: str, count: int = 1) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send(f"stepi {count}")
        regs = s.gdb_client.send("info registers")
        return {
            "session": session,
            "count": count,
            "step_output": out,
            "registers": gdb_text.parse_registers(regs.get("output", "")),
        }


def step_over(session: str, count: int = 1) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send(f"nexti {count}")
        regs = s.gdb_client.send("info registers")
        return {
            "session": session,
            "count": count,
            "step_output": out,
            "registers": gdb_text.parse_registers(regs.get("output", "")),
        }


def step_out(session: str) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send("finish")
        regs = s.gdb_client.send("info registers")
        return {
            "session": session,
            "step_output": out,
            "registers": gdb_text.parse_registers(regs.get("output", "")),
        }


# ── tools: register read/write ──────────────────────────────────────────


def read_registers(session: str) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send("info registers")
        return {
            "session": session,
            "registers": gdb_text.parse_registers(out.get("output", "")),
        }


def write_register(session: str, name: str, value: int) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        # GDB accepts ``set $name = value`` for any register; the
        # ``$`` prefix is optional but we add it for clarity.
        reg = name if name.startswith("$") else f"${name}"
        out = s.gdb_client.send(f"set {reg} = {value}")
        return {
            "session": session,
            "name": name,
            "value": value,
            "output": out,
        }


# ── tools: memory read/write ────────────────────────────────────────────


def read_memory(
    session: str,
    addr: str,
    count: int = 16,
    fmt: str = "hex",
) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        # GDB format char is the first char of fmt ("x" / "d" / "i" / "c" / "s" / "t")
        ch = (fmt or "hex")[0].lower()
        out = s.gdb_client.send(f"x/{count}{ch} {addr}")
        return {
            "session": session,
            "addr": addr,
            "count": count,
            "fmt": fmt,
            "output": out,
        }


def write_memory(
    session: str,
    addr: str,
    bytes_b64: str,
) -> dict[str, Any]:
    """Write *bytes_b64* (base64-encoded) to *addr*. Uses
    ``set {<type>}<addr> = <int>`` for the first 8 bytes and
    ``set {char}<addr+i> = <byte>`` for the tail."""
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        try:
            payload = base64.b64decode(bytes_b64)
        except Exception as exc:  # noqa: BLE001
            return {"status": "ERROR", "error": f"invalid_base64: {exc}"}
        if not payload:
            return {"session": session, "written": 0}
        steps: list[dict[str, Any]] = []
        if len(payload) <= 8:
            as_int = int.from_bytes(payload, byteorder="little")
            steps.append(s.gdb_client.send(f"set {{long long}}{addr} = {as_int}"))
        else:
            head = payload[:8]
            as_int = int.from_bytes(head, byteorder="little")
            steps.append(s.gdb_client.send(f"set {{long long}}{addr} = {as_int}"))
            for i, byte in enumerate(payload[8:], start=8):
                steps.append(s.gdb_client.send(f"set {{char}}{addr}+{i} = {byte}"))
        return {
            "session": session,
            "addr": addr,
            "written": len(payload),
            "steps": steps,
        }


# ── tools: info_modules / info_threads / backtrace ──────────────────────


def info_modules(session: str) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send("info sharedlibrary")
        parsed = gdb_text.parse_sharedlibrary(out.get("output", ""))
        # Update the module_bases cache; user-visible: any new
        # modules the runtime has loaded since first attach.
        s.module_bases.update(parsed)
        return {
            "session": session,
            "modules": [
                {"name": name, "base": base}
                for name, base in sorted(parsed.items())
            ],
        }


def info_threads(session: str) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send("info threads")
        return {
            "session": session,
            "raw": out.get("output", ""),
        }


def backtrace(session: str, max_frames: int = 30) -> dict[str, Any]:
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        out = s.gdb_client.send(f"bt {max_frames}")
        return {
            "session": session,
            "max_frames": max_frames,
            "raw": out.get("output", ""),
        }


# ── tool: gef_trace_breakpoint ──────────────────────────────────────────


def gef_trace_breakpoint(
    session: str,
    target: str,
    register: str = "$rcx",
    format: str = "idx=%d\\n",
    max_hits: int = 1000,
) -> dict[str, Any]:
    """Set a breakpoint at *target* and a ``commands N; silent;
    printf "<format>", <register>; continue; end`` block, then issue
    ``continue`` until either *max_hits* breakpoints have fired or
    the program stops for another reason. Each hit's register value
    is read via ``info registers`` and returned.

    This is the v2.4 of the workaround the v1 ``re-vm-reverse`` skill
    described by hand (``SKILL.md:67``); it removes the GDB-command
    prose from the skill and gives the agent a structured
    ``{hits, truncated}`` return.
    """
    s = get_session(session)
    with s._lock:
        if s.gdb_client is None or not s.gdb_attached:
            return {"status": "ERROR", "error": "not_attached"}
        resolved = _resolve_target_to_address(s, target)
        # 1. set the breakpoint
        bp_resp = s.gdb_client.send(f"break {resolved}")
        bp_id = _parse_breakpoint_id(bp_resp.get("output", ""))
        if bp_id is None:
            return {
                "status": "ERROR",
                "error": "breakpoint_not_set",
                "raw": bp_resp,
            }
        # 2. attach a silent-printing command list. We avoid
        #    ``printf "format", reg`` because the comma-separated
        #    printf form requires a single printf arg list. Use the
        #    single-arg printf with a literal format and the reg
        #    substitution, which GDB accepts as
        #    ``printf "<fmt>", $<reg>``.
        reg_name = register.lstrip("$")
        cmd_block = (
            f"commands {bp_id}\n"
            f"silent\n"
            f"printf \"{format}\", ${reg_name}\n"
            f"continue\n"
            f"end"
        )
        s.gdb_client.send(cmd_block)
        # 3. continue; collect up to max_hits register samples.
        #    Without a true MI parser we cannot stream the printf
        #    output, so we re-read registers at each ``continue``
        #    call. This is slower than a server-side command-list
        #    would be, but it works for the v1 use case (a few
        #    hundred samples). For dense traces the agent should
        #    fall back to the manual GDB-command workaround.
        hits: list[dict[str, Any]] = []
        truncated = False
        for n in range(max_hits):
            cont_out = s.gdb_client.send("continue")
            text = cont_out.get("output", "")
            if "Program exited" in text or "exited normally" in text:
                truncated = True
                break
            regs_out = s.gdb_client.send("info registers")
            parsed = gdb_text.parse_registers(regs_out.get("output", ""))
            if reg_name in parsed:
                hits.append({"n": n, "regs": {reg_name: parsed[reg_name]}})
            else:
                hits.append({"n": n, "regs": parsed})
        return {
            "session": session,
            "target": target,
            "resolved": resolved,
            "register": reg_name,
            "format": format,
            "max_hits": max_hits,
            "hits": hits,
            "truncated": truncated,
        }


# ── tool: end_session (teardown) ────────────────────────────────────────


def end_session(session: str) -> dict[str, Any]:
    """Close the GDB client, stop the winedbg gdbserver,
    ``wineserver -k`` the per-session prefix, and kill the Wine
    process tree. Idempotent.

    A3 fix (v2.8.0): the v2.7.0 implementation called
    ``get_session(session)`` first, which had the side-effect of
    *creating* the session if it didn't exist. Then the
    ``session in _SESSIONS`` check always returned True, so the
    ``not_found`` path was dead and a teardown was performed on
    an empty session. Fixed by checking the registry directly
    before touching it.
    """
    with _SESSIONS_LOCK:
        s = _SESSIONS.pop(session, None)
    if s is None:
        return {"session": session, "status": "not_found"}
    with s._lock:
        _teardown_locked(s)
    return {
        "session": session,
        "status": "ended",
    }
