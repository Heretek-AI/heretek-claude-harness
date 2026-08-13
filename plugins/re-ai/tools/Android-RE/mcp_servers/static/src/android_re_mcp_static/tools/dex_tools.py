"""DEX query and per-method decompile tools.

- :func:`find_classes` — FQCN substring search across the project's DEX.
- :func:`find_methods` — method search by class/name/native.
- :func:`decompile_method` — jadx-backed decompilation of a single
  method, with start/end line numbers in the decompiled class.
  Backed by :meth:`android_re_core.sources.SourcesView.decompile_method`.
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
    """Per-flag workdir suffix (shared with smali_tools and decompile_tools)."""
    parts = ["jadx"]
    parts.append("deobf" if deobfuscate else "plain")
    parts.append(output_format)
    return "-".join(parts)


def register(mcp: FastMCP) -> None:
    """Register DEX query tools."""

    @mcp.tool(
        name="find_classes",
        description=(
            "Find classes by JNI-style FQCN substring (e.g. 'Lcom/example/'). "
            "Returns up to ``limit`` matches."
        ),
    )
    def find_classes(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        query: Annotated[
            str, Field(description="Substring to search for in FQCN, e.g. 'Lcom/example/'")
        ],
        limit: Annotated[int, Field(ge=1, le=1000, description="Maximum number of results")] = 100,
        exact: Annotated[bool, Field(description="If true, require exact FQCN match")] = False,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        results = project.dex.find_classes(query, limit=limit, exact=exact)
        return {
            "project_id": project_id,
            "query": query,
            "count": len(results),
            "classes": [c.to_dict() for c in results],
        }

    @mcp.tool(
        name="find_methods",
        description=(
            "Find methods by class FQCN and/or name substring. "
            "Optionally restrict to native (JNI) methods only."
        ),
    )
    def find_methods(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        class_name: Annotated[
            str | None,
            Field(description="Optional substring filter on the FQCN, e.g. 'Lcom/example/Foo;'"),
        ] = None,
        name_substring: Annotated[
            str | None,
            Field(description="Optional substring filter on the method name"),
        ] = None,
        native_only: Annotated[
            bool,
            Field(description="If true, return only native (JNI) methods"),
        ] = False,
        limit: Annotated[int, Field(ge=1, le=5000, description="Maximum number of results")] = 100,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        results = project.dex.find_methods(
            class_name=class_name,
            name_substring=name_substring,
            native_only=native_only,
            limit=limit,
        )
        return {
            "project_id": project_id,
            "count": len(results),
            "methods": [m.to_dict() for m in results],
        }

    @mcp.tool(
        name="decompile_method",
        description=(
            "Decompile a single method to Java (or Kotlin) source via "
            "jadx. Returns the method body as a slice with 1-indexed "
            "start_line / end_line, plus the full class source for "
            "context. When the method cannot be located in the "
            "decompiled output, returns found=false and a reason; the "
            "caller can then fall back to decompile_class."
        ),
    )
    def decompile_method(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        class_name: Annotated[str, Field(description="FQCN in JNI form, e.g. 'Lcom/example/Foo;'")],
        method_name: Annotated[str, Field(description="Method name")],
        descriptor: Annotated[str, Field(description="JVM type descriptor, e.g. '(I)V'")],
        deobfuscate: Annotated[
            bool,
            Field(description="Pass --deobf to jadx (must match decompile_class cache)"),
        ] = False,
        output_format: Annotated[
            Literal["java", "kotlin"],
            Field(description="'java' (default) or 'kotlin'"),
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
                output_format=output_format,
            )
            slice_ = view.decompile_method(class_name, method_name, descriptor)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        if slice_ is None:
            full = view.decompile_class(class_name)
            return {
                "project_id": project_id,
                "class_name": class_name,
                "method_name": method_name,
                "descriptor": descriptor,
                "source": None,
                "found": False,
                "workdir": str(workdir),
                "start_line": None,
                "end_line": None,
                "full_class_source": full,
                "reason": (
                    "method signature not located in the decompiled "
                    "output. The full class source is returned as "
                    "fallback; if the method is obfuscated, retry with "
                    "deobfuscate=True."
                ),
            }
        return {
            "project_id": project_id,
            "class_name": slice_.fqcn,
            "method_name": slice_.method_name,
            "descriptor": slice_.descriptor,
            "source": slice_.source,
            "found": True,
            "workdir": str(workdir),
            "start_line": slice_.start_line,
            "end_line": slice_.end_line,
            "full_class_source": slice_.full_class_source,
        }
