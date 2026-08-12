"""Tests for scripts/issue_runner.py reference runner."""

from __future__ import annotations

from pathlib import Path

from scripts.issue_runner import IssueRunner, IssueTask, MechanicalGateRunner


def test_issue_runner_pass_first_attempt(tmp_path: Path) -> None:
    sample_file = tmp_path / "good.py"
    sample_file.write_text("x = 1\n")

    gate = MechanicalGateRunner(repo_root=tmp_path)
    runner = IssueRunner(gate_runner=gate, max_attempts=3)
    task = IssueTask(task_id="test-1", description="Clean task", target_files=["good.py"])

    def dummy_executor(t: IssueTask, diags: list[str]) -> str:
        return "done"

    res = runner.run_task(task, dummy_executor)
    assert res.passed is True
    assert res.attempts == 1


def test_issue_runner_fail_missing_file(tmp_path: Path) -> None:
    gate = MechanicalGateRunner(repo_root=tmp_path)
    runner = IssueRunner(gate_runner=gate, max_attempts=2)
    task = IssueTask(task_id="test-2", description="Missing file task", target_files=["missing.py"])

    def dummy_executor(t: IssueTask, diags: list[str]) -> str:
        return "attempted"

    res = runner.run_task(task, dummy_executor)
    assert res.passed is False
    assert res.attempts == 2
    assert len(res.diagnostics) == 2
    assert "does not exist" in res.diagnostics[0]
