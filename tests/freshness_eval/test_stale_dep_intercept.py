"""Tests for stale_dep_intercept.py (#37).

All tests are fully isolated: the on-disk cache directory is redirected
to a per-test `tmp_path` via `monkeypatch`, synthetic cache YAML files
are written in for whichever libs each test needs, and stdin is mocked
via `monkeypatch.setattr(sys, "stdin", ...)`. No test ever touches the
real `catalog/freshness/` tree or relies on which libs the cron has run.
"""

import io
import json
import sys


import scripts.stale_dep_intercept as hook


def _build_payload(tool_name: str, file_path: str, content: str) -> dict:
    """Build a synthetic PostToolUse hook payload for the given tool event shape."""
    payload: dict = {
        "session_id": "test",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    }
    if tool_name == "Edit":
        payload["tool_input"]["new_string"] = content
    elif tool_name == "Write":
        payload["tool_input"]["content"] = content
    elif tool_name == "MultiEdit":
        payload["tool_input"]["edits"] = [{"new_string": content}]
    else:
        # Defensive: unknown tool name — handler should still try common fields.
        payload["tool_input"]["new_string"] = content
    return payload


def _run_hook(monkeypatch, tool_name: str, file_path: str, content: str) -> int:
    """Invoke hook.main() with synthetic stdin JSON; returns exit code."""
    payload = _build_payload(tool_name, file_path, content)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def _write_cache(tmp_path, lib: str, latest_version: str) -> None:
    """Write a synthetic freshness cache file into tmp_path."""
    cache_file = tmp_path / f"{lib}.yaml"
    cache_file.write_text(
        f"latest_version: {latest_version}\n"
        "latest_release_date: '2025-09-25T21:31:46'\n"
        "eol_date: null\n"
        "cve_count_critical: 0\n"
    )


def test_stale_dep_intercept_warns_on_old_pin(monkeypatch, tmp_path, capsys):
    """#37: when requirements.txt pins an old version, hook warns (Edit event)."""
    monkeypatch.setattr(hook, "CACHE_DIR", tmp_path)
    _write_cache(tmp_path, "requests", "2.32.0")

    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.20.0\n")

    rc = _run_hook(monkeypatch, "Edit", str(fake_req), fake_req.read_text())
    captured = capsys.readouterr()
    assert rc == 0, f"hook should not error; stderr: {captured.err}"
    output = json.loads(captured.out) if captured.out.strip() else {}
    assert "hookSpecificOutput" in output, f"expected warning JSON, got: {output!r}"
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "requests" in ctx
    assert "stale" in ctx


def test_stale_dep_intercept_silent_on_fresh_pin(monkeypatch, tmp_path, capsys):
    """#37: when requirements.txt pins the latest version, hook stays silent."""
    monkeypatch.setattr(hook, "CACHE_DIR", tmp_path)
    _write_cache(tmp_path, "requests", "2.32.0")

    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.32.0\n")

    rc = _run_hook(monkeypatch, "Edit", str(fake_req), fake_req.read_text())
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "", f"unexpected output on fresh pin: {captured.out!r}"


def test_stale_dep_intercept_ignores_non_dep_files(monkeypatch, tmp_path, capsys):
    """#37: hook does nothing when file is not a dep manifest."""
    monkeypatch.setattr(hook, "CACHE_DIR", tmp_path)
    _write_cache(tmp_path, "requests", "2.32.0")

    fake_py = tmp_path / "main.py"
    fake_py.write_text("import requests\n")

    rc = _run_hook(monkeypatch, "Edit", str(fake_py), fake_py.read_text())
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "", f"hook should ignore non-dep files, got: {captured.out!r}"


def test_stale_dep_intercept_handles_write_event(monkeypatch, tmp_path, capsys):
    """#37: Write events (tool_input.content) are scanned, not silently dropped."""
    monkeypatch.setattr(hook, "CACHE_DIR", tmp_path)
    _write_cache(tmp_path, "requests", "2.32.0")

    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.20.0\n")

    rc = _run_hook(monkeypatch, "Write", str(fake_req), fake_req.read_text())
    captured = capsys.readouterr()
    assert rc == 0
    output = json.loads(captured.out) if captured.out.strip() else {}
    assert (
        "hookSpecificOutput" in output
    ), f"Write event should emit stale-pin warning, got: {output!r}"
    assert "requests" in output["hookSpecificOutput"]["additionalContext"]


def test_stale_dep_intercept_handles_multiedit_event(monkeypatch, tmp_path, capsys):
    """#37: MultiEdit events scan each tool_input.edits[*].new_string."""
    monkeypatch.setattr(hook, "CACHE_DIR", tmp_path)
    _write_cache(tmp_path, "requests", "2.32.0")

    fake_req = tmp_path / "requirements.txt"
    stale_edit = "requests==2.20.0\n"
    unrelated_edit = "# unrelated edit to a different region\n"

    payload = {
        "session_id": "test",
        "hook_event_name": "PostToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(fake_req),
            "edits": [
                {"new_string": unrelated_edit},
                {"new_string": stale_edit},
            ],
        },
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    output = json.loads(captured.out) if captured.out.strip() else {}
    assert (
        "hookSpecificOutput" in output
    ), f"MultiEdit event should emit stale-pin warning, got: {output!r}"
    assert "requests" in output["hookSpecificOutput"]["additionalContext"]


def test_stale_dep_intercept_multiedit_silent_when_no_stale_edits(monkeypatch, tmp_path, capsys):
    """#37: MultiEdit with no stale edits stays silent."""
    monkeypatch.setattr(hook, "CACHE_DIR", tmp_path)
    _write_cache(tmp_path, "requests", "2.32.0")

    fake_req = tmp_path / "requirements.txt"

    payload = {
        "session_id": "test",
        "hook_event_name": "PostToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(fake_req),
            "edits": [{"new_string": "requests==2.32.0\n"}],
        },
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "", f"MultiEdit with fresh pin should be silent, got: {captured.out!r}"
