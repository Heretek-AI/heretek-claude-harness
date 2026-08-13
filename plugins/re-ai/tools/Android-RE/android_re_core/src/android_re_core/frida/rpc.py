"""Frida RPC helper.

Phase 2 wires most RPC through the :class:`ScriptWrapper.messages`
buffer. This module adds a structured helper for calling an
``rpc.exports.*`` method on a loaded script.
"""

from __future__ import annotations

from typing import Any

try:
    import frida  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "frida is required for android_re_core.frida.rpc. "
        "Install with: uv pip install 'frida==17.10.1'"
    ) from e


__all__ = [
    "DEFAULT_RPC_TIMEOUT_S",
    "call_rpc",
]


#: Default timeout for an RPC call. Override per-call.
DEFAULT_RPC_TIMEOUT_S: float = 30.0


def call_rpc(
    script: Any,
    method: str,
    *args: Any,
    timeout_s: float = DEFAULT_RPC_TIMEOUT_S,
) -> Any:
    """Call an ``rpc.exports.<method>`` function on a loaded script.

    Args:
        script: A :class:`frida.Script` (or our :class:`ScriptWrapper`).
        method: The bare method name, e.g. ``"getCredentials"``.
        *args: Positional arguments to pass to the RPC.
        timeout_s: Timeout in seconds. Frida's default is 0 (forever).

    Returns:
        Whatever the RPC function returns.

    Raises:
        KeyError: The script does not export the requested method.
        RuntimeError: The call failed (timeout, exception, etc.).
    """
    # Allow passing either a raw frida.Script or our ScriptWrapper.
    raw = getattr(script, "raw", script)
    exports = getattr(raw, "rpc_exports", None) or {}
    # Some Frida versions expose rpc.exports directly; some via rpc.exports() callable
    if hasattr(exports, "get"):
        try:
            fn = exports.get(method)
        except Exception:
            fn = None
    else:
        fn = None
    if fn is None:
        # Fallback to attribute access
        fn = getattr(exports, method, None) if exports is not None else None
    if fn is None:
        raise KeyError(f"Script does not export rpc.{method}")
    try:
        if timeout_s and timeout_s > 0:
            return fn(*args, timeout=timeout_s)
        return fn(*args)
    except frida.OperationCancelledError as e:
        raise RuntimeError(f"RPC call {method} cancelled: {e}") from e
    except Exception as e:
        raise RuntimeError(f"RPC call {method} failed: {e}") from e
