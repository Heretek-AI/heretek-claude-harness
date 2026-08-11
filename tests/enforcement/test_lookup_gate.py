"""Tests for lookup_gate.py (#45)."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

LOOKUP_GATE = Path("scripts/lookup_gate.py")
CACHE_DIR = Path("catalog/freshness")
SENTINEL_FILE = Path(".heretek/last_lookup.json")


def _run_gate(file_path: str, content: str, sentinel_age_hours: float = 0) -> dict:
    """Invoke the gate; optionally pre-age the sentinel file."""
    if SENTINEL_FILE.exists():
        SENTINEL_FILE.unlink()

    # Always (re)create the sentinel — age 0 means "consulted right now".
    SENTINEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    import json as _json

    SENTINEL_FILE.write_text(
        _json.dumps(
            {
                "last_lookup_at": time.time() - (sentinel_age_hours * 3600),
            }
        )
    )

    payload = json.dumps(
        {
            "session_id": "test-lookup",
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path, "new_string": content},
        }
    )
    result = subprocess.run(
        [sys.executable, str(LOOKUP_GATE)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_lookup_gate_warns_on_tracked_lib_without_recent_lookup(tmp_path, monkeypatch):
    """#45: editing a tracked lib without recent lookup → warning."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "qwen3.6-27b")
    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.34.0\n")

    # Pre-condition: freshness cache exists for 'requests'
    if not (CACHE_DIR / "requests.yaml").exists():
        pytest.skip("populate catalog/freshness/requests.yaml first")

    output = _run_gate(str(fake_req), fake_req.read_text(), sentinel_age_hours=999)
    assert (
        "lookup" in json.dumps(output).lower() or "freshness" in json.dumps(output).lower()
    ), f"expected lookup warning, got: {output}"


def test_lookup_gate_silent_after_recent_lookup(tmp_path, monkeypatch):
    """#45: editing a tracked lib with recent lookup → silent."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "qwen3.6-27b")
    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.34.0\n")

    if not (CACHE_DIR / "requests.yaml").exists():
        pytest.skip("populate catalog/freshness/requests.yaml first")

    output = _run_gate(str(fake_req), fake_req.read_text(), sentinel_age_hours=0)
    assert output == {}, f"unexpected warning after recent lookup: {output}"


def test_lookup_gate_ignores_untracked_libs(tmp_path, monkeypatch):
    """#45: editing a non-tracked library → silent."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "deepseek-v3")  # minimal lookup list
    fake = tmp_path / "main.py"
    fake.write_text("import json\n")

    output = _run_gate(str(fake), fake.read_text())
    assert output == {}, f"unexpected warning on untracked lib: {output}"
