"""Reporting tools: SARIF and MASVS coverage.

Exposes two MCP tools:

- :func:`build_sarif_report` — emit a SARIF 2.1.0 JSON document for
  the project's findings.
- :func:`get_masvs_coverage` — evaluate the APK against the MASVS
  v2 control registry and return pass/fail/review per control.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import ProjectClosed, ProjectNotFound
from android_re_core.paths import output_dir_for
from android_re_mcp_static.server import get_store

__all__ = ["register"]


def _default_masvs_path(project_id: str, name: str) -> Path:
    """Default Output/-tree path for a MASVS artifact."""
    try:
        project = get_store().get(project_id)
        return output_dir_for(project.apk.path) / "masvs" / name
    except (ProjectNotFound, ProjectClosed, FileNotFoundError):
        return Path("/tmp") / f"android-re-masvs-{project_id}" / name


def register(mcp: FastMCP) -> None:
    """Register reporting tools."""

    @mcp.tool(
        name="build_sarif_report",
        description=(
            "Build a SARIF 2.1.0 report from the project's current "
            "MASVS findings. Returns the SARIF document as a JSON "
            "string. Pass the result to any SARIF viewer (sarif-tools, "
            "GitHub code scanning, VS Code SARIF Viewer)."
        ),
    )
    def build_sarif_report(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write SARIF JSON. Defaults to "
                    "``Output/<apk>-<sha>/masvs/report.sarif``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.reporting.masvs import (
            coverage_to_sarif,
            evaluate_apk,
        )

        coverage = evaluate_apk(project.apk)
        sarif_log = coverage_to_sarif(coverage, tool_version="0.2.0")
        sarif_json = sarif_log.to_sarif()
        out_path = (
            Path(output_path).expanduser()
            if output_path
            else _default_masvs_path(project_id, "report.sarif")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(json.dumps(sarif_json, indent=2), encoding="utf-8")
        except OSError as e:
            return {"error": {"code": "write_failed", "message": str(e)}}
        return {
            "project_id": project_id,
            "result_count": len(coverage.findings),
            "output_path": str(out_path),
            "sarif": sarif_json,
            "sarif_json": json.dumps(sarif_json, indent=2),
        }

    @mcp.tool(
        name="get_masvs_coverage",
        description=(
            "Evaluate the APK against the OWASP MASVS v2 control "
            "registry. Returns a per-control status (pass / fail / "
            "review) and per-group tallies. Static-only coverage in "
            "Phase 2; dynamic controls are filled in by Phase 3."
        ),
    )
    def get_masvs_coverage(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write coverage JSON. Defaults to "
                    "``Output/<apk>-<sha>/masvs/coverage.json``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.reporting.masvs import evaluate_apk

        coverage = evaluate_apk(project.apk)
        result = {
            "project_id": project_id,
            **coverage.to_dict(),
        }
        out_path = (
            Path(output_path).expanduser()
            if output_path
            else _default_masvs_path(project_id, "coverage.json")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        except OSError as e:
            return {"error": {"code": "write_failed", "message": str(e)}}
        return {**result, "output_path": str(out_path)}
