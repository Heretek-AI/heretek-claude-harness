"""Subagent pipeline runner.

Threads artifacts from one subagent to the next. The actual Agent SDK
dispatch is injected via `dispatch=` so unit tests can stub it. In
production (driver.py), `dispatch` is wired to the Agent tool.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .ledger import IssueRef

DispatchFn = Callable[[str, str, Path, IssueRef], str]


@dataclass
class PipelineResult:
    verdict: dict = field(default_factory=dict)
    blocked_reason: str | None = None
    log_files: list[Path] = field(default_factory=list)


def _default_dispatch(name: str, prompt: str, worktree: Path, issue: IssueRef) -> str:
    # Real dispatch is wired by driver.py using the Agent SDK.
    # This default exists only so the class is constructible in isolation.
    raise NotImplementedError(
        "SubagentRunner requires an explicit dispatch= in production. "
        "The driver wires this to the Agent tool."
    )


class SubagentRunner:
    def __init__(
        self,
        prompts_dir: Path,
        worktree: Path | None = None,
        dispatch: DispatchFn | None = None,
    ) -> None:
        self.prompts_dir = prompts_dir
        self.worktree = worktree or Path.cwd()
        self.dispatch = dispatch or _default_dispatch

    def _prompt(self, name: str) -> str:
        return (self.prompts_dir / f"{name}.md").read_text()

    def run_pipeline(self, issue: IssueRef) -> PipelineResult:
        result = PipelineResult()

        # 1. explore
        self.dispatch("explore", self._prompt("explore"), self.worktree, issue)

        # 2. planner
        planner_out = self.dispatch("planner", self._prompt("planner"), self.worktree, issue)
        if planner_out.startswith("BLOCKED"):
            result.blocked_reason = planner_out
            return result

        # 3. executor
        executor_out = self.dispatch("executor", self._prompt("executor"), self.worktree, issue)
        if executor_out.startswith("BLOCKED"):
            result.blocked_reason = executor_out
            return result

        # 4. test-engineer
        te_out = self.dispatch("test_engineer", self._prompt("test_engineer"), self.worktree, issue)
        if te_out.startswith("BLOCKED"):
            result.blocked_reason = te_out
            return result

        # 5. verifier
        verifier_out = self.dispatch("verifier", self._prompt("verifier"), self.worktree, issue)
        try:
            result.verdict = json.loads(verifier_out)
        except json.JSONDecodeError:
            result.blocked_reason = f"verifier returned non-JSON: {verifier_out[:200]}"
            return result

        return result
