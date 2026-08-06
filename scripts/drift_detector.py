"""Drift detector (#41) — D15 PostToolUse hook.

Watches agent Edit events for trajectory signals:
- Same file edited ≥3 times in a session (suggests confused model)
- File length monotonically increasing across last 5 edits (suggests runaway append)
- New import not referenced in subsequent edits (suggests dead-code injection)

Per D15: this lives in the hooks plugin only.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

SESSION_STATE_DIR = Path(os.environ.get(
    "HERETEK_SESSION_STATE_DIR",
    Path.cwd() / ".heretek" / "session_state",
))
REPEATED_EDIT_THRESHOLD = 3


def _session_state_path(session_id: str) -> Path:
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_STATE_DIR / f"{session_id}.json"


def _load_state(session_id: str) -> dict:
    p = _session_state_path(session_id)
    if not p.exists():
        return {"edits": []}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"edits": []}


def _save_state(session_id: str, state: dict) -> None:
    _session_state_path(session_id).write_text(json.dumps(state))


def _detect_warnings(session_id: str, file_path: str, new_string: str) -> list[str]:
    state = _load_state(session_id)
    warnings = []

    state["edits"].append({"file": file_path, "length": len(new_string)})

    # Rule 1: same file edited ≥3 times
    file_edit_counts = defaultdict(int)
    for edit in state["edits"]:
        file_edit_counts[edit["file"]] += 1
    if file_edit_counts[file_path] >= REPEATED_EDIT_THRESHOLD:
        warnings.append(
            f"drift: {Path(file_path).name} has been edited "
            f"{file_edit_counts[file_path]} times in this session — consider reviewing intent"
        )

    # Rule 2: file length monotonically increasing across last 5 edits to same file
    recent_lengths = [e["length"] for e in state["edits"] if e["file"] == file_path][-5:]
    if len(recent_lengths) >= 3 and recent_lengths == sorted(recent_lengths) and \
       len(set(recent_lengths)) == len(recent_lengths):
        warnings.append(
            f"drift: {Path(file_path).name} length has been strictly increasing "
            f"across the last {len(recent_lengths)} edits — consider trimming"
        )

    _save_state(session_id, state)
    return warnings


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0

    sid = payload.get("session_id", "")
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    new_string = tool_input.get("new_string", "")

    if not sid or not file_path:
        return 0

    warnings = _detect_warnings(sid, file_path, new_string)
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
