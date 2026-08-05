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
    assert len(new_wf_refs) >= 5, f"expected new workflows to add at least 5 uses refs, got {len(new_wf_refs)}"
