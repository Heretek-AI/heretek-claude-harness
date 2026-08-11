"""Top-level ralph loop. Selects the next issue, runs the pipeline,
waits the gate, merges, advances the ledger. Resumable: on each entry,
reads ledger first and picks up where the last tick left off.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .branch import BranchManager
from .gate import GatePoller
from .ledger import IssueRef, Ledger
from .merge import Merger
from .subagents import SubagentRunner


@dataclass
class Summary:
    merged: int = 0
    skipped: int = 0
    failed: int = 0
    issue_numbers: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.issue_numbers is None:
            self.issue_numbers = []


class IssueLoop:
    def __init__(
        self,
        *,
        ledger: Ledger,
        branch: BranchManager,
        subagents: SubagentRunner,
        gate: GatePoller,
        merger: Merger,
        github_token: str,
        repo: str,
        prompts_dir: Path,
        candidates_provider: Callable[[], list[IssueRef]],
        pr_opener: Callable[[IssueRef, str], tuple[int, str]],
        squash_merge: Callable[..., str],
    ) -> None:
        # TODO(follow-up): I1 — GatePoller pr_number is masked until production fetcher is wired.
        self.ledger = ledger
        self.branch = branch
        self.subagents = subagents
        self.gate = gate
        self.merger = merger
        self.github_token = github_token
        self.repo = repo
        self.prompts_dir = prompts_dir
        self.candidates_provider = candidates_provider
        self.pr_opener = pr_opener
        self.squash_merge = squash_merge

    def _process(self, issue: IssueRef) -> None:
        self.ledger.mark_attempt(issue.number)

        # 1. create branch
        branch_name = self.branch.create(issue.number, issue.title)

        # 2. run subagent pipeline
        result = self.subagents.run_pipeline(issue)
        if result.blocked_reason:
            self.ledger.mark_skipped(issue.number, result.blocked_reason)
            return

        verdict = result.verdict
        if not verdict.get("approved"):
            # Check per-issue skip BEFORE global halt so that mark_skipped
            # (which resets the reject counter) fires first when applicable.
            if self.ledger._entries[str(issue.number)]["attempts"] >= 3:
                self.ledger.mark_skipped(issue.number, "verifier rejected 3x")
                return
            rejects = self.ledger.record_verifier_reject()
            if rejects >= 5:
                raise SystemExit(f"verifier_rejects_in_a_row={rejects} >= 5 — halting loop")
            # Re-enter from planner is handled by the ralph prompt; here we
            # just record the failure and skip to next issue.
            self.ledger.mark_failed(issue.number, "verifier rejected")
            return

        # 3. open PR
        pr_number, pr_url = self.pr_opener(issue, branch_name)

        # 4. wait for gate
        gate_verdict = self.gate.wait()
        if not gate_verdict.ok:
            self.ledger.mark_failed(issue.number, f"gate: {gate_verdict}")
            return

        # 5. diff-sanity + merge
        if not self.merger.diff_is_scoped(branch_name, issue.files):
            self.ledger.mark_failed(issue.number, "diff-sanity failed")
            return
        self.squash_merge(branch=branch_name, pr_number=pr_number, issue_number=issue.number)
        self.ledger.mark_merged(issue.number, pr_url)
        self.ledger.reset_verifier_rejects()

    def run_once(self) -> bool:
        issue = self.ledger.select_next(self.candidates_provider())
        if issue is None:
            return False
        self._process(issue)
        return True

    def run_until_empty(self) -> Summary:
        s = Summary()
        while self.run_once():
            # update summary
            entry = self.ledger._entries[str(self._last_processed_number())]
            if entry["status"] == "merged":
                s.merged += 1
            elif entry["status"] == "skipped":
                s.skipped += 1
            else:
                s.failed += 1
            s.issue_numbers.append(int(next(reversed(self.ledger._entries))))
        return s

    def _last_processed_number(self) -> int:
        # Used only by run_until_empty summary. Cheap: scan keys.
        # TODO(follow-up): I2 — private _entries access from driver; fragile.
        # Consider a public accessor on Ledger instead.
        return max(
            (int(k) for k in self.ledger._entries if k != "__root__"),
            default=0,
        )
