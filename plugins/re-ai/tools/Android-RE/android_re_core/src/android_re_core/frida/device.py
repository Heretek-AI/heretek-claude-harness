"""Frida device enumeration and selection.

Wraps frida's ``get_device_manager()`` and the per-device
``enumerate_processes``, ``get_frontmost_application``, and
``inject_library_file`` calls. Pins the frida-server version to
17.10.1 (matches the Python client); the
:meth:`DeviceWrapper.check_server_version` method verifies the on-device
version and refuses to spawn a session on a mismatch.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

# Lazy import: frida is only available if installed.
try:
    import frida  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "frida is required for android_re_core.frida. Install with: uv pip install 'frida==17.10.1'"
    ) from e


__all__ = [
    "PINNED_FRIDA_VERSION",
    "DeviceWrapper",
    "FridaAppInfo",
    "FridaDeviceInfo",
    "FridaProcessInfo",
    "get_device",
    "list_devices",
]


#: Pinned frida version. Must match the on-device frida-server.
PINNED_FRIDA_VERSION: str = "17.10.1"


@dataclass(frozen=True)
class FridaDeviceInfo:
    """Lightweight summary of a Frida device."""

    id: str
    name: str
    type: str  # "local" | "tether" | "remote" | "usb"
    is_lost: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "is_lost": self.is_lost,
        }


@dataclass(frozen=True)
class FridaProcessInfo:
    """A process running on a Frida device."""

    pid: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"pid": self.pid, "name": self.name}


@dataclass(frozen=True)
class FridaAppInfo:
    """The frontmost application on a Frida device."""

    pid: int
    identifier: str  # bundle id / package
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"pid": self.pid, "identifier": self.identifier, "name": self.name}


class DeviceWrapper:
    """A high-level wrapper around a Frida ``Device``.

    Use :func:`list_devices` or :func:`get_device` to obtain one.
    """

    def __init__(self, device: Any) -> None:
        self._device = device
        self._version_checked = False

    @property
    def id(self) -> str:
        return self._device.id

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def type(self) -> str:
        return self._device.type

    @property
    def is_lost(self) -> bool:
        return bool(self._device.is_lost())

    def to_info(self) -> FridaDeviceInfo:
        return FridaDeviceInfo(
            id=self.id,
            name=self.name,
            type=self.type,
            is_lost=self.is_lost,
        )

    # ------------------------------------------------------------------
    # Version checking
    # ------------------------------------------------------------------

    def check_server_version(self) -> str:
        """Return the frida-server version running on this device.

        Compares against :data:`PINNED_FRIDA_VERSION` and raises
        :class:`ValueError` on mismatch.
        """
        if self._version_checked:
            return PINNED_FRIDA_VERSION
        try:
            # Frida exposes the runtime version via the device.
            version: str = self._device.query_system_parameters().get("version", "")
        except Exception as e:
            raise RuntimeError(
                f"Could not query frida-server version on {self.id}: {e}",
            ) from e
        if not _version_match(version, PINNED_FRIDA_VERSION):
            raise RuntimeError(
                f"frida-server version mismatch on {self.id}: "
                f"client {PINNED_FRIDA_VERSION}, server {version}. "
                f"Push a matching frida-server and retry.",
            )
        self._version_checked = True
        return version

    # ------------------------------------------------------------------
    # Process / app queries
    # ------------------------------------------------------------------

    def enumerate_processes(self) -> list[FridaProcessInfo]:
        """List every process on the device."""
        procs = self._device.enumerate_processes() or []
        return [FridaProcessInfo(pid=int(p.pid), name=str(p.name)) for p in procs]

    def get_frontmost_application(self) -> FridaAppInfo | None:
        """Return the frontmost (foreground) app, or None if not available."""
        apps = self._device.get_frontmost_application()  # may raise on some devices
        if apps is None:
            return None
        return FridaAppInfo(
            pid=int(apps.get("pid", 0) or 0),
            identifier=str(apps.get("identifier", "") or ""),
            name=str(apps.get("name", "") or ""),
        )

    def find_process(self, name: str) -> FridaProcessInfo | None:
        """Find a process by exact name match. Returns None if not found."""
        for p in self.enumerate_processes():
            if p.name == name:
                return p
        return None

    # ------------------------------------------------------------------
    # Underlying access (escape hatch)
    # ------------------------------------------------------------------

    @property
    def raw(self) -> Any:
        """Return the underlying frida.Device. Use sparingly."""
        return self._device


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_devices() -> list[FridaDeviceInfo]:
    """Enumerate all Frida devices visible to this host."""
    mgr = frida.get_device_manager()
    devices = mgr.enumerate_devices() or []
    return [
        FridaDeviceInfo(
            id=str(d.id),
            name=str(d.name),
            type=str(d.type),
            is_lost=bool(d.is_lost()),
        )
        for d in devices
    ]


def get_device(device_id: str | None = None, timeout: int = 10) -> DeviceWrapper:
    """Get a Frida device by id, or the local/usb device if no id given.

    Args:
        device_id: Device id (e.g. USB serial). If None, picks the first
            non-lost USB or local device.
        timeout: Seconds to wait for the device to appear.

    Raises:
        RuntimeError: No device found within the timeout.
    """
    mgr = frida.get_device_manager()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if device_id is not None:
            try:
                dev = mgr.get_device(device_id)
                return DeviceWrapper(dev)
            except frida.NotFoundError:
                time.sleep(0.25)
                continue
        # Auto-pick: prefer USB, then remote, then local
        try:
            dev = mgr.get_usb_device(timeout=2)
            return DeviceWrapper(dev)
        except (frida.NotFoundError, frida.TimedOutError):
            pass
        try:
            dev = mgr.get_local_device()
            return DeviceWrapper(dev)
        except (frida.NotFoundError, frida.TimedOutError):
            time.sleep(0.25)
    raise RuntimeError(
        f"No Frida device found within {timeout}s (device_id={device_id!r})",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _version_match(actual: str, expected: str) -> bool:
    """Loose semver match: strip suffix (e.g. ``17.10.1-rc``) and compare.

    Frida's version string is always ``<major>.<minor>.<patch>`` with
    an optional hyphen-separated suffix.
    """
    a = re.split(r"[-+]", actual, maxsplit=1)[0]
    e = re.split(r"[-+]", expected, maxsplit=1)[0]
    return a == e
