import os
import subprocess
from pathlib import Path

import pytest

from scripts.issue_loop.branch import BranchManager, slug_from_title


def _clean_env() -> dict[str, str]:
    """Strip GIT_* env so test fixtures target tmp_path, not parent repo.

    Mirrors scripts/issue_loop/branch.py:_clean_env. Pre-commit framework
    sets GIT_DIR in the hook subprocess; without stripping, `git init`
    re-initializes the main repo and `git worktree add` attaches to it.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def test_slug_from_title_basic() -> None:
    assert (
        slug_from_title("Security: yaml.load without Loader") == "security-yaml-load-without-loader"
    )


def test_slug_from_title_truncates_at_max_len() -> None:
    long = "x" * 200
    s = slug_from_title(long, max_len=30)
    assert len(s) <= 30
    assert s == "x" * 30


def test_slug_from_title_drops_punctuation() -> None:
    assert (
        slug_from_title("Fix: TOCTOU race in `_save_done_items`")
        == "fix-toctou-race-in-save-done-items"
    )


def test_slug_from_title_collapses_dashes() -> None:
    assert slug_from_title("a -- b") == "a-b"


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _clean_env()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo, env=env)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo, env=env)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo, env=env)
    (repo / "f").write_text("0\n")
    subprocess.check_call(["git", "add", "f"], cwd=repo, env=env)
    subprocess.check_call(["git", "commit", "-q", "-m", "init"], cwd=repo, env=env)
    return repo


def test_branch_manager_create(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml.load without Loader")
    assert name == "auto/158-yaml-load-without-loader"
    out = subprocess.check_output(["git", "branch"], cwd=git_repo, env=_clean_env()).decode()
    assert "auto/158-yaml-load-without-loader" in out


def test_branch_manager_spawn_worktree(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml.load without Loader")
    wt = git_repo.parent / "wt"
    bm.spawn_worktree(name, wt)
    assert wt.exists()
    assert (wt / "f").exists()
    bm.remove_worktree(wt)


def test_branch_manager_rebase_clean(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml")
    wt = git_repo.parent / "wt"
    bm.spawn_worktree(name, wt)
    assert bm.rebase_onto_main(wt) is True


def test_branch_manager_rebase_conflict(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml")
    wt = git_repo.parent / "wt"
    bm.spawn_worktree(name, wt)
    # mutate on main
    (git_repo / "f").write_text("main-change\n")
    env = _clean_env()
    subprocess.check_call(["git", "commit", "-q", "-am", "main"], cwd=git_repo, env=env)
    # conflicting change on branch
    (wt / "f").write_text("branch-change\n")
    subprocess.check_call(["git", "commit", "-q", "-am", "branch"], cwd=wt, env=env)
    assert bm.rebase_onto_main(wt) is False
