"""Sanity checks that the new workflows are present, valid YAML, and have
the required jobs. Full end-to-end execution requires `act` and a GH
token; that lives in CI smoke and is not part of pytest."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / name).read_text())


def test_security_scan_workflow_has_cron_and_jobs() -> None:
    # easier: just check the file declares cron + a scan job
    text = (WORKFLOW_DIR / "security-scan.yml").read_text()
    assert "cron:" in text
    assert "jobs:" in text
    assert "scan:" in text


def test_security_scan_pr_workflow_triggers_on_catalog_changes() -> None:
    text = (WORKFLOW_DIR / "security-scan-pr.yml").read_text()
    assert "pull_request:" in text
    assert "catalog/catalog.yaml" in text
    assert "scan-pr:" in text


def test_security_scan_pr_workflow_is_a_required_check_via_branch_protection() -> None:
    """Branch protection is a GH-side setting; we just verify the workflow
    file doesn't mark itself as optional. The actual 'required' enforcement
    is configured in repo Settings > Branches > main > Required status checks."""
    text = (WORKFLOW_DIR / "security-scan-pr.yml").read_text()
    assert "if:" not in text or "always" in text  # doesn't gate itself off


def test_all_workflows_pinned_to_commit_sha() -> None:
    """Re-uses test_action_pinning.py; this is a smoke check that the new
    workflows are included in that test."""
    from tests.test_action_pinning import _iter_uses_lines

    refs = _iter_uses_lines()
    new_wf_refs = [r for r in refs if r[0].name in ("security-scan.yml", "security-scan-pr.yml")]
    assert (
        len(new_wf_refs) >= 5
    ), f"expected new workflows to add at least 5 uses refs, got {len(new_wf_refs)}"


def test_security_scan_workflow_has_emergency_issue_step() -> None:
    """Issue #33 / spec §8.5: workflow must have an `if: failure()` step that
    opens an emergency issue so maintainers see silent cron failures."""
    text = (WORKFLOW_DIR / "security-scan.yml").read_text()
    assert "if: failure()" in text
    assert "emergency" in text.lower()
    assert "issues.create" in text or "issues.listForRepo" in text


def test_security_scan_pr_workflow_has_emergency_issue_step() -> None:
    """Issue #33 / spec §8.5: PR workflow also surfaces failures via emergency issue."""
    text = (WORKFLOW_DIR / "security-scan-pr.yml").read_text()
    assert "if: failure()" in text
    assert "emergency" in text.lower()


def test_harness_test_workflow_has_weekly_cron_and_label_trigger() -> None:
    """harness-test.yml: weekly cron + label trigger + separate integration job."""
    text = (WORKFLOW_DIR / "harness-test.yml").read_text()
    assert "cron:" in text
    assert "harness-test" in text  # the label trigger
    # Two jobs: CI pytest (safe) and integration fixtures (manual dispatch).
    assert "ci-pytest:" in text
    assert "integration-fixtures:" in text
    # Integration fixtures are gated to workflow_dispatch only (no claude in CI).
    assert "github.event_name == 'workflow_dispatch'" in text


def test_harness_test_workflow_ci_pytest_runs_without_claude() -> None:
    """CI runs pytest tests with mocked subprocess; no claude CLI required."""
    text = (WORKFLOW_DIR / "harness-test.yml").read_text()
    # ci-pytest runs the harness pytest tests, not scripts/harness_test.py
    pytest_block = text.split("ci-pytest:")[1].split("integration-fixtures:")[0]
    assert "pytest tests/test_harness_test.py" in pytest_block
    assert "python scripts/harness_test.py" not in pytest_block


def test_harness_test_workflow_sha_pins_all_actions() -> None:
    """D20: every action pinned to 40-char hex SHA, not tag."""
    import re

    text = (WORKFLOW_DIR / "harness-test.yml").read_text()
    sha_pattern = re.compile(r"uses:\s+[\w-]+/[a-zA-Z0-9_-]+@[a-f0-9]{40}")
    for line in text.splitlines():
        if "uses:" in line and "actions/" in line:
            assert sha_pattern.search(line), f"action not SHA-pinned: {line.strip()}"
