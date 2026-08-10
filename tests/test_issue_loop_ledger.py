# tests/test_issue_loop_ledger.py
import json
from pathlib import Path

import pytest
from scripts.issue_loop.ledger import IssueRef, Ledger


@pytest.fixture
def tmp_ledger(tmp_path: Path) -> Path:
    return tmp_path / "ledger.json"


def test_ledger_creates_empty_file(tmp_ledger: Path) -> None:
    Ledger(tmp_ledger)
    assert tmp_ledger.exists()
    assert json.loads(tmp_ledger.read_text()) == {}


def test_select_next_returns_lowest_open(tmp_ledger: Path) -> None:
    Ledger(tmp_ledger)  # empty
    candidates = [
        IssueRef(number=160, title="x", files=[]),
        IssueRef(number=158, title="y", files=[]),
        IssueRef(number=159, title="z", files=[]),
    ]
    assert Ledger(tmp_ledger).select_next(candidates).number == 158


def test_select_next_skips_already_merged(tmp_ledger: Path) -> None:
    ledger = Ledger(tmp_ledger)
    ledger.mark_merged(158, "https://github.com/foo/bar/pull/1")
    candidates = [
        IssueRef(number=158, title="x", files=[]),
        IssueRef(number=159, title="y", files=[]),
    ]
    assert ledger.select_next(candidates).number == 159


def test_select_next_skips_three_time_failure(tmp_ledger: Path) -> None:
    ledger = Ledger(tmp_ledger)
    ledger.mark_attempt(158)
    ledger.mark_attempt(158)
    ledger.mark_attempt(158)
    candidates = [IssueRef(number=158, title="x", files=[])]
    assert ledger.select_next(candidates) is None


def test_mark_attempt_increments(tmp_ledger: Path) -> None:
    ledger = Ledger(tmp_ledger)
    ledger.mark_attempt(158)
    ledger.mark_attempt(158)
    assert ledger._entries["158"]["attempts"] == 2


def test_mark_merged_sets_terminal_status(tmp_ledger: Path) -> None:
    ledger = Ledger(tmp_ledger)
    ledger.mark_merged(158, "https://example/pr/1")
    assert ledger._entries["158"]["status"] == "merged"
    assert ledger._entries["158"]["pr_url"] == "https://example/pr/1"
    assert ledger._entries["158"]["finished_at"] is not None


def test_verifier_rejects_counter(tmp_ledger: Path) -> None:
    ledger = Ledger(tmp_ledger)
    assert ledger.verifier_rejects_in_a_row() == 0
    assert ledger.record_verifier_reject() == 1
    assert ledger.record_verifier_reject() == 2
    ledger.reset_verifier_rejects()
    assert ledger.verifier_rejects_in_a_row() == 0


def test_mark_skipped_resets_counter(tmp_ledger: Path) -> None:
    ledger = Ledger(tmp_ledger)
    ledger.record_verifier_reject()
    ledger.record_verifier_reject()
    ledger.mark_skipped(158, "rejected thrice")
    assert ledger.verifier_rejects_in_a_row() == 0
    assert ledger._entries["158"]["status"] == "skipped"


def test_mark_investigated_sets_status_and_findings(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_investigated(123, "/tmp/findings.json")
    entry = ledger._entries["123"]
    assert entry["status"] == "investigated"
    assert entry["findings_path"] == "/tmp/findings.json"
    assert entry["finished_at"] is not None


def test_mark_investigated_is_terminal(tmp_path: Path) -> None:
    from scripts.issue_loop.ledger import TERMINAL

    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_investigated(456, "x")
    assert ledger._entries["456"]["status"] in TERMINAL


def test_validate_path_rejects_dotdot_traversal(tmp_ledger: Path) -> None:
    """Path-traversal escape: '..' component must be rejected."""
    with pytest.raises(ValueError, match="contains '..' component"):
        Ledger(Path(".omc/state/issue-loop/../../../etc/passwd"))
    with pytest.raises(ValueError, match="contains '..' component"):
        Ledger(Path("foo/../bar/ledger.json"))
    with pytest.raises(ValueError, match="contains '..' component"):
        Ledger(Path("../ledger.json"))


def test_validate_path_allows_normal_paths(tmp_ledger: Path) -> None:
    """Non-traversal paths work normally (existing behavior preserved)."""
    Ledger(tmp_ledger)
    Ledger(Path(".omc/state/issue-loop/ledger.json"))
    Ledger(Path("/tmp/some/ledger.json"))
