"""Finding tools: add_finding, link_finding_to_evidence."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.store.sqlite import (
    Evidence,
    Finding,
    FindingSeverity,
    FindingSource,
)
from android_re_mcp_triage.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register finding tools."""

    @mcp.tool(
        name="add_finding",
        description=(
            "Add a single finding to a triage. The caller (an "
            "agent running a static / native / dynamic tool) "
            "converts the tool's output into one or more findings "
            "and adds them here. The orchestrator correlates them "
            "later."
        ),
    )
    def add_finding(
        triage_id: Annotated[str, Field(description="Triage id")],
        rule_id: Annotated[
            str, Field(description="Rule that fired (e.g. 'MASVS-CODE-1', 'aws-access-key-id')")
        ],
        message: Annotated[str, Field(description="Human-readable message")],
        severity: Annotated[
            str,
            Field(description="critical | high | medium | low | info"),
        ] = "info",
        source: Annotated[
            str,
            Field(description="static | native | dynamic | network | manual | correlation"),
        ] = "static",
        masvs_control: Annotated[
            str | None,
            Field(description="MASVS control id, if applicable"),
        ] = None,
        artifact_path: Annotated[
            str | None,
            Field(description="File/URL/identifier of the source artifact"),
        ] = None,
        start_line: Annotated[int | None, Field(ge=0)] = None,
        start_column: Annotated[int | None, Field(ge=0)] = None,
        properties: Annotated[
            dict[str, Any] | None,
            Field(description="Optional structured properties (e.g. {fingerprint_sha256: '...'})"),
        ] = None,
    ) -> dict[str, Any]:
        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        try:
            sev = FindingSeverity(severity)
        except ValueError:
            return {"error": {"code": "invalid_severity", "message": severity}}
        try:
            src = FindingSource(source)
        except ValueError:
            return {"error": {"code": "invalid_source", "message": source}}
        finding = Finding(
            finding_id="",
            triage_id=triage_id,
            rule_id=rule_id,
            severity=sev,
            source=src,
            message=message,
            masvs_control=masvs_control,
            artifact_path=artifact_path,
            start_line=start_line,
            start_column=start_column,
            properties=properties or {},
        )
        saved = store.add_finding(finding)
        return {"finding_id": saved.finding_id}

    @mcp.tool(
        name="link_finding_to_evidence",
        description=(
            "Attach a piece of evidence to a finding. Use this to "
            "back a static finding with a runtime observation, or a "
            "rule-based finding with a file/line citation."
        ),
    )
    def link_finding_to_evidence(
        triage_id: Annotated[str, Field(description="Triage id")],
        finding_id: Annotated[str, Field(description="Finding id from add_finding")],
        kind: Annotated[
            str, Field(description="file | url | logcat | rpc_result | string | screenshot")
        ],
        value: Annotated[
            str, Field(description="The evidence content (path, URL, log line, etc.)")
        ],
        annotation: Annotated[
            str | None,
            Field(description="Optional human-readable note explaining the evidence"),
        ] = None,
    ) -> dict[str, Any]:
        store = get_store()
        # Verify the finding exists
        finding = store.get_finding(finding_id)
        if finding is None or finding.triage_id != triage_id:
            return {"error": {"code": "finding_not_found", "message": finding_id}}
        ev = Evidence(
            evidence_id="",
            triage_id=triage_id,
            finding_id=finding_id,
            kind=kind,
            value=value,
            annotation=annotation,
        )
        saved = store.add_evidence(ev)
        return {"evidence_id": saved.evidence_id}

    @mcp.tool(
        name="list_findings",
        description=("List all findings on a triage, optionally filtered by severity or source."),
    )
    def list_findings(
        triage_id: Annotated[str, Field(description="Triage id")],
        severity: Annotated[
            str | None,
            Field(description="critical | high | medium | low | info"),
        ] = None,
        source: Annotated[
            str | None,
            Field(description="static | native | dynamic | network | manual | correlation"),
        ] = None,
    ) -> dict[str, Any]:
        store = get_store()
        try:
            sev = FindingSeverity(severity) if severity else None
        except ValueError:
            return {"error": {"code": "invalid_severity", "message": severity}}
        try:
            src = FindingSource(source) if source else None
        except ValueError:
            return {"error": {"code": "invalid_source", "message": source}}
        findings = store.list_findings(triage_id, severity=sev, source=src)
        return {
            "triage_id": triage_id,
            "count": len(findings),
            "findings": [f.to_dict() for f in findings],
        }
