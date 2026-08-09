"""Finding dataclass + load/save helpers for the harness self-audit.

One Finding = one card per the spec's per-finding schema. Cluster
agents emit YAML or JSON lists; this module loads them, validates each
card via `audit.validate`, and exposes a dataclass for synthesis / issues
to consume without re-parsing the schema each time.

JSON is the canonical output format (so downstream tools and the GitHub
issue builder don't have to handle two parsers).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from audit import validate

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True)
class Evidence:
    code_refs: list[str]
    file: str
    line_range: list[int]
    metric: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Evidence":
        return cls(
            code_refs=list(d["code_refs"]),
            file=d["file"],
            line_range=list(d["line_range"]),
            metric=d["metric"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code_refs": list(self.code_refs),
            "file": self.file,
            "line_range": list(self.line_range),
            "metric": self.metric,
        }


@dataclass(frozen=True)
class Finding:
    finding_id: str
    cluster: str
    principle: str
    severity: str
    adversarial_posture: str
    evidence: Evidence
    failure_scenario: str
    recommended_action: str
    rationale: str
    principle_reference: str
    drift_signals: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Finding":
        return cls(
            finding_id=d["finding_id"],
            cluster=d["cluster"],
            principle=d["principle"],
            severity=d["severity"],
            adversarial_posture=d["adversarial_posture"],
            evidence=Evidence.from_dict(d["evidence"]),
            failure_scenario=d["failure_scenario"],
            recommended_action=d["recommended_action"],
            rationale=d["rationale"],
            principle_reference=d["principle_reference"],
            drift_signals=list(d.get("drift_signals", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "cluster": self.cluster,
            "principle": self.principle,
            "severity": self.severity,
            "adversarial_posture": self.adversarial_posture,
            "evidence": self.evidence.to_dict(),
            "failure_scenario": self.failure_scenario,
            "recommended_action": self.recommended_action,
            "rationale": self.rationale,
            "principle_reference": self.principle_reference,
            "drift_signals": list(self.drift_signals),
        }


def _load_instance(path: Path) -> Any:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        return YAML(typ="safe").load(text)
    return json.loads(text)


def load_findings(path: Path) -> list[Finding]:
    """Read a YAML or JSON file containing one finding or a list; validate each card."""
    instance = _load_instance(path)
    findings_in = instance if isinstance(instance, list) else [instance]
    invalid_indexes: list[str] = []
    out: list[Finding] = []
    for i, d in enumerate(findings_in):
        errors = validate.validate_finding(d)
        if errors:
            invalid_indexes.append(f"#{i}: " + "; ".join(errors))
            continue
        out.append(Finding.from_dict(d))
    if invalid_indexes:
        raise ValueError(
            f"{path}: {len(invalid_indexes)} invalid finding(s): "
            + " | ".join(invalid_indexes)
        )
    return out


def save_findings(items: list[Finding], path: Path) -> None:
    """Write findings as a JSON array (canonical output format)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([f.to_dict() for f in items], indent=2, sort_keys=True) + "\n"
    )


def severity_rank(finding: Finding) -> int:
    """Lower rank = more severe. critical=0, high=1, medium=2, low=3, info=4."""
    return SEVERITY_ORDER.index(finding.severity)
