"""Device control: ADB and emulator wrappers.

- :mod:`android_re_core.device.adb` — typed wrapper around the
  ``adb`` CLI subprocess.
- :mod:`android_re_core.device.adb_install` — SDK-34+ aware APK
  install (push + ``pm install`` ladder, with a staged
  ``install-create`` / ``-write`` / ``-commit`` fallback).
- :mod:`android_re_core.device.emulator` — start / stop / detect
  Android emulators.

Phase 3 ships both. The :mod:`mcp_bridge` MCP server (TypeScript)
also wraps ``adb`` but at a different abstraction layer — adbkit
gives us a connection-pooled async client there.
"""

from __future__ import annotations

__all__ = ["adb", "adb_install", "emulator"]
