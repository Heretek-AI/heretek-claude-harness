"""Frida client wrappers (Phase 3).

- :mod:`android_re_core.frida.device` — enumerate, select, and manage
  Frida ``Device`` objects. Includes version-pinning to frida-server.
- :mod:`android_re_core.frida.session` — session lifecycle
  (``spawn``, ``attach``, ``detach``).
- :mod:`android_re_core.frida.scripts` — load / unload / list scripts
  on a session.
- :mod:`android_re_core.frida.rpc` — call RPC methods exported by
  a loaded script.

All frida-side imports are lazy so this package can be installed on a
host that has no frida-tools (the install is gated by Python version
in the pyproject).
"""

from __future__ import annotations

__all__ = [
    "device",
    "rpc",
    "scripts",
    "session",
]
