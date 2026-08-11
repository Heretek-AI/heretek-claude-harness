"""Branch + worktree operations for the issue loop.

All commands are shell-out via subprocess.run with check=False so callers
can inspect exit codes (e.g. rebase conflict returns False, not raise).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug_from_title(title: str, max_len: int = 50) -> str:
    s = title.lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:max_len]


def _clean_env() -> dict[str, str]:
    """Strip GIT_* env vars so subprocess.run targets the cwd repo, not parent.

    Pre-commit framework sets GIT_DIR (and sometimes GIT_INDEX_FILE /
    GIT_WORK_TREE) in the hook subprocess. Without this filter, `git worktree
    add` would attach to the main repo instead of the temp one, and any
    fixture that runs `git init` would re-init the parent repo instead of
    its own tmp_path.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=_clean_env(),
    )


class BranchManager:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def create(self, issue_number: int, title: str) -> str:
        slug = slug_from_title(title)
        branch = f"auto/{issue_number}-{slug}"
        r = _run(["git", "branch", branch], self.repo_root)
        if r.returncode != 0:
            raise RuntimeError(f"git branch failed: {r.stderr}")
        return branch

    def spawn_worktree(self, branch: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        r = _run(["git", "worktree", "add", str(target), branch], self.repo_root)
        if r.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {r.stderr}")
        return target

    def rebase_onto_main(self, worktree: Path) -> bool:
        r = _run(["git", "rebase", "main"], worktree)
        if r.returncode != 0:
            # abort the in-progress rebase so the worktree is usable
            _run(["git", "rebase", "--abort"], worktree)
            return False
        return True

    def remove_worktree(self, worktree: Path) -> None:
        _run(["git", "worktree", "remove", "--force", str(worktree)], self.repo_root)
