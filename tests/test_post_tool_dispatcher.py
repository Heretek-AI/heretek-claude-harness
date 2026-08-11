"""Tests for plugins/hooks/scripts/post_tool_dispatcher.py.

The dispatcher fans out to 4 async analyzers (stale_dep_intercept,
forbidden_pattern_scanner, drift_detector, lookup_gate) and aggregates
their JSON additionalContext outputs into one envelope.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = REPO_ROOT / "plugins" / "hooks" / "scripts" / "post_tool_dispatcher.py"


def _run(payload: dict, timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DISPATCHER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/usr/local/bin"},
    )


def test_dispatcher_returns_zero_on_clean_payload() -> None:
    """No warnings → exit 0, no JSON envelope emitted."""
    import uuid

    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/unrelated.txt", "new_string": "# hello\n"},
        # Unique session_id per test run so drift_detector's session-state
        # file doesn't accumulate across runs (drift_detector tracks edits
        # by session_id and emits once an identical file is edited ≥3 times).
        "session_id": f"dispatcher-smoke-{uuid.uuid4().hex[:8]}",
    }
    result = _run(payload)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # No warnings → empty stdout (or no JSON envelope)
    if result.stdout.strip():
        envelope = json.loads(result.stdout)
        assert envelope.get("hookSpecificOutput", {}).get("additionalContext", "") == ""


def test_dispatcher_handles_empty_stdin() -> None:
    """Empty stdin → exit 0, no crash."""
    result = subprocess.run(
        [sys.executable, str(DISPATCHER)],
        input="",
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
        env={"PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0


def test_dispatcher_handles_malformed_json() -> None:
    """Malformed JSON on stdin → exit 0 (fail-open)."""
    result = subprocess.run(
        [sys.executable, str(DISPATCHER)],
        input="{not json",
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
        env={"PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0
