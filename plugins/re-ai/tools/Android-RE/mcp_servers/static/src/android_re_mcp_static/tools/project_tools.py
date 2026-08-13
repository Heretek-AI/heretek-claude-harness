"""Project lifecycle tools: ``open_project``, ``close_project``, ``list_projects``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import AndroidReError
from android_re_mcp_static.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register project-lifecycle tools on the given FastMCP instance."""

    @mcp.tool(
        name="open_project",
        description=(
            "Open an APK file and register a new project. Returns a "
            "project_id that you must pass to every subsequent call. "
            "Re-opening the same APK returns the existing project. "
            "Performs zip-bomb and size checks before parsing. "
            "The default size cap is 500 MB; pass `max_size` to raise it for a single call."
        ),
    )
    def open_project(
        apk_path: Annotated[
            str, Field(description="Absolute or CWD-relative path to the .apk file")
        ],
        project_id: Annotated[
            str | None,
            Field(
                description="Optional explicit project id; one is derived from SHA-256 if omitted"
            ),
        ] = None,
        max_size: Annotated[
            int | None,
            Field(
                description=(
                    "Override the per-APK size cap in bytes. "
                    "Default: ANDROID_RE_MAX_APK_SIZE env var, else 500 MB. "
                    "Pass a larger value to analyze large APKs without restarting the server."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Open an APK file and return a new or existing project."""
        # Resolve to absolute path for the manifest sha/et al.
        resolved = str(Path(apk_path).expanduser().resolve())
        store = get_store()
        try:
            project = store.open(resolved, project_id=project_id, max_size=max_size)
        except AndroidReError as e:
            return {"error": e.to_dict()}
        return project.to_dict()

    @mcp.tool(
        name="close_project",
        description="Close a previously opened project and release its file handles.",
    )
    def close_project(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
    ) -> dict[str, Any]:
        """Close a project. Idempotent."""
        get_store().close(project_id)
        return {"ok": True, "project_id": project_id}

    @mcp.tool(
        name="list_projects",
        description="List all currently open projects.",
    )
    def list_projects() -> list[dict[str, Any]]:
        """Return summaries of every open project."""
        return get_store().list_summaries()
