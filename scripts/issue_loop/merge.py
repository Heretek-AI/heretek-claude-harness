"""Diff-sanity check + squash-merge for the issue loop.

diff_is_scoped() runs against a local repo (the worktree from Task 2).
squash_merge() hits the GitHub API; in tests it is stubbed.
"""

from __future__ import annotations

from pathlib import Path

from .branch import _run


def _real_github_merge(*args, **kwargs) -> str:
    # Wired in driver.py. Tests stub this.
    raise NotImplementedError("Merger.squash_merge requires a github_merge= " "callable in tests.")


class Merger:
    def __init__(
        self,
        github_token: str,
        repo: str,
        local_repo: Path | None = None,
        github_merge=_real_github_merge,
    ) -> None:
        self.github_token = github_token
        self.repo = repo
        self.local_repo = local_repo or Path.cwd()
        self.github_merge = github_merge

    def diff_is_scoped(self, branch: str, allowed_files: list[str]) -> bool:
        r = _run(["git", "diff", "--name-only", "main", branch], self.local_repo)
        if r.returncode != 0:
            return False
        changed = {Path(p).as_posix() for p in r.stdout.strip().splitlines() if p}
        allowed = {Path(p).as_posix() for p in allowed_files}
        return changed.issubset(allowed)

    def squash_merge(self, branch: str, pr_number: int, issue_number: int) -> str:
        return self.github_merge(
            token=self.github_token,
            repo=self.repo,
            pr_number=pr_number,
            commit_message=f"fix(#{issue_number}): squash-merge from {branch}",
        )
