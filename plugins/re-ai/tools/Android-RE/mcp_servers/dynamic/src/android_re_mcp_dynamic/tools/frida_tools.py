"""Frida session, script, and RPC tools."""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.frida.device import (
    DeviceWrapper,
    get_device,
)
from android_re_core.frida.rpc import DEFAULT_RPC_TIMEOUT_S, call_rpc
from android_re_mcp_dynamic.server import (
    get_script_store,
    get_session_store,
)

__all__ = ["register"]


# Simple in-memory cache of device wrappers, keyed by serial.
_DEVICE_CACHE: dict[str, DeviceWrapper] = {}


def _get_cached_device(serial: str | None = None) -> DeviceWrapper:
    """Return a cached or fresh DeviceWrapper for the given serial."""
    if serial is None:
        # Auto-pick
        return get_device()
    if serial in _DEVICE_CACHE:
        return _DEVICE_CACHE[serial]
    dev = get_device(serial)
    _DEVICE_CACHE[serial] = dev
    return dev


def register(mcp: FastMCP) -> None:
    """Register Frida session / script / RPC tools."""

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    @mcp.tool(
        name="frida_list_processes",
        description=("Enumerate processes on a Frida device. Returns name + PID for each."),
    )
    def frida_list_processes(
        serial: Annotated[str, Field(description="Frida device id (e.g. USB serial)")],
    ) -> dict[str, Any]:
        try:
            dev = _get_cached_device(serial)
            procs = dev.enumerate_processes()
        except Exception as e:
            return {"error": {"code": "device_unreachable", "message": str(e)}}
        return {
            "device_id": serial,
            "count": len(procs),
            "processes": [p.to_dict() for p in procs],
        }

    @mcp.tool(
        name="frida_ps",
        description=(
            "Enumerate processes on a device using both ADB and "
            "Frida, returning a unified list. Useful when you want "
            "to confirm a PID is reachable from both."
        ),
    )
    def frida_ps(
        serial: Annotated[str, Field(description="Frida device id")],
    ) -> dict[str, Any]:
        # Use frida's enumerate_processes for the canonical list.
        return frida_list_processes(serial=serial)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    @mcp.tool(
        name="frida_spawn",
        description=(
            "Spawn a fresh process and attach Frida immediately. "
            "Returns a session_id to use with all subsequent "
            "frida_load_script / frida_rpc_call calls. The "
            "frida-server version is verified before spawn."
        ),
    )
    def frida_spawn(
        serial: Annotated[str, Field(description="Frida device id")],
        package: Annotated[str, Field(description="Package to spawn")],
        argv: Annotated[list[str] | None, Field(description="Extra argv")] = None,
        env: Annotated[dict[str, str] | None, Field(description="Extra env vars")] = None,
    ) -> dict[str, Any]:
        try:
            dev = _get_cached_device(serial)
            session = get_session_store().spawn(dev, package, argv=argv, env=env)
        except Exception as e:
            return {"error": {"code": "spawn_failed", "message": str(e)}}
        return {
            "session_id": session.session_id,
            "pid": session.pid,
            "package": package,
        }

    @mcp.tool(
        name="frida_attach",
        description=("Attach to an already-running process by PID or exact process name."),
    )
    def frida_attach(
        serial: Annotated[str, Field(description="Frida device id")],
        pid: Annotated[int | None, Field(ge=1, description="Process id")] = None,
        process_name: Annotated[
            str | None,
            Field(description="Process name (exact match); alternative to pid"),
        ] = None,
    ) -> dict[str, Any]:
        if pid is None and process_name is None:
            return {"error": {"code": "input_required", "message": "pid or process_name required"}}
        try:
            dev = _get_cached_device(serial)
            store = get_session_store()
            if pid is not None:
                session = store.attach(dev, pid)
            else:
                session = store.attach_by_name(dev, process_name or "")
        except Exception as e:
            return {"error": {"code": "attach_failed", "message": str(e)}}
        return {
            "session_id": session.session_id,
            "pid": session.pid,
            "device_id": serial,
        }

    @mcp.tool(
        name="close_session",
        description="Detach a session and unload its scripts.",
    )
    def close_session(
        session_id: Annotated[str, Field(description="Session id from frida_spawn / frida_attach")],
    ) -> dict[str, Any]:
        scripts = get_script_store()
        scripts.cleanup_session(session_id)
        get_session_store().close(session_id)
        return {"ok": True, "session_id": session_id}

    @mcp.tool(
        name="list_sessions",
        description="List all active Frida sessions.",
    )
    def list_sessions() -> dict[str, Any]:
        sessions = get_session_store().list()
        return {"count": len(sessions), "sessions": [s.to_dict() for s in sessions]}

    # ------------------------------------------------------------------
    # Scripts
    # ------------------------------------------------------------------

    @mcp.tool(
        name="frida_load_script",
        description=(
            "Compile and load a Frida JavaScript source on a session. "
            "Returns a script_id. The script is enabled immediately."
        ),
    )
    def frida_load_script(
        session_id: Annotated[str, Field(description="Session id")],
        name: Annotated[str, Field(description="User-visible script name")],
        source: Annotated[str, Field(description="JavaScript source code")],
        runtime: Annotated[str, Field(description="'v8' (default) or 'qjs'")] = "v8",
    ) -> dict[str, Any]:
        try:
            session = get_session_store().get(session_id)
        except KeyError as e:
            return {"error": {"code": "session_not_found", "message": str(e)}}
        try:
            wrapper = get_script_store().load(
                session.raw, session_id, name, source, runtime=runtime
            )
        except (ValueError, RuntimeError) as e:
            return {"error": {"code": "load_failed", "message": str(e)}}
        return {
            "script_id": wrapper.script_id,
            "name": wrapper.name,
            "session_id": session_id,
            "runtime": wrapper.info.runtime,
        }

    @mcp.tool(
        name="frida_unload_script",
        description="Unload a previously-loaded script.",
    )
    def frida_unload_script(
        script_id: Annotated[str, Field(description="Script id from frida_load_script")],
    ) -> dict[str, Any]:
        get_script_store().unload(script_id)
        return {"ok": True, "script_id": script_id}

    @mcp.tool(
        name="frida_list_scripts",
        description="List all scripts loaded on a given session.",
    )
    def frida_list_scripts(
        session_id: Annotated[str, Field(description="Session id")],
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "scripts": [s.to_dict() for s in get_script_store().list_for_session(session_id)],
        }

    @mcp.tool(
        name="frida_rpc_call",
        description=(
            "Call an ``rpc.exports.<method>`` function on a loaded "
            "script. Returns the function's return value (JSON-serializable)."
        ),
    )
    def frida_rpc_call(
        script_id: Annotated[str, Field(description="Script id")],
        rpc_method: Annotated[str, Field(description="Bare method name, e.g. 'getCredentials'")],
        args: Annotated[list[Any], Field(description="Positional arguments")] = [],
        timeout_s: Annotated[float, Field(ge=0, le=600)] = DEFAULT_RPC_TIMEOUT_S,
    ) -> dict[str, Any]:
        try:
            wrapper = get_script_store().get(script_id)
        except KeyError as e:
            return {"error": {"code": "script_not_found", "message": str(e)}}
        try:
            result = call_rpc(wrapper.raw, rpc_method, *args, timeout_s=timeout_s)
        except (KeyError, RuntimeError) as e:
            return {"error": {"code": "rpc_failed", "message": str(e)}}
        return {"result": result}

    @mcp.tool(
        name="frida_list_classes",
        description=(
            "Enumerate Java classes loaded in the process attached to "
            "a session. Optionally filter by name substring."
        ),
    )
    def frida_list_classes(
        session_id: Annotated[str, Field(description="Session id")],
        package_filter: Annotated[
            str | None,
            Field(description="Filter to classes whose name contains this substring"),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=2000)] = 500,
    ) -> dict[str, Any]:
        try:
            session = get_session_store().get(session_id)
        except KeyError as e:
            return {"error": {"code": "session_not_found", "message": str(e)}}
        # Use Java.perform + Java.enumerateLoadedClasses
        try:
            js = (
                "rpc.exports = {}; "
                "Java.perform(function() { "
                "Java.enumerateLoadedClasses({ onComplete: function(classes) { "
                "rpc.exports.__classes = classes; } }); "
                "});"
            )
            scripts = get_script_store()
            probe = scripts.load(
                session.raw,
                session_id,
                "__probe_classes__",
                js,
                runtime="v8",
            )
            # The above returns immediately; the result lives in the
            # message buffer. Wait for the message.
            for _ in range(50):
                msgs = probe.messages
                if msgs:
                    break
                time.sleep(0.05)
            classes: list[str] = []
            for m in probe.messages:
                if m.get("type") == "send" and isinstance(m.get("payload"), list):
                    classes = [str(c) for c in m["payload"]]
                    break
            scripts.unload(probe.script_id)
            if package_filter:
                classes = [c for c in classes if package_filter in c]
            return {
                "session_id": session_id,
                "count": len(classes[:limit]),
                "classes": classes[:limit],
            }
        except Exception as e:
            return {"error": {"code": "enumerate_failed", "message": str(e)}}

    @mcp.tool(
        name="frida_eval",
        description=(
            "Evaluate an arbitrary JavaScript expression in a session. "
            "Use with care — the result must be JSON-serializable."
        ),
    )
    def frida_eval(
        session_id: Annotated[str, Field(description="Session id")],
        js_source: Annotated[str, Field(description="JavaScript to evaluate")],
        timeout_ms: Annotated[int, Field(ge=100, le=60000)] = 5000,
    ) -> dict[str, Any]:
        try:
            session = get_session_store().get(session_id)
        except KeyError as e:
            return {"error": {"code": "session_not_found", "message": str(e)}}
        try:
            # Use a transient script
            scripts = get_script_store()
            sid = f"__eval_{uuid.uuid4()}"
            wrapper = scripts.load(session.raw, session_id, sid, js_source, runtime="v8")
            # Allow messages to arrive
            time.sleep(timeout_ms / 1000.0)
            msgs = list(wrapper.messages)
            scripts.unload(wrapper.script_id)
            return {"messages": msgs}
        except Exception as e:
            return {"error": {"code": "eval_failed", "message": str(e)}}
