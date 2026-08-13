"""Cross-finding control: correlate, propose dynamic tests."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.store.sqlite import (
    Finding,
    FindingSource,
)
from android_re_mcp_triage.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register control tools."""

    @mcp.tool(
        name="correlate_findings",
        description=(
            "Run a cross-source correlation pass over the findings "
            "on a triage. Produces a set of correlation cards: a "
            "static finding + a matching dynamic finding = a "
            "confirmed control failure. Returns the list of "
            "correlations and a high-level summary."
        ),
    )
    def correlate_findings(
        triage_id: Annotated[str, Field(description="Triage id")],
    ) -> dict[str, Any]:
        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        findings = store.list_findings(triage_id)
        correlations: list[dict[str, Any]] = []
        # Bucket findings by MASVS control id (if present).
        by_control: dict[str, list[Finding]] = defaultdict(list)
        for f in findings:
            if f.masvs_control:
                by_control[f.masvs_control].append(f)
        # For each control with findings from more than one source,
        # emit a correlation.
        for control_id, group in by_control.items():
            sources = {f.source for f in group}
            if len(sources) > 1:
                correlations.append(
                    {
                        "control_id": control_id,
                        "kind": "cross_source",
                        "sources": sorted(s.value for s in sources),
                        "finding_ids": [f.finding_id for f in group],
                        "summary": (
                            f"{control_id} has findings from {len(sources)} sources — confirmed."
                        ),
                    }
                )
        # Also: detect static-secret → dynamic-leak correlations by
        # matching the rule_id family ("aws-access-key-id" ↔ a log
        # line that mentions "AWS").
        static_secrets = [
            f for f in findings if f.source == FindingSource.STATIC and "key" in f.rule_id.lower()
        ]
        dynamic_logs = [
            f
            for f in findings
            if f.source == FindingSource.DYNAMIC and f.rule_id == "logcat.observation"
        ]
        for s in static_secrets:
            for d in dynamic_logs:
                token = s.rule_id.split("-")[0]
                if token and re.search(token, d.message, re.IGNORECASE):
                    correlations.append(
                        {
                            "control_id": "MASVS-CRYPTO-1",
                            "kind": "static_to_dynamic",
                            "sources": ["static", "dynamic"],
                            "finding_ids": [s.finding_id, d.finding_id],
                            "summary": (
                                f"Static secret {s.rule_id} observed "
                                f"in dynamic logs: {d.message[:100]}"
                            ),
                        }
                    )
        # Persist a summary on the triage
        store.update_triage(
            triage_id,
            summary={
                **triage.summary,
                "correlation_count": len(correlations),
            },
        )
        return {
            "triage_id": triage_id,
            "correlation_count": len(correlations),
            "correlations": correlations,
        }

    @mcp.tool(
        name="propose_dynamic_tests",
        description=(
            "Given the static findings on a triage, propose the "
            "top N dynamic tests (frida hooks, MITM setup, "
            "logcat filters) that would confirm or refute the most "
            "important static claims. Pure heuristic; the agent "
            "should review before running."
        ),
    )
    def propose_dynamic_tests(
        triage_id: Annotated[str, Field(description="Triage id")],
        top_n: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> dict[str, Any]:
        store = get_store()
        triage = store.get_triage(triage_id)
        if triage is None:
            return {"error": {"code": "triage_not_found", "message": triage_id}}
        findings = store.list_findings(triage_id)
        # Score findings by severity: critical=5, high=4, medium=3, low=2, info=1.
        scores: dict[str, int] = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
        ranked = sorted(
            findings,
            key=lambda f: scores.get(f.severity.value, 0),
            reverse=True,
        )
        proposals: list[dict[str, Any]] = []
        for f in ranked[:top_n]:
            proposals.append(
                {
                    "trigger_finding_id": f.finding_id,
                    "rule_id": f.rule_id,
                    "severity": f.severity.value,
                    "proposed_test": _suggest_test(f),
                }
            )
        return {
            "triage_id": triage_id,
            "proposal_count": len(proposals),
            "proposals": proposals,
        }


def _suggest_test(finding: Finding) -> dict[str, Any]:
    """Heuristic mapping: finding -> a concrete dynamic test proposal."""
    rule = finding.rule_id.lower()
    if "key" in rule or "secret" in rule or "token" in rule:
        return {
            "kind": "logcat_search",
            "tool": "mcp__android-re-dynamic__recent_logcat",
            "params": {
                "package": finding.properties.get("package"),
                "level": "I",
                "max_lines": 500,
            },
            "rationale": "Look for the leaked secret in runtime logs.",
        }
    if "cleartext" in rule or "network" in rule:
        return {
            "kind": "mitm_setup",
            "tool": "mcp__android-re-dynamic__setup_mitm",
            "params": {
                "mitm_host": "10.0.2.2",
                "mitm_port": 8080,
                "install_cert": True,
                "confirm": True,
            },
            "rationale": "Route traffic through a proxy to capture the cleartext requests.",
        }
    if "exported" in rule or "component" in rule:
        return {
            "kind": "frida_intent",
            "tool": "mcp__android-re-dynamic__start_intent",
            "params": {
                "action": "android.intent.action.MAIN",
                "component": finding.artifact_path,
            },
            "rationale": "Try launching the exported component to confirm it can be reached.",
        }
    if "debug" in rule or "root" in rule or "tamper" in rule:
        return {
            "kind": "frida_hook",
            "tool": "mcp__android-re-dynamic__frida_load_script",
            "params": {
                "source": "Java.perform(function(){Java.use('java.lang.Runtime').exec.overload('java.lang.String').implementation=function(s){console.log('exec:',s);return this.exec(s);};});"
            },
            "rationale": "Hook Runtime.exec to observe tamper / shell-out attempts.",
        }
    # Default
    return {
        "kind": "general",
        "tool": "mcp__android-re-dynamic__frida_load_script",
        "params": {"source": f"// TODO: write a hook for {finding.rule_id}"},
        "rationale": f"Generic hook scaffold for {finding.rule_id}.",
    }
