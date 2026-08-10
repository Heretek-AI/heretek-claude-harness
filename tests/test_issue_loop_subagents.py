from pathlib import Path

import pytest

from scripts.issue_loop.ledger import IssueRef
from scripts.issue_loop.subagents import SubagentRunner


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    p = tmp_path / "prompts"
    p.mkdir()
    for name in ("explore", "planner", "executor", "test_engineer", "verifier"):
        (p / f"{name}.md").write_text(f"# {name}\n")
    return p


def test_runner_orchestrates_all_five_steps(prompts_dir: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    issue = IssueRef(number=158, title="x", files=["scripts/refresh_pins.py"])

    calls: list[str] = []

    def fake_dispatch(name: str, prompt: str, worktree: Path, issue: IssueRef) -> str:
        calls.append(name)
        if name == "verifier":
            return '{"approved": true, "severity_max": "LOW", "findings": []}'
        return ""

    runner = SubagentRunner(prompts_dir, worktree=wt, dispatch=fake_dispatch)
    result = runner.run_pipeline(issue)
    assert calls == ["explore", "planner", "executor", "test_engineer", "verifier"]
    assert result.verdict == {"approved": True, "severity_max": "LOW", "findings": []}


def test_runner_records_blocked_reason(prompts_dir: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    issue = IssueRef(number=158, title="x", files=[])

    def fake_dispatch(name: str, prompt: str, worktree: Path, issue: IssueRef) -> str:
        if name == "planner":
            return "BLOCKED: too large for single-iteration loop"
        return ""

    runner = SubagentRunner(prompts_dir, worktree=wt, dispatch=fake_dispatch)
    result = runner.run_pipeline(issue)
    assert result.blocked_reason is not None
    assert "too large" in result.blocked_reason