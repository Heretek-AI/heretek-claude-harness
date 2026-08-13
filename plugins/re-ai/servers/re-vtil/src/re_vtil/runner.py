"""Subprocess wrapper around the ``vtil-cli`` C++ helper binary.

VTIL-Core (vtil-project/VTIL-Core, MIT) is a C++ library with no
first-class Python bindings. The expected install layout is a
single ``vtil-cli`` binary built by install.sh via
``cmake --build`` against the vendored VTIL-Core source tree.

When the binary is missing (e.g. on a fresh checkout before
install.sh has been run, or on a host that cannot build the
C++ helper), the tools return ``WARN`` rather than crashing —
this is the standard RE-AI degraded-mode behavior. The Python
server itself always loads.

If the binary is present, it exposes a small CLI surface:

  vtil-cli check                                  -> version
  vtil-cli lift <arch> <code_b64> <base>          -> VTIL IL JSON
  vtil-cli optimize <il_json> <passes>            -> optimized IL JSON
  vtil-cli emit <il_json>                        -> pseudo-C text
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


_CLI_NAME = "vtil-cli"


def _binary_path() -> Path | None:
    override = os.environ.get("RE_VTIL_CLI_PATH")
    if override and Path(override).is_file():
        return Path(override)

    server_root = Path(__file__).resolve().parent.parent.parent
    default = server_root / "bin" / _CLI_NAME
    if default.is_file() and os.access(default, os.X_OK):
        return default

    on_path = shutil.which(_CLI_NAME)
    if on_path:
        return Path(on_path)

    return None


def run_subcommand(subcommand: str, *args: str, timeout_s: int = 60) -> dict[str, Any] | None:
    """Invoke vtil-cli with ``subcommand`` + extra args, parse JSON output.

    Returns ``None`` if the binary is missing. On a non-zero exit
    or non-JSON output, returns ``{"error": str, "exit_code": int}``.
    """
    binary = _binary_path()
    if binary is None:
        return None
    cmd = [str(binary), subcommand, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    output = (proc.stdout or "").strip()
    if not output:
        return {
            "error": (proc.stderr or "").strip() or "no output",
            "exit_code": proc.returncode,
        }
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        # emit-pseudo-c may return plain text rather than JSON
        return {"text": output, "exit_code": proc.returncode}
    if isinstance(parsed, dict) and "error" in parsed:
        return {
            "error": parsed.get("error", "unknown"),
            "exit_code": proc.returncode,
        }
    return parsed if isinstance(parsed, dict) else {"result": parsed}
