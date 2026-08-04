"""Tests for plugins/hooks/scripts/install_git_hooks.sh."""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "plugins" / "hooks" / "scripts" / "install_git_hooks.sh"


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
    if subprocess.run(
        ["python3", "-c", "import pre_commit"], capture_output=True
    ).returncode != 0:
        pytest.skip("pre-commit not installed in test env")
    first = subprocess.run(
        ["bash", str(INSTALL_SH)], capture_output=True, text=True
    )
    assert first.returncode == 0, f"first run failed: {first.stderr}"
    second = subprocess.run(
        ["bash", str(INSTALL_SH)], capture_output=True, text=True
    )
    assert second.returncode == 0, f"second run failed: {second.stderr}"
    assert "already installed" in second.stderr.lower() or "OK" in second.stdout
