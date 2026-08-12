"""Shared test factories for Terminal-Bench A/B eval tests.

Centralizes the `_summary`/`_make_summary` builders and the fixture-root
path resolver that were previously duplicated across
`test_comparison_report.py` and `test_comparison_diff.py`.
"""

from __future__ import annotations

import json
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


def write_trial(
    jobs_dir: Path,
    task_name: str,
    *,
    verdict_pass: bool = True,
    n_input_tokens: int = 0,
    n_output_tokens: int = 0,
    started_at: str = "2026-08-12T00:00:00Z",
    finished_at: str = "2026-08-12T00:01:00Z",
    job_name: str = "job-1",
) -> None:
    """Write a single harbor-style trial result.json.

    Mirrors harbor 0.21.0's TrialResult schema (only the fields the
    aggregator reads). Used by aggregate_results tests; future harbor-
    related tests can reuse this.
    """
    trial_dir = jobs_dir / job_name / task_name
    trial_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_name": task_name,
        "verifier_result": {"rewards": {"reward": 1.0 if verdict_pass else 0.0}},
        "agent_result": {
            "n_input_tokens": n_input_tokens,
            "n_output_tokens": n_output_tokens,
        },
        "started_at": started_at,
        "finished_at": finished_at,
    }
    (trial_dir / "result.json").write_text(json.dumps(payload))
