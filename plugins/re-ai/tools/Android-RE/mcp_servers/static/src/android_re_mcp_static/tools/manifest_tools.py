"""Manifest, component, and permission tools.

Exposes three tools on the static MCP server:

- :func:`read_manifest` — full decoded ``AndroidManifest.xml`` (string or
  structured form).
- :func:`list_components` — typed enumeration of activity/service/
  receiver/provider declarations, with optional filters.
- :func:`get_permissions` — ``<uses-permission>`` list, with optional
  classification by protection level.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import ProjectClosed, ProjectNotFound
from android_re_mcp_static.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register manifest/component/permission tools."""

    @mcp.tool(
        name="read_manifest",
        description=(
            "Return the decoded AndroidManifest.xml. By default returns a "
            "structured dict (package, uses-sdk, components, permissions). "
            "Set formatted=true to get the raw XML string."
        ),
    )
    def read_manifest(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        formatted: Annotated[
            bool,
            Field(description="If true, return the raw XML string instead of a structured dict"),
        ] = False,
    ) -> dict[str, Any] | str:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        if formatted:
            return project.manifest.xml
        return project.manifest.to_dict()

    @mcp.tool(
        name="list_components",
        description=(
            "List the activity/service/receiver/provider declarations. "
            "Optionally filter by type and/or exported status."
        ),
    )
    def list_components(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        component_type: Annotated[
            Literal["activity", "service", "receiver", "provider", "all"],
            Field(description="Filter to a single component type, or 'all'"),
        ] = "all",
        exported_only: Annotated[
            bool,
            Field(description="If true, return only components with exported=true"),
        ] = False,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        components = project.manifest.components
        if component_type != "all":
            components = [c for c in components if c.type == component_type]
        if exported_only:
            components = [c for c in components if c.exported is True]
        return {
            "project_id": project_id,
            "count": len(components),
            "components": [c.to_dict() for c in components],
        }

    @mcp.tool(
        name="get_permissions",
        description=(
            "Return the <uses-permission> list with dangerous flags. "
            "Optionally filter by protection level."
        ),
    )
    def get_permissions(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        classification: Annotated[
            Literal["all", "dangerous", "normal", "custom"],
            Field(description="Filter by classification"),
        ] = "all",
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        perms = project.manifest.permissions
        if classification == "dangerous":
            perms = [p for p in perms if p.is_dangerous]
        elif classification == "normal":
            perms = [p for p in perms if not p.is_dangerous and not p.is_custom]
        elif classification == "custom":
            perms = [p for p in perms if p.is_custom]
        return {
            "project_id": project_id,
            "count": len(perms),
            "permissions": [p.to_dict() for p in perms],
        }
