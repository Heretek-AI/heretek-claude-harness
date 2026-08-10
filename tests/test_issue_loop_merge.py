import subprocess
from pathlib import Path

import pytest
from scripts.issue_loop.merge import Merger


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    (repo / "a.py").write_text("a\n")
    subprocess.check_call(["git", "add", "a.py"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "-m", "init"], cwd=repo)
    return repo


def test_diff_is_scoped_true_when_only_allowed_files(git_repo: Path) -> None:
    subprocess.check_call(["git", "checkout", "-q", "-b", "auto/x"], cwd=git_repo)
    (git_repo / "a.py").write_text("a-changed\n")
    subprocess.check_call(["git", "commit", "-q", "-am", "x"], cwd=git_repo)
    m = Merger("tok", "o/r", local_repo=git_repo)
    assert m.diff_is_scoped("auto/x", ["a.py"]) is True


def test_diff_is_scoped_false_when_other_file(git_repo: Path) -> None:
    subprocess.check_call(["git", "checkout", "-q", "-b", "auto/x"], cwd=git_repo)
    (git_repo / "b.py").write_text("b\n")
    subprocess.check_call(["git", "add", "b.py"], cwd=git_repo)
    subprocess.check_call(["git", "commit", "-q", "-m", "x"], cwd=git_repo)
    m = Merger("tok", "o/r", local_repo=git_repo)
    assert m.diff_is_scoped("auto/x", ["a.py"]) is False