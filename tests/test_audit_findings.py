"""Tests for scripts/audit/findings.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import findings, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


def _sample_dict() -> dict:
    return {
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


def test_finding_from_dict_round_trips() -> None:
    d = _sample_dict()
    f = findings.Finding.from_dict(d)
    assert f.finding_id == "A-001"
    assert f.severity == "high"
    assert f.evidence.line_range == [1, 10]
    assert f.to_dict() == d


def test_load_findings_accepts_yaml(fixtures_dir: Path) -> None:
    p = fixtures_dir / "audit" / "valid_finding.yaml"
    loaded = findings.load_findings(p)
    assert len(loaded) == 1
    assert loaded[0].finding_id == "A-001"


def test_load_findings_rejects_invalid(fixtures_dir: Path) -> None:
    p = fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml"
    with pytest.raises(ValueError, match="invalid"):
        findings.load_findings(p)


def test_save_findings_writes_json(tmp_path: Path) -> None:
    f = findings.Finding.from_dict(_sample_dict())
    out = tmp_path / "out.json"
    findings.save_findings([f], out)
    assert out.is_file()
    data = json.loads(out.read_text())
    assert data[0]["finding_id"] == "A-001"


def test_severity_rank_orders_critical_first() -> None:
    f_crit = findings.Finding.from_dict({**_sample_dict(), "severity": "critical"})
    f_high = findings.Finding.from_dict({**_sample_dict(), "severity": "high"})
    f_info = findings.Finding.from_dict({**_sample_dict(), "severity": "info"})
    assert (
        findings.severity_rank(f_crit)
        < findings.severity_rank(f_high)
        < findings.severity_rank(f_info)
    )
