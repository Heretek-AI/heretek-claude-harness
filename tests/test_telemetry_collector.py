"""Hermetic tests for telemetry_collector. All filesystem ops go to tmp_path."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from plugins.hooks.scripts import telemetry_collector as tc


@pytest.fixture
def schema() -> dict:
    return json.loads((PLUGIN_ROOT / "tests" / "fixtures" / "telemetry_schema.json").read_text())


def test_redact_path_strips_home(tmp_path: Path) -> None:
    home = str(tmp_path)
    assert tc.redact_path(f"{home}/foo.py", home=home) == "~/foo.py"
    assert tc.redact_path(f"{home}/a/b/c.txt", home=home) == "~/a/b/c.txt"
    assert tc.redact_path(f"{home}", home=home) == "~"


def test_redact_path_passthrough_when_not_under_home(tmp_path: Path) -> None:
    home = str(tmp_path)
    assert tc.redact_path("/etc/passwd", home=home) == "/etc/passwd"
    assert tc.redact_path("relative/path.py", home=home) == "relative/path.py"


def test_redact_path_handles_none_and_empty(tmp_path: Path) -> None:
    assert tc.redact_path(None, home=str(tmp_path)) is None
    assert tc.redact_path("", home=str(tmp_path)) == ""


def test_parse_payload_minimal() -> None:
    payload = '{"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x.py"}}'
    result = tc.parse_payload(payload)
    assert result["tool_name"] == "Edit"


def test_parse_payload_raises_on_invalid_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        tc.parse_payload("not json")


def test_parse_payload_raises_on_non_object() -> None:
    with pytest.raises(ValueError, match="not a JSON object"):
        tc.parse_payload("[1, 2, 3]")


def test_emit_event_writes_valid_jsonl(tmp_path: Path, schema: dict) -> None:
    event = {
        "session_id": "00000000-0000-4000-8000-000000000001",
        "event_type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input_path": "~/foo.py",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/home/john/.claude/plugins/hooks",
        "schema_version": 1,
    }
    assert tc.emit_event(tmp_path, event, schema=schema) is True
    session_file = tmp_path / "session-00000000-0000-4000-8000-000000000001.jsonl"
    assert session_file.exists()
    line = session_file.read_text().strip()
    parsed = json.loads(line)
    jsonschema.validate(parsed, schema)


def test_emit_event_fail_open_on_schema_failure(tmp_path: Path, schema: dict) -> None:
    event = {"schema_version": 1, "tool_name": "NotARealTool"}
    assert tc.emit_event(tmp_path, event, schema=schema) is False
    assert list(tmp_path.iterdir()) == []  # nothing written


def test_emit_event_accepts_non_uuid_session_id(tmp_path: Path, schema: dict) -> None:
    """Non-UUID session ids (e.g., from future Claude Code versions or env var)
    must NOT fail schema validation — pattern is permissive by design (Finding 1)."""
    event = {
        "session_id": "non-uuid-string-from-claude-code",
        "event_type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input_path": "~/foo.py",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/home/john/.claude/plugins/hooks",
        "schema_version": 1,
    }
    assert tc.emit_event(tmp_path, event, schema=schema) is True
    session_file = tmp_path / "session-non-uuid-string-from-claude-code.jsonl"
    assert session_file.exists()
    parsed = json.loads(session_file.read_text().strip())
    jsonschema.validate(parsed, schema)
    assert parsed["session_id"] == "non-uuid-string-from-claude-code"


def test_emit_event_fail_open_on_disk_full(
    tmp_path: Path, schema: dict, capsys: pytest.CaptureFixture
) -> None:
    event = {
        "session_id": "00000000-0000-4000-8000-000000000002",
        "event_type": "PreToolUse",
        "tool_name": "Read",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/x",
        "schema_version": 1,
    }
    with patch("pathlib.Path.open", side_effect=OSError("disk full")):
        assert tc.emit_event(tmp_path, event, schema=schema) is False
    captured = capsys.readouterr()
    assert "write failed" in captured.err


def test_main_returns_zero_on_invalid_payload(capsys: pytest.CaptureFixture) -> None:
    with patch.object(sys, "stdin") as mock_stdin:
        mock_stdin.read.return_value = "not json"
        assert tc.main() == 0
    captured = capsys.readouterr()
    assert "not valid JSON" in captured.err


def test_main_writes_event_to_expected_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    monkeypatch.setattr(tc, "TELEMETRY_ROOT", tmp_path)
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/x.py"},
            "hook_exit_code": 0,
            "session_id": "00000000-0000-4000-8000-000000000003",
        }
    )
    with patch.object(sys, "stdin") as mock_stdin:
        mock_stdin.read.return_value = payload
        assert tc.main() == 0
    sessions = list((tmp_path / "sessions").iterdir())
    assert len(sessions) == 1


def test_latency_under_50ms(tmp_path: Path, schema: dict) -> None:
    """P95 emit latency must be < 50ms over 100 iterations."""
    import time

    event = {
        "session_id": "00000000-0000-4000-8000-000000000004",
        "event_type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input_path": "~/x.py",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/x",
        "schema_version": 1,
    }
    samples = []
    for _ in range(100):
        t0 = time.perf_counter()
        tc.emit_event(tmp_path, event, schema=schema)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p95 = samples[int(0.95 * len(samples))]
    assert p95 < 50, f"P95 latency {p95:.2f}ms exceeds 50ms budget"


def test_derive_decision_branches() -> None:
    assert tc._derive_decision({"hook_exit_code": 2}) == "block"
    assert tc._derive_decision({"hook_exit_code": 0, "hook_stderr": "WARNING: x"}) == "warn"
    assert tc._derive_decision({"hook_exit_code": 0, "hook_stderr": ""}) == "allow"


def test_build_event_handles_non_dict_tool_input() -> None:
    event = tc._build_event({"tool_name": "Edit", "tool_input": "not-a-dict"})
    assert event["tool_name"] == "Edit"
    assert event["tool_input_path"] is None


def test_main_returns_zero_when_build_event_fails(
    capsys: pytest.CaptureFixture,
) -> None:
    payload = json.dumps({"tool_name": "Edit"})
    with (
        patch.object(sys, "stdin") as mock_stdin,
        patch.object(tc, "_build_event", side_effect=RuntimeError("boom")),
    ):
        mock_stdin.read.return_value = payload
        assert tc.main() == 0
    captured = capsys.readouterr()
    assert "build_event failed" in captured.err


def test_telemetry_root_rejects_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for issue #163: HERETEK_TELEMETRY_ROOT must reject values
    that resolve outside ~/.heretek. Validation runs at import time, so we
    reload the module under a hostile env var and expect RuntimeError."""
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", "/tmp/anywhere")
    try:
        with pytest.raises(RuntimeError, match="escapes safe root"):
            importlib.reload(tc)
    finally:
        # Restore module to a sane state for subsequent tests.
        monkeypatch.delenv("HERETEK_TELEMETRY_ROOT", raising=False)
        importlib.reload(tc)


def test_telemetry_root_accepts_safe_subpath(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for issue #163: paths inside ~/.heretek must be accepted,
    including nested subdirectories like ~/.heretek/telemetry/sub."""
    safe_path = str((Path.home() / ".heretek" / "telemetry" / "sub").resolve())
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", safe_path)
    try:
        importlib.reload(tc)
        assert tc.TELEMETRY_ROOT == Path(safe_path)
    finally:
        monkeypatch.delenv("HERETEK_TELEMETRY_ROOT", raising=False)
        importlib.reload(tc)
