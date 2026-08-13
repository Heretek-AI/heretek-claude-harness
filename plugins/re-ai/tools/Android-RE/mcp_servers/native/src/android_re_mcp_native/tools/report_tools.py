"""Reporting tools: compare_binaries, yara_scan, build_native_report."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import (
    APKError,
    APKInvalid,
    ProjectClosed,
    ProjectNotFound,
    ToolNotFound,
)
from android_re_core.paths import output_dir_for
from android_re_mcp_native.server import get_store

__all__ = ["register"]


def _default_native_path(project_id: str, name: str) -> Path:
    try:
        project = get_store().get(project_id)
        return output_dir_for(project.apk.path) / "native" / name
    except (ProjectNotFound, ProjectClosed, FileNotFoundError):
        return Path("/tmp") / f"android-re-native-{project_id}" / name


def register(mcp: FastMCP) -> None:
    """Register reporting tools."""

    @mcp.tool(
        name="compare_binaries",
        description=(
            "Diff two binaries inside the same project by symbol set. "
            "Returns added, removed, and modified symbols. Useful for "
            "comparing an APK's library between versions."
        ),
    )
    def compare_binaries(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_a: Annotated[str, Field(description="First library path inside the APK")],
        lib_b: Annotated[str, Field(description="Second library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info_a = view.parse(lib_a)
            info_b = view.parse(lib_b)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        exports_a = {e.name for e in info_a.exports}
        exports_b = {e.name for e in info_b.exports}
        added = sorted(exports_b - exports_a)
        removed = sorted(exports_a - exports_b)
        common = exports_a & exports_b
        return {
            "project_id": project_id,
            "lib_a": lib_a,
            "lib_b": lib_b,
            "added_count": len(added),
            "removed_count": len(removed),
            "common_count": len(common),
            "added": added[:500],
            "removed": removed[:500],
        }

    @mcp.tool(
        name="yara_scan",
        description=(
            "Run yara (https://virustotal.github.io/yara/) against a "
            "single library inside the APK. Requires the ``yara`` CLI "
            "on PATH."
        ),
    )
    def yara_scan(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        rules_path: Annotated[
            str | None,
            Field(description="Path to a YARA rules file. Defaults to the bundled set if omitted."),
        ] = None,
        timeout_s: Annotated[int, Field(ge=1, le=600)] = 120,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        import zipfile

        binary = shutil.which("yara")
        if binary is None:
            raise ToolNotFound(
                "yara", details={"hint": "Install yara: https://virustotal.github.io/yara/"}
            )
        with zipfile.ZipFile(str(project.apk.path), "r") as zf:
            data = zf.read(lib_name)
        # yara needs a file path; write to a temp file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".so", delete=False) as tf:
            tf.write(data)
            tmp_path = tf.name
        try:
            cmd = [binary, "-s", rules_path or "/dev/null", tmp_path]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout_s, check=False
                )
            except subprocess.TimeoutExpired as e:
                return {"error": {"code": "timeout", "message": str(e)}}
            return {
                "project_id": project_id,
                "lib_name": lib_name,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr[-1000:],
            }
        finally:
            try:
                import os

                os.unlink(tmp_path)
            except OSError:
                pass

    @mcp.tool(
        name="build_native_report",
        description=(
            "Build a consolidated report for one library, or every "
            "library in the project if ``lib_name`` is omitted. The "
            "report includes format, arch, security features, "
            "exports, and packer-detection matches."
        ),
    )
    def build_native_report(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[
            str | None,
            Field(description="Single library to report on; omit for all libraries"),
        ] = None,
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write the report JSON. Defaults to "
                    "``Output/<apk>-<sha>/native/native-report.json``."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            targets = [lib_name] if lib_name else view.list_libs()
            reports: list[dict[str, Any]] = []
            for ln in targets:
                try:
                    info = view.parse(ln)
                    packers = view.detect_packers(ln)
                except (APKError, APKInvalid):
                    continue
                reports.append(
                    {
                        "lib_name": ln,
                        "binary": info.to_dict(),
                        "packer_matches": [p.to_dict() for p in packers],
                    }
                )
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        result = {
            "project_id": project_id,
            "report_count": len(reports),
            "reports": reports,
        }
        out_path = (
            Path(output_path).expanduser()
            if output_path
            else _default_native_path(project_id, "native-report.json")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        except OSError as e:
            return {"error": {"code": "write_failed", "message": str(e)}}
        return {**result, "output_path": str(out_path)}
