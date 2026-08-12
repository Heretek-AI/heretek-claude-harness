"""Tests for scripts/aggregate_results.py — per-trial walker → summary dict."""

from __future__ import annotations

import json
from pathlib import Path

from aggregate_results import aggregate_jobs_dir


def _write_trial(
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
    """Write a single trial result.json under <jobs_dir>/<job_name>/<task_name>/."""
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


def _make_jobs_dir(tmp_path: Path) -> Path:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    return jobs


def test_all_pass(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    for i in range(4):
        _write_trial(jobs, f"tb-{i:03d}", verdict_pass=True)
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 4
    assert summary["passed"] == 4
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 1.0
    assert len(summary["per_task"]) == 4


def test_all_fail(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    for i in range(4):
        _write_trial(jobs, f"tb-{i:03d}", verdict_pass=False)
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["passed"] == 0
    assert summary["failed"] == 4
    assert summary["pass_rate"] == 0.0


def test_mixed_split(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    for tid in ["tb-001", "tb-002", "tb-003"]:
        _write_trial(jobs, tid, verdict_pass=(tid != "tb-003"))
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 2 / 3
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-001", "tb-002", "tb-003"]


def test_empty_jobs_dir(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 0
    assert summary["passed"] == 0
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["per_task"] == []
    assert summary["wall_clock_sec_total"] == 0
    assert summary["wall_clock_sec_p50"] == 0
    assert summary["tokens_total"] == 0


def test_jobs_dir_does_not_exist(tmp_path: Path) -> None:
    """Missing jobs-dir is a no-op; emit zero summary."""
    summary = aggregate_jobs_dir(
        tmp_path / "does-not-exist",
        agent_label="agent-a-with-heretek",
        model="m",
        commit_sha="abc",
    )
    assert summary["n_tasks"] == 0
    assert summary["passed"] == 0


def test_verdict_absent_skips_trial(tmp_path: Path) -> None:
    """A trial with no verifier_result.rewards is skipped (not counted in n_tasks)."""
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-good", verdict_pass=True)
    # Manually overwrite the second trial to have no rewards.
    bad_dir = jobs / "job-1" / "tb-bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "result.json").write_text(
        json.dumps(
            {
                "task_name": "tb-bad",
                "verifier_result": {"rewards": {}},
                "agent_result": {"n_input_tokens": 0, "n_output_tokens": 0},
                "started_at": "2026-08-12T00:00:00Z",
                "finished_at": "2026-08-12T00:01:00Z",
            }
        )
    )
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 1
    assert summary["passed"] == 1
    assert summary["failed"] == 0
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-good"]


def test_tokens_and_wall_clock_aggregated(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(
        jobs,
        "tb-001",
        n_input_tokens=100,
        n_output_tokens=50,
        started_at="2026-08-12T00:00:00Z",
        finished_at="2026-08-12T00:01:00Z",  # 60s
    )
    _write_trial(
        jobs,
        "tb-002",
        n_input_tokens=200,
        n_output_tokens=75,
        started_at="2026-08-12T00:01:00Z",
        finished_at="2026-08-12T00:03:00Z",  # 120s
    )
    _write_trial(
        jobs,
        "tb-003",
        n_input_tokens=300,
        n_output_tokens=100,
        started_at="2026-08-12T00:03:00Z",
        finished_at="2026-08-12T00:06:00Z",  # 180s
    )
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["tokens_total"] == 100 + 50 + 200 + 75 + 300 + 100
    assert summary["wall_clock_sec_total"] == 60 + 120 + 180
    assert summary["wall_clock_sec_p50"] == 120  # median of [60, 120, 180]


def test_heretek_harness_flag_derived_from_label(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-001", job_name="a-jobs")
    a = aggregate_jobs_dir(jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc")
    b = aggregate_jobs_dir(jobs, agent_label="agent-b-baseline", model="m", commit_sha="abc")
    assert a["heretek_harness"] is True
    assert b["heretek_harness"] is False


def test_picks_most_recent_job_dir(tmp_path: Path) -> None:
    """If harbor was resumed, multiple job dirs exist; use the most recent mtime."""
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-old", job_name="job-old")
    _write_trial(jobs, "tb-new", job_name="job-new")
    # Force job-new to be more recent.
    import os

    (jobs / "job-new").touch()
    os.utime(jobs / "job-new", (2_000_000_000, 2_000_000_000))
    os.utime(jobs / "job-old", (1_000_000_000, 1_000_000_000))
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-new"]


def test_malformed_json_skipped(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-good")
    bad_dir = jobs / "job-1" / "tb-bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "result.json").write_text("not json{{{")
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 1
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-good"]


def test_missing_agent_result_zeros_tokens_and_wall_clock(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-001")
    # Overwrite to remove agent_result.
    (jobs / "job-1" / "tb-001" / "result.json").write_text(
        json.dumps(
            {
                "task_name": "tb-001",
                "verifier_result": {"rewards": {"reward": 1.0}},
                "started_at": "2026-08-12T00:00:00Z",
                "finished_at": "2026-08-12T00:01:00Z",
            }
        )
    )
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 1
    assert summary["passed"] == 1
    assert summary["tokens_total"] == 0
    assert summary["wall_clock_sec_total"] == 0
