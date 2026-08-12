"""Hermetic tests for heretek_cli telemetry subcommand group. All filesystem
ops go to tmp_path; HERETEK_TELEMETRY_ROOT is monkeypatched per-test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import heretek_cli as cli


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


def test_show_prints_events(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "show"]) == 0
    captured = capsys.readouterr()
    assert "PostToolUse" in captured.out
    assert "Edit" in captured.out


def test_show_filters_by_tool(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "show", "--tool", "Read"]) == 0
    captured = capsys.readouterr()
    assert "(no events)" in captured.err


def test_grep_finds_matching_events(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "grep", "Edit"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip().splitlines()[0])
    assert parsed["tool_name"] == "Edit"


def test_diff_compares_two_sessions(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
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


def test_export_writes_with_pii_flag(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "export", "--i-understand-pii-implications"]) == 0
    out = telemetry_root / "exports" / "export.jsonl"
    assert out.exists()
    assert out.read_text().strip().startswith("{")


def test_config_set_writes_properties(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "config", "set", "retention_days", "60"]) == 0
    config = (telemetry_root / "config.properties").read_text()
    assert "retention_days: 60" in config


def test_schema_prints_schema(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
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


def test_diff_reports_each_missing_session_individually(
    telemetry_root: Path, capsys: pytest.CaptureFixture
) -> None:
    """cmd_telemetry_diff reports each missing session name, not 'or'."""
    assert cli.main(["telemetry", "diff", "session-aaa", "no-such-b"]) == 1
    captured = capsys.readouterr()
    assert "session not found: no-such-b" in captured.err
    assert "or" not in captured.err

    assert cli.main(["telemetry", "diff", "no-such-a", "no-such-b"]) == 1
    captured = capsys.readouterr()
    assert "session not found: no-such-a" in captured.err
    assert "session not found: no-such-b" in captured.err
    assert "or" not in captured.err


def test_show_session_help_mentions_substring_match() -> None:
    """--session help text documents substring match behavior."""
    import argparse

    parser = cli.build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    choices = getattr(subparsers_action, "choices", {})
    show_parser = choices.get("telemetry")
    assert show_parser is not None
    telemetry_subparsers = next(
        a for a in show_parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    telemetry_choices = getattr(telemetry_subparsers, "choices", {})
    show_sub = telemetry_choices.get("show")
    assert show_sub is not None
    for action in show_sub._actions:
        if action.dest == "session" and action.help:
            assert "substring match" in action.help
            assert "2026-08-08" in action.help
            return
    pytest.fail("--session argument not found on show subcommand")


def test_read_events_warns_on_malformed_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """_read_events emits a stderr warning when a JSONL line is malformed."""
    monkeypatch.setattr(cli, "TELEMETRY_ROOT", tmp_path)
    (tmp_path / "sessions" / "2026-08-09").mkdir(parents=True)
    good = {
        "ts": "2026-08-09T10:00:00.000Z",
        "session_id": "00000000-0000-4000-8000-000000000ccc",
        "event_type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input_path": "~/good.py",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/x",
        "schema_version": 1,
    }
    bad_line = "this is not valid json {{{"
    (tmp_path / "sessions" / "2026-08-09" / "session-ddd.jsonl").write_text(
        json.dumps(good) + "\n" + bad_line + "\n"
    )
    assert cli.main(["telemetry", "show"]) == 0
    captured = capsys.readouterr()
    assert "warning: 1 malformed JSONL line(s) skipped" in captured.err
