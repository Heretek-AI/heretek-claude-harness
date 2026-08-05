"""Tests for the SkillSpector wrapper. The SkillSpector CLI is mocked;
see tests/fixtures/security_scan/ for real-fixture integration tests."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.scanners.skills import SkillsScanner, scan_skill


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    (tmp_path / "SKILL.md").write_text("# my skill\nSome instructions here.\n")
    return tmp_path


def _skillspector_output_clean(findings_count: int = 0) -> dict:
    return {
        "findings": [
            {
                "path": "SKILL.md",
                "line": i + 1,
                "message": f"finding {i}",
                "rule_id": f"R{i}",
            }
            for i in range(findings_count)
        ],
        "scanner_version": "1.2.3",
    }


def test_scan_skill_clean(skill_dir: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(_skillspector_output_clean(0)), stderr=""
        )
        report = scan_skill(skill_dir, item_id="my-skill")
    assert report.severity == "clean"
    assert report.scanner == "skillspector"
    assert report.findings == []


def test_scan_skill_block_when_subprocess_fails(skill_dir: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="skillspector crashed"
        )
        report = scan_skill(skill_dir, item_id="my-skill")
    assert report.severity == "block"
    assert any("scanner-unavailable" in (f.rule_id or "") for f in report.findings)


def test_scan_skill_block_when_subprocess_times_out(skill_dir: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=60)
        report = scan_skill(skill_dir, item_id="my-skill")
    assert report.severity == "block"
    assert any("timeout" in (f.rule_id or "") for f in report.findings)


def test_scan_skill_block_when_binary_missing(skill_dir: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("npx not found")
        report = scan_skill(skill_dir, item_id="my-skill")
    assert report.severity == "block"
    assert any("scanner-unavailable" in (f.rule_id or "") for f in report.findings)


def test_scan_skill_warn_when_subprocess_returns_warn_severity(skill_dir: Path) -> None:
    output = _skillspector_output_clean(1)
    output["findings"][0]["severity"] = "warn"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(output), stderr=""
        )
        report = scan_skill(skill_dir, item_id="my-skill")
    assert report.severity == "warn"
    assert len(report.findings) == 1


def test_scan_skill_block_when_subprocess_returns_block_severity(skill_dir: Path) -> None:
    output = _skillspector_output_clean(1)
    output["findings"][0]["severity"] = "block"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(output), stderr=""
        )
        report = scan_skill(skill_dir, item_id="my-skill")
    assert report.severity == "block"


def test_skills_scanner_class_implements_protocol(skill_dir: Path) -> None:
    """SkillsScanner exposes the same .scan() interface as the protocol."""
    scanner = SkillsScanner()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(_skillspector_output_clean(0)), stderr=""
        )
        report = scanner.scan(skill_dir, item_id="my-skill")
    assert report.severity == "clean"


@pytest.mark.integration
class TestRealSkillSpector:
    """Runs the REAL SkillSpector CLI against planted fixtures.
    Skipped by default; run with `pytest -m integration`."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "tests/fixtures/security_scan"

    def test_good_skill_is_clean(self, fixtures_dir: Path) -> None:
        report = scan_skill(fixtures_dir / "good_skill", item_id="good-skill")
        # SkillSpector may produce info-level findings on perfectly clean
        # content; we assert NO block or warn severity.
        assert report.severity in ("clean", "info")

    def test_prompt_inject_skill_is_blocked(self, fixtures_dir: Path) -> None:
        report = scan_skill(fixtures_dir / "bad_skill_prompt_inject", item_id="bad-skill-inject")
        assert report.severity in ("block", "warn"), (
            f"SkillSpector should have flagged prompt injection but got {report.severity}"
        )

    def test_exfil_skill_is_blocked(self, fixtures_dir: Path) -> None:
        report = scan_skill(fixtures_dir / "bad_skill_exfil", item_id="bad-skill-exfil")
        assert report.severity in ("block", "warn"), (
            f"SkillSpector should have flagged curl|bash but got {report.severity}"
        )
