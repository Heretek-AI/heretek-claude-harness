"""Tests for drift_detector.py (#41)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

DETECTOR = Path("scripts/drift_detector.py")
SESSION_STATE_DIR = Path(".heretek/session_state")


def _run_detector(session_id: str, file_path: str, new_string: str) -> dict:
    payload = json.dumps({
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": new_string},
    })
    result = subprocess.run(
        [sys.executable, str(DETECTOR)],
        input=payload, capture_output=True, text=True, timeout=5,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_drift_detector_warns_on_repeated_edits(tmp_path, monkeypatch):
    """#41: 3+ edits to same file → warning."""
    monkeypatch.setenv("HERETEK_SESSION_STATE_DIR", str(tmp_path))
    sid = "test-session-repeated"
    target = tmp_path / "foo.py"
    target.write_text("v1\n")

    # First two edits — silent
    _run_detector(sid, str(target), "v1\n")
    _run_detector(sid, str(target), "v2\n")

    # Third edit — should warn
    output = _run_detector(sid, str(target), "v3\n")
    output_str = json.dumps(output)
    assert "repeated edit" in output_str.lower() or "drift" in output_str.lower(), \
        f"expected drift warning on 3rd edit, got: {output}"


def test_drift_detector_silent_on_normal_workflow(tmp_path, monkeypatch):
    """#41: distinct file edits do NOT trigger warnings."""
    monkeypatch.setenv("HERETEK_SESSION_STATE_DIR", str(tmp_path))
    sid = "test-session-clean"
    for i in range(3):
        target = tmp_path / f"file_{i}.py"
        target.write_text(f"v{i}\n")
        output = _run_detector(sid, str(target), f"v{i}\n")
        assert output == {}, f"unexpected warning on distinct file: {output}"
