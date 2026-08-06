"""Tests for the security_scan.py orchestrator. External HTTP and scanners
are mocked; see tests/fixtures/security_scan/ for end-to-end integration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.security_scan import run
from scripts.scanners.base import ScannerReport


@pytest.fixture
def sample_catalog(tmp_path: Path) -> Path:
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """marketplace:
  name: heretek
plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: upstash/context7
        sha: "0000000000000000000000000000000000000000"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    return p


@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_emits_no_report_when_upstream_matches_pinned(
    mock_scan: MagicMock, mock_sha: MagicMock, sample_catalog: Path, tmp_path: Path
) -> None:
    """All items fresh → zero reports, no issues opened."""
    mock_sha.return_value = ("0" * 40, "tag")
    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        dry_run=True,
    )
    assert summary.report_count == 0
    mock_scan.assert_not_called()


@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
@patch("scripts.security_scan.shutil.rmtree")
@patch("scripts.security_scan.subprocess.run")
def test_run_emits_report_when_upstream_changed(
    mock_subprocess: MagicMock,
    mock_rmtree: MagicMock,
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """Upstream SHA differs → shallow-clone + scan + report."""
    mock_sha.return_value = ("a" * 40, "tag")
    # mock git clone: creates a fake checkout dir
    def fake_clone(*args, **kwargs):
        target = Path(kwargs.get("cwd", "/")) / "context7"
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text("# fake")
        return MagicMock(returncode=0, stderr="", stdout="")
    mock_subprocess.side_effect = fake_clone
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        dry_run=True,
    )
    assert summary.report_count == 1
    report_file = next(tmp_path.glob("*.json"))
    report = json.loads(report_file.read_text())
    assert report["severity"] == "clean"


@patch("scripts.security_scan.draft_issue_and_pr")
@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_errors_when_latest_sha_is_zero_fallback(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    mock_draft: MagicMock,
    tmp_path: Path,
) -> None:
    """Orchestrator guards scripts/issue_drafter.py's JSON-shape-zero-SHA fallback
    (line 238). Upstream changes to a zero SHA → error_count++, no draft."""
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: upstash/context7
        sha: "abc123abc123abc123abc123abc123abc123abcd"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    mock_sha.return_value = ("0" * 40, "tag")  # upstream SHA "changed" to zero
    mock_clone.return_value = None
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    summary = run(
        catalog_path=p,
        output_dir=tmp_path,
        dry_run=False,
        gh_token="fake",
    )
    assert summary.report_count == 1
    assert summary.error_count == 1
    mock_draft.assert_not_called()


def test_run_skips_first_party_items(tmp_path: Path) -> None:
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: agents
    items:
      - id: code-reviewer
        upstream: Heretek-AI/heretek-claude-harness
        sha: "first-party-agent"
"""
    )
    summary = run(catalog_path=p, output_dir=tmp_path, dry_run=True)
    assert summary.report_count == 0


def test_scan_summary_dataclass_basic() -> None:
    from scripts.security_scan import ScanSummary
    s = ScanSummary(report_count=0, error_count=0)
    assert s.report_count == 0


@patch("scripts.security_scan.draft_issue_and_pr")
@patch("scripts.security_scan.bump_item_sha")
@patch("scripts.security_scan.subprocess.run")
@patch("scripts.security_scan.scan_skill")
@patch("scripts.security_scan._get_latest_release_sha")
def test_run_commits_catalog_bump_before_drafting_pr(
    mock_sha: MagicMock,
    mock_scan: MagicMock,
    mock_subprocess: MagicMock,
    mock_bump: MagicMock,
    mock_draft: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """C1: when upstream changes, bump_item_sha + git commit/push must
    happen BEFORE draft_issue_and_pr so the daily cron opens PRs with
    the catalog.yaml edit already in their diff."""
    mock_sha.return_value = ("a" * 40, "v1.0.0")

    call_order: list[str] = []

    def bump_side(*args, **kwargs):
        call_order.append("bump_item_sha")

    def subprocess_side(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and cmd:
            label = cmd[1] if len(cmd) > 1 else cmd[0]
            call_order.append(f"git:{label}")
        # Make git clone create the scratch dir so dispatch_scanner gets a path.
        if isinstance(cmd, list) and len(cmd) >= 3 and cmd[1] == "clone":
            cwd = kwargs.get("cwd", "/")
            Path(cwd).mkdir(parents=True, exist_ok=True)
            (Path(cwd) / "SKILL.md").write_text("# fake")
        return MagicMock(returncode=0, stderr="", stdout="")

    def draft_side(*args, **kwargs):
        call_order.append("draft_issue_and_pr")
        return ("http://issue", "http://pr")

    mock_bump.side_effect = bump_side
    mock_subprocess.side_effect = subprocess_side
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    mock_draft.side_effect = draft_side

    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        gh_token="fake-token",
        repo_root=tmp_path,
    )

    assert summary.report_count == 1
    # bump_item_sha must be called before draft_issue_and_pr.
    assert "bump_item_sha" in call_order, call_order
    assert "draft_issue_and_pr" in call_order, call_order
    bump_idx = call_order.index("bump_item_sha")
    draft_idx = call_order.index("draft_issue_and_pr")
    assert bump_idx < draft_idx, f"bump must precede draft: {call_order}"
    # git commit must happen before draft_issue_and_pr.
    commit_idx = next(
        (i for i, c in enumerate(call_order) if c == "git:commit"), -1
    )
    assert commit_idx >= 0, f"expected git commit, got: {call_order}"
    assert commit_idx < draft_idx, f"git commit must precede draft: {call_order}"
    # git push must happen before draft_issue_and_pr.
    push_idx = next(
        (i for i, c in enumerate(call_order) if c == "git:push"), -1
    )
    assert push_idx >= 0, f"expected git push, got: {call_order}"
    assert push_idx < draft_idx, f"git push must precede draft: {call_order}"
