"""Layer-1 fast-gate dispatcher for the heretek hooks plugin.

Reads a Claude Code hook payload from stdin, extracts the changed file path,
dispatches to the right linter/formatter (ruff / rustfmt / biome) on JUST
that file, and enforces a 100 ms self-kill timer. Exit codes:

- 0: allow (lint passed, or file type is not gated, or time-budget killed us and we fail-open)
- 2: block (linter reported violations — Claude Code treats exit-2 as deny)

The wrapper enforces the <100ms goal internally via the `timeout` argument
to `subprocess.run`, which raises `subprocess.TimeoutExpired` when the
budget elapses. Claude Code's hook timeout is integer seconds
(`timeout=1` minimum per Claude Code docs), so the wrapper's
sub-second self-kill is what makes the <100ms goal real.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Map of file extension -> (binary name, argv template)
# `{}` is replaced with the file path.
DISPATCH_TABLE: dict[str, tuple[str, list[str]]] = {
    ".py": ("ruff", ["ruff", "check", "--no-fix", "{}"]),
    ".rs": ("rustfmt", ["rustfmt", "--check", "--edition", "2021", "{}"]),
    ".js": ("biome", ["biome", "check", "--no-errors-on-unmatched", "{}"]),
    ".jsx": ("biome", ["biome", "check", "--no-errors-on-unmatched", "{}"]),
    ".ts": ("biome", ["biome", "check", "--no-errors-on-unmatched", "{}"]),
    ".tsx": ("biome", ["biome", "check", "--no-errors-on-unmatched", "{}"]),
    ".json": ("biome", ["biome", "check", "--no-errors-on-unmatched", "{}"]),
    ".css": ("biome", ["biome", "check", "--no-errors-on-unmatched", "{}"]),
}


def parse_payload(payload_text: str) -> dict:
    """Parse a Claude Code hook payload and return {tool_name, file_path}.

    Raises ValueError if the payload is malformed or missing required keys.
    """
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"payload is not a JSON object: {type(payload).__name__}")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ValueError("payload missing or non-dict tool_input")
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("payload missing or empty tool_input.file_path")
    return {"tool_name": payload.get("tool_name", "?"), "file_path": file_path}


def _resolve_binary(preferred: str) -> Optional[str]:
    """Find the binary on PATH; fall back to npx for biome."""
    found = shutil.which(preferred)
    if found:
        return found
    if preferred == "biome":
        # Try `npx @biomejs/biome` instead of plain `biome`.
        npx = shutil.which("npx")
        if npx:
            return npx
    return None


def dispatch(file_path: Path, time_budget_s: float = 0.1) -> int:
    """Run the appropriate linter on file_path within time_budget_s seconds.

    Returns 0 if the file extension is not gated (allow silently).
    Returns 2 if the linter reports violations.
    Returns 0 if the binary is not installed (fail-open, allow).
    Returns 0 on time-budget expiry (fail-open, allow).
    """
    ext = file_path.suffix.lower()
    entry = DISPATCH_TABLE.get(ext)
    if entry is None:
        return 0
    binary, argv_template = entry
    resolved = _resolve_binary(binary)
    if resolved is None:
        print(
            f"fast_gate: {binary} not installed; failing open for {file_path}",
            file=sys.stderr,
        )
        return 0
    argv = [resolved] + [arg.replace("{}", str(file_path)) for arg in argv_template[1:]]
    # If using npx as the biome wrapper, the actual biome binary is the next arg.
    if binary == "biome" and resolved.endswith("npx"):
        argv = ["npx", "-y", "@biomejs/biome", "check", "--no-errors-on-unmatched", str(file_path)]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=time_budget_s,
        )
    except FileNotFoundError:
        return 0
    except subprocess.TimeoutExpired:
        print(
            f"fast_gate: {file_path} exceeded {time_budget_s}s — failing open",
            file=sys.stderr,
        )
        return 0
    if result.returncode == 0:
        return 0
    # Print stderr to surface the lint output for the agent.
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.stdout:
        print(result.stdout, file=sys.stderr, end="")
    return 2


def run(payload_text: str, time_budget_s: float = 0.1) -> int:
    """Top-level: parse payload + dispatch + enforce time budget.

    On time-budget expiry, prints a warning and exits 0 (fail-open).
    """
    try:
        parsed = parse_payload(payload_text)
    except ValueError as exc:
        print(f"fast_gate: {exc}", file=sys.stderr)
        return 0
    file_path = Path(parsed["file_path"])
    return dispatch(file_path, time_budget_s)


def main() -> int:
    payload_text = sys.stdin.read()
    return run(payload_text)


if __name__ == "__main__":
    sys.exit(main())
