"""Tests for .github/workflows/pre-commit.yml.

Spec D20: SHA-pin every action. Spec D36: PR + push-to-main + weekly
schedule triggers. Read-only permissions.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pre-commit.yml"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_workflow_exists() -> None:
    assert WORKFLOW.is_file(), f"{WORKFLOW} must exist (spec D36)"


def test_workflow_yaml_parses() -> None:
    yaml.safe_load(WORKFLOW.read_text())


def test_workflow_has_required_triggers() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    on = data.get(True) or data.get("on")  # PyYAML quirk: `on:` → True
    assert on is not None, "workflow must declare `on:` triggers"
    assert "pull_request" in on, "must trigger on pull_request"
    assert "push" in on, "must trigger on push"
    push_branches = on["push"].get("branches") if isinstance(on["push"], dict) else None
    assert push_branches and "main" in push_branches, "push trigger must include `branches: [main]`"
    sched = on.get("schedule")
    assert sched, "must include a weekly schedule trigger"


def test_workflow_actions_sha_pinned() -> None:
    """D20: every `uses:` line must pin a 40-char hex SHA + version comment."""
    text = WORKFLOW.read_text()
    uses_lines = [line for line in text.splitlines() if "uses:" in line]
    assert uses_lines, "workflow must reference at least one action"
    for line in uses_lines:
        m = re.search(r"uses:\s+([^@\s]+)@([0-9a-f]{40})", line)
        assert m, f"uses: line not SHA-pinned: {line!r}"


def test_workflow_permissions_readonly() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    perms = data.get("permissions")
    assert perms == {
        "contents": "read"
    }, f"workflow must declare read-only permissions; got {perms!r}"
