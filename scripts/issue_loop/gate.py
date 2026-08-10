"""Merge gate: wait for CI + Copilot + SonarCloud + code-reviewer to agree.

All four signals must be green/approved/passed before the loop proceeds
to merge. Polled on a short interval until all signals are terminal or
the timeout fires.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Status = Literal[
    "green",
    "red",
    "pending",
    "approved",
    "changes_requested",
    "passed",
    "failed",
]


@dataclass
class GateVerdict:
    ci: Status = "pending"
    copilot: Status = "pending"
    sonar: Status = "pending"
    code_reviewer: Status = "pending"

    @property
    def ok(self) -> bool:
        return (
            self.ci == "green"
            and self.copilot == "approved"
            and self.sonar == "passed"
            and self.code_reviewer == "approved"
        )


def _real_fetcher() -> GateVerdict:
    # Wired in driver.py. Tests inject a fetcher via the constructor.
    raise NotImplementedError(
        "GatePoller requires fetcher= in tests; driver.py wires real fetcher."
    )


class GatePoller:
    def __init__(
        self,
        github_token: str,
        repo: str,
        pr_number: int,
        fetcher: Callable[[], GateVerdict] = _real_fetcher,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.github_token = github_token
        self.repo = repo
        self.pr_number = pr_number
        self.fetcher = fetcher
        self.sleep = sleep
        self.clock = clock

    def wait(self, timeout_s: int = 600) -> GateVerdict:
        deadline = self.clock() + timeout_s
        while self.clock() < deadline:
            v = self.fetcher()
            if v.ok or any(
                [
                    v.ci == "red",
                    v.copilot == "changes_requested",
                    v.sonar == "failed",
                    v.code_reviewer == "changes_requested",
                ]
            ):
                return v
            self.sleep(2)
        return self.fetcher()