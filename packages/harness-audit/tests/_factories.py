"""Test factories and helper fixtures for harness-audit test suite."""

from __future__ import annotations

import json
from pathlib import Path

from comparison_report import PerTaskResult, Summary

TESTS_DIR = Path(__file__).parent
REPO_ROOT = TESTS_DIR.parent


def fixture_root(name: str | None = None) -> Path:
    """Return path to tests fixture root directory or sub-fixture."""
    base = TESTS_DIR / "fixtures"
    if name:
        return base / name
    return base


def write_trial(
    jobs_dir: Path,
    task_id: str,
    *,
    job_name: str = "job-1",
    verdict_pass: bool = True,
    n_input_tokens: int = 100,
    n_output_tokens: int = 50,
    started_at: str = "2026-08-12T00:00:00Z",
    finished_at: str = "2026-08-12T00:01:00Z",
) -> Path:
    """Write mock Harbor trial result.json file."""
    trial_dir = jobs_dir / job_name / task_id
    trial_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_name": task_id,
        "verifier_result": {"rewards": {"reward": 1.0 if verdict_pass else 0.0}},
        "agent_result": {
            "n_input_tokens": n_input_tokens,
            "n_output_tokens": n_output_tokens,
        },
        "started_at": started_at,
        "finished_at": finished_at,
    }
    result_path = trial_dir / "result.json"
    result_path.write_text(json.dumps(payload, indent=2))
    return trial_dir


def make_summary(
    passed_ids: list[str] | None = None,
    failed_ids: list[str] | None = None,
    *,
    agent: str = "agent-a-with-heretek",
    model: str = "claude-sonnet-5-20260301",
    commit_sha: str = "abc1234",
    heretek_harness: bool = True,
) -> Summary:
    """Generate Summary dataclass instance for test assertions."""
    p_ids = passed_ids or []
    f_ids = failed_ids or []
    per_task: list[PerTaskResult] = []

    for tid in p_ids:
        per_task.append(PerTaskResult(task_id=tid, verdict="pass", wall_clock_sec=10, tokens=100))
    for tid in f_ids:
        per_task.append(PerTaskResult(task_id=tid, verdict="fail", wall_clock_sec=15, tokens=200))

    passed = len(p_ids)
    failed = len(f_ids)
    n_tasks = passed + failed
    pass_rate = passed / n_tasks if n_tasks else 0.0

    return Summary(
        agent=agent,
        model=model,
        commit_sha=commit_sha,
        heretek_harness=heretek_harness,
        n_tasks=n_tasks,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        wall_clock_sec_total=sum(t.wall_clock_sec for t in per_task),
        wall_clock_sec_p50=10,
        tokens_total=sum(t.tokens for t in per_task),
        per_task=per_task,
    )
