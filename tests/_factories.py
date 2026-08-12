"""Shared test factories for Terminal-Bench A/B eval tests.

Centralizes the `_summary`/`_make_summary` builders and the fixture-root
path resolver that were previously duplicated across
`test_comparison_report.py` and `test_comparison_diff.py`.
"""

from __future__ import annotations

from pathlib import Path

from comparison_report import PerTaskResult, Summary

FIXTURES_DIR = (
    Path(__file__).resolve().parent / "fixtures" / "terminal_bench_ab"
)


def fixture_root(name: str) -> Path:
    """Return the path to a fixture directory under tests/fixtures/terminal_bench_ab/."""
    return FIXTURES_DIR / name


def make_summary(
    passed_ids: list[str],
    failed_ids: list[str],
    *,
    agent: str = "test",
    model: str = "m",
    commit_sha: str = "abc",
    heretek_harness: bool = True,
    wall_clock_sec_total: int = 900,
    wall_clock_sec_p50: int = 60,
    tokens_total: int = 100000,
) -> Summary:
    """Build a Summary with deterministic defaults.

    Each passed task gets wall_clock_sec=60 / tokens=10000; each failed
    task gets wall_clock_sec=30 / tokens=5000. Override any of the
    keyword args for variants.
    """
    per_task = [
        PerTaskResult(task_id=tid, verdict="pass", wall_clock_sec=60, tokens=10000)
        for tid in passed_ids
    ] + [
        PerTaskResult(task_id=tid, verdict="fail", wall_clock_sec=30, tokens=5000)
        for tid in failed_ids
    ]
    n = len(per_task)
    return Summary(
        agent=agent,
        model=model,
        commit_sha=commit_sha,
        heretek_harness=heretek_harness,
        n_tasks=n,
        passed=len(passed_ids),
        failed=len(failed_ids),
        pass_rate=len(passed_ids) / n if n else 0.0,
        wall_clock_sec_total=wall_clock_sec_total,
        wall_clock_sec_p50=wall_clock_sec_p50,
        tokens_total=tokens_total,
        per_task=per_task,
    )
