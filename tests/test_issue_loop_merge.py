import os
import subprocess
from pathlib import Path

import pytest
from scripts.issue_loop.merge import Merger


def _clean_env() -> dict[str, str]:
    """Strip GIT_* env so test fixtures target tmp_path, not parent repo.

    Mirrors scripts/issue_loop/branch.py:_clean_env. Pre-commit framework
    sets GIT_DIR in the hook subprocess; without stripping, `git init`
    re-initializes the main repo and `git checkout`/`commit` hit the wrong
    gitdir.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _clean_env()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo, env=env)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo, env=env)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo, env=env)
    (repo / "a.py").write_text("a\n")
    subprocess.check_call(["git", "add", "a.py"], cwd=repo, env=env)
    subprocess.check_call(["git", "commit", "-q", "-m", "init"], cwd=repo, env=env)
    return repo


def test_diff_is_scoped_true_when_only_allowed_files(git_repo: Path) -> None:
    env = _clean_env()
    subprocess.check_call(["git", "checkout", "-q", "-b", "auto/x"], cwd=git_repo, env=env)
    (git_repo / "a.py").write_text("a-changed\n")
    subprocess.check_call(["git", "commit", "-q", "-am", "x"], cwd=git_repo, env=env)
    m = Merger("tok", "o/r", local_repo=git_repo)
    assert m.diff_is_scoped("auto/x", ["a.py"]) is True


def test_diff_is_scoped_false_when_other_file(git_repo: Path) -> None:
    env = _clean_env()
    subprocess.check_call(["git", "checkout", "-q", "-b", "auto/x"], cwd=git_repo, env=env)
    (git_repo / "b.py").write_text("b\n")
    subprocess.check_call(["git", "add", "b.py"], cwd=git_repo, env=env)
    subprocess.check_call(["git", "commit", "-q", "-m", "x"], cwd=git_repo, env=env)
    m = Merger("tok", "o/r", local_repo=git_repo)
    assert m.diff_is_scoped("auto/x", ["a.py"]) is False
