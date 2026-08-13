"""Whole-APK decompile + raw source navigation.

Exposes two MCP tools that complement ``decompile_class`` (single class)
and ``decompile_method`` (single method):

- :func:`decompile_apk` — decompile the whole APK and return a
  bounded file listing (path + line count + byte size) so an agent or
  UI can navigate the tree without materialising every file.

- :func:`read_source` — read a single file by path relative to the
  decompiled ``sources/`` dir. Refuses path traversal and oversized
  files. Useful after ``decompile_apk`` returns a list of paths.

Both reuse :class:`android_re_core.sources.SourcesView` and inherit its
per-flag caching: each ``(deobfuscate, output_format)`` combination
gets its own workdir so different decode options don't poison each
other's cache.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import APKError, APKInvalid
from android_re_core.sources import MAX_READ_SOURCE_BYTES, SourcesView
from android_re_mcp_static.server import get_store
from android_re_mcp_static.tools._common import project_workdir

__all__ = ["register"]


def _jadx_suffix(deobfuscate: bool, output_format: str) -> str:
    """Derive a per-flag workdir suffix so each decode option has its
    own cache.
    """
    parts = ["jadx"]
    parts.append("deobf" if deobfuscate else "plain")
    parts.append(output_format)
    return "-".join(parts)


def register(mcp: FastMCP) -> None:
    """Register decompile_tools on the given FastMCP instance."""

    @mcp.tool(
        name="decompile_apk",
        description=(
            "Decompile the whole APK to Java (or Kotlin) via jadx and "
            "return a bounded file listing. The first call in a project "
            "(per deobfuscate/output_format combination) runs the full "
            "jadx decode and caches the result on disk; subsequent "
            "calls are fast. Use this to enumerate the decompiled tree "
            "before picking classes to inspect."
        ),
    )
    def decompile_apk(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        force: Annotated[
            bool,
            Field(description="Re-run jadx even if a cached decode exists for this workdir"),
        ] = False,
        deobfuscate: Annotated[
            bool,
            Field(description="Pass --deobf to jadx for R8/ProGuard name recovery"),
        ] = False,
        threads: Annotated[
            int | None,
            Field(description="Optional jadx thread count (--threads-count)"),
        ] = None,
        output_format: Annotated[
            Literal["java"],
            Field(
                description=(
                    "Only 'java' is supported by the vendored jadx 1.5.0. "
                    "Kotlin classes are decompiled as .java files with "
                    "@kotlin.Metadata annotations, which the Kotlin Gradle "
                    "plugin compiles correctly. See skills/android-re-decompile/."
                )
            ),
        ] = "java",
        limit: Annotated[
            int,
            Field(description="Maximum number of file entries to return (default 500)"),
        ] = 500,
        offset: Annotated[
            int,
            Field(description="Number of file entries to skip (default 0)"),
        ] = 0,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        suffix = _jadx_suffix(deobfuscate, output_format)
        workdir = project_workdir(project_id, suffix)
        try:
            view = SourcesView.decompile(
                project.apk.path,
                workdir=workdir,
                force=force,
                deobfuscate=deobfuscate,
                threads=threads,
                output_format=output_format,
            )
            summary = view.summary(limit=limit, offset=offset)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        return {
            "project_id": project_id,
            "workdir": summary["workdir"],
            "class_count": summary["class_count"],
            "files": summary["files"],
            "total_files": summary["total_files"],
            "deobfuscated": summary["deobfuscated"],
            "output_format": summary["output_format"],
            "threads": summary["threads"],
            "jadx_duration_s": summary["jadx_duration_s"],
            "truncated": summary["truncated"],
            "force": force,
        }

    @mcp.tool(
        name="read_source",
        description=(
            "Read a single file from the decompiled sources tree. The "
            "path is relative to the project's jadx sources/ directory. "
            "Use after decompile_apk to inspect individual files "
            "without re-running jadx. Refuses path traversal and "
            f"files larger than {MAX_READ_SOURCE_BYTES // (1024 * 1024)} MB."
        ),
    )
    def read_source(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        path: Annotated[
            str,
            Field(
                description=(
                    "Path relative to the jadx sources/ dir. "
                    "Examples: 'com/example/Foo.java', 'kotlin/com/example/Bar.kt'. "
                    "Must not start with '/' or contain '..'."
                )
            ),
        ],
        deobfuscate: Annotated[
            bool,
            Field(description="Match the cache of a deobfuscated decode"),
        ] = False,
        output_format: Annotated[
            Literal["java", "kotlin"],
            Field(description="Match the cache of a java/kotlin decode"),
        ] = "java",
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        suffix = _jadx_suffix(deobfuscate, output_format)
        workdir = project_workdir(project_id, suffix)
        try:
            view = SourcesView.decompile(
                project.apk.path,
                workdir=workdir,
                deobfuscate=deobfuscate,
                output_format=output_format,
            )
            result = view.read_source(path)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        if result is None:
            return {
                "project_id": project_id,
                "path": path,
                "found": False,
                "content": None,
                "line_count": 0,
                "byte_size": 0,
                "reason": (
                    "path not found, escaped the sources/ tree, or "
                    f"exceeded the {MAX_READ_SOURCE_BYTES // (1024 * 1024)} MB size cap"
                ),
            }
        content, line_count, byte_size = result
        return {
            "project_id": project_id,
            "path": path,
            "found": True,
            "content": content,
            "line_count": line_count,
            "byte_size": byte_size,
        }
