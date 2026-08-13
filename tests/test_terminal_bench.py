"""Hermetic unit tests for Harbor TerminalBench 2.0 evaluation scripts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.aggregate_results import aggregate_jobs_dir
from scripts.comparison_report import (
    Summary,
    compute_diff,
    render_with_secret_check,
    scan_for_secrets,
)
from scripts.harness_auto_grade import auto_grade


def test_aggregate_jobs_dir_with_mock_trials(tmp_path: Path) -> None:
    """aggregate_jobs_dir accurately extracts verdicts and computes metrics."""
    jobs_dir = tmp_path / "jobs"
    job_1 = jobs_dir / "job-100"
    trial_1 = job_1 / "trial-1"
    trial_2 = job_1 / "trial-2"
    trial_1.mkdir(parents=True)
    trial_2.mkdir(parents=True)

    t1_data = {
        "task_name": "task-alpha",
        "verifier_result": {"rewards": {"main": 1.0}},
        "agent_result": {"n_input_tokens": 100, "n_output_tokens": 50},
        "started_at": "2026-08-12T12:00:00Z",
        "finished_at": "2026-08-12T12:00:10Z",
    }
    t2_data = {
        "task_name": "task-beta",
        "verifier_result": {"rewards": {"main": 0.0}},
        "agent_result": {"n_input_tokens": 200, "n_output_tokens": 80},
        "started_at": "2026-08-12T12:00:00Z",
        "finished_at": "2026-08-12T12:00:20Z",
    }

    (trial_1 / "result.json").write_text(json.dumps(t1_data))
    (trial_2 / "result.json").write_text(json.dumps(t2_data))

    res = aggregate_jobs_dir(
        jobs_dir,
        agent_label="agent-a-with-heretek",
        model="claude-sonnet-5-20260301",
        commit_sha="testsha123",
    )

    assert res["agent"] == "agent-a-with-heretek"
    assert res["n_tasks"] == 2
    assert res["passed"] == 1
    assert res["failed"] == 1
    assert res["pass_rate"] == 0.5
    assert res["wall_clock_sec_total"] == 30
    assert res["tokens_total"] == 430


def test_comparison_report_diff_computation() -> None:
    """compute_diff calculates correct pass rate delta and helped/hurt task sets."""
    sum_a = Summary(
        agent="agent-a-with-heretek",
        model="test-model",
        commit_sha="sha-a",
        heretek_harness=True,
        n_tasks=2,
        passed=2,
        failed=0,
        pass_rate=1.0,
        wall_clock_sec_total=40,
        wall_clock_sec_p50=20,
        tokens_total=500,
        per_task=[],
    )
    sum_b = Summary(
        agent="agent-b-baseline",
        model="test-model",
        commit_sha="sha-b",
        heretek_harness=False,
        n_tasks=2,
        passed=1,
        failed=1,
        pass_rate=0.5,
        wall_clock_sec_total=50,
        wall_clock_sec_p50=25,
        tokens_total=600,
        per_task=[],
    )

    diff = compute_diff(sum_a, sum_b)
    assert diff["delta_pass_rate"] == 0.5
    assert diff["delta_passed"] == 1
    assert diff["wall_clock_delta_sec"] == -10
    assert diff["tokens_delta"] == -100


def test_secret_scanner_blocks_api_keys() -> None:
    """scan_for_secrets identifies token patterns and render_with_secret_check raises error."""
    clean_text = "All tests passed with 100% success rate."
    assert scan_for_secrets(clean_text) == []
    assert render_with_secret_check(clean_text) == clean_text

    secret_text = "Leaked key: sk-ant-api03-123456789012345678901234567890"
    hits = scan_for_secrets(secret_text)
    assert len(hits) == 1
    with pytest.raises(RuntimeError, match="secret-shaped string"):
        render_with_secret_check(secret_text)


def test_auto_grader_evaluates_patch_diff() -> None:
    """auto_grade evaluates patch diff limits correctly."""
    eval_input = {
        "fixture": "fix-git",
        "expected": {
            "auto_grade": {
                "patch_diff_max_bytes": 1000,
                "files_changed_required": ["README.md"],
            }
        },
    }
    patch_diff = "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new"
    res = auto_grade(eval_input, patch_diff=patch_diff)
    assert res["verdict"] == "pass"
    assert res["checks"]["patch_diff_under_limit"] is True
