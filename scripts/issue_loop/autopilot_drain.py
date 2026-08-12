"""End-to-end autopilot drain script.

Exercises all 5 paths against fixture issues. Used as integration smoke test
for the autopilot issue-loop extension. Not for production use — production
drains are driven by the Claude orchestrator via the Agent tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = ROOT / ".omc" / "state" / "issue-loop" / "ledger.json"
CONFIG = ROOT / ".heretek" / "issue-loop-config.json"

FIXTURES = [
    {
        "number": 158,
        "title": "Security: yaml.load without Loader in scripts/catalog_updater.py:81",
        "body": "Found `yaml.load(...)` at `scripts/catalog_updater.py:81`. Fix: use yaml.safe_load.",
        "expected_path": "fix",
    },
    {
        "number": 176,
        "title": "docs(research): MVP-1 Codegen fan-out",
        "body": "Deep research on plugin design with audit scope.",
        "expected_path": "spec",
    },
    {
        "number": 200,
        "title": "Improve error message in CLI",
        "body": "When the user passes a bad flag, the error is unclear.",
        "expected_path": "investigate",
    },
    {
        "number": 89,
        "title": "v2: hooks hardening + security",
        "body": "Phase scope: graceful truncation, JSON parsing, checkpoint commits. Split into phases.",
        "expected_path": "break-down",
    },
    {
        "number": 99,
        "title": "duplicate of #50",
        "body": "Won't fix, by design. Duplicate of #50.",
        "expected_path": "skip",
    },
]


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", "-m", "scripts.issue_loop.cli", "--ledger-path", str(LEDGER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def classify_fixture(fix: dict) -> str:
    """Inject fixture body via a fake-gh runner is overkill for smoke; instead
    use the classifier directly and verify against expected_path."""
    from scripts.issue_loop.classifier import classify
    from scripts.issue_loop.ledger import IssueRef

    issue = IssueRef(number=fix["number"], title=fix["title"], files=[])
    actual = classify(issue, body=fix["body"])
    assert (
        actual == fix["expected_path"]
    ), f"{fix['number']}: expected {fix['expected_path']}, got {actual}"
    return actual


def main() -> int:
    print(f"drain: {len(FIXTURES)} fixtures")
    config = json.loads(CONFIG.read_text())
    assert config["paths_enabled"] == [
        "fix",
        "investigate",
        "spec",
        "break-down",
        "skip",
    ]
    assert config["periodic_summary_minutes"] == 30

    for fix in FIXTURES:
        path = classify_fixture(fix)
        run_cli("mark-attempt", str(fix["number"]))
        run_cli(
            "log-event",
            str(fix["number"]),
            "--kind",
            "info",
            "--message",
            f"classified as {path}",
        )

    statuses = json.loads(run_cli("status").stdout)
    print(f"status: {statuses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
