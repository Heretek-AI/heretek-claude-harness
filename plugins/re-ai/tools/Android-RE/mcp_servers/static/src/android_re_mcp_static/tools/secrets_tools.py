"""Secrets scanning tools.

Exposes three MCP tools:

- :func:`scan_secrets` — pure-Python regex scan over the decompiled
  Java source. No external dependency.
- :func:`scan_with_quark` — wrapper around quark-engine (vendored).
- :func:`run_androwarn` — wrapper around androwarn.

All three accept an ``output_path`` / ``output_dir`` parameter so the
findings file lands under the per-APK ``Output/`` tree by default
(``Output/<apk>-<sha>/secrets/...``). The default is computed from
:func:`android_re_core.paths.output_dir_for` when an APK is registered
with a project.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import ProjectClosed, ProjectNotFound
from android_re_core.paths import output_dir_for
from android_re_mcp_static.errors import ToolNotInstalled
from android_re_mcp_static.server import get_store

__all__ = ["register"]


def _default_secrets_path(project_id: str, name: str) -> Path:
    """Default output path for a secrets artifact, derived from the APK."""
    try:
        project = get_store().get(project_id)
        return output_dir_for(project.apk.path) / "secrets" / name
    except (ProjectNotFound, ProjectClosed, FileNotFoundError):
        # Fall back to /tmp if we can't resolve the APK (e.g. project is closed
        # or the APK was moved). This is best-effort.
        return Path("/tmp") / f"android-re-secrets-{project_id}" / name


def register(mcp: FastMCP) -> None:
    """Register secrets-scanning tools."""

    @mcp.tool(
        name="scan_secrets",
        description=(
            "Scan the decompiled Java source of the APK for hard-coded "
            "secrets: URLs, API keys, JWTs, AWS/GCP credentials, "
            "private keys, IP addresses, and more. Pure Python; no "
            "external tools required. Writes findings to "
            "``Output/<apk>-<sha>/secrets/secrets-findings.json`` by "
            "default; override with ``output_path``."
        ),
    )
    def scan_secrets(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        rules: Annotated[
            str,
            Field(
                description="'default' for the built-in rule set, 'strict' to also flag INFO-level hits"
            ),
        ] = "default",
        limit: Annotated[
            int,
            Field(ge=1, le=10000, description="Maximum number of findings to return"),
        ] = 500,
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write findings JSON. Defaults to "
                    "``Output/<apk>-<sha>/secrets/secrets-findings.json``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.secrets.rules import SecretSeverity, scan_text
        from android_re_core.sources import SourcesView

        workdir = _project_workdir(project_id, "jadx")
        try:
            view = SourcesView.decompile(project.apk.path, workdir=workdir, no_res=True)
        except Exception as e:
            return {"error": {"code": "decompile_failed", "message": str(e)}}

        min_sev = SecretSeverity.LOW if rules == "strict" else SecretSeverity.MEDIUM
        findings: list[dict[str, Any]] = []
        java_files = view.list_java_files()
        for java in java_files:
            try:
                text = java.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for f in scan_text(text, min_severity=min_sev):
                findings.append(
                    {
                        **f.to_dict(),
                        "file": str(java.relative_to(view.workdir)),
                    }
                )
                if len(findings) >= limit:
                    break

        # Resolve the output path; default to the per-APK Output/ tree.
        out_path = (
            Path(output_path).expanduser()
            if output_path
            else _default_secrets_path(project_id, "secrets-findings.json")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project_id": project_id,
            "files_scanned": len(java_files),
            "finding_count": len(findings),
            "truncated": len(findings) >= limit,
            "findings": findings,
        }
        try:
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as e:
            return {"error": {"code": "write_failed", "message": str(e)}}
        return {**payload, "output_path": str(out_path)}

    @mcp.tool(
        name="scan_with_quark",
        description=(
            "Run quark-engine (https://quark-engine.net) against the "
            "APK. Returns the count of matched rules. Requires quark "
            "on PATH; bin/pull-tools.sh vendors it (Phase 2 extension). "
            "Output lands in ``Output/<apk>-<sha>/secrets/quark`` by "
            "default; override with ``output_dir``."
        ),
    )
    def scan_with_quark(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        timeout_s: Annotated[int, Field(ge=1, le=3600)] = 300,
        output_dir: Annotated[
            str | None,
            Field(
                description=(
                    "Directory to write quark's report. Defaults to "
                    "``Output/<apk>-<sha>/secrets/quark`` (replacing the "
                    "previous hardcoded ``/tmp/quark-out``)."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        import shutil
        import subprocess

        binary = shutil.which("quark")
        if binary is None:
            raise ToolNotInstalled("quark", "Install with: pipx install quark-engine")
        out_dir = (
            Path(output_dir).expanduser()
            if output_dir
            else _default_secrets_path(project_id, "quark")
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [binary, "--apk", str(project.apk.path), "-o", str(out_dir)]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired as e:
            return {"error": {"code": "timeout", "message": str(e)}}
        return {
            "project_id": project_id,
            "exit_code": proc.returncode,
            "output_dir": str(out_dir),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }

    @mcp.tool(
        name="run_androwarn",
        description=(
            "Run androwarn (https://github.com/maaaaz/AndroWarn) "
            "against the APK. Returns a JSON-shaped warning report. "
            "Writes a structured JSON copy to "
            "``Output/<apk>-<sha>/secrets/androwarn.json`` by default; "
            "override with ``output_path``."
        ),
    )
    def run_androwarn(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        timeout_s: Annotated[int, Field(ge=1, le=3600)] = 300,
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write findings JSON. Defaults to "
                    "``Output/<apk>-<sha>/secrets/androwarn.json``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        import shutil
        import subprocess

        binary = shutil.which("androwarn")
        if binary is None:
            raise ToolNotInstalled("androwarn", "Install with: pipx install androwarn")
        out_path = (
            Path(output_path).expanduser()
            if output_path
            else _default_secrets_path(project_id, "androwarn.json")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [binary, "-i", str(project.apk.path), "-v", "0"]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired as e:
            return {"error": {"code": "timeout", "message": str(e)}}
        # Save the raw stdout as a structured JSON-ish sidecar so the
        # agent can grep / jq it without re-running androwarn.
        try:
            out_path.write_text(proc.stdout, encoding="utf-8")
        except OSError as e:
            return {"error": {"code": "write_failed", "message": str(e)}}
        return {
            "project_id": project_id,
            "exit_code": proc.returncode,
            "output_path": str(out_path),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-1000:],
        }


def _project_workdir(project_id: str, suffix: str) -> str:
    import os
    from pathlib import Path

    base = (
        Path(os.environ.get("ANDROID_RE_TMP_DIR", "/tmp")) / "android-re" / f"{project_id}-{suffix}"
    )
    return str(base)
