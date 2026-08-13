"""Frida session lifecycle: ``spawn``, ``attach``, ``detach``.

A :class:`SessionWrapper` holds a :class:`frida.Session` plus the PID
it was attached to. Sessions are tracked in a process-local
:class:`SessionStore` so MCP tools can refer to them by id.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .device import PINNED_FRIDA_VERSION, DeviceWrapper, list_devices

try:
    import frida  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "frida is required for android_re_core.frida.session. "
        "Install with: uv pip install 'frida==17.10.1'"
    ) from e


__all__ = [
    "DEFAULT_SPAWN_WAIT_S",
    "SessionInfo",
    "SessionStore",
    "SessionWrapper",
]


#: Default time to wait for a freshly-spawned process to initialize.
DEFAULT_SPAWN_WAIT_S: float = 1.0


@dataclass
class SessionInfo:
    """Lightweight summary of an active session."""

    session_id: str
    pid: int
    device_id: str
    package: str | None
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pid": self.pid,
            "device_id": self.device_id,
            "package": self.package,
            "created_at": self.created_at,
        }


@dataclass
class SessionWrapper:
    """A wrapper around a Frida ``Session``.

    Use :class:`SessionStore` to manage lifecycle; do not construct
    directly.
    """

    info: SessionInfo
    _session: Any = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def session_id(self) -> str:
        return self.info.session_id

    @property
    def pid(self) -> int:
        return self.info.pid

    @property
    def device_id(self) -> str:
        return self.info.device_id

    @property
    def is_detached(self) -> bool:
        return self._closed or bool(self._session.is_detached)

    @property
    def raw(self) -> Any:
        return self._session

    def detach(self) -> None:
        """Detach from the target process. Idempotent."""
        if self._closed:
            return
        try:
            self._session.detach()
        except Exception:
            pass
        self._closed = True


class SessionStore:
    """Process-local registry of active :class:`SessionWrapper` instances."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionWrapper] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # spawn / attach
    # ------------------------------------------------------------------

    def spawn(
        self,
        device: DeviceWrapper,
        package: str,
        *,
        argv: list[str] | None = None,
        env: dict[str, str] | None = None,
        wait_s: float = DEFAULT_SPAWN_WAIT_S,
    ) -> SessionWrapper:
        """Spawn a fresh process and attach immediately.

        The on-device frida-server version is verified before spawn.
        """
        device.check_server_version()
        raw_dev = device.raw
        try:
            pid = raw_dev.spawn([package, *(argv or [])], env=env or {})
        except frida.NotFoundError as e:
            raise RuntimeError(f"Package not found on device: {package}") from e
        except frida.PermissionDeniedError as e:
            raise RuntimeError(
                f"Permission denied spawning {package}; "
                f"is the device rooted and frida-server running as root?",
            ) from e
        # The spawn() call may not exist on all backends; use spawn() in v17
        time.sleep(wait_s)
        session = raw_dev.attach(pid)
        wrapper = SessionWrapper(
            info=SessionInfo(
                session_id=str(uuid.uuid4()),
                pid=int(pid),
                device_id=device.id,
                package=package,
                created_at=time.time(),
            ),
            _session=session,
        )
        with self._lock:
            self._sessions[wrapper.session_id] = wrapper
        return wrapper

    def attach(
        self,
        device: DeviceWrapper,
        pid: int,
    ) -> SessionWrapper:
        """Attach to an already-running process by PID."""
        device.check_server_version()
        try:
            session = device.raw.attach(pid)
        except frida.NotFoundError as e:
            raise RuntimeError(f"Process {pid} not found on device") from e
        except frida.PermissionDeniedError as e:
            raise RuntimeError(
                f"Permission denied attaching to PID {pid}; "
                f"is frida-server running with the right privileges?",
            ) from e
        wrapper = SessionWrapper(
            info=SessionInfo(
                session_id=str(uuid.uuid4()),
                pid=int(pid),
                device_id=device.id,
                package=None,
                created_at=time.time(),
            ),
            _session=session,
        )
        with self._lock:
            self._sessions[wrapper.session_id] = wrapper
        return wrapper

    def attach_by_name(
        self,
        device: DeviceWrapper,
        process_name: str,
    ) -> SessionWrapper:
        """Attach to a process by exact name match."""
        proc = device.find_process(process_name)
        if proc is None:
            raise RuntimeError(f"Process {process_name!r} not found on device")
        return self.attach(device, proc.pid)

    # ------------------------------------------------------------------
    # close / get
    # ------------------------------------------------------------------

    def close(self, session_id: str) -> None:
        """Detach and remove a session. Idempotent."""
        with self._lock:
            wrapper = self._sessions.get(session_id)
            if wrapper is None:
                return
            wrapper.detach()
            del self._sessions[session_id]

    def get(self, session_id: str) -> SessionWrapper:
        """Return the session with the given id, or raise."""
        with self._lock:
            wrapper = self._sessions.get(session_id)
            if wrapper is None or wrapper.is_detached:
                raise KeyError(f"Session {session_id!r} not found or detached")
            return wrapper

    def try_get(self, session_id: str) -> SessionWrapper | None:
        try:
            return self.get(session_id)
        except KeyError:
            return None

    def list(self) -> list[SessionInfo]:
        """Return all live sessions."""
        with self._lock:
            return [w.info for w in self._sessions.values() if not w.is_detached]

    def __len__(self) -> int:
        return len(self.list())

    def __contains__(self, session_id: object) -> bool:
        if not isinstance(session_id, str):
            return False
        return self.try_get(session_id) is not None


__ = list_devices  # re-export
_ = PINNED_FRIDA_VERSION
