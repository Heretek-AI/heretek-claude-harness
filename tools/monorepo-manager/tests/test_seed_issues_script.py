"""Sandbox tests for scripts/seed-issues.sh — no live GitHub API calls."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
SEED_ISSUES = ROOT / "scripts" / "seed-issues.sh"


def _run(
    *args: str, env: dict | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SEED_ISSUES), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        cwd=cwd or ROOT,
    )


def test_seed_issues_sh_exists_and_is_executable():
    assert SEED_ISSUES.is_file()
    import stat

    mode = SEED_ISSUES.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/seed-issues.sh must be executable"


def test_seed_issues_sh_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0
    # gh auth is not satisfied in CI → we only assert --help works on its own
    # (the script should print usage and exit 0 before any gh call).


def test_seed_issues_sh_dry_run_exits_nonzero_without_seed():
    """With no --seed-file and no network, --dry-run should fail fast."""
    result = _run("--repo", "Heretek-AI/llama-builds", "--dry-run")
    # If the script tries gh auth before seed fetch, we'd see a different code.
    # The contract: missing seed is a precondition failure.
    assert result.returncode != 0
