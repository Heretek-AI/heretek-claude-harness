"""Subprocess wrapper around the ``angr-cli`` Python helper.

angr (angr/angr, BSD) is a heavy Python binary-analysis platform
with rich in-process APIs. The expected install layout is a
``angr-cli`` Python script installed by install.sh via
``pip install 're-angr[core]'`` (which pulls in angr>=9.2).

The CLI surface is intentionally tiny — the MCP server only
needs a few operations that are awkward to do from the JSON-RPC
layer (because angr keeps long-lived AngrProject objects).

  angr-cli check                                 -> version
  angr-cli cfg <path> [--function NAME]           -> CFG JSON
  angr-cli symbolic-exec <path> <addr> <args...>  -> constraints JSON
  angr-cli reaching-defs <path> <func>           -> def-use JSON

When the helper is missing, the tools return ``WARN`` and
Claude Code surfaces a clear install hint.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


_CLI_NAME = "angr-cli"


def _binary_path() -> Path | None:
    override = os.environ.get("RE_ANGR_CLI_PATH")
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


def run_subcommand(subcommand: str, *args: str, timeout_s: int = 300) -> dict[str, Any] | None:
    """Invoke angr-cli; return parsed JSON, or None if missing."""
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
        return {"text": output, "exit_code": proc.returncode}
    if isinstance(parsed, dict) and "error" in parsed:
        return {"error": parsed.get("error", "unknown"), "exit_code": proc.returncode}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def python_import_check(timeout_s: int = 30) -> dict[str, Any]:
    """Probe whether the ``angr`` and ``cle`` Python modules are
    importable in the active Python interpreter (Gap 23 fix, v2.9.1).

    The ``check_angr`` tool previously only checked the ``angr-cli``
    binary on PATH. The angr Python module can be missing in a
    venv where the CLI helper was installed but the angr package
    itself was not (the CLI runs as a subprocess that imports
    angr in its own interpreter). The Gap 23 regression: the
    CLI check returned OK while downstream tools
    (``build_cfg``, ``symbolic_exec``, ``reaching_definitions``)
    emitted ``No module named 'angr'`` because the *server's*
    interpreter didn't have angr installed.

    The probe runs ``import angr; import cle`` in a subprocess
    using the same Python interpreter that the MCP server is
    running under (``sys.executable``). The response carries
    three fields:
    - ``python_import_ok`` (bool): whether both imports succeeded
    - ``python_angr_version`` (str | None): angr.__version__ if
      importable, else None
    - ``python_cle_version`` (str | None): cle.__version__ if
      importable, else None
    - ``python_executable`` (str): the interpreter path used

    Returns ``{"python_import_ok": False, "error": "..."}`` on
    subprocess failure (timeout, exit nonzero, missing interp).
    """
    cmd = [
        sys.executable,
        "-c",
        "import angr, cle; "
        "print(angr.__version__); "
        "print(cle.__version__); "
        "import angr.analyses; "
        "print('ok')",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return {
            "python_import_ok": False,
            "python_executable": sys.executable,
            "error": f"subprocess failed: {exc}",
        }
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        return {
            "python_import_ok": False,
            "python_executable": sys.executable,
            "error": stderr or f"import probe exited {proc.returncode}",
            "exit_code": proc.returncode,
        }
    lines = (proc.stdout or "").strip().splitlines()
    angr_version = lines[0] if len(lines) >= 1 else None
    cle_version = lines[1] if len(lines) >= 2 else None
    return {
        "python_import_ok": True,
        "python_angr_version": angr_version,
        "python_cle_version": cle_version,
        "python_executable": sys.executable,
    }
