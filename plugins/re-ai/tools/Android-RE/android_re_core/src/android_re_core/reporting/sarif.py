"""SARIF 2.1.0 emission.

SARIF (Static Analysis Results Interchange Format) is the OASIS standard
for static-analysis output. This module produces a minimal-but-valid
SARIF 2.1.0 document from a list of :class:`Finding` objects.

Reference: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "Finding",
    "Log",
    "Run",
    "Severity",
    "Tool",
    "build_log",
    "to_json",
]


class Severity(str, Enum):
    """SARIF severity levels. Maps to the ``level`` property."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"
    NONE = "none"


@dataclass(frozen=True)
class Finding:
    """A single static-analysis finding."""

    rule_id: str
    message: str
    severity: Severity = Severity.WARNING
    uri: str | None = None
    artifact_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    # SARIF properties bag (for MASVS control, CVSS, etc.)
    properties: dict[str, Any] = field(default_factory=dict)

    def to_sarif(self) -> dict[str, Any]:
        """Serialize to a SARIF ``result`` object."""
        result: dict[str, Any] = {
            "ruleId": self.rule_id,
            "level": self.severity.value,
            "message": {"text": self.message},
        }
        if self.properties:
            result["properties"] = dict(self.properties)
        if self.artifact_path is not None:
            location: dict[str, Any] = {
                "physicalLocation": {
                    "artifactLocation": {"uri": self.artifact_path},
                },
            }
            region: dict[str, Any] = {}
            if self.start_line is not None:
                region["startLine"] = self.start_line
            if self.start_column is not None:
                region["startColumn"] = self.start_column
            if self.end_line is not None:
                region["endLine"] = self.end_line
            if self.end_column is not None:
                region["endColumn"] = self.end_column
            if region:
                location["physicalLocation"]["region"] = region
            result["locations"] = [location]
        if self.uri is not None:
            result["target"] = {"uri": self.uri}
        return result


@dataclass(frozen=True)
class Tool:
    """A SARIF ``tool.driver`` block."""

    name: str
    version: str
    information_uri: str | None = None
    rules: tuple[dict[str, Any], ...] = ()

    def to_sarif(self) -> dict[str, Any]:
        driver: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
        }
        if self.information_uri:
            driver["informationUri"] = self.information_uri
        if self.rules:
            driver["rules"] = list(self.rules)
        return {"tool": {"driver": driver}}


@dataclass(frozen=True)
class Run:
    """A single SARIF ``run`` (one tool, one pass)."""

    tool: Tool
    findings: tuple[Finding, ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()

    def to_sarif(self) -> dict[str, Any]:
        out = self.tool.to_sarif()
        if self.findings:
            out["results"] = [f.to_sarif() for f in self.findings]
        if self.artifacts:
            out["artifacts"] = list(self.artifacts)
        return out


@dataclass(frozen=True)
class Log:
    """A SARIF ``sarifLog`` (the top-level object)."""

    runs: tuple[Run, ...]

    def to_sarif(self) -> dict[str, Any]:
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [r.to_sarif() for r in self.runs],
        }


def build_log(
    *,
    tool_name: str,
    tool_version: str,
    findings: list[Finding],
    rules: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    information_uri: str | None = None,
) -> Log:
    """Build a complete SARIF :class:`Log` from a list of findings.

    Convenience constructor that handles the boilerplate.
    """
    run = Run(
        tool=Tool(
            name=tool_name,
            version=tool_version,
            information_uri=information_uri,
            rules=tuple(rules or ()),
        ),
        findings=tuple(findings),
        artifacts=tuple(artifacts or ()),
    )
    return Log(runs=(run,))


def to_json(log: Log, *, indent: int | None = 2) -> str:
    """Serialize a :class:`Log` to a SARIF JSON string."""
    return json.dumps(log.to_sarif(), indent=indent, sort_keys=False)


# ---------------------------------------------------------------------------
# Convenience: rule-builder for the MASVS-mapped rules
# ---------------------------------------------------------------------------


def masvs_rule(
    masvs_id: str,
    *,
    short_description: str,
    full_description: str | None = None,
    help_uri: str | None = None,
    default_severity: Severity = Severity.WARNING,
) -> dict[str, Any]:
    """Build a SARIF ``reportingDescriptor`` for a MASVS control."""
    rule: dict[str, Any] = {
        "id": masvs_id,
        "name": masvs_id,
        "shortDescription": {"text": short_description},
        "defaultConfiguration": {"level": default_severity.value},
    }
    if full_description:
        rule["fullDescription"] = {"text": full_description}
    if help_uri:
        rule["helpUri"] = help_uri
    return rule


# Generate a fresh run-id. Used internally; not exported.
def _new_run_id() -> str:
    return str(uuid.uuid4())
