"""Frida session management for the re-frida MCP server.

This module is a thin layer over the official ``frida`` Python
bindings. The MCP wrappers in ``server.py`` never touch the Frida
API directly — they go through this module so the session table
is consistent and the soft-skip behaviour (when the native
libfrida is missing) is centralised.

The session table maps a string session_id to a dict::

    {
        "session":  frida.Session,        # the live session
        "device":   frida.Device,         # the device the session lives on
        "scripts":  {name: frida.Script}, # loaded scripts by name
        "rpc":      {name: callable},     # python-side rpc exports
        "hooks":    [str],                # installed hook ids (for cleanup)
        "kind":     "spawn" | "attach",
        "pid":      int,
        "spawn_arg": str | None,
    }

The MCP server holds this table in a module-level dict. Each MCP
tool takes a ``session`` name and looks up the live session
record; ``end_session`` pops the entry and tears the Frida
session down cleanly.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger("re_frida")
logger.setLevel(logging.INFO)


_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSIONS_LOCK = threading.Lock()


# ── availability ────────────────────────────────────────────────────────


def check_frida() -> dict:
    """Return frida version + native lib presence + USB device list.

    On a host without ``libfrida`` the wrapper import raises
    ``OSError``; the MCP layer catches that and returns ``WARN``
    with an install hint. The MCP wrapper does the same, but
    having a non-MCP entry point here means tests can import
    this module without spinning up FastMCP.
    """
    import importlib

    frida_spec = importlib.util.find_spec("frida")
    if frida_spec is None:
        return {
            "server": "re-frida",
            "version": "0.1.0",
            "status": "WARN",
            "frida_python_available": False,
            "frida_version": None,
            "install_hint": "pip install frida frida-tools",
        }
    try:
        import frida  # type: ignore[import-untyped]
    except (ImportError, OSError) as exc:
        return {
            "server": "re-frida",
            "version": "0.1.0",
            "status": "WARN",
            "frida_python_available": True,
            "frida_version": None,
            "native_lib_error": str(exc),
            "install_hint": "frida Python module loaded but the native libfrida is missing",
        }
    version = getattr(frida, "__version__", "imported")
    # Enumerate USB devices. This call requires a running frida
    # server on the host; on a clean host it just returns [].
    devices: list[dict] = []
    try:
        manager = frida.get_device_manager()
        for d in manager.enumerate_devices():
            devices.append({
                "id": d.id,
                "name": d.name,
                "type": str(getattr(d.type, "name", d.type)),
            })
    except Exception as exc:  # noqa: BLE001
        logger.debug("enumerate_devices failed: %s", exc)
    return {
        "server": "re-frida",
        "version": "0.1.0",
        "status": "OK",
        "frida_python_available": True,
        "frida_version": version,
        "devices": devices,
    }


# ── session lifecycle ───────────────────────────────────────────────────


def _require_frida() -> "object":  # type: ignore[name-defined]
    """Import frida and surface a clean error to the caller when
    the native lib is missing. The MCP wrappers return the error
    dict directly when this raises.
    """
    try:
        import frida  # type: ignore[import-untyped]
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "frida Python module or native libfrida is missing; "
            "pip install frida frida-tools"
        ) from exc
    return frida


def get_session(session_id: str) -> dict | None:
    with _SESSIONS_LOCK:
        rec = _SESSIONS.get(session_id)
        return rec


def list_sessions() -> list[str]:
    with _SESSIONS_LOCK:
        return sorted(_SESSIONS.keys())


def _put_session(session_id: str, rec: dict) -> None:
    with _SESSIONS_LOCK:
        if session_id in _SESSIONS:
            # Refuse to clobber a live session. The caller should
            # call end_session first.
            raise RuntimeError(
                f"session_id already in use: {session_id!r}; "
                "call end_session first"
            )
        _SESSIONS[session_id] = rec


def _drop_session(session_id: str) -> dict | None:
    with _SESSIONS_LOCK:
        return _SESSIONS.pop(session_id, None)


# ── spawn / attach ──────────────────────────────────────────────────────


def start_session(
    session_id: str,
    target: str,
    *,
    device_id: str | None = None,
    spawn_args: list[str] | None = None,
    wait: bool = True,
) -> dict:
    """Spawn *target* on the named device and attach.

    Args:
        session_id: the analyst's chosen session name.
        target: package name (Android), bundle ID (iOS), or
            absolute path to a binary (native).
        device_id: ``"usb"``, ``"local"``, ``"remote:<addr>"``,
            or a specific device ID. ``None`` means the first
            available USB / local device.
        spawn_args: extra argv for the target (Android spawn
            accepts a list).
        wait: if True, block until the spawned process is fully
            started. Set False for fire-and-forget spawns.

    Returns the populated session record.
    """
    frida = _require_frida()
    manager = frida.get_device_manager()
    if device_id is None or device_id == "":
        # Pick the first device — on a host with no devices
        # attached, frida.get_device('local') would still work
        # for self-instrumentation.
        device = manager.get_device(manager.enumerate_devices()[0].id)
    else:
        device = manager.get_device(device_id)
    pid = device.spawn([target, *(spawn_args or [])])
    session = device.attach(pid)
    rec = {
        "session": session,
        "device": device,
        "scripts": {},
        "rpc": {},
        "hooks": [],
        "kind": "spawn",
        "pid": pid,
        "spawn_arg": target,
        "device_id": device.id,
    }
    _put_session(session_id, rec)
    if wait:
        # resume() is the post-spawn handshake. We don't await
        # any particular signal — the call returns as soon as
        # the process is unpaused.
        device.resume(pid)
    return {
        "session_id": session_id,
        "pid": pid,
        "device_id": device.id,
        "kind": "spawn",
        "target": target,
    }


def attach_pid(session_id: str, pid: int, *, device_id: str | None = None) -> dict:
    """Attach to a running host process by PID."""
    frida = _require_frida()
    manager = frida.get_device_manager()
    if device_id is None or device_id == "":
        device = manager.get_device(manager.enumerate_devices()[0].id)
    else:
        device = manager.get_device(device_id)
    session = device.attach(pid)
    rec = {
        "session": session,
        "device": device,
        "scripts": {},
        "rpc": {},
        "hooks": [],
        "kind": "attach",
        "pid": pid,
        "spawn_arg": None,
        "device_id": device.id,
    }
    _put_session(session_id, rec)
    return {
        "session_id": session_id,
        "pid": pid,
        "device_id": device.id,
        "kind": "attach",
    }


def end_session(session_id: str) -> dict:
    """Tear down a session. Idempotent — returns a status field
    the caller can check.
    """
    rec = _drop_session(session_id)
    if rec is None:
        return {"session_id": session_id, "status": "ok", "note": "no live session"}
    # Detach the Frida session. The detach call is non-blocking
    # and never raises when the process is already gone.
    try:
        rec["session"].detach()
    except Exception as exc:  # noqa: BLE001
        logger.debug("detach %s: %s", session_id, exc)
    return {"session_id": session_id, "status": "ok"}


# ── scripts ─────────────────────────────────────────────────────────────


def script_load(session_id: str, name: str, source: str) -> dict:
    """Compile + load a Frida script under *session_id* with the
    given *name*. Subsequent ``script_call`` lookups the script
    by *name*.
    """
    rec = get_session(session_id)
    if rec is None:
        return {"status": "ERROR", "error": f"no such session: {session_id!r}"}
    session = rec["session"]
    if name in rec["scripts"]:
        return {
            "status": "ERROR",
            "error": f"script {name!r} already loaded in session {session_id!r}",
        }
    script = session.create_script(source)
    # Wire up the Python-side RPC exports so the script can
    # call back into Python.
    if rec["rpc"]:
        script.on("message", _make_message_handler(rec))
    script.load()
    rec["scripts"][name] = script
    return {
        "status": "OK",
        "session_id": session_id,
        "script": name,
        "scripts_loaded": sorted(rec["scripts"].keys()),
    }


def _make_message_handler(rec: dict) -> Callable[..., None]:
    """Build a Fridamessage handler that routes ``frida:rpc``
    messages to the registered Python callables.
    """
    def on_message(message: Any, payload: Any) -> None:
        if message.get("type") != "send":
            return
        data = message.get("payload") or {}
        if not isinstance(data, dict):
            return
        if data.get("from") == "frida:rpc":
            name = data.get("name")
            args = data.get("args", [])
            fn = rec["rpc"].get(name)
            if fn is None:
                # Reply with an error; the script side gets a JS exception.
                script = next(iter(rec["scripts"].values()), None)
                if script is not None:
                    script.post({"type": "frida:rpc:reply", "id": data.get("id"),
                                 "error": f"no such rpc export: {name!r}"})
                return
            try:
                result = fn(*args)
            except Exception as exc:  # noqa: BLE001
                script = next(iter(rec["scripts"].values()), None)
                if script is not None:
                    script.post({"type": "frida:rpc:reply", "id": data.get("id"),
                                 "error": f"{type(exc).__name__}: {exc}"})
                return
            script = next(iter(rec["scripts"].values()), None)
            if script is not None:
                script.post({"type": "frida:rpc:reply", "id": data.get("id"),
                             "result": result})
    return on_message


def script_call(
    session_id: str,
    name: str,
    method: str,
    args: list[Any] | None = None,
    *,
    timeout_s: float = 10.0,
) -> dict:
    """Call *method* on the named script's exports. Returns the
    JS-side return value as a JSON-safe Python value (or the
    exception text on a JS throw).
    """
    rec = get_session(session_id)
    if rec is None:
        return {"status": "ERROR", "error": f"no such session: {session_id!r}"}
    script = rec["scripts"].get(name)
    if script is None:
        return {
            "status": "ERROR",
            "error": f"no such script {name!r} in session {session_id!r}",
        }
    fn = getattr(script.exports, method, None)
    if fn is None:
        return {
            "status": "ERROR",
            "error": (
                f"script {name!r} has no exports.{method}; "
                f"available: {sorted(k for k in dir(script.exports) if not k.startswith('_'))}"
            ),
        }
    try:
        result = fn(*(args or []))
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "error": f"rpc call raised: {exc}"}
    return {
        "status": "OK",
        "session_id": session_id,
        "script": name,
        "method": method,
        "result": result,
    }


# ── enumeration ─────────────────────────────────────────────────────────


def enumerate_modules(session_id: str) -> dict:
    rec = get_session(session_id)
    if rec is None:
        return {"status": "ERROR", "error": f"no such session: {session_id!r}"}
    session = rec["session"]
    mods = session.enumerate_modules()
    return {
        "status": "OK",
        "session_id": session_id,
        "modules": [
            {
                "name": m.name,
                "base": int(m.base_address),
                "size": int(m.size),
                "path": m.path,
            }
            for m in mods
        ],
    }


def enumerate_exports(session_id: str, module: str) -> dict:
    rec = get_session(session_id)
    if rec is None:
        return {"status": "ERROR", "error": f"no such session: {session_id!r}"}
    session = rec["session"]
    mods = {m.name: m for m in session.enumerate_modules()}
    if module not in mods:
        return {
            "status": "ERROR",
            "error": f"module {module!r} not loaded; pick from: {sorted(mods)[:10]}...",
        }
    exports = mods[module].enumerate_exports()
    return {
        "status": "OK",
        "session_id": session_id,
        "module": module,
        "exports": [
            {"name": e.name, "address": int(e.relative_address)}
            for e in exports
        ],
    }


# ── hooks / rpc exports ─────────────────────────────────────────────────


_HOOK_TEMPLATE = """\
// Auto-generated hook installed by re-frida.hook_method.
// target: %(module)s %(symbol)s
Interceptor.attach(
    ptr("%(address)s"),
    {
        onEnter(args) {
            send({op: "hook:enter", symbol: "%(symbol)s", args: args.map(a => a.toString())});
        },
        onLeave(retval) {
            send({op: "hook:leave", symbol: "%(symbol)s", retval: retval.toString()});
        }
    }
);
"""


def hook_method(session_id: str, module: str, symbol: str) -> dict:
    """Install a tracing hook on *module:symbol*.

    The hook is implemented by a small auto-generated Frida
    script that uses ``Interceptor.attach`` to capture both
    arguments and the return value. The script posts ``hook:enter``
    and ``hook:leave`` messages back to Python; the MCP caller
    reads them off the next ``script_call`` that polls
    ``recv_message``.
    """
    rec = get_session(session_id)
    if rec is None:
        return {"status": "ERROR", "error": f"no such session: {session_id!r}"}
    session = rec["session"]
    mods = {m.name: m for m in session.enumerate_modules()}
    if module not in mods:
        return {
            "status": "ERROR",
            "error": f"module {module!r} not loaded; pick from: {sorted(mods)[:10]}...",
        }
    target_mod = mods[module]
    sym_obj = None
    for e in target_mod.enumerate_exports():
        if e.name == symbol:
            sym_obj = e
            break
    if sym_obj is None:
        return {
            "status": "ERROR",
            "error": f"symbol {symbol!r} not exported by {module!r}",
        }
    address = int(target_mod.base_address) + int(sym_obj.relative_address)
    source = _HOOK_TEMPLATE % {
        "module": module,
        "symbol": symbol,
        "address": hex(address),
    }
    # Use a deterministic name so subsequent script_call can find
    # the hook's recv_message pump.
    name = f"hook::{module}::{symbol}"
    res = script_load(session_id, name, source)
    if res.get("status") != "OK":
        return res
    rec["hooks"].append(f"{module}!{symbol}")
    return {
        "status": "OK",
        "session_id": session_id,
        "hook": f"{module}!{symbol}",
        "address": address,
        "script": name,
    }


def rpc_export(session_id: str, name: str, fn: Callable[..., Any] | None = None) -> dict:
    """Register *fn* (or, if absent, a tiny reflective shim) as an
    RPC export the script side can call.

    The handler is wired in via ``script_load``'s message
    routing. The function *fn* runs on the Python side and
    returns a JSON-serialisable value.
    """
    rec = get_session(session_id)
    if rec is None:
        return {"status": "ERROR", "error": f"no such session: {session_id!r}"}
    if name in rec["rpc"]:
        return {
            "status": "ERROR",
            "error": f"rpc export {name!r} already registered",
        }
    rec["rpc"][name] = fn or (lambda *a: None)
    return {
        "status": "OK",
        "session_id": session_id,
        "rpc_export": name,
        "exports": sorted(rec["rpc"].keys()),
    }
