"""Drift detector (#41) — D15 PostToolUse hook.

Watches agent Edit events for trajectory signals:
- Same file edited ≥3 times in a session (suggests confused model)
- File length monotonically increasing across last 5 edits (suggests runaway append)
- New import not referenced in subsequent edits (suggests dead-code injection)

Per D15: this lives in the hooks plugin only.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._allowlist import require_session_id  # noqa: E402

SESSION_STATE_DIR = Path(os.environ.get(
    "HERETEK_SESSION_STATE_DIR",
    Path.cwd() / ".heretek" / "session_state",
))
REPEATED_EDIT_THRESHOLD = 3
MONOTONIC_DIFF_THRESHOLD = 3


def _session_state_path(session_id: str) -> Path:
    require_session_id(session_id)
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_STATE_DIR / f"{session_id}.json"


def _load_state(session_id: str) -> dict:
    p = _session_state_path(session_id)
    if not p.exists():
        return {"edits": [], "imports": {}}
    try:
        state = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"edits": [], "imports": {}}
    # Migrate older state files missing the "imports" key.
    state.setdefault("edits", [])
    state.setdefault("imports", {})
    # Re-review I-NEW-1: legacy edit records used `length` instead of
    # `diff_size`. Rename in-place so recent_diffs lookups don't KeyError.
    # Preserves session history rather than dropping records.
    for edit in state["edits"]:
        if "length" in edit and "diff_size" not in edit:
            edit["diff_size"] = edit.pop("length")
    return state


def _save_state(session_id: str, state: dict) -> None:
    # SonarCloud S2083 (BLOCKER) — false positive: session_id is validated
    # against ^[A-Za-z0-9_-]{1,128}$ in _session_state_path() via
    # require_session_id() before any path construction. See #141.
    _session_state_path(session_id).write_text(json.dumps(state))  # nosonar


def _extract_imports(text: str) -> set[str]:
    """Extract top-level import names from Python code (best-effort)."""
    imports: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname or alias.name)
    return imports


def _extract_references(text: str) -> set[str]:
    """Extract name references from Python code (excluding import statements).

    Used to decide whether an import has been 'used' in a given edit.
    """
    refs: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return refs
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                refs.add(base.id)
    return refs


def _detect_warnings(
    session_id: str,
    file_path: str,
    new_string: str,
    old_string: str = "",
) -> list[str]:
    state = _load_state(session_id)
    warnings: list[str] = []

    # diff_size is the actual change in file length — positive means file grew.
    diff_size = len(new_string) - len(old_string)
    state["edits"].append({"file": file_path, "diff_size": diff_size})

    # Rule 1: same file edited ≥3 times
    file_edit_counts: dict[str, int] = defaultdict(int)
    for edit in state["edits"]:
        file_edit_counts[edit["file"]] += 1
    if file_edit_counts[file_path] >= REPEATED_EDIT_THRESHOLD:
        warnings.append(
            f"drift: {Path(file_path).name} has been edited "
            f"{file_edit_counts[file_path]} times in this session — consider reviewing intent"
        )

    # Rule 2: file length monotonically increasing across last 5 edits to same file
    recent_diffs = [
        e["diff_size"] for e in state["edits"] if e["file"] == file_path
    ][-5:]
    if (
        len(recent_diffs) >= MONOTONIC_DIFF_THRESHOLD
        and all(d > 0 for d in recent_diffs)
        and recent_diffs == sorted(recent_diffs)
        and len(set(recent_diffs)) == len(recent_diffs)
    ):
        warnings.append(
            f"drift: {Path(file_path).name} length has been strictly increasing "
            f"across the last {len(recent_diffs)} edits — consider trimming"
        )

    # Rule 3: new import not referenced in subsequent edits to the same file.
    # Only applies to Python files; non-Python edits just reset the pending list.
    pending: list[str] = list(state["imports"].get(file_path, []))
    prior_edits_for_file = file_edit_counts[file_path] - 1  # excludes current

    if file_path.endswith(".py"):
        new_refs = _extract_references(new_string)

        # Anything still pending and not referenced in this edit stays pending.
        pending = [imp for imp in pending if imp not in new_refs]

        if pending and prior_edits_for_file >= 1:
            warnings.append(
                f"drift: {Path(file_path).name} added import(s) not referenced "
                f"in subsequent edits: {', '.join(sorted(pending))}"
            )
            # Re-review M-NEW: emit warning once per unreferenced import, then
            # drop from pending so the same warning doesn't fire on every
            # subsequent edit.
            pending = []

        # Re-review I-NEW-2: only queue imports that are genuinely new.
        # Truly new = (imports in new_string - imports in old_string)
        #              minus imports used in the same edit.
        old_imports = _extract_imports(old_string)
        new_imports = _extract_imports(new_string)
        truly_new = (new_imports - old_imports) - new_refs
        for imp in truly_new:
            if imp not in pending:
                pending.append(imp)

    state["imports"][file_path] = pending

    _save_state(session_id, state)
    return warnings


def main() -> int:
    # SonarCloud S3516 (BLOCKER) — false positive: hook-script entrypoint always
    # returns 0 (success). The hook infrastructure reads warnings from stdout
    # JSON, not the exit code. See #141.
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0  # nosonar

    sid = payload.get("session_id", "")
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    new_string = tool_input.get("new_string", "")
    old_string = tool_input.get("old_string", "")

    if not sid or not file_path:
        return 0  # nosonar

    warnings = _detect_warnings(sid, file_path, new_string, old_string)
    if not warnings:
        return 0  # nosonar

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(f"⚠️  {w}" for w in warnings),
        }
    }))
    return 0  # nosonar


if __name__ == "__main__":
    sys.exit(main())
