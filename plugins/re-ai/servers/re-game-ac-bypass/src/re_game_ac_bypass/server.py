"""MCP server entry point for re-game-ac-bypass.

Game anti-cheat runtime analysis. The server wraps
``re-frida`` (userland hook surface), ``re-winedbg``
(kernel-mode single-step via Wine), and
``re-static-triage`` (import / export surface). All
output is vendor-neutral: the server talks about
*observable* anti-cheat primitives (kernel callbacks,
integrity checks, telemetry beacons, driver loads),
not specific products.

This is a workflow server — every tool returns a
*checklist* or *recipe*, never an auto-patch.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("re_game_ac_bypass")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-game-ac-bypass")


@mcp.tool()
def check_game_ac_bypass() -> dict:
    """Report server status + the wrapped servers' availability."""
    return {
        "server": "re-game-ac-bypass",
        "version": "0.1.0",
        "status": "OK",
        "wrapped_servers": ["re-frida", "re-winedbg", "re-static-triage"],
    }


@mcp.tool()
def enumerate_kernel_callbacks(path: str) -> dict:
    """Catalog kernel-callback registrations by category.

    Returns::

        {
          "path": "...",
          "callbacks": [{"category": "process-creation",
                         "symbol": "PsSetCreateProcessNotifyRoutine",
                         "address": "0x...", "kind": "register"}, ...],
          "callback_categories": {"process-creation": 4, "thread-creation": 1, ...}
        }

    Categories: process-creation, thread-creation,
    image-load, registry-change, object-handle,
    driver-load, file-system. The categories are
    observable kernel-primitive classes; the names
    are the Windows kernel API names (which are
    public documentation, not vendor names).
    """
    return {
        "path": path,
        "callbacks": [],
        "callback_categories": {},
        "note": (
            "the v2.7.0 first-pass walker is a recipe — the actual "
            "kernel-callback enumeration runs the re-winedbg "
            ".info_modules + the disasm pass on the loaded driver. "
            "Use re-winedbg to enumerate the loaded drivers, then "
            "re-rizin.analyze_function on each driver's .text."
        ),
    }


@mcp.tool()
def map_anti_cheat_primitives(path: str) -> dict:
    """Map the anti-cheat primitive surface (categories only).

    Returns a per-category count of matched primitives:
    kernel-callback, integrity-check, telemetry-beacon,
    driver-load, file-system-watch, registry-watch.

    Categories only — never names a specific commercial
    anti-cheat product.
    """
    return {
        "path": path,
        "primitives": {
            "kernel-callback": 0,
            "integrity-check": 0,
            "telemetry-beacon": 0,
            "driver-load": 0,
            "file-system-watch": 0,
            "registry-watch": 0,
        },
        "note": (
            "the v2.7.0 first-pass walker is a recipe; the actual "
            "primitive map is built by the analyst using "
            "re-static-triage (imports / sections) + re-frida "
            "(runtime hook surface) + re-winedbg (kernel "
            "callbacks via the loaded driver)."
        ),
    }


@mcp.tool()
def trace_telemetry_beacon(session: str, target: str, duration_s: int = 30) -> dict:
    """Trace the runtime telemetry beacon.

    Args:
        session: a re-frida session id
        target: package name or PID
        duration_s: trace duration in seconds (default 30)

    Returns a list of ``{ts, src, dst, protocol, payload_size}``
    per observed network event.
    """
    return {
        "session": session,
        "target": target,
        "duration_s": duration_s,
        "events": [],
        "note": (
            "the v2.7.0 first-pass walker is a recipe; the actual "
            "trace runs re-frida's hook_method on the WinHTTP / "
            "WinINet / ws2_32 APIs and posts the captured events. "
            "Pair with re-pcap to confirm the network trace on the "
            "wire."
        ),
    }


@mcp.tool()
def classify_anti_cheat_runtime(path: str) -> dict:
    """Classify the anti-cheat runtime (category-only).

    Returns a category label from the set:
    - ``"userland-only"`` — no driver load observed.
    - ``"driver-attached"`` — a ``*.sys`` driver is loaded
      by the launcher.
    - ``"kernel-callback-rich"`` — multiple kernel
      callbacks registered.
    - ``"telemetry-rich"`` — many HTTP / WinHTTP calls
      per minute.

    Categories only — never names a specific commercial
    anti-cheat product.
    """
    return {
        "path": path,
        "runtime_class": "unknown",
        "evidence": [],
        "note": (
            "the v2.7.0 first-pass walker is a recipe; the actual "
            "classification runs re-static-triage on the launcher "
            "exe + re-winedbg on the loaded driver (if any). Pair "
            "with re-frida to capture the runtime telemetry beacons."
        ),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
