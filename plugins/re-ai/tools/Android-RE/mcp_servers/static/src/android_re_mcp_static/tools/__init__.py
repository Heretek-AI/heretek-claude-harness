"""Tool topic modules.

Each module exposes a single ``register(mcp: FastMCP) -> None`` function
that uses the :func:`mcp.server.fastmcp.FastMCP.tool` decorator to
register one or more tools.

The split mirrors the user-facing tool groups:

- :mod:`project_tools` — project lifecycle
- :mod:`manifest_tools` — manifest, components, permissions
- :mod:`dex_tools` — classes, methods, per-method decompile
- :mod:`decompile_tools` — whole-APK decompile + raw source reading
- :mod:`smali_tools` — apktool-backed smali, manifest patching
- :mod:`certs` — signing scheme and certificate info
- :mod:`native_tools` — native (ELF/.so) analysis
- :mod:`secrets_tools` — secret / hard-coded-credential scanning
- :mod:`reporting_tools` — MASVS coverage + SARIF export
"""

from __future__ import annotations

__all__ = [
    "certs",
    "decompile_tools",
    "dex_tools",
    "manifest_tools",
    "native_tools",
    "project_tools",
    "reporting_tools",
    "secrets_tools",
    "smali_tools",
]
