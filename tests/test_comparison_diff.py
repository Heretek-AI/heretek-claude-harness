"""Tests for the diff computation in scripts/comparison_report.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from comparison_report import Summary, PerTaskResult, compute_diff, load_summary


def _summary(passed_ids: list[str], failed_ids: list[str]) -> Summary:
    per_task = [
        PerTaskResult(task_id=tid, verdict="pass", wall_clock_sec=60, tokens=10000)
        for tid in passed_ids
    ] + [
        PerTaskResult(task_id=tid, verdict="fail", wall_clock_sec=30, tokens=5000)
        for tid in failed_ids
    ]
    n = len(per_task)
    return Summary(
        agent="test",
        model="m",
        commit_sha="abc",
        heretek_harness=True,
        n_tasks=n,
        passed=len(passed_ids),
        failed=len(failed_ids),
        pass_rate=len(passed_ids) / n if n else 0.0,
        wall_clock_sec_total=900,
        wall_clock_sec_p50=60,
        tokens_total=100000,
        per_task=per_task,
    )


def test_diff_identical() -> None:
    a = _summary(["tb-1", "tb-2"], ["tb-3"])
    b = _summary(["tb-1", "tb-2"], ["tb-3"])
    d = compute_diff(a, b)
    assert d["delta_passed"] == 0
    assert d["tasks_agent_a_passed_b_failed"] == []
    assert d["tasks_agent_b_passed_a_failed"] == []
    assert d["tasks_both_passed"] == ["tb-1", "tb-2"]
    assert d["tasks_both_failed"] == ["tb-3"]


def test_diff_a_wins_on_two_tasks() -> None:
    a = _summary(["tb-1", "tb-2", "tb-3"], ["tb-4"])
    b = _summary(["tb-1"], ["tb-2", "tb-3", "tb-4"])
    d = compute_diff(a, b)
    assert d["delta_passed"] == 2
    assert sorted(d["tasks_agent_a_passed_b_failed"]) == ["tb-2", "tb-3"]
    assert d["tasks_agent_b_passed_a_failed"] == []
    assert d["tasks_both_passed"] == ["tb-1"]


def test_diff_b_wins_on_one_task() -> None:
    a = _summary(["tb-1"], ["tb-2", "tb-3"])
    b = _summary(["tb-1", "tb-2"], ["tb-3"])
    d = compute_diff(a, b)
    assert d["delta_passed"] == -1
    assert d["tasks_agent_a_passed_b_failed"] == []
    assert d["tasks_agent_b_passed_a_failed"] == ["tb-2"]


def test_diff_wall_clock_and_tokens() -> None:
    a = _summary(["tb-1"], [])
    b = _summary(["tb-1"], [])
    a.wall_clock_sec_total = 100
    b.wall_clock_sec_total = 150
    a.tokens_total = 1000
    b.tokens_total = 2000
    d = compute_diff(a, b)
    assert d["wall_clock_delta_sec"] == -50
    assert d["tokens_delta"] == -1000


def _fixture_root(name: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "terminal_bench_ab" / name


def test_all_fail_renders_with_zero_delta() -> None:
    a = load_summary(_fixture_root("case-all-fail") / "agent-a" / "summary.json")
    b = load_summary(_fixture_root("case-all-fail") / "agent-b" / "summary.json")
    d = compute_diff(a, b)
    assert d["delta_pass_rate"] == 0.0
    assert d["delta_passed"] == 0
    assert d["tasks_both_passed"] == []
    assert sorted(d["tasks_both_failed"]) == ["tb-A", "tb-B", "tb-C", "tb-D"]


def test_identical_results_yield_zero_deltas() -> None:
    a = load_summary(_fixture_root("case-identical-results") / "agent-a" / "summary.json")
    b = load_summary(_fixture_root("case-identical-results") / "agent-b" / "summary.json")
    d = compute_diff(a, b)
    assert d["delta_pass_rate"] == 0.0
    assert d["delta_passed"] == 0
    assert d["tasks_agent_a_passed_b_failed"] == []
    assert d["tasks_agent_b_passed_a_failed"] == []
    assert d["wall_clock_delta_sec"] == 0
    assert d["tokens_delta"] == 0


def test_missing_agent_b_raises_file_not_found() -> None:
    """If agent-b/summary.json is missing, load_summary must raise."""
    with pytest.raises(FileNotFoundError):
        load_summary(_fixture_root("case-agent-b-missing") / "agent-b" / "summary.json")
