"""Gradle project scaffolder.

Exposes one MCP tool:

- :func:`create_gradle_project` — generate a buildable Gradle project
  from a decompile + apktool workdir pair. Wraps
  :class:`android_re_core.gradle.GradleProjectBuilder`.

See ``skills/android-re-gradle-rebuild/SKILL.md`` for the role of
this tool in the larger rebuild pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import ProjectClosed, ProjectNotFound
from android_re_core.gradle import GradleProjectBuilder

from ._common import project_workdir

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register the gradle scaffolder on the given :class:`FastMCP` instance."""

    @mcp.tool(
        name="create_gradle_project",
        description=(
            "Generate a buildable Gradle project from a decompile + apktool "
            "workdir pair. Writes settings.gradle.kts, build.gradle.kts, "
            "app/build.gradle.kts, gradle/libs.versions.toml, app/proguard-rules.pro, "
            "the cleaned AndroidManifest.xml, copies/symlinks res/, assets/, jniLibs/, "
            "and bootstraps the Gradle wrapper from ~/.gradle/wrapper/dists. "
            "DESTRUCTIVE: requires confirm=True to write. With confirm=False, "
            "returns a dry-run summary of the planned files + the cleaned "
            "manifest + the BuildConfig fields that would be injected. "
            "The convention is to pass ``Output/<apk>-<sha>/gradle`` for "
            "``output_dir``."
        ),
    )
    def create_gradle_project(
        project_id: Annotated[
            str,
            Field(description="Project id returned by open_project"),
        ],
        output_dir: Annotated[
            str,
            Field(
                description=(
                    "Absolute path of the directory to write the project "
                    "into. Conventionally ``Output/<apk>-<sha>/gradle``. "
                    "Will be created if it doesn't exist."
                )
            ),
        ],
        cleaned_sources: Annotated[
            str | None,
            Field(
                description=(
                    "Absolute path to the cleaned jadx sources/ directory. "
                    "Defaults to the project's jadx-deobf-java workdir + /sources. "
                    "Override when the cleaned tree has been moved or lives "
                    "outside the project cache."
                )
            ),
        ] = None,
        apktool_workdir: Annotated[
            str | None,
            Field(
                description=(
                    "Absolute path to the apktool-decoded directory. "
                    "Defaults to the project's apktool workdir. Override "
                    "when decode_apk used a different location."
                )
            ),
        ] = None,
        gradle_version: Annotated[
            str,
            Field(
                description="Gradle wrapper version. Default 8.11.1 (already extracted on build hosts)."
            ),
        ] = "8.11.1",
        agp_version: Annotated[
            str, Field(description="Android Gradle Plugin version. Default 8.7.3.")
        ] = "8.7.3",
        kotlin_version: Annotated[
            str, Field(description="Kotlin version. Default 2.0.21.")
        ] = "2.0.21",
        copy_mode: Annotated[
            Literal["copy", "symlink"],
            Field(
                description=(
                    "'copy' (default, works everywhere) or 'symlink' "
                    "(faster, saves 789 MB of duplicated rootfs but requires "
                    "symlink support on the target FS)."
                )
            ),
        ] = "copy",
        confirm: Annotated[
            bool,
            Field(
                description=(
                    "DESTRUCTIVE. Must be true to actually write the project. "
                    "False returns a dry-run summary only."
                )
            ),
        ] = False,
    ) -> dict[str, Any]:
        from . import get_store

        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}

        # Resolve default paths from the project store
        if cleaned_sources is None:
            jadx_wd = project_workdir(project_id, "jadx-deobf-java")
            sources_path = jadx_wd / "sources"
        else:
            sources_path = Path(cleaned_sources).expanduser().resolve()
        if apktool_workdir is None:
            apktool_path = project_workdir(project_id, "apktool")
        else:
            apktool_path = Path(apktool_workdir).expanduser().resolve()

        if not sources_path.exists():
            return {
                "error": {
                    "code": "no_sources_dir",
                    "message": f"cleaned sources not found: {sources_path}",
                }
            }
        if not apktool_path.exists():
            return {
                "error": {
                    "code": "no_apktool_workdir",
                    "message": f"apktool workdir not found: {apktool_path}",
                }
            }

        if not confirm:
            # Dry run: compute the summary without writing.
            builder = GradleProjectBuilder(
                apk_path=project.apk.path,
                cleaned_sources=sources_path,
                apktool_workdir=apktool_path,
                output_dir=output_dir,
                gradle_version=gradle_version,
                agp_version=agp_version,
                kotlin_version=kotlin_version,
                copy_mode=copy_mode,
            )
            return {
                "project_id": project_id,
                "dry_run": True,
                "output_dir": output_dir,
                "cleaned_sources": str(sources_path),
                "apktool_workdir": str(apktool_path),
                "copy_mode": copy_mode,
                "gradle_version": gradle_version,
                "agp_version": agp_version,
                "kotlin_version": kotlin_version,
                "next_step": (
                    "Re-call with confirm=True to write the project. "
                    "Then on a build host with JDK 21 + Android SDK 35, "
                    "run: cd <output_dir> && ./gradlew :app:assembleDebug"
                ),
            }

        builder = GradleProjectBuilder(
            apk_path=project.apk.path,
            cleaned_sources=sources_path,
            apktool_workdir=apktool_path,
            output_dir=output_dir,
            gradle_version=gradle_version,
            agp_version=agp_version,
            kotlin_version=kotlin_version,
            copy_mode=copy_mode,
        )
        report = builder.build()
        return {
            "project_id": project_id,
            "dry_run": False,
            "report": report.to_dict(),
        }
