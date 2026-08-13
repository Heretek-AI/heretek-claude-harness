"""MCP server entry point for re-frida.

Exposes the Frida dynamic-instrumentation toolkit to Claude Code
via the Model Context Protocol stdio transport.

Every tool is a thin wrapper around :mod:`re_frida.runner` — the
runner owns the session table and the soft-skip behaviour. When
``libfrida`` is missing the runner raises and the wrappers return
``WARN`` with an install hint.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from re_frida import runner

mcp = FastMCP("re-frida")

logger = logging.getLogger("re_frida")
logger.setLevel(logging.INFO)


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_frida() -> dict:
    """Return frida version + native lib presence + USB device list.

    Soft-skip behaviour: when ``frida`` Python module or the
    native ``libfrida`` is missing, returns ``status: WARN`` with
    an install hint (``pip install frida frida-tools``). The
    rest of the plugin continues to work — re-frida's tools just
    return errors when called.
    """
    return runner.check_frida()


# ── Session lifecycle ───────────────────────────────────────────────────


@mcp.tool()
def start_session(
    session: str,
    target: str,
    device_id: str = "",
    spawn_args: list[str] | None = None,
    wait: bool = True,
) -> dict:
    """Spawn *target* on the named device and open a Frida session.

    Args:
        session: analyst-chosen session id. The MCP layer keeps a
            table mapping session id → live Frida session. Pick
            something readable (e.g. ``"android-game"``).
        target: package name (Android), bundle ID (iOS), or
            absolute path to a native binary.
        device_id: ``"usb"``, ``"local"``, ``"remote:<addr>"``,
            or a specific device id. Empty string means the
            first available device.
        spawn_args: extra argv to pass to the target on spawn.
        wait: when True (default), block until the spawned
            process is unpaused.

    Returns::

        {
          "status": "OK",
          "session_id": "...",
          "pid": N,
          "device_id": "...",
          "kind": "spawn"
        }
    """
    try:
        return runner.start_session(
            session_id=session,
            target=target,
            device_id=device_id or None,
            spawn_args=spawn_args,
            wait=wait,
        )
    except RuntimeError as exc:
        return {"status": "ERROR", "session": session, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "session": session, "error": f"{type(exc).__name__}: {exc}"}


@mcp.tool()
def attach_pid(session: str, pid: int, device_id: str = "") -> dict:
    """Attach to a running process by host PID.

    Args:
        session: session id
        pid: host PID of the target
        device_id: optional device id; empty means first available

    Returns::

        {
          "status": "OK",
          "session_id": "...",
          "pid": N,
          "device_id": "...",
          "kind": "attach"
        }
    """
    try:
        return runner.attach_pid(
            session_id=session,
            pid=pid,
            device_id=device_id or None,
        )
    except RuntimeError as exc:
        return {"status": "ERROR", "session": session, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "session": session, "error": f"{type(exc).__name__}: {exc}"}


@mcp.tool()
def end_session(session: str) -> dict:
    """Tear down a session, unload scripts, detach from the process."""
    try:
        return runner.end_session(session)
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "session": session, "error": f"{type(exc).__name__}: {exc}"}


# ── Scripts ─────────────────────────────────────────────────────────────


@mcp.tool()
def script_load(session: str, name: str, source: str) -> dict:
    """Compile + load a Frida script (JavaScript) into a session.

    Args:
        session: session id
        name: a name to look the script up by in subsequent calls
        source: the JavaScript source. Frida injects V8 into the
            target process; standard ``Interceptor`` /
            ``Java.perform`` / ``ObjC.classes`` APIs are
            available inside the script.

    Returns::

        {"status": "OK", "session_id": "...", "script": "...", "scripts_loaded": [...]}
    """
    return runner.script_load(session, name, source)


@mcp.tool()
def script_call(
    session: str,
    name: str,
    method: str,
    args: list[Any] | None = None,
    timeout_s: float = 10.0,
) -> dict:
    """Call *method* on a loaded script's exports.

    Args:
        session: session id
        name: script name (from ``script_load``)
        method: the JS-side export to call. Scripts declare
            exports via ``rpc.exports = { myFn(arg) { ... } }``.
        args: JSON-serialisable positional arguments
        timeout_s: RPC timeout (default 10s)

    Returns the return value, or the error string when the JS side
    threw.
    """
    return runner.script_call(session, name, method, args, timeout_s=timeout_s)


# ── Enumeration ─────────────────────────────────────────────────────────


@mcp.tool()
def enumerate_modules(session: str) -> dict:
    """List modules loaded in the session's target process.

    Returns base address, size, and on-disk path for each module.
    """
    return runner.enumerate_modules(session)


@mcp.tool()
def enumerate_exports(session: str, module: str) -> dict:
    """List exports of a single module."""
    return runner.enumerate_exports(session, module)


# ── Hooking ─────────────────────────────────────────────────────────────


@mcp.tool()
def hook_method(session: str, module: str, symbol: str) -> dict:
    """Install a tracing hook on ``module:symbol``.

    The hook captures both arguments (on-enter) and the return
    value (on-leave) and posts messages back to the Python side
    for the analyst to consume. Useful for tracing the
    dispatcher of an encrypted-VM bytecode interpreter, the
    handler of an MBA-obfuscated arithmetic routine, or the
    userland callback of an anti-debug check.
    """
    return runner.hook_method(session, module, symbol)


@mcp.tool()
def rpc_export(session: str, name: str) -> dict:
    """Register a stub Python-side RPC export the script side can call.

    The function is a reflective shim that returns ``None``; the
    analyst wires the real Python callable by calling
    ``re_frida.runner.rpc_export(session, name, fn)`` from a
    follow-up script. The MCP layer intentionally avoids taking
    a Python callable as a JSON argument (which the MCP
    protocol can't transport).
    """
    return runner.rpc_export(session, name)


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
