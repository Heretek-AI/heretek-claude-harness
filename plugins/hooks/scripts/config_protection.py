"""Config Protection PreToolUse Interceptor.

Prevents AI agents from illegally editing linter or compiler configuration files
(`ruff.toml`, `pyproject.toml`, `biome.json`, `.eslintrc`, `tsconfig.json`) to
suppress errors instead of fixing underlying code bugs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROTECTED_CONFIG_PATTERNS = [
    "ruff.toml",
    ".ruff.toml",
    "biome.json",
    ".oxlintrc.json",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    "tsconfig.json",
    "Cargo.toml",
    ".clippy.toml",
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if not file_path:
        return 0

    path_obj = Path(file_path)
    if path_obj.name in PROTECTED_CONFIG_PATTERNS:
        output = {
            "decision": "block",
            "reason": (
                f"Config Protection Interceptor: Modifying linter/compiler config '{path_obj.name}' "
                "is restricted. Fix the underlying code violations rather than suppressing linter rules."
            ),
        }
        print(json.dumps(output))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
