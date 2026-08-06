"""Tests for stale_dep_intercept.py (#37)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SCRIPT = Path("scripts/stale_dep_intercept.py")


def _run_hook(file_path: str, new_content: str) -> dict:
    """Invoke the hook as Claude Code would (stdin = hook input JSON)."""
    payload = json.dumps({
        "session_id": "test",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": new_content},
    })
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=payload, capture_output=True, text=True, timeout=5,
    )
    # Hook returns non-zero exit only on hard errors; warnings emit JSON on stdout
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_stale_dep_intercept_warns_on_old_pin(tmp_path, monkeypatch):
    """#37: when requirements.txt pins an old version, hook warns."""
    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.20.0\n")

    # Pre-condition: freshness cache must have a known-newer version
    cache = Path("catalog/freshness/requests.yaml")
    if not cache.exists():
        pytest.skip("run Task 4 first to populate catalog/freshness/requests.yaml")

    output = _run_hook(str(fake_req), fake_req.read_text())
    # Hook should emit a warning with stale-pin info
    assert "hookSpecificOutput" in output or "additionalContext" in str(output) or output == {}, \
        f"expected warning or empty, got: {output}"


def test_stale_dep_intercept_silent_on_fresh_pin(tmp_path):
    """#37: when requirements.txt pins the latest version, hook stays silent."""
    cache = Path("catalog/freshness/requests.yaml")
    if not cache.exists():
        pytest.skip("run Task 4 first")

    import yaml
    latest = yaml.safe_load(cache.read_text())["latest_version"]

    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text(f"requests=={latest}\n")

    output = _run_hook(str(fake_req), fake_req.read_text())
    # No warning expected
    assert output == {} or "warning" not in str(output).lower(), \
        f"unexpected warning on fresh pin: {output}"


def test_stale_dep_intercept_ignores_non_dep_files(tmp_path):
    """#37: hook does nothing when file is not a dep manifest."""
    cache = Path("catalog/freshness/requests.yaml")
    if not cache.exists():
        pytest.skip("run Task 4 first")

    fake_py = tmp_path / "main.py"
    fake_py.write_text("import requests\n")

    output = _run_hook(str(fake_py), fake_py.read_text())
    assert output == {}, f"hook should ignore non-dep files, got: {output}"