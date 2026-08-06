"""AST-grep fast gate (#43) — synchronous D15 PreToolUse hook.

Runs ast-grep synchronously (<100ms p95) on Edit/Write/MultiEdit events.
Emits `permissionDecision=ask` if a severity=error forbidden pattern matches.
Warn-only patterns live in the async #40 scanner (forbidden_pattern_scanner).

D15 compliance: this lives in the hooks plugin only.
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
# Per spec §2: blocking edit-time stays <100ms. We surface only severity=error
# patterns here (currently: rust-todo-macro); warn-only patterns live in #40.
BLOCKING_SEVERITIES = {"error"}


def _load_blocking_patterns() -> list[dict]:
    all_patterns = yaml.safe_load(CATALOG.read_text())["patterns"]
    return [p for p in all_patterns if p.get("severity") in BLOCKING_SEVERITIES]


def _scan(file_path: str, content: str) -> list[dict]:
    ext = Path(file_path).suffix
    lang = EXT_TO_LANG.get(ext)
    if not lang:
        return []

    ast_grep = shutil.which("ast-grep")
    if not ast_grep:
        return []

    matches = []
    for pattern_def in _load_blocking_patterns():
        if pattern_def["language"] != lang:
            continue
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
            input=content, capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0 and result.stdout.strip():
            matches.append(pattern_def)
    return matches


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

    matches = _scan(file_path, new_content)
    if not matches:
        return 0

    summary = "; ".join(f"{m['id']}: {m['reason']}" for m in matches)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"AST-grep blocked pattern(s): {summary}",
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
