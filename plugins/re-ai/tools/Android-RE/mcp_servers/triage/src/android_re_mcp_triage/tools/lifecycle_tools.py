"""Triage lifecycle: start, get_plan, resume, cancel, status."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.store.sqlite import TriageStatus
from android_re_mcp_triage.server import get_store

__all__ = ["register"]


# Templates for the multi-step plan. Each step names the underlying
# MCP tool the user should call.
_PLAN_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "full": [
        {
            "step": "static.open_project",
            "tool": "mcp__android-re-static__open_project",
            "description": "Open the APK",
        },
        {
            "step": "static.triage",
            "tool": "mcp__android-re-static__read_manifest + list_components + get_permissions + find_classes + find_methods",
            "description": "Static triage",
        },
        {
            "step": "static.masvs",
            "tool": "mcp__android-re-static__get_masvs_coverage",
            "description": "MASVS coverage",
        },
        {
            "step": "native.list",
            "tool": "mcp__android-re-native__list_binaries + parse_binary",
            "description": "Native binary audit",
        },
        {
            "step": "static.sarif",
            "tool": "mcp__android-re-static__build_sarif_report",
            "description": "SARIF report",
        },
        {
            "step": "static.secrets",
            "tool": "mcp__android-re-static__scan_secrets",
            "description": "Secrets scan",
        },
        {
            "step": "dynamic.attach",
            "tool": "mcp__android-re-dynamic__frida_attach + frida_load_script",
            "description": "Dynamic instrumentation",
        },
        {
            "step": "dynamic.network",
            "tool": "mcp__android-re-dynamic__setup_mitm + take_screenshot",
            "description": "Network capture (optional)",
        },
        {
            "step": "triage.correlate",
            "tool": "mcp__android-re-triage__correlate_findings",
            "description": "Cross-source correlation",
        },
        {
            "step": "triage.finalize",
            "tool": "mcp__android-re-triage__finalize_triage",
            "description": "Produce MASVS report",
        },
    ],
    "masvs": [
        {"step": "static.open_project", "tool": "mcp__android-re-static__open_project"},
        {"step": "static.masvs", "tool": "mcp__android-re-static__get_masvs_coverage"},
        {"step": "static.sarif", "tool": "mcp__android-re-static__build_sarif_report"},
        {"step": "triage.finalize", "tool": "mcp__android-re-triage__finalize_triage"},
    ],
    "static_only": [
        {"step": "static.open_project", "tool": "mcp__android-re-static__open_project"},
        {
            "step": "static.triage",
            "tool": "mcp__android-re-static__read_manifest + list_components",
        },
        {"step": "static.masvs", "tool": "mcp__android-re-static__get_masvs_coverage"},
        {"step": "triage.finalize", "tool": "mcp__android-re-triage__finalize_triage"},
    ],
    "native_only": [
        {"step": "static.open_project", "tool": "mcp__android-re-static__open_project"},
        {"step": "native.list", "tool": "mcp__android-re-native__list_binaries + parse_binary"},
        {"step": "triage.finalize", "tool": "mcp__android-re-triage__finalize_triage"},
    ],
    "dynamic_only": [
        {
            "step": "dynamic.attach",
            "tool": "mcp__android-re-dynamic__frida_attach + frida_load_script",
        },
        {"step": "triage.finalize", "tool": "mcp__android-re-triage__finalize_triage"},
    ],
}


def register(mcp: FastMCP) -> None:
    """Register lifecycle tools."""

    @mcp.tool(
        name="start_triage",
        description=(
            "Open a new triage against an APK. Returns a triage_id "
            "and a multi-step plan. State is persisted to SQLite."
        ),
    )
    def start_triage(
        apk_path: Annotated[str, Field(description="Path to the .apk on disk")],
        apk_sha256: Annotated[
            str,
            Field(
                description="SHA-256 of the APK (use static.open_project or sha256sum to get this)"
            ),
        ],
        goals: Annotated[
            list[str],
            Field(
                description=(
                    "List of goals: 'full', 'masvs', 'static_only', 'dynamic_only', 'native_only'"
                )
            ),
        ] = ["masvs"],
        output_dir: Annotated[
            str | None,
            Field(
                description=(
                    "Override the per-triage workdir. Defaults to "
                    "``Output/<apk-basename>-<short-sha>/<triage_id>/`` "
                    "(see :func:`android_re_core.paths.output_dir_for`). "
                    "Stored on the triage record so subsequent "
                    "``finalize_triage`` calls land in the same directory."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        store = get_store()
        # Validate goals
        for g in goals:
            if g not in _PLAN_TEMPLATES:
                return {"error": {"code": "invalid_goal", "message": f"unknown goal: {g}"}}
        triage = store.open_triage(apk_path, apk_sha256, goals=goals)
        # Materialize the plan: union of all goal templates, deduped
        plan: list[dict[str, Any]] = []
        seen_steps: set[str] = set()
        for g in goals:
            for step in _PLAN_TEMPLATES.get(g, []):
                if step["step"] not in seen_steps:
                    plan.append(dict(step))
                    seen_steps.add(step["step"])
        # If an explicit output_dir was passed, store it on the record so
        # finalize_triage lands in the same place. The summary field is
        # free-form; we use a stable key ``output_dir``.
        summary_update: dict[str, Any] = {}
        if output_dir:
            summary_update["output_dir"] = output_dir
        store.update_triage(
            triage.triage_id,
            status=TriageStatus.RUNNING,
            plan=plan,
            pending_steps=[s["step"] for s in plan],
            summary=summary_update,
        )
        updated = store.get_triage(triage.triage_id)
        return {
            "triage_id": triage.triage_id,
            "apk_path": triage.apk_path,
            "apk_sha256": triage.apk_sha256,
            "goals": list(goals),
            "status": updated.status.value if updated else triage.status.value,
            "plan": updated.plan if updated else plan,
            "pending_steps": updated.pending_steps if updated else [s["step"] for s in plan],
            "output_dir": output_dir,
        }

    @mcp.tool(
        name="get_plan",
        description="Return the multi-step plan for a triage.",
    )
    def get_plan(
        triage_id: Annotated[str, Field(description="Triage id")],
    ) -> dict[str, Any]:
        triage = get_store().get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        return {
            "triage_id": triage.triage_id,
            "status": triage.status.value,
            "plan": triage.plan,
            "completed_steps": triage.completed_steps,
            "pending_steps": triage.pending_steps,
        }

    @mcp.tool(
        name="resume_triage",
        description=(
            "Resume a paused or cancelled triage. Sets status to "
            "running and returns the remaining pending steps."
        ),
    )
    def resume_triage(
        triage_id: Annotated[str, Field(description="Triage id")],
        from_step: Annotated[
            str | None,
            Field(description="Optional step name to resume from; defaults to first pending"),
        ] = None,
    ) -> dict[str, Any]:
        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        if triage.status not in (TriageStatus.PAUSED, TriageStatus.CANCELLED, TriageStatus.FAILED):
            return {"error": {"code": "not_resumable", "message": triage.status.value}}
        # If from_step, ensure all steps before it are marked complete.
        pending = list(triage.pending_steps)
        if from_step is not None:
            if from_step not in pending:
                return {"error": {"code": "step_not_pending", "message": from_step}}
            idx = pending.index(from_step)
            completed = list(triage.completed_steps) + pending[:idx]
            pending = pending[idx:]
            store.update_triage(
                triage_id,
                status=TriageStatus.RUNNING,
                completed_steps=completed,
                pending_steps=pending,
            )
        else:
            store.update_triage(triage_id, status=TriageStatus.RUNNING)
        updated = store.get_triage(triage_id)
        return {
            "triage_id": triage_id,
            "status": updated.status.value,
            "pending_steps": updated.pending_steps,
            "completed_steps": updated.completed_steps,
        }

    @mcp.tool(
        name="cancel_triage",
        description=(
            "Cancel a running triage. Findings added so far are "
            "preserved; the triage can be resumed later."
        ),
    )
    def cancel_triage(
        triage_id: Annotated[str, Field(description="Triage id")],
    ) -> dict[str, Any]:
        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        store.update_triage(triage_id, status=TriageStatus.CANCELLED)
        return {"ok": True, "triage_id": triage_id, "status": TriageStatus.CANCELLED.value}

    @mcp.tool(
        name="triage_status",
        description="Snapshot of a triage's progress, including all findings so far.",
    )
    def triage_status(
        triage_id: Annotated[str, Field(description="Triage id")],
    ) -> dict[str, Any]:

        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        findings = store.list_findings(triage_id)
        by_sev: dict[str, int] = {}
        by_src: dict[str, int] = {}
        for f in findings:
            by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
            by_src[f.source.value] = by_src.get(f.source.value, 0) + 1
        blockers: list[str] = []
        for step in triage.pending_steps:
            if "dynamic" in step and not triage.summary.get("device_connected"):
                blockers.append(f"{step}: no device connected")
        return {
            "triage_id": triage_id,
            "status": triage.status.value,
            "completed_steps": triage.completed_steps,
            "pending_steps": triage.pending_steps,
            "finding_count": len(findings),
            "by_severity": by_sev,
            "by_source": by_src,
            "blockers": blockers,
            "report_path": triage.report_path,
        }

    @mcp.tool(
        name="resume_from_checkpoint",
        description=(
            "Re-open a triage from a saved checkpoint file (JSON). "
            "Returns the new triage_id and the imported findings."
        ),
    )
    def resume_from_checkpoint(
        checkpoint_path: Annotated[str, Field(description="Path to a checkpoint JSON file")],
    ) -> dict[str, Any]:
        import json
        from pathlib import Path

        p = Path(checkpoint_path)
        if not p.exists():
            return {"error": {"code": "checkpoint_not_found", "message": checkpoint_path}}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": {"code": "checkpoint_invalid", "message": str(e)}}

        apk_path = data.get("apk_path", "")
        apk_sha256 = data.get("apk_sha256", "")
        if not apk_path or not apk_sha256:
            return {
                "error": {"code": "checkpoint_missing_fields", "message": "apk_path or apk_sha256"}
            }

        store = get_store()
        triage = store.open_triage(apk_path, apk_sha256, goals=data.get("goals", []))
        for f in data.get("findings", []):
            store.add_finding(_finding_from_dict(triage.triage_id, f))
        store.update_triage(
            triage.triage_id,
            status=TriageStatus.RUNNING,
            plan=data.get("plan", []),
            pending_steps=data.get("pending_steps", []),
            completed_steps=data.get("completed_steps", []),
        )
        return {
            "triage_id": triage.triage_id,
            "imported_findings": len(data.get("findings", [])),
            "status": TriageStatus.RUNNING.value,
        }


def _finding_from_dict(triage_id: str, d: dict) -> Finding:  # type: ignore[name-defined]  # noqa: F821
    from android_re_core.store.sqlite import Finding, FindingSeverity, FindingSource

    return Finding(
        finding_id=d.get("finding_id", ""),
        triage_id=triage_id,
        rule_id=d.get("rule_id", ""),
        severity=FindingSeverity(d.get("severity", "info")),
        source=FindingSource(d.get("source", "manual")),
        message=d.get("message", ""),
        masvs_control=d.get("masvs_control"),
        artifact_path=d.get("artifact_path"),
        start_line=d.get("start_line"),
        start_column=d.get("start_column"),
        properties=dict(d.get("properties", {})),
    )
