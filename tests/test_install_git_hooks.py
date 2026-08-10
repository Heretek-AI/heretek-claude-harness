"""Tests for plugins/hooks/scripts/install_git_hooks.sh."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "plugins" / "hooks" / "scripts" / "install_git_hooks.sh"


def _pre_commit_cli_works() -> bool:
    """True iff `python3 -m pre_commit --version` exits 0 (CLI is runnable).

    `import pre_commit` is not enough — the CLI requires additional deps
    (e.g. PyYAML) that the install script also requires.
    """
    return (
        subprocess.run(
            ["python3", "-m", "pre_commit", "--version"],
            capture_output=True,
        ).returncode
        == 0
    )


def test_install_sh_exists_and_executable() -> None:
    assert INSTALL_SH.is_file()
    import os
    import stat

    mode = os.stat(INSTALL_SH).st_mode
    assert mode & stat.S_IXUSR, "install_git_hooks.sh must be user-executable"


def test_install_sh_fails_outside_git_repo(tmp_path: Path) -> None:
    """In a non-git directory, install_git_hooks.sh should exit 1 with a clear error."""
    if not shutil.which("bash"):
        pytest.skip("bash not installed")
    result = subprocess.run(
        ["bash", str(INSTALL_SH)],
        cwd=tmp_path,
        env={**__import__("os").environ, "REPO_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not a git repository" in result.stderr.lower()


def test_install_sh_idempotent_in_real_repo() -> None:
    """Running twice in the real repo: first installs, second is idempotent."""
    if not shutil.which("bash"):
        pytest.skip("bash not installed")
    if not shutil.which("python3"):
        pytest.skip("python3 not installed")
    if not _pre_commit_cli_works():
        pytest.skip("pre-commit CLI not runnable (missing deps like pyyaml)")
    first = subprocess.run(["bash", str(INSTALL_SH)], capture_output=True, text=True)
    assert first.returncode == 0, f"first run failed: {first.stderr}"
    second = subprocess.run(["bash", str(INSTALL_SH)], capture_output=True, text=True)
    assert second.returncode == 0, f"second run failed: {second.stderr}"
    assert "already installed" in second.stderr.lower() or "OK" in second.stdout


def test_install_sh_skips_reinstall_when_already_present() -> None:
    """Second run must not re-run `pre-commit install` — hook file mtime unchanged (#97)."""
    if not shutil.which("bash"):
        pytest.skip("bash not installed")
    if not shutil.which("python3"):
        pytest.skip("python3 not installed")
    if not _pre_commit_cli_works():
        pytest.skip("pre-commit CLI not runnable (missing deps like pyyaml)")
    repo_root = Path(__file__).resolve().parents[1]
    # Resolve hooks path via `git rev-parse --git-common-dir` so the test
    # works in worktrees. In a worktree, `.git/` is a file pointing at the
    # worktree-specific git dir, but `pre-commit install` writes hooks to
    # the COMMON git dir (shared with the main checkout). Hardcoding
    # `<repo_root>/.git/hooks/pre-commit` only works in a non-worktree clone.
    git_common_dir = Path(
        subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
            text=True,
        ).strip()
    )
    if not git_common_dir.is_absolute():
        git_common_dir = repo_root / git_common_dir
    hook_path = git_common_dir / "hooks" / "pre-commit"
    # Ensure installed first.
    first = subprocess.run(["bash", str(INSTALL_SH)], capture_output=True, text=True)
    assert first.returncode == 0, f"first install failed: {first.stderr}"
    assert hook_path.is_file(), "hook file should exist after first install"
    mtime_before = hook_path.stat().st_mtime
    # Second run.
    second = subprocess.run(["bash", str(INSTALL_SH)], capture_output=True, text=True)
    assert second.returncode == 0, f"second run failed: {second.stderr}"
    mtime_after = hook_path.stat().st_mtime
    assert (
        mtime_before == mtime_after
    ), "second run should not modify the hook file (must short-circuit)"
