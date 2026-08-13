"""Smali/sources tools: decode, get_smali, decompile_class, repackage.

Exposes five MCP tools:

- :func:`decompile_class` — jadx-backed Java decompilation of a
  class. Supports ``--deobf`` and ``--threads-count`` via MCP
  parameters. Kotlin classes are decompiled as ``.java`` files
  with ``@kotlin.Metadata`` annotations (jadx 1.5.0 does not
  support ``--use-kotlin-source``).
- :func:`get_smali` — apktool-disassembled smali for a class.
- :func:`decode_apk` — full apktool decode into a workdir.
- :func:`rebuild_apk` — apktool build from a decoded workdir.
- :func:`patch_manifest` — apply a structured patch to a decoded
  manifest (Phase 2 ships dry-run only).

Whole-APK decompilation and per-file source reading live in
:mod:`decompile_tools`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import APKError, APKInvalid, ProjectClosed, ProjectNotFound
from android_re_mcp_static.server import get_store
from android_re_mcp_static.tools._common import project_workdir

__all__ = ["register"]


def _jadx_suffix(deobfuscate: bool, output_format: str) -> str:
    """Per-flag workdir suffix (shared with decompile_tools)."""
    parts = ["jadx"]
    parts.append("deobf" if deobfuscate else "plain")
    parts.append(output_format)
    return "-".join(parts)


def register(mcp: FastMCP) -> None:
    """Register smali/sources tools."""

    @mcp.tool(
        name="decompile_class",
        description=(
            "Decompile a single class to Java (or Kotlin) source via "
            "jadx. The first call in a project (per deobfuscate / "
            "output_format combination) runs the full jadx decode and "
            "caches the result on disk; subsequent calls are fast."
        ),
    )
    def decompile_class(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        class_name: Annotated[str, Field(description="FQCN in JNI form, e.g. 'Lcom/example/Foo;'")],
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
                    "@kotlin.Metadata annotations."
                )
            ),
        ] = "java",
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.sources import SourcesView

        suffix = _jadx_suffix(deobfuscate, output_format)
        workdir = project_workdir(project_id, suffix)
        try:
            view = SourcesView.decompile(
                project.apk.path,
                workdir=workdir,
                deobfuscate=deobfuscate,
                threads=threads,
                output_format=output_format,
            )
            source = view.decompile_class(class_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "class_name": class_name,
            "source": source,
            "found": source is not None,
            "workdir": str(workdir),
            "deobfuscated": deobfuscate,
            "output_format": output_format,
        }

    @mcp.tool(
        name="get_smali",
        description=(
            "Return the smali disassembly of a class via apktool. The "
            "first call decodes the whole APK; subsequent calls are "
            "fast (file read)."
        ),
    )
    def get_smali(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        class_name: Annotated[str, Field(description="FQCN in JNI form, e.g. 'Lcom/example/Foo;'")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.smali import SmaliView

        workdir = project_workdir(project_id, "apktool")
        try:
            view = SmaliView.decode(project.apk.path, workdir=workdir, no_res=True)
            smali = view.get_smali(class_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "class_name": class_name,
            "smali": smali,
            "found": smali is not None,
            "workdir": str(workdir),
        }

    @mcp.tool(
        name="decode_apk",
        description=(
            "Decode an APK to an apktool project directory (smali + "
            "resources + manifest). Returns the workdir path; cached "
            "per project. DESTRUCTIVE if workdir already exists unless "
            "``force=true`` is set."
        ),
    )
    def decode_apk(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        force: Annotated[
            bool,
            Field(description="Overwrite any existing decoded workdir"),
        ] = False,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.smali import SmaliView

        workdir = project_workdir(project_id, "apktool")
        try:
            view = SmaliView.decode(
                project.apk.path, workdir=workdir, force=force, no_src=False, no_res=False
            )
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "workdir": str(workdir),
            "class_count": view.class_count(),
            "smali_dirs": [str(p) for p in view.smali_dirs],
            "manifest_path": str(view.manifest_path),
        }

    @mcp.tool(
        name="rebuild_apk",
        description=(
            "Rebuild an APK from a decoded apktool project. Returns "
            "the path to the unsigned rebuilt APK. Sign it with "
            "apksigner or uber-apk-signer before installing. "
            "REQUIRES confirm=true. ``output_path`` defaults to "
            "``Output/<apk>-<sha>/repackage/rebuilt.apk``; pass an "
            "explicit path to override."
        ),
    )
    def rebuild_apk(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Where to write the rebuilt APK. Defaults to "
                    "``Output/<apk>-<sha>/repackage/rebuilt.apk``."
                )
            ),
        ] = None,
        confirm: Annotated[
            bool,
            Field(description="Must be true to actually write the output APK"),
        ] = False,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        if not confirm:
            return {
                "error": {
                    "code": "confirm_required",
                    "message": "rebuild_apk requires confirm=true",
                }
            }
        from android_re_core.paths import output_dir_for
        from android_re_core.smali import SmaliView

        # Default the output path to the per-APK Output/ tree.
        if output_path is None:
            output_path = str(output_dir_for(project.apk.path) / "repackage" / "rebuilt.apk")
        workdir = project_workdir(project_id, "apktool")
        try:
            view = SmaliView.decode(project.apk.path, workdir=workdir, no_res=True)
            out = view.rebuild(output_path=output_path)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "output_path": str(out),
            "size": out.stat().st_size,
        }

    @mcp.tool(
        name="patch_manifest",
        description=(
            "Apply a structured patch to the decoded manifest. Phase 2 "
            "supports dry-run only; set confirm=true to write the "
            "patched manifest to disk (writes only; the rebuilt APK "
            "is not produced here — use rebuild_apk for that)."
        ),
    )
    def patch_manifest(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        patch: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Patch to apply. Phase 2 supports the application "
                    "attributes: debuggable, allowBackup, "
                    "usesCleartextTraffic, networkSecurityConfig."
                )
            ),
        ],
        confirm: Annotated[
            bool,
            Field(description="Must be true to write the patched manifest"),
        ] = False,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.smali import SmaliView

        workdir = project_workdir(project_id, "apktool")
        try:
            view = SmaliView.decode(project.apk.path, workdir=workdir, no_res=True)
            current = view.read_manifest()
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        # Compute the proposed new manifest with a simple text replacement
        proposed = _apply_manifest_patch(current, patch)
        diff_summary: list[str] = []
        for k, v in patch.items():
            diff_summary.append(f"{k}={v}")

        if confirm:
            view.manifest_path.write_text(proposed, encoding="utf-8")
            return {
                "project_id": project_id,
                "manifest_path": str(view.manifest_path),
                "applied": True,
                "changes": diff_summary,
            }
        return {
            "project_id": project_id,
            "manifest_path": str(view.manifest_path),
            "applied": False,
            "dry_run": True,
            "changes": diff_summary,
            "proposed_preview": proposed[:1000],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_manifest_patch(current: str, patch: dict[str, Any]) -> str:
    """Apply a structured manifest patch via text replacement.

    Phase 2: handles a small set of <application> attributes by rewriting
    the existing attribute on the ``<application ...>`` tag. Phase 3
    will use a real XML editor.
    """
    import re

    if not current.lstrip().startswith("<?xml"):
        # apktool already produced decoded XML; proceed
        pass

    proposed = current
    for k, v in patch.items():
        # Match android:k="..."  (any quoted value)
        pattern = re.compile(rf'android:{re.escape(k)}="[^"]*"')
        replacement = f'android:{k}="{v}"'
        if pattern.search(proposed):
            proposed = pattern.sub(replacement, proposed)
        else:
            # Insert as a new attribute on the <application ...> tag.
            # Bind k and v as default args to avoid late-binding issues
            # in the lambda.
            proposed = re.sub(
                r"(<application\b)([^>]*?)(>)",
                lambda m, _k=k, _v=v: (
                    m.group(1) + m.group(2) + f' android:{_k}="{_v}"' + m.group(3)
                ),
                proposed,
                count=1,
            )
    return proposed
