"""Tests for scripts/audit/harness_self.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import harness_self, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


# -- emit-prompts ----------------------------------------------------------


def test_emit_prompts_writes_five_files(tmp_path: Path, repo_root: Path) -> None:
    """emit-prompts creates exactly one .txt per cluster letter A-E."""
    out_dir = tmp_path / "prompts"
    rc = harness_self.main(
        [
            "emit-prompts",
            "--repo-root",
            str(repo_root),
            "--commit-sha",
            "abcd1234",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert rc == 0
    letters = sorted(f.stem for f in out_dir.iterdir())
    assert letters == ["A", "B", "C", "D", "E"]
    for f in out_dir.iterdir():
        assert f.suffix == ".txt"


def test_emit_prompts_substitutes_placeholders(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Rendered prompt contains the literal repo_root and commit_sha."""
    out_dir = tmp_path / "prompts"
    harness_self.main(
        [
            "emit-prompts",
            "--repo-root",
            str(repo_root),
            "--commit-sha",
            "deadbeef",
            "--out-dir",
            str(out_dir),
        ]
    )
    content = (out_dir / "A.txt").read_text()
    assert str(repo_root) in content
    assert "deadbeef" in content


# -- synthesize ------------------------------------------------------------


def test_synthesize_writes_report_and_json(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """synthesize delegates to audit.synthesis and produces report + JSON."""
    # Put one minimal finding in cluster A
    cluster_dir = tmp_path / "clusters"
    cluster_dir.mkdir()
    (cluster_dir / "A.json").write_text(
        json.dumps(
            [
                {
                    "finding_id": "A-001",
                    "cluster": "Readability & quality bar",
                    "principle": "Small, focused functions",
                    "severity": "high",
                    "adversarial_posture": "violated",
                    "evidence": {
                        "code_refs": ["scripts/x.py:1-10"],
                        "file": "scripts/x.py",
                        "line_range": [1, 10],
                        "metric": "x",
                    },
                    "failure_scenario": "x",
                    "recommended_action": "refactor",
                    "rationale": "x",
                    "principle_reference": "x",
                    "drift_signals": [],
                }
            ]
        )
        + "\n"
    )
    out_dir = tmp_path / "synth-out"
    rc = harness_self.main(
        [
            "synthesize",
            "--cluster-results",
            str(cluster_dir),
            "--output-dir",
            str(out_dir),
            "--commit-sha",
            "cafe0000",
        ]
    )
    assert rc == 0
    # Should produce a report .md and a findings .json
    md_files = list(out_dir.glob("*.md"))
    json_files = list(out_dir.glob("*.json"))
    assert md_files, "no .md report written"
    assert json_files, "no .json findings written"
    content = json_files[0].read_text()
    assert "A-001" in content


# -- build-issues ----------------------------------------------------------


def test_build_issues_writes_payload_file(tmp_path: Path) -> None:
    """build-issues reads findings JSON and writes IssuePayload list."""
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps(
            [
                {
                    "finding_id": "A-001",
                    "cluster": "Readability & quality bar",
                    "principle": "Small, focused functions",
                    "severity": "critical",
                    "adversarial_posture": "violated",
                    "evidence": {
                        "code_refs": ["scripts/x.py:1-10"],
                        "file": "scripts/x.py",
                        "line_range": [1, 10],
                        "metric": "x",
                    },
                    "failure_scenario": "x",
                    "recommended_action": "refactor",
                    "rationale": "x",
                    "principle_reference": "x",
                    "drift_signals": [],
                }
            ]
        )
        + "\n"
    )
    out_path = tmp_path / "issues-to-create.json"
    rc = harness_self.main(
        [
            "build-issues",
            "--findings-json",
            str(findings_path),
            "--output",
            str(out_path),
        ]
    )
    assert rc == 0
    payload = json.loads(out_path.read_text())
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert "title" in payload[0]
    assert "body" in payload[0]
    assert "labels" in payload[0]


# -- argparse rejection ----------------------------------------------------


def test_unknown_subcommand_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown subcommand should exit with a non-zero status (argparse rejects)."""
    monkeypatch.setattr(sys, "argv", ["harness_self.py", "bogus-cmd"])
    with pytest.raises(SystemExit) as exc_info:
        harness_self.main()
    # argparse with required=True subparsers calls sys.exit(2) for unknown subcommand
    assert exc_info.value.code != 0
