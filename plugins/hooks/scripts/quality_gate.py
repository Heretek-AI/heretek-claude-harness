"""Layer-2 quality-gate runner for the heretek hooks plugin.

Invoked by /quality-gate:run slash command. Runs the available slow
analyzers and reports a unified pass/fail. Tools not installed are
silently skipped (fail-open) so users with partial tooling don't get
spurious failures.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# Map: tool name -> (binary to check on PATH, argv template to run on repo)
TOOL_TABLE: dict[str, tuple[str, list[str]]] = {
    "clippy": ("cargo", ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"]),
    "megalinter": ("megalinter", ["megalinter", "--fix", "false"]),
    "tdd-guard": ("tdd-guard", ["tdd-guard"]),
    "jscpd": ("jscpd", ["jscpd", "--reporters", "console", "src/"]),
    "sonarqube": ("sonar-scanner", ["sonar-scanner"]),
}

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_scope_path(raw: str) -> Path:
    """Resolve scope path against REPO_ROOT; reject escapes."""
    resolved = (REPO_ROOT / raw).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError(f"scope path {raw!r} escapes REPO_ROOT")
    return resolved


def parse_scope(arg: str) -> dict:
    """Parse a /quality-gate:run argument into a scope dict."""
    if arg == "" or arg == "repo":
        return {"scope": "repo"}
    if arg == "diff":
        return {"scope": "diff"}
    _resolve_scope_path(arg)
    return {"scope": "path", "path": arg}


def resolve_tools() -> list[str]:
    """Return the subset of TOOL_TABLE whose binary is installed."""
    available: list[str] = []
    for name, (binary, _) in TOOL_TABLE.items():
        if shutil.which(binary) is not None:
            available.append(name)
    return available


def _scope_cwd(scope: dict) -> Path:
    if scope.get("scope") == "path":
        return _resolve_scope_path(scope["path"])
    return Path(".")


def run(scope: dict, available_only: bool = True) -> int:
    """Run the available tools in TOOL_TABLE. Returns 0 if all pass, 2 if any fail."""
    tools = resolve_tools() if available_only else list(TOOL_TABLE.keys())
    if not tools:
        print("quality_gate: no Layer-2 tools installed; nothing to run", file=sys.stderr)
        return 0
    failures: list[str] = []
    for name in tools:
        binary, argv = TOOL_TABLE[name]
        print(f"quality_gate: running {name} ({binary})...", file=sys.stderr)
        try:
            result = subprocess.run(
                argv, cwd=_scope_cwd(scope), capture_output=True, text=True, check=False
            )
        except FileNotFoundError:
            print(f"quality_gate: {name}: binary disappeared mid-run; skipping", file=sys.stderr)
            continue
        if result.returncode != 0:
            failures.append(name)
            if result.stdout:
                print(result.stdout, file=sys.stderr, end="")
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="")
    if failures:
        print(f"quality_gate: FAILED ({', '.join(failures)})", file=sys.stderr)
        return 2
    print(f"quality_gate: OK ({len(tools)} tools passed)", file=sys.stderr)
    return 0


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    return run(parse_scope(arg))


if __name__ == "__main__":
    sys.exit(main())
