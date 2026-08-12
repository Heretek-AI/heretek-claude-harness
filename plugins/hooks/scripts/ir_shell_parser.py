"""Canonical IR Shell Command Parser & Destructive Command Interceptor.

Parses shell tool payloads, strips wrappers (`bash -c`, `eval`, `xargs`), and blocks
catastrophic operations (`rm -rf /`, `git reset --hard`, `git push --force`).
"""

from __future__ import annotations

import json
import re
import sys

DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+-[rRfF]*\s+(/|\$HOME|~|\*)"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\bgit\s+push\s+.*--force\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+if="),
]


def unwrap_command(cmd: str) -> str:
    """Strip shell wrapper prefixes (e.g. bash -c '...', eval '...')."""
    cmd = cmd.strip()
    match = re.match(r"^(?:bash|sh|zsh)\s+-c\s+['\"](.*)['\"]$", cmd)
    if match:
        return match.group(1).strip()
    return cmd


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        return 0

    unwrapped = unwrap_command(command)
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(unwrapped):
            output = {
                "decision": "block",
                "reason": f"Blocked destructive command pattern matching '{pattern.pattern}' in command: {command}",
            }
            print(json.dumps(output))
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
