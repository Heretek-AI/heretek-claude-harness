"""Frida script loading, unloading, and listing.

Wraps :class:`frida.Session`'s ``create_script()`` /
``enable_scripts()`` calls. The :class:`ScriptStore` tracks scripts
per session so the MCP server can refer to them by id.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

try:
    import frida  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "frida is required for android_re_core.frida.scripts. "
        "Install with: uv pip install 'frida==17.10.1'"
    ) from e


__all__ = [
    "ScriptInfo",
    "ScriptStore",
    "ScriptWrapper",
]


#: Default message handlers receive (message, data). The default
#: implementation prints to stderr; the MCP server wires its own
#: handler that buffers messages for tool return values.


@dataclass
class ScriptInfo:
    """Lightweight summary of a loaded script."""

    script_id: str
    name: str
    session_id: str
    runtime: str  # "v8" | "qjs"
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "name": self.name,
            "session_id": self.session_id,
            "runtime": self.runtime,
            "created_at": self.created_at,
        }


@dataclass
class ScriptWrapper:
    """A wrapper around a Frida ``Script``."""

    info: ScriptInfo
    _script: Any = field(repr=False)
    _messages: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def script_id(self) -> str:
        return self.info.script_id

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def session_id(self) -> str:
        return self.info.session_id

    @property
    def raw(self) -> Any:
        return self._script

    @property
    def is_destroyed(self) -> bool:
        try:
            return self._closed or not bool(self._script.is_destroyed)
        except Exception:
            return True

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Return the buffered messages received from this script."""
        return list(self._messages)

    def unload(self) -> None:
        """Unload the script. Idempotent."""
        if self._closed:
            return
        try:
            self._script.unload()
        except Exception:
            pass
        self._closed = True


class ScriptStore:
    """Process-local registry of loaded scripts, keyed by session."""

    def __init__(self) -> None:
        self._scripts: dict[str, ScriptWrapper] = {}
        self._by_session: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def load(
        self,
        session: Any,
        session_id: str,
        name: str,
        source: str,
        *,
        runtime: str = "v8",
    ) -> ScriptWrapper:
        """Compile and load a Frida script on a session.

        Args:
            session: A raw frida.Session.
            session_id: The id we use to refer to the parent session.
            name: User-visible script name.
            source: JavaScript source.
            runtime: "v8" (default) or "qjs".
        """
        try:
            script = session.create_script(source, runtime=runtime)
        except frida.InvalidArgumentError as e:
            raise ValueError(f"Invalid Frida script: {e}") from e
        except frida.ScriptDestroyedError as e:
            raise RuntimeError("Session is detached") from e

        wrapper = ScriptWrapper(
            info=ScriptInfo(
                script_id=str(uuid.uuid4()),
                name=name,
                session_id=session_id,
                runtime=runtime,
                created_at=time.time(),
            ),
            _script=script,
        )

        # Buffer messages so MCP tools can return them.
        def _on_message(message: dict[str, Any], data: bytes | None) -> None:  # type: ignore[no-untyped-def]
            wrapper._messages.append(
                {
                    "type": message.get("type", ""),
                    "payload": message.get("payload"),
                    "data_b64": data.hex() if data else None,
                }
            )

        script.on("message", _on_message)
        try:
            script.load()
        except frida.CompileError as e:
            raise ValueError(f"Frida script compilation failed: {e}") from e

        with self._lock:
            self._scripts[wrapper.script_id] = wrapper
            self._by_session.setdefault(session_id, set()).add(wrapper.script_id)
        return wrapper

    def unload(self, script_id: str) -> None:
        with self._lock:
            wrapper = self._scripts.pop(script_id, None)
            if wrapper is None:
                return
            self._by_session.get(wrapper.session_id, set()).discard(script_id)
            wrapper.unload()

    def get(self, script_id: str) -> ScriptWrapper:
        with self._lock:
            wrapper = self._scripts.get(script_id)
            if wrapper is None or wrapper.is_destroyed:
                raise KeyError(f"Script {script_id!r} not found or destroyed")
            return wrapper

    def try_get(self, script_id: str) -> ScriptWrapper | None:
        try:
            return self.get(script_id)
        except KeyError:
            return None

    def list_for_session(self, session_id: str) -> list[ScriptInfo]:
        with self._lock:
            ids = list(self._by_session.get(session_id, set()))
            return [self._scripts[i].info for i in ids if i in self._scripts]

    def cleanup_session(self, session_id: str) -> None:
        """Unload every script belonging to a session."""
        with self._lock:
            ids = list(self._by_session.get(session_id, set()))
        for sid in ids:
            self.unload(sid)
