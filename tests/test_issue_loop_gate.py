"""Tests for the merge gate poller.

Covers GateVerdict.ok semantics and GatePoller.wait() timeout + happy path
with injectable fetcher / sleep / clock.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.issue_loop.gate import GatePoller, GateVerdict


@dataclass
class FakeGitHub:
    ci: str = "green"
    copilot: str = "approved"
    sonar: str = "passed"
    cr: str = "approved"

    @property
    def code_reviewer(self) -> str:
        return self.cr

    @property
    def ok(self) -> bool:
        return (
            self.ci == "green"
            and self.copilot == "approved"
            and self.sonar == "passed"
            and self.cr == "approved"
        )


def test_gate_verdict_ok_when_all_green() -> None:
    v = GateVerdict(ci="green", copilot="approved", sonar="passed", code_reviewer="approved")
    assert v.ok is True


def test_gate_verdict_not_ok_on_any_red() -> None:
    v = GateVerdict(ci="red", copilot="approved", sonar="passed", code_reviewer="approved")
    assert v.ok is False


def test_gate_poller_returns_verdict_on_first_pass() -> None:
    fake = FakeGitHub()
    poller = GatePoller(
        github_token="x",
        repo="o/r",
        pr_number=1,
        fetcher=lambda: fake,
        sleep=lambda s: None,
    )
    v = poller.wait(timeout_s=10)
    assert v.ok is True


def test_gate_poller_times_out_to_red() -> None:
    fake = FakeGitHub(ci="red")
    poller = GatePoller(
        github_token="x",
        repo="o/r",
        pr_number=1,
        fetcher=lambda: fake,
        sleep=lambda s: None,
    )
    v = poller.wait(timeout_s=0)
    assert v.ci == "red"
    assert v.ok is False