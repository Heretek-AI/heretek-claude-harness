"""Forbidden-pattern scanner (#40) — D15 PostToolUse hook.

Runs ast-grep on Edit events for Python/JS/TS/Rust files. If a forbidden
pattern matches (per `catalog/forbidden_patterns.yaml`), emits a warning
via additionalContext.

D15 compliance: this lives in the hooks plugin only — no other plugin may
declare hooks.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

CATALOG = Path(__file__).resolve().parent.parent.parent / "catalog" / "forbidden_patterns.yaml"
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
}


def _load_catalog() -> list[dict]:
    return yaml.safe_load(CATALOG.read_text())["patterns"]


def _scan(file_path: str, content: str) -> list[str]:
    ext = Path(file_path).suffix
    lang = EXT_TO_LANG.get(ext)
    if not lang:
        return []

    ast_grep = shutil.which("ast-grep")
    if not ast_grep:
        return []

    patterns = [p for p in _load_catalog() if p["language"] == lang]
    warnings = []

    for pattern_def in patterns:
        rule = yaml.safe_dump(
            {
                "id": pattern_def["id"],
                "language": lang,
                "rule": {"pattern": pattern_def["pattern"]},
            },
            sort_keys=False,
        )
        result = subprocess.run(
            [ast_grep, "scan", "--inline-rules", rule, "--stdin"],
            input=content, capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            warnings.append(
                f"[{pattern_def['id']}] {pattern_def['reason']} "
                f"Replacement: {pattern_def['replacement']}"
            )

    return warnings


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    new_content = tool_input.get("new_string", "")
    if not file_path or not new_content:
        return 0

    warnings = _scan(file_path, new_content)
    if not warnings:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(f"⚠️  {w}" for w in warnings),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
