"""Tests for the security_scan.py orchestrator. External HTTP and scanners
are mocked; see tests/fixtures/security_scan/ for end-to-end integration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.security_scan import run
from scripts.scanners.base import Finding, ScannerReport


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