"""Tests for scripts/comparison_report.py — argument parsing and summary.json loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from comparison_report import build_arg_parser, load_summary


def test_build_arg_parser_has_required_flags() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--results-dir",
            "./results",
            "--commit-sha",
            "abc1234",
            "--trigger",
            "push",
            "--actor",
            "alice",
            "--tier",
            "quick",
            "--model",
            "claude-test",
            "--base-url",
            "https://example.com",
            "--output",
            "/tmp/c.md",
        ]
    )
    assert args.results_dir == Path("./results")
    assert args.commit_sha == "abc1234"
    assert args.trigger == "push"
    assert args.actor == "alice"
    assert args.tier == "quick"
    assert args.model == "claude-test"
    assert args.base_url == "https://example.com"
    assert args.output == Path("/tmp/c.md")


def test_load_summary_minimal(tmp_path: Path) -> None:
    payload = {
        "agent": "agent-a-with-heretek",
        "model": "claude-test",
        "commit_sha": "abc1234",
        "heretek_harness": True,
        "n_tasks": 8,
        "passed": 5,
        "failed": 3,
        "pass_rate": 0.625,
        "wall_clock_sec_total": 845,
        "wall_clock_sec_p50": 92,
        "tokens_total": 412345,
        "per_task": [
            {"task_id": "tb-001", "verdict": "pass", "wall_clock_sec": 45, "tokens": 12345},
            {"task_id": "tb-002", "verdict": "fail", "wall_clock_sec": 60, "tokens": 8000},
        ],
    }
    p = tmp_path / "summary.json"
    p.write_text(json.dumps(payload))
    s = load_summary(p)
    assert s.agent == "agent-a-with-heretek"
    assert s.passed == 5
    assert s.failed == 3
    assert s.pass_rate == pytest.approx(0.625)
    assert len(s.per_task) == 2
    assert s.per_task[0].task_id == "tb-001"
    assert s.per_task[0].verdict == "pass"


def test_load_summary_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_summary(tmp_path / "does-not-exist.json")
