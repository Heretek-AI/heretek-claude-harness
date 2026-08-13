"""Subprocess wrappers around the .NET ``re-dotnet-cli`` and ``ilspycmd``.

The metadata-only CLI is built once via ``dotnet publish`` (see
``install.sh``) and stored at ``<server>/bin/re-dotnet-cli``. The
C# decompiler (``ilspycmd``) is installed as a global dotnet tool
by the same install step.

This module locates both binaries, runs a single subcommand, and
returns the parsed JSON / text the underlying tool produces.

Keeping the subprocess boundary here means the MCP server itself
stays pure Python — no pythonnet, no Mono, no fragile .NET-host
APIs. The .NET dependency is contained to two published executables
that the user can replace without touching Python.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


# ── Locate the binaries ─────────────────────────────────────────────────


_CLI_NAME = "re-dotnet-cli"
_DECOMPILER_NAME = "ilspycmd"


def _binary_path(name: str, env_var: str) -> Path | None:
    """Return the path to a binary, or None if not found.

    Search order:
      1. env_var override (escape hatch for tests / CI)
      2. ``<server_root>/bin/<name>`` (install.sh's default)
      3. ``~/.dotnet/tools/<name>`` (dotnet global tool install location)
      4. ``<name>`` on PATH
    """
    override = os.environ.get(env_var)
    if override and Path(override).is_file():
        return Path(override)

    server_root = Path(__file__).resolve().parent.parent.parent  # servers/re-dotnet
    default = server_root / "bin" / name
    if default.is_file() and os.access(default, os.X_OK):
        return default

    # dotnet global tool install location (the ilspycmd default).
    if name == "ilspycmd":
        dotnet_tools = Path.home() / ".dotnet" / "tools" / name
        if dotnet_tools.is_file() and os.access(dotnet_tools, os.X_OK):
            return dotnet_tools

    on_path = shutil.which(name)
    if on_path:
        return Path(on_path)

    return None


def _cli_binary() -> Path | None:
    return _binary_path(_CLI_NAME, "RE_DOTNET_CLI_PATH")


def _decompiler_binary() -> Path | None:
    return _binary_path(_DECOMPILER_NAME, "RE_DOTNET_DECOMPILER_PATH")


# ── Run a metadata subcommand ───────────────────────────────────────────


def run_subcommand(
    subcommand: str,
    *args: str,
    timeout_s: int = 60,
) -> dict[str, Any]:
    """Invoke the .NET metadata CLI with ``subcommand`` + extra args, parse JSON.

    Returns a dict. On error, returns ``{"error": str, "exit_code": int}``.
    """
    binary = _cli_binary()
    if binary is None:
        return {
            "error": (
                "re-dotnet-cli not found. Run install.sh (or "
                "`dotnet publish` inside src/re_dotnet/dotnet/Re.Dotnet.Cli) "
                "to build the .NET helper."
            ),
            "exit_code": -1,
        }

    cmd = [str(binary), subcommand, *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": f"re-dotnet-cli {subcommand} timed out after {timeout_s}s",
            "exit_code": -1,
        }
    except FileNotFoundError as exc:
        return {"error": f"failed to exec {binary}: {exc}", "exit_code": -1}

    # The CLI always prints one JSON document on stdout (or stderr on error).
    output = (proc.stdout or "").strip()
    if not output:
        err = (proc.stderr or "").strip()
        return {
            "error": err or f"re-dotnet-cli exited {proc.returncode} with no output",
            "exit_code": proc.returncode,
        }

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        return {
            "error": f"non-JSON output from re-dotnet-cli: {exc}; raw={output[:500]}",
            "exit_code": proc.returncode,
        }

    if proc.returncode != 0 or (isinstance(parsed, dict) and "error" in parsed):
        return {
            "error": parsed.get("error", "unknown error")
            if isinstance(parsed, dict)
            else "non-dict error payload",
            "exit_code": proc.returncode,
        }
    return parsed if isinstance(parsed, dict) else {"result": parsed}


# ── Run ilspycmd for C# decompilation ──────────────────────────────────


def decompile_type(path: str, fqn: str, timeout_s: int = 120) -> str | None:
    """Decompile a single class to C# via ilspycmd.

    Returns the C# source as a string, or None on failure.
    """
    binary = _decompiler_binary()
    if binary is None:
        return None
    cmd = [str(binary), "-t", fqn, path]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def decompile_method(path: str, method_fqn: str, timeout_s: int = 120) -> str | None:
    """Decompile a single method to C# via ilspycmd.

    ilspycmd exposes ``-m`` for method-name decompile. Pass the
    ``"Namespace.Type::Method"`` form.
    """
    binary = _decompiler_binary()
    if binary is None:
        return None
    cmd = [str(binary), "-m", method_fqn, path]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout
