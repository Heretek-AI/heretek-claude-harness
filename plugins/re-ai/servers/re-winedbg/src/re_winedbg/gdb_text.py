"""Small CLI-output parsers for GDB commands.

We do not run a true GDB/MI parser. The GDB subprocess is started
with ``--interpreter=mi3`` but we drive it via plain CLI commands
(same trick ``re-gdb`` uses today) — see ``re_gdb.gdb_mi.GDBSession``.
The few tools that need structured data (per-module base addresses,
register dicts, stopped-event frames) parse the text-mode output
of standard GDB commands here.

All parsers are deliberately permissive: missing or unexpected
fields are ignored rather than raising. The caller receives a dict
with whatever was recovered.
"""

from __future__ import annotations

import re
from typing import Any

# ── info sharedlibrary ───────────────────────────────────────────────────
#
# Real GDB 12-15 output looks like:
#   From                To                  Syms Read   Shared Object Library
#   0x00007f1234000000  0x00007f1234005000  Yes         /usr/lib/wine/ntdll.dll
#   0x00007f1234007000  0x00007f1234012000  Yes         /usr/lib/wine/kernelbase.dll
#
# Some versions print a leading "Shared Object Library" or "From To"
# header; some have a "Shared Object Library" suffix. We just split
# each line on whitespace and take the first token as the base
# address, the last as the path.

_SHAREDLIB_HEADER_PATTERNS = (
    re.compile(r"From\s+To\b", re.IGNORECASE),
    re.compile(r"Shared\s+Object\s+Library", re.IGNORECASE),
)


def parse_sharedlibrary(text: str) -> dict[str, int]:
    """Parse ``info sharedlibrary`` output.

    Returns ``{module_name: base_address}`` where ``module_name`` is
    the basename of the path (``ntdll.dll`` from
    ``/usr/lib/wine/ntdll.dll``). Empty / unparseable lines are
    skipped silently.
    """
    modules: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if any(p.search(line) for p in _SHAREDLIB_HEADER_PATTERNS):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        if not parts[0].lower().startswith("0x"):
            continue
        try:
            base = int(parts[0], 16)
        except ValueError:
            continue
        # The path is the last field on the line. Some lines have a
        # "0x..."  column paired with the base (e.g. an offset
        # column) — we only need the base + path.
        path = parts[-1]
        name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if not name:
            continue
        modules[name] = base
    return modules


# ── info registers ──────────────────────────────────────────────────────
#
# Example:
#   rax            0x7fffffffe4a0      140737488352416
#   rbx            0x0                 0
#   r8             0x7fffffffe380      140737488351104
# Flags / EFlags may include symbol characters (ZF, IF, ...) — we
# only parse the hex+dec form, which is the dominant shape.

_REG_RE = re.compile(
    r"^(?P<reg>[a-zA-Z][a-zA-Z0-9_.]*)\s+"
    r"(?P<hex>0x[0-9a-fA-F]+)\s+"
    r"(?P<dec>\d+)\s*$"
)


def parse_registers(text: str) -> dict[str, str]:
    """Parse ``info registers`` output → ``{name: hex_string}``."""
    regs: dict[str, str] = {}
    for line in text.splitlines():
        m = _REG_RE.match(line)
        if m:
            regs[m.group("reg")] = m.group("hex")
    return regs


# ── stopped event ───────────────────────────────────────────────────────
#
# The CLI text GDB prints when a target stops comes in several
# flavours:
#   "Breakpoint 1, 0x00007f1234001000 in main ()"
#   "Thread 1 received signal SIGSEGV, Segmentation fault."
#   "0x00007f1234012345 in ?? ()"
#   "Program received signal SIGTRAP, Trace/breakpoint trap."
# We map these to a minimal {reason, frame_addr, frame_func} dict.

_BP_RE = re.compile(r"Breakpoint\s+\d+,\s*(0x[0-9a-fA-F]+)\s+in\s+(\S+)")
_SIG_RE = re.compile(
    r"received\s+signal\s+(SIG[A-Z0-9]+)", re.IGNORECASE
)
_ADDR_RE = re.compile(r"(0x[0-9a-fA-F]+)")


def parse_stopped(text: str) -> dict[str, Any]:
    """Return a minimal stop-reason dict from a stopped-event text."""
    info: dict[str, Any] = {
        "reason": "unknown",
        "frame_addr": None,
        "frame_func": None,
    }
    m = _BP_RE.search(text)
    if m:
        info["reason"] = "breakpoint-hit"
        info["frame_addr"] = m.group(1)
        info["frame_func"] = m.group(2)
        return info
    m = _SIG_RE.search(text)
    if m:
        info["reason"] = f"signal-received: {m.group(1).upper()}"
    # Even when the reason is "signal-received", the next line is
    # usually "0x... in ?? ()" which gives us the frame.
    m = _ADDR_RE.search(text)
    if m and info["frame_addr"] is None:
        info["frame_addr"] = m.group(1)
    # Try to extract a function name (anything between "in " and " (")
    m = re.search(r"in\s+(\S+)\s*\(\)", text)
    if m and info["frame_func"] is None:
        info["frame_func"] = m.group(1)
    return info
