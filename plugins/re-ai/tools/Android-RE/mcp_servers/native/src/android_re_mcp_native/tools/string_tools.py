"""String extraction tool."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import APKError, APKInvalid, ProjectClosed, ProjectNotFound
from android_re_mcp_native.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register string-extraction tools."""

    @mcp.tool(
        name="get_strings",
        description=(
            "Extract printable strings from a section of a native "
            "library. Default section is ``.rodata``. The encoding is "
            "always ASCII; longer runs (UTF-16-LE) are a Phase 3 add."
        ),
    )
    def get_strings(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        section: Annotated[str, Field(description="Section to scan, e.g. '.rodata'")] = ".rodata",
        min_length: Annotated[int, Field(ge=1, le=64)] = 4,
        limit: Annotated[int, Field(ge=1, le=10000)] = 1000,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            strings = view.get_strings(
                lib_name, section=section, min_length=min_length, limit=limit
            )
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "section": section,
            "count": len(strings),
            "strings": [s.to_dict() for s in strings],
        }
