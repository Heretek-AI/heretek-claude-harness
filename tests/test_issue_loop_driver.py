import os
import subprocess
from pathlib import Path

import pytest

from scripts.issue_loop.branch import BranchManager
from scripts.issue_loop.driver import IssueLoop
from scripts.issue_loop.gate import GatePoller, GateVerdict
from scripts.issue_loop.ledger import IssueRef, Ledger
from scripts.issue_loop.merge import Merger
from scripts.issue_loop.subagents import SubagentRunner


def _clean_env() -> dict[str, str]:
    """Strip GIT_* env so test fixtures target tmp_path, not parent repo.

    Mirrors scripts/issue_loop/branch.py:_clean_env. Pre-commit framework
    sets GIT_DIR in the hook subprocess; without stripping, `git init`
    re-initializes the main repo and subsequent git ops hit the wrong
    gitdir.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@pytest.fixture
def fake_loop(tmp_path: Path) -> IssueLoop:
    # tmp_path is not a git repo by default; BranchManager.create() shells out
    # to `git branch`, so initialize one. Brief fixture uses BranchManager(tmp_path)
    # verbatim but does not init git — this is the minimal deviation required to
    # let the verbatim implementation run.
    env = _clean_env()
    subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    (tmp_path / "init.txt").write_text("init")
    subprocess.run(
        ["git", "add", "init.txt"], cwd=tmp_path, check=True, capture_output=True, env=env
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    for name in ("explore", "planner", "executor", "test_engineer", "verifier"):
        (prompts / f"{name}.md").write_text(f"# {name}\n")
    ledger = Ledger(tmp_path / "ledger.json")
    bm = BranchManager(tmp_path)  # unused in this test, just needs to construct
    sr = SubagentRunner(
        prompts_dir=tmp_path / "prompts",
        worktree=tmp_path,
        dispatch=lambda n, p, w, issue: '{"approved": true, "severity_max": "LOW", "findings": []}',
    )
    gp = GatePoller(
        "tok",
        "o/r",
        pr_number=1,
        fetcher=lambda: GateVerdict(
            ci="green", copilot="approved", sonar="passed", code_reviewer="approved"
        ),
        sleep=lambda s: None,
    )
    m = Merger("tok", "o/r", local_repo=tmp_path)
    candidates = [IssueRef(number=158, title="x", files=["a.py"])]

    return IssueLoop(
        ledger=ledger,
        branch=bm,
        subagents=sr,
        gate=gp,
        merger=m,
        github_token="tok",
        repo="o/r",
        prompts_dir=tmp_path / "prompts",
        candidates_provider=lambda: candidates,
        pr_opener=lambda issue, branch: (1, "https://example/pr/1"),  # returns (pr_number, url)
        squash_merge=lambda **kw: "deadbeef",
    )


def test_run_once_returns_false_when_queue_empty(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.json")
    loop = IssueLoop(
        ledger=ledger,
        branch=BranchManager(tmp_path),
        subagents=SubagentRunner(tmp_path / "prompts", tmp_path, dispatch=lambda *a: "{}"),
        gate=GatePoller("t", "o/r", 1, fetcher=lambda: GateVerdict(), sleep=lambda s: None),
        merger=Merger("t", "o/r", local_repo=tmp_path),
        github_token="t",
        repo="o/r",
        prompts_dir=tmp_path / "prompts",
        candidates_provider=list,
        pr_opener=lambda i, b: (0, ""),
        squash_merge=lambda **kw: "",
    )
    assert loop.run_once() is False


def test_run_once_returns_true_and_marks_merged(fake_loop: IssueLoop) -> None:
    assert fake_loop.run_once() is True
    assert fake_loop.ledger._entries["158"]["status"] == "merged"


def test_run_until_empty_returns_summary(fake_loop: IssueLoop) -> None:
    summary = fake_loop.run_until_empty()
    assert summary.merged == 1
    assert summary.skipped == 0
