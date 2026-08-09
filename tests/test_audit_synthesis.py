"""Tests for scripts/audit/synthesis.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import synthesis, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


def _finding(
    severity: str = "high",
    fid: str = "A-001",
    file: str = "scripts/x.py",
    lines=(1, 10),
) -> dict:
    return {
        "finding_id": fid,
        "cluster": "Readability & quality bar",
        "principle": "Small, focused functions",
        "severity": severity,
        "adversarial_posture": "violated",
        "evidence": {
            "code_refs": [f"{file}:{lines[0]}-{lines[1]}"],
            "file": file,
            "line_range": list(lines),
            "metric": "x",
        },
        "failure_scenario": "x",
        "recommended_action": "refactor",
        "rationale": "x",
        "principle_reference": "x",
        "drift_signals": [],
    }


def test_synthesize_dedupes_across_clusters(tmp_path: Path, schemas_dir: Path) -> None:
    """Two findings with identical (file, line_range) collapse to one."""
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    (cluster_dir / "A.yaml").write_text(
        "[" + json.dumps(_finding(fid="A-001", severity="high")) + "]"
    )
    (cluster_dir / "B.yaml").write_text(
        "["
        + json.dumps(
            {
                **_finding(fid="B-001", severity="medium"),
                "cluster": "Design & architecture",
            }
        )
        + "]"
    )

    result = synthesis.synthesize(
        cluster_results_dir=cluster_dir,
        output_dir=tmp_path / "out",
        commit_sha="deadbeef",
    )
    assert result.duplicate_count == 1
    assert len(result.findings) == 1
    # Higher-severity finding wins.
    assert result.findings[0].severity == "high"


def test_synthesize_writes_report_and_json(tmp_path: Path, schemas_dir: Path) -> None:
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    (cluster_dir / "A.yaml").write_text("[" + json.dumps(_finding()) + "]")
    out_dir = tmp_path / "out"
    result = synthesis.synthesize(cluster_dir, out_dir, commit_sha="deadbeef")
    assert result.report_path.is_file()
    assert result.json_path.is_file()
    data = json.loads(result.json_path.read_text())
    assert len(data) == 1
    md = result.report_path.read_text()
    assert "harness-self-audit" in md or "Harness Self-Audit" in md
    assert "deadbeef" in md


def test_synthesize_skips_sonar_excluded(tmp_path: Path, schemas_dir: Path) -> None:
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    (cluster_dir / "A.yaml").write_text(
        "[" + json.dumps(_finding(file="scripts/excl.py")) + "]"
    )
    result = synthesis.synthesize(
        cluster_dir,
        tmp_path / "out",
        commit_sha="deadbeef",
        sonar_exclusions={"scripts/excl.py"},
    )
    assert result.findings == []


def test_synthesize_records_coverage_gap_for_missing_cluster(
    tmp_path: Path, schemas_dir: Path
) -> None:
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    # Only cluster A present; B, C, D, E missing.
    (cluster_dir / "A.yaml").write_text("[" + json.dumps(_finding()) + "]")
    result = synthesis.synthesize(cluster_dir, tmp_path / "out", commit_sha="deadbeef")
    gap_clusters = " ".join(result.coverage_gaps)
    for letter in ("B", "C", "D", "E"):
        assert letter in gap_clusters
