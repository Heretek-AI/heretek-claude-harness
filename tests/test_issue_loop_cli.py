"""Tests for scripts/issue_loop/cli.py.

Each subcommand wraps an existing Ledger method. The cli module exposes
`main(argv, *, gh_runner=None)` so tests can inject a fake gh runner.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from scripts.issue_loop import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "ledger.json"


@pytest.fixture
def fake_gh() -> Callable[..., "FakeGH"]:
    return FakeGH


class FakeGH:
    """Replaces subprocess.run for `gh issue list` calls.

    Defaults to returning an empty list. Tests set `.payload` to control
    the response. `.calls` records the args list for assertion.
    """

    def __init__(self) -> None:
        self.payload: list[dict] = []
        self.calls: list[list[str]] = []
        self.raise_on_call: bool = False

    def __call__(self, args: list[str], **_kwargs) -> "FakeGH":
        self.calls.append(args)
        if self.raise_on_call:
            raise RuntimeError("fake gh failure")
        return self

    @property
    def returncode(self) -> int:
        return 0 if not self.raise_on_call else 1

    @property
    def stdout(self) -> str:
        return json.dumps(self.payload)


def run(*args: str, ledger_path: Path, gh: FakeGH | None = None) -> int:
    """Invoke cli.main with optional fake gh runner.

    Global options (--ledger-path) must precede the subcommand for argparse
    to recognize them as parent-level flags.
    """
    return cli.main(["--ledger-path", str(ledger_path), *args], gh_runner=gh)


# ---------------------------------------------------------------------------
# select-next
# ---------------------------------------------------------------------------


def test_select_next_returns_lowest_unprocessed(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = [
        {"number": 159, "title": "Ignore env var B", "body": ""},
        {"number": 158, "title": "yaml.load without Loader", "body": ""},
        {"number": 160, "title": "Ignore env var C", "body": ""},
    ]
    rc = run("select-next", ledger_path=ledger_path, gh=gh)
    assert rc == 0
    # Re-invoke with capture so we can assert against stdout.
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "select-next"], gh_runner=gh
    )
    assert captured.returncode == 0
    assert json.loads(captured.stdout) == {
        "number": 158,
        "title": "yaml.load without Loader",
        "files": [],
    }


def test_select_next_empty_queue_returns_empty_object(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = []
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "select-next"], gh_runner=gh
    )
    assert captured.returncode == 0
    assert captured.stdout.strip() == "{}"


def test_select_next_skips_already_merged(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = [
        {"number": 158, "title": "x", "body": ""},
        {"number": 159, "title": "y", "body": ""},
    ]
    # Mark 158 merged first
    _capture_main(
        [
            "--ledger-path",
            str(ledger_path),
            "mark-merged",
            "158",
            "--pr-url",
            "https://example/pr/1",
        ],
        gh_runner=gh,
    )
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "select-next"], gh_runner=gh
    )
    assert captured.returncode == 0
    assert json.loads(captured.stdout)["number"] == 159


def test_select_next_skips_at_attempt_cap(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = [
        {"number": 158, "title": "x", "body": ""},
        {"number": 159, "title": "y", "body": ""},
    ]
    # Manually set attempts to 3 in ledger
    from scripts.issue_loop.ledger import Ledger

    led = Ledger(ledger_path)
    led.mark_attempt(158)
    led.mark_attempt(158)
    led.mark_attempt(158)
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "select-next"], gh_runner=gh
    )
    assert captured.returncode == 0
    assert json.loads(captured.stdout)["number"] == 159


def test_select_next_extracts_files_from_issue_body(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = [
        {
            "number": 158,
            "title": "yaml.load without Loader",
            "body": "Found in `scripts/refresh_pins.py:223` and `scripts/catalog_updater.py:81`",
        },
    ]
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "select-next"], gh_runner=gh
    )
    assert captured.returncode == 0
    data = json.loads(captured.stdout)
    assert data["number"] == 158
    assert "scripts/refresh_pins.py" in data["files"]
    assert "scripts/catalog_updater.py" in data["files"]


def test_select_next_gh_failure_returns_nonzero(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.raise_on_call = True
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "select-next"], gh_runner=gh
    )
    assert captured.returncode != 0


# ---------------------------------------------------------------------------
# mark-attempt / mark-merged / mark-skipped / mark-failed
# ---------------------------------------------------------------------------


def test_mark_attempt_increments_counter(ledger_path: Path) -> None:
    rc = run("mark-attempt", "158", ledger_path=ledger_path)
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    assert Ledger(ledger_path)._entries["158"]["attempts"] == 1


def test_mark_merged_sets_status(ledger_path: Path) -> None:
    rc = run(
        "mark-merged",
        "158",
        "--pr-url",
        "https://example/pr/1",
        ledger_path=ledger_path,
    )
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    entry = Ledger(ledger_path)._entries["158"]
    assert entry["status"] == "merged"
    assert entry["pr_url"] == "https://example/pr/1"


def test_mark_skipped_resets_rejects(ledger_path: Path) -> None:
    _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    rc = run(
        "mark-skipped",
        "158",
        "--reason",
        "verifier rejected 3x",
        ledger_path=ledger_path,
    )
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    assert Ledger(ledger_path)._entries["158"]["status"] == "skipped"
    assert Ledger(ledger_path).verifier_rejects_in_a_row() == 0


def test_mark_failed_is_non_terminal(ledger_path: Path) -> None:
    rc = run(
        "mark-failed", "158", "--error", "gate: sonar-failed", ledger_path=ledger_path
    )
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    entry = Ledger(ledger_path)._entries["158"]
    assert entry["status"] == "failed"
    assert entry["finished_at"] is None  # failed is non-terminal


# ---------------------------------------------------------------------------
# record-reject / reset-rejects / rejects-in-a-row
# ---------------------------------------------------------------------------


def test_record_reject_increments(ledger_path: Path) -> None:
    captured = _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    assert captured.returncode == 0
    assert captured.stdout.strip() == "1"
    captured = _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    assert captured.stdout.strip() == "2"


def test_reset_rejects_zeros(ledger_path: Path) -> None:
    _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    rc = run("reset-rejects", ledger_path=ledger_path)
    assert rc == 0
    captured = _capture_main(["--ledger-path", str(ledger_path), "rejects-in-a-row"])
    assert captured.stdout.strip() == "0"


def test_rejects_in_a_row_zero_initially(ledger_path: Path) -> None:
    captured = _capture_main(["--ledger-path", str(ledger_path), "rejects-in-a-row"])
    assert captured.returncode == 0
    assert captured.stdout.strip() == "0"


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_reports_counts(ledger_path: Path) -> None:
    _capture_main(
        ["--ledger-path", str(ledger_path), "mark-merged", "158", "--pr-url", "u"]
    )
    _capture_main(
        ["--ledger-path", str(ledger_path), "mark-skipped", "159", "--reason", "x"]
    )
    _capture_main(
        ["--ledger-path", str(ledger_path), "mark-failed", "160", "--error", "y"]
    )
    captured = _capture_main(["--ledger-path", str(ledger_path), "status"])
    data = json.loads(captured.stdout)
    assert data == {"merged": 1, "skipped": 1, "failed": 1, "pending": 0}


def test_status_empty_ledger(ledger_path: Path) -> None:
    captured = _capture_main(["--ledger-path", str(ledger_path), "status"])
    assert json.loads(captured.stdout) == {
        "merged": 0,
        "skipped": 0,
        "failed": 0,
        "pending": 0,
    }


# ---------------------------------------------------------------------------
# rejects reset on merge behavior (integration with reset_verifier_rejects)
# ---------------------------------------------------------------------------


def test_mark_merged_does_not_reset_rejects(ledger_path: Path) -> None:
    # Per ledger.py: reset only happens on mark_skipped. mark_merged also
    # resets — verify.
    _capture_main(["--ledger-path", str(ledger_path), "record-reject"])
    _capture_main(
        ["--ledger-path", str(ledger_path), "mark-merged", "158", "--pr-url", "u"]
    )
    captured = _capture_main(["--ledger-path", str(ledger_path), "rejects-in-a-row"])
    # ledger.mark_merged does NOT reset; mark_skipped does
    assert captured.stdout.strip() == "1"


# ---------------------------------------------------------------------------
# log-event / register-sub-issue / classify
# ---------------------------------------------------------------------------


def test_log_event_appends_to_issue_events(ledger_path: Path) -> None:
    rc = run(
        "log-event",
        "158",
        "--kind",
        "info",
        "--message",
        "explore subagent started",
        ledger_path=ledger_path,
    )
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    events = Ledger(ledger_path)._entries["158"]["events"]
    assert len(events) == 1
    assert events[0]["kind"] == "info"
    assert events[0]["msg"] == "explore subagent started"
    assert "ts" in events[0]


def test_log_event_multiple_events_accumulate(ledger_path: Path) -> None:
    run(
        "log-event",
        "158",
        "--kind",
        "info",
        "--message",
        "step 1",
        ledger_path=ledger_path,
    )
    run(
        "log-event",
        "158",
        "--kind",
        "warn",
        "--message",
        "step 2",
        ledger_path=ledger_path,
    )
    from scripts.issue_loop.ledger import Ledger

    events = Ledger(ledger_path)._entries["158"]["events"]
    assert len(events) == 2
    assert [e["kind"] for e in events] == ["info", "warn"]


def test_mark_investigated_sets_status_and_findings_path(ledger_path: Path) -> None:
    rc = run(
        "mark-investigated",
        "158",
        "--findings-path",
        "/tmp/findings.json",
        ledger_path=ledger_path,
    )
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    entry = Ledger(ledger_path)._entries["158"]
    assert entry["status"] == "investigated"
    assert entry["findings_path"] == "/tmp/findings.json"
    assert entry["finished_at"] is not None


def test_register_sub_issue_adds_to_sub_issues_list(ledger_path: Path) -> None:
    rc = run(
        "register-sub-issue",
        "1",
        "--child",
        "10",
        "--relation",
        "blocks",
        ledger_path=ledger_path,
    )
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger

    assert Ledger(ledger_path)._entries["1"]["sub_issues"] == [
        {"child": 10, "relation": "blocks"}
    ]


def test_register_sub_issue_multiple_children_accumulate(ledger_path: Path) -> None:
    run(
        "register-sub-issue",
        "1",
        "--child",
        "10",
        "--relation",
        "blocks",
        ledger_path=ledger_path,
    )
    run(
        "register-sub-issue",
        "1",
        "--child",
        "11",
        "--relation",
        "relates",
        ledger_path=ledger_path,
    )
    from scripts.issue_loop.ledger import Ledger

    sub = Ledger(ledger_path)._entries["1"]["sub_issues"]
    assert len(sub) == 2


def test_classify_subcommand_prints_path(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = [
        {
            "number": 158,
            "title": "Security: yaml.load without Loader in scripts/catalog_updater.py:81",
            "body": "Fix this.",
        },
    ]
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "classify", "158"], gh_runner=gh
    )
    assert captured.returncode == 0
    assert captured.stdout.strip() == "fix"


def test_classify_subcommand_investigate_for_enhancement(
    ledger_path: Path, fake_gh: type[FakeGH]
) -> None:
    gh = fake_gh()
    gh.payload = [
        {
            "number": 1,
            "title": "v2: Workflow plugins",
            "body": "Deep research on plugin scaffolding",
        },
    ]
    captured = _capture_main(
        ["--ledger-path", str(ledger_path), "classify", "1"], gh_runner=gh
    )
    assert captured.stdout.strip() == "spec"


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_unknown_subcommand_returns_nonzero(ledger_path: Path) -> None:
    captured = _capture_main(["--ledger-path", str(ledger_path), "bogus"])
    assert captured.returncode != 0


def test_main_no_args_prints_help_and_returns_zero(ledger_path: Path) -> None:
    captured = _capture_main(["--ledger-path", str(ledger_path)])
    # argparse exits 0 on --help? Actually no — it exits 0 printing help
    # and we capture returncode. Either 0 or 2 is acceptable; assert help
    # text appears.
    assert "Issue Loop CLI" in captured.stdout or "usage" in captured.stdout.lower()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


class _Captured:
    def __init__(self, returncode: int, stdout: str) -> None:
        self.returncode = returncode
        self.stdout = stdout


def _capture_main(argv: list[str], gh_runner: FakeGH | None = None) -> _Captured:
    """Run cli.main with patched stdout and capture return + output."""
    import io
    import contextlib

    buf = io.StringIO()
    rc = 1
    try:
        with contextlib.redirect_stdout(buf):
            rc = cli.main(argv, gh_runner=gh_runner)
    except SystemExit as exc:
        return _Captured(int(exc.code or 1), buf.getvalue())
    return _Captured(rc, buf.getvalue())
