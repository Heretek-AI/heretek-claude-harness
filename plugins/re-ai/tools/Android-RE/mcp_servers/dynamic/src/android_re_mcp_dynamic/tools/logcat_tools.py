"""Logcat streaming tools."""

from __future__ import annotations

import re
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

__all__ = ["register"]


#: Process-wide logcat stream registry. Each follow is a thread that
#: runs ``adb logcat`` and appends lines to a buffer.
@dataclass
class _LogcatStream:
    token: str
    serial: str
    package: str | None
    level: str
    lines: deque = field(default_factory=lambda: deque(maxlen=2000))
    proc: Any = None  # subprocess.Popen
    stop: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "serial": self.serial,
            "package": self.package,
            "level": self.level,
            "line_count": len(self.lines),
        }


_STREAMS: dict[str, _LogcatStream] = {}
_STREAMS_LOCK = threading.RLock()


def _reader_thread(stream: _LogcatStream) -> None:
    """Read lines from the logcat subprocess and append to the buffer."""
    while not stream.stop.is_set():
        if stream.proc is None or stream.proc.stdout is None:
            break
        line = stream.proc.stdout.readline()
        if not line:
            break
        line = line.rstrip()
        if stream.package and stream.package not in line:
            continue
        if stream.level and not _level_at_least(line, stream.level):
            continue
        stream.lines.append(line)


_LEVEL_ORDER = {"V": 0, "D": 1, "I": 2, "W": 3, "E": 4, "F": 5}


def _level_at_least(line: str, min_level: str) -> bool:
    """Return True if a logcat line's level is at least ``min_level``."""
    # Format: "01-01 00:00:00.000  pid  tid LEVEL tag: message"
    m = re.search(r"\b([VDIWEFA])\b\s+\S+:", line)
    if not m:
        return True
    letter = m.group(1)
    if letter not in _LEVEL_ORDER or min_level not in _LEVEL_ORDER:
        return True
    return _LEVEL_ORDER[letter] >= _LEVEL_ORDER[min_level]


def register(mcp: FastMCP) -> None:
    """Register logcat streaming tools."""

    @mcp.tool(
        name="start_logcat",
        description=(
            "Begin a logcat follow on a device. Returns a token that "
            "can be used to read buffered lines or stop the follow. "
            "Lines older than the buffer (default 2000) are dropped."
        ),
    )
    def start_logcat(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[
            str | None,
            Field(description="Filter to lines whose payload contains this package name"),
        ] = None,
        level: Annotated[str, Field(description="Minimum level: V, D, I, W, E, F")] = "I",
        follow_token: Annotated[
            str | None,
            Field(description="Unused; reserved for future resource-stream return"),
        ] = None,
    ) -> dict[str, Any]:
        import subprocess

        from android_re_core.device.adb import find_adb

        binary = find_adb()
        cmd: list[str] = [str(binary), "-s", serial, "logcat", "-v", "time"]
        if level:
            cmd.append(f"*:{level}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            return {"error": {"code": "logcat_failed", "message": str(e)}}
        stream = _LogcatStream(
            token=str(uuid.uuid4()),
            serial=serial,
            package=package,
            level=level,
            proc=proc,
        )
        stream.thread = threading.Thread(
            target=_reader_thread,
            args=(stream,),
            daemon=True,
        )
        stream.thread.start()
        with _STREAMS_LOCK:
            _STREAMS[stream.token] = stream
        return stream.to_dict()

    @mcp.tool(
        name="stop_logcat",
        description="Stop a logcat follow and return its buffered lines.",
    )
    def stop_logcat(
        token: Annotated[str, Field(description="Token from start_logcat")],
    ) -> dict[str, Any]:
        with _STREAMS_LOCK:
            stream = _STREAMS.pop(token, None)
        if stream is None:
            return {"error": {"code": "token_not_found", "message": token}}
        stream.stop.set()
        if stream.proc is not None:
            try:
                stream.proc.terminate()
                stream.proc.wait(timeout=3)
            except Exception:
                try:
                    stream.proc.kill()
                except Exception:
                    pass
        if stream.thread is not None:
            stream.thread.join(timeout=3)
        return {
            "token": token,
            "line_count": len(stream.lines),
            "lines": list(stream.lines),
        }

    @mcp.tool(
        name="read_logcat",
        description=(
            "Read the most recent N lines from an active logcat follow without stopping it."
        ),
    )
    def read_logcat(
        token: Annotated[str, Field(description="Token from start_logcat")],
        max_lines: Annotated[int, Field(ge=1, le=2000)] = 200,
    ) -> dict[str, Any]:
        with _STREAMS_LOCK:
            stream = _STREAMS.get(token)
        if stream is None:
            return {"error": {"code": "token_not_found", "message": token}}
        return {
            "token": token,
            "line_count": len(stream.lines),
            "lines": list(stream.lines)[-max_lines:],
        }

    @mcp.tool(
        name="recent_logcat",
        description=(
            "Read the most recent N logcat lines from a device "
            "without starting a follow. Uses a one-shot ``adb logcat -d``."
        ),
    )
    def recent_logcat(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[
            str | None, Field(description="Filter to lines containing this package")
        ] = None,
        level: Annotated[str, Field(description="Minimum level: V, D, I, W, E, F")] = "I",
        max_lines: Annotated[int, Field(ge=1, le=2000)] = 200,
        timeout_s: Annotated[int, Field(ge=1, le=60)] = 10,
    ) -> dict[str, Any]:
        from android_re_core.device.adb import run_adb

        args: list[str] = ["-s", serial, "logcat", "-d", "-v", "time"]
        if level:
            args.append(f"*:{level}")
        try:
            proc = run_adb(args, timeout_s=timeout_s)
        except Exception as e:
            return {"error": {"code": "logcat_failed", "message": str(e)}}
        out: list[str] = []
        for line in proc.stdout.splitlines():
            if package and package not in line:
                continue
            out.append(line)
            if len(out) >= max_lines:
                break
        return {"serial": serial, "line_count": len(out), "lines": out}
