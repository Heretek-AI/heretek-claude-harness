"""Report tools: finalize_triage, get_triage_history."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.store.paths import triage_workdir
from android_re_core.store.sqlite import TriageStatus
from android_re_mcp_triage.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register report tools."""

    @mcp.tool(
        name="finalize_triage",
        description=(
            "Produce the final MASVS-aligned report. Aggregates "
            "all findings on the triage, runs cross-source "
            "correlation, and writes a markdown / JSON / SARIF "
            "report. The report lands at the per-triage workdir "
            "(``Output/<apk>-<sha>/<triage_id>/``) by default; "
            "override with ``output_path``. Returns the report path."
        ),
    )
    def finalize_triage(
        triage_id: Annotated[str, Field(description="Triage id")],
        format: Annotated[
            str,
            Field(description="Output format: 'markdown' (default), 'html', 'json', 'sarif'"),
        ] = "markdown",
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write the report to. If omitted, "
                    "writes to the per-triage workdir "
                    "(``Output/<apk>-<sha>/<triage_id>/triage-<id>.{ext>``). "
                    "The format's extension is appended if not already present."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        findings = store.list_findings(triage_id)
        by_sev = Counter(f.severity.value for f in findings)
        by_src = Counter(f.source.value for f in findings)
        by_control: dict[str, list[Any]] = {}
        for f in findings:
            if f.masvs_control:
                by_control.setdefault(f.masvs_control, []).append(f)

        ext = "json" if format == "json" else ("sarif" if format == "sarif" else "md")
        if output_path:
            out_path = Path(output_path).expanduser()
            # Append the extension if the user didn't include it
            if out_path.suffix != f".{ext}":
                out_path = out_path.with_suffix(f".{ext}")
        else:
            # Honor the output_dir stored on the triage record by start_triage.
            stored_dir = (triage.summary or {}).get("output_dir")
            if stored_dir:
                out_path = Path(stored_dir).expanduser() / f"triage-{triage_id}.{ext}"
            else:
                workdir = triage_workdir(triage_id=triage.triage_id, apk_path=triage.apk_path)
                out_path = workdir / f"triage-{triage_id}.{ext}"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            payload = {
                "triage": triage.to_dict(),
                "findings": [f.to_dict() for f in findings],
                "by_severity": dict(by_sev),
                "by_source": dict(by_src),
                "by_control": {k: [f.to_dict() for f in v] for k, v in by_control.items()},
            }
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        elif format == "sarif":
            payload = _build_sarif(triage, findings)
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            out_path.write_text(
                _render_markdown(triage, findings, by_sev, by_src, by_control),
                encoding="utf-8",
            )
        store.update_triage(
            triage_id,
            status=TriageStatus.COMPLETED,
            report_path=str(out_path),
            summary={
                **triage.summary,
                "finding_count": len(findings),
                "by_severity": dict(by_sev),
                "by_source": dict(by_src),
                "completed_at": datetime.now(tz=UTC).isoformat(),
            },
        )
        return {
            "triage_id": triage_id,
            "report_path": str(out_path),
            "format": format,
            "finding_count": len(findings),
        }

    @mcp.tool(
        name="get_triage_history",
        description="List all triages in the local SQLite store.",
    )
    def get_triage_history(
        limit: Annotated[int, Field(ge=1, le=500)] = 20,
    ) -> dict[str, Any]:
        triages = get_store().list_triages(limit=limit)
        return {
            "count": len(triages),
            "triages": [t.to_dict() for t in triages],
        }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _render_markdown(triage, findings, by_sev: Counter, by_src: Counter, by_control: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Triage Report — {triage.apk_path}")
    lines.append("")
    lines.append(f"- **Triage id**: `{triage.triage_id}`")
    lines.append(f"- **APK SHA-256**: `{triage.apksha256}`")
    lines.append(f"- **Status**: {triage.status.value}")
    lines.append(f"- **Goals**: {', '.join(triage.goals) or '(none)'}")
    lines.append(f"- **Created**: {datetime.fromtimestamp(triage.created_at, tz=UTC).isoformat()}")
    lines.append(f"- **Updated**: {datetime.fromtimestamp(triage.updated_at, tz=UTC).isoformat()}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total findings**: {len(findings)}")
    lines.append("- **By severity**: " + ", ".join(f"{k}={v}" for k, v in sorted(by_sev.items())))
    lines.append("- **By source**: " + ", ".join(f"{k}={v}" for k, v in sorted(by_src.items())))
    lines.append(f"- **Controls touched**: {len(by_control)}")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if not findings:
        lines.append("_(No findings recorded.)")
    else:
        for f in findings:
            lines.append(f"### [{f.severity.value.upper()}] {f.rule_id} — {f.message[:80]}")
            lines.append(f"- **id**: `{f.finding_id}`")
            lines.append(f"- **source**: {f.source.value}")
            if f.masvs_control:
                lines.append(f"- **MASVS**: {f.masvs_control}")
            if f.artifact_path:
                lines.append(
                    f"- **artifact**: `{f.artifact_path}`"
                    + (f":{f.start_line}" if f.start_line else "")
                )
            if f.properties:
                lines.append(f"- **properties**: `{json.dumps(f.properties)[:200]}`")
            lines.append("")
    lines.append("## MASVS Coverage")
    lines.append("")
    if by_control:
        for ctrl in sorted(by_control):
            lines.append(f"- **{ctrl}** — {len(by_control[ctrl])} finding(s)")
    else:
        lines.append("_(No MASVS-mapped findings yet.)")
    lines.append("")
    return "\n".join(lines)


def _build_sarif(triage, findings) -> dict[str, Any]:
    """Minimal SARIF 2.1.0 emission for a triage."""
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "android-re-triage",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/Heretek-AI/Android-RE",
                    }
                },
                "results": [
                    {
                        "ruleId": f.rule_id,
                        "level": _severity_to_sarif(f.severity.value),
                        "message": {"text": f.message},
                        "properties": {
                            "triage_id": triage.triage_id,
                            "finding_id": f.finding_id,
                            "masvs_control": f.masvs_control,
                            "source": f.source.value,
                            "severity": f.severity.value,
                            "properties": f.properties,
                        },
                    }
                    for f in findings
                ],
            }
        ],
    }


def _severity_to_sarif(sev: str) -> str:
    return {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
        "info": "note",
    }.get(sev, "note")
