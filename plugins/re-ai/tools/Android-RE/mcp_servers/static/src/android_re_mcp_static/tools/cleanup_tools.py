"""Post-decompile cleanup tools.

Exposes one MCP tool:

- :func:`jadx_cleanup_workdir` — apply the 9 in-place cleanup
  transforms (and optionally the 10th "move broken files" pass) to a
  jadx-decompiled ``sources/`` directory. Wraps
  :class:`android_re_core.cleanup.JadxCleanup`.

See ``skills/android-re-gradle-rebuild/SKILL.md`` for the role of
this tool in the larger rebuild pipeline.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.cleanup import JadxCleanup
from android_re_core.errors import ProjectClosed, ProjectNotFound

from ._common import project_workdir

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register the cleanup tool on the given :class:`FastMCP` instance."""

    @mcp.tool(
        name="jadx_cleanup_workdir",
        description=(
            "Apply post-decompile cleanup transforms to a jadx-decompiled "
            "sources/ directory. Fixes the 9 well-known jadx 1.5.0 artifacts "
            "(p00Xui deobf leftovers, ?? type placeholders, JADX ERROR + throw "
            "patterns, m<line> prefixes on @Metadata/@DebugMetadata fields, "
            "f<line> prefixes on commons-lang3 static fields, removed "
            "androidx.autofill.HintConstants, Kotlin 2.0 enumEntries, "
            "duplicate getter methods). With agressivo=True, also runs a "
            "Gradle compile attempt and moves broken files to java-broken/ "
            "(requires a build.gradle.kts in the project root). Idempotent: "
            "writes a .jadx-cleanup-complete marker after success."
        ),
    )
    def jadx_cleanup_workdir(
        project_id: Annotated[
            str,
            Field(description="Project id returned by open_project"),
        ],
        agressivo: Annotated[
            bool,
            Field(
                description=(
                    "When true, also runs the move_broken_files pass: tries "
                    "./gradlew :app:compileDebugJavaWithJavac and moves "
                    "files that fail the build to java-broken/. Default false."
                ),
            ),
        ] = False,
        gradle_cmd: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Override for the Gradle command used by the "
                    "move_broken_files pass. Default: "
                    "['./gradlew', ':app:compileDebugJavaWithJavac', '--no-daemon']"
                ),
            ),
        ] = None,
    ) -> dict[str, Any]:
        from . import get_store

        try:
            get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}

        # Find the decompile workdir. The cleanup targets the most
        # recent deobf-java workdir by convention; if the project has
        # multiple cached workdirs, callers can set JADX_WORKDIR env
        # to override.
        workdir_override = project_workdir(project_id, "jadx-deobf-java")
        if not workdir_override.exists():
            return {
                "error": {
                    "code": "no_decompile_cache",
                    "message": (
                        f"No deobf-java workdir found at {workdir_override}. "
                        "Run decompile_apk(deobfuscate=True, output_format='java') first."
                    ),
                }
            }
        sources_dir = workdir_override / "sources"
        if not sources_dir.exists():
            return {
                "error": {
                    "code": "no_sources_dir",
                    "message": f"sources/ not found in {workdir_override}",
                }
            }

        report = JadxCleanup.cleanup(sources_dir, agressivo=agressivo, gradle_cmd=gradle_cmd)
        return {"project_id": project_id, "report": report.to_dict()}
