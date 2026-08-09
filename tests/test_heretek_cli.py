"""Hermetic tests for heretek_cli telemetry subcommand group. All filesystem
ops go to tmp_path; HERETEK_TELEMETRY_ROOT is monkeypatched per-test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import heretek_cli as cli  # noqa: E402


@pytest.fixture
def telemetry_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    monkeypatch.setattr(cli, "TELEMETRY_ROOT", tmp_path)
    (tmp_path / "sessions" / "2026-08-08").mkdir(parents=True)
    sample = tmp_path / "sessions" / "2026-08-08" / "session-aaa.jsonl"
    sample.write_text(
        json.dumps(
            {
                "ts": "2026-08-08T12:00:00.000Z",
                "session_id": "00000000-0000-4000-8000-000000000aaa",
                "event_type": "PostToolUse",
                "tool_name": "Edit",
                "tool_input_path": "~/foo.py",
                "hook_decision": "allow",
                "hook_exit_code": 0,
                "matcher_matched": True,
                "plugin_root": "/x",
                "schema_version": 1,
            }
        )
        + "\n"
    )
    return tmp_path


def test_show_prints_events(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "show"]) == 0
    captured = capsys.readouterr()
    assert "PostToolUse" in captured.out
    assert "Edit" in captured.out


def test_show_filters_by_tool(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "show", "--tool", "Read"]) == 0
    captured = capsys.readouterr()
    assert "(no events)" in captured.err


def test_grep_finds_matching_events(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "grep", "Edit"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip().splitlines()[0])
    assert parsed["tool_name"] == "Edit"


def test_diff_compares_two_sessions(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    (telemetry_root / "sessions" / "2026-08-08" / "session-bbb.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-08-08T13:00:00.000Z",
                "session_id": "00000000-0000-4000-8000-000000000bbb",
                "event_type": "PostToolUse",
                "tool_name": "Edit",
                "tool_input_path": "~/bar.py",
                "hook_decision": "block",
                "hook_exit_code": 2,
                "matcher_matched": True,
                "plugin_root": "/x",
                "schema_version": 1,
            }
        )
        + "\n"
    )
    assert cli.main(["telemetry", "diff", "session-aaa", "session-bbb"]) == 0
    captured = capsys.readouterr()
    assert "allow" in captured.out
    assert "block" in captured.out


def test_export_refuses_without_pii_flag(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "export"]) == 2
    captured = capsys.readouterr()
    assert "PII" in captured.err


def test_export_writes_with_pii_flag(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "export", "--i-understand-pii-implications"]) == 0
    out = telemetry_root / "exports" / "export.jsonl"
    assert out.exists()
    assert out.read_text().strip().startswith("{")


def test_config_set_writes_yaml(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "config", "set", "retention_days", "60"]) == 0
    config = (telemetry_root / "config.yaml").read_text()
    assert "retention_days: 60" in config


def test_schema_prints_schema(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    assert cli.main(["telemetry", "schema"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["title"] == "TelemetryEvent"
    assert parsed["properties"]["schema_version"]["const"] == 1


def test_schema_returns_1_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """cmd_telemetry_schema returns 1 with friendly error when schema file is absent."""
    missing = tmp_path / "no_such_schema.json"
    monkeypatch.setattr(cli, "SCHEMA_PATH", missing)
    assert cli.main(["telemetry", "schema"]) == 1
    captured = capsys.readouterr()
    assert "schema file not found" in captured.err
