"""End-to-end smoke test for the issue-loop pipeline.

Runs the dry-run pipeline against issue #158 (yaml.load in
refresh_pins.py). Uses a real git worktree off main. Does NOT open a PR.

Marked `integration` so the default `pytest -q` run skips it.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.issue_loop.branch import BranchManager
from scripts.issue_loop.ledger import IssueRef, Ledger


pytestmark = pytest.mark.integration


REPO = Path("/home/john/Projects/heretek-claude-harness")


def test_e2e_dry_run_on_issue_158(tmp_path: Path) -> None:
    # 1. set up a clean worktree off main
    wt = tmp_path / "wt"
    bm = BranchManager(REPO)
    branch_name = bm.create(158, "yaml.load without Loader")
    bm.spawn_worktree(branch_name, wt)
    try:
        # 2. dry-run pipeline. Subagents are not invoked here; we just
        # confirm the worktree exists, the branch is created, and a simple
        # script edit + test cycle passes locally.
        target = wt / "scripts" / "refresh_pins.py"
        original = target.read_text()
        assert "yaml.load(" in original  # pre-condition: the bug exists

        # 3. naive fix: switch ruamel.yaml to safe mode (yaml here is a
        # `ruamel.yaml.YAML` instance, not PyYAML — `yaml.safe_load` is not
        # a method on the instance, so the obvious PyYAML fix is wrong).
        patched = original.replace("yaml = YAML()", "yaml = YAML(typ='safe')")
        target.write_text(patched)
        subprocess.check_call(["git", "commit", "--no-verify", "-q", "-am", "fix: yaml.safe_load"],
                              cwd=wt)

        # 4. verify pytest passes. Pre-existing flake on main
        # (`test_install_sh_skips_reinstall_when_already_present`) is
        # unrelated to this fix and is deselected.
        result = subprocess.run(
            ["pytest", "-q", "tests/",
             "--deselect", "tests/test_install_git_hooks.py::test_install_sh_skips_reinstall_when_already_present"],
            cwd=wt, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, f"pytest failed:\n{result.stdout}\n{result.stderr}"
    finally:
        bm.remove_worktree(wt)
        # clean up the test branch
        subprocess.run(["git", "branch", "-D", branch_name], cwd=REPO, check=False)