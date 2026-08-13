"""
Memory Versioning API

Provides REST endpoints for:
- Creating memory snapshots (version commits)
- Listing version history with filters
- Getting version details and entries
- Computing diffs between versions
- Rolling back to previous versions
- Labeling versions

Inspired by Deep Lake dataset versioning.
"""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.memory.versioned import (
    get_versioned_store,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/memory/versions", tags=["memory versions"])


@router.post("/snapshot", status_code=201)
async def create_snapshot(
    message: Annotated[str, Query(description="Version commit message")],
    authenticated: dict = Depends(verify_auth),  # noqa: B008
    agent_id: Annotated[str | None, Query(description="Agent triggering this snapshot")] = None,
    deliberation_id: Annotated[
        str | None, Query(description="Associated deliberation round")
    ] = None,
    branch: Annotated[str | None, Query(description="Branch name")] = None,
    labels: Annotated[str | None, Query(description="Comma-separated labels")] = None,
) -> dict[str, Any]:
    """
    Create a new memory snapshot (version commit).

    Captures the current state of all memory entries as an immutable version.
    """
    store = get_versioned_store()
    label_list = [l.strip() for l in labels.split(",")] if labels else None  # noqa: E741

    try:
        version = await store.create_snapshot(
            message=message,
            agent_id=agent_id,
            deliberation_id=deliberation_id,
            branch=branch,
            labels=label_list,
        )

        return {
            "version_id": version.id,
            "short_id": version.short_id,
            "version_number": version.version_id,
            "message": version.message,
            "branch": version.branch,
            "labels": version.labels,
            "total_entries": version.total_entries,
            "created_at": version.created_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("")
async def list_versions(
    authenticated: dict = Depends(verify_auth),  # noqa: B008
    branch: Annotated[str | None, Query(description="Filter by branch")] = None,
    limit: Annotated[int, Query(description="Max versions to return", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(description="Skip first N versions", ge=0)] = 0,
    labels: Annotated[str | None, Query(description="Filter by comma-separated labels")] = None,
    agent_id: Annotated[str | None, Query(description="Filter by agent ID")] = None,
) -> dict[str, Any]:
    """
    List memory version history with optional filters.
    """
    store = get_versioned_store()

    label_list = [l.strip() for l in labels.split(",")] if labels else None  # noqa: E741

    versions = await store.list_versions(
        branch=branch,
        limit=limit,
        offset=offset,
        labels=label_list,
        agent_id=agent_id,
    )

    return {
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_id,
                "short_id": v.short_id,
                "message": v.message,
                "branch": v.branch,
                "labels": v.labels,
                "agent_id": v.agent_id,
                "deliberation_id": v.deliberation_id,
                "total_entries": v.total_entries,
                "created_at": v.created_at,
            }
            for v in versions
        ],
        "count": len(versions),
        "limit": limit,
        "offset": offset,
    }


@router.get("/labels")
async def get_all_labels(
    authenticated: dict = Depends(verify_auth),  # noqa: B008
) -> dict[str, Any]:
    """Get all version labels and their associated version IDs."""
    store = get_versioned_store()
    labels = await store.get_labels()

    return {"labels": labels, "count": len(labels)}


@router.get("/head")
async def get_current_head(
    authenticated: dict = Depends(verify_auth),  # noqa: B008
    branch: Annotated[str | None, Query(description="Branch name")] = None,
) -> dict[str, Any]:
    """Get the latest version on a branch."""
    store = get_versioned_store()
    version = await store.get_current_head(branch=branch)

    if not version:
        raise HTTPException(status_code=404, detail="No versions found on this branch")

    return {
        "id": version.id,
        "version_number": version.version_id,
        "short_id": version.short_id,
        "message": version.message,
        "branch": version.branch,
        "total_entries": version.total_entries,
        "created_at": version.created_at,
    }


@router.get("/{version_id}")
async def get_version(
    version_id: str,
    authenticated: dict = Depends(verify_auth),  # noqa: B008
    include_entries: Annotated[bool, Query(description="Include full entry list")] = False,
) -> dict[str, Any]:
    """
    Get details for a specific version.

    Optionally includes all memory entries at that version.
    """
    store = get_versioned_store()
    version = await store.get_version(version_id)

    if not version:
        raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")

    result = {
        "id": version.id,
        "version_number": version.version_id,
        "short_id": version.short_id,
        "message": version.message,
        "branch": version.branch,
        "parent_id": version.parent_id,
        "labels": version.labels,
        "agent_id": version.agent_id,
        "deliberation_id": version.deliberation_id,
        "total_entries": version.total_entries,
        "created_at": version.created_at,
    }

    if include_entries:
        entries = await store.get_version_entries(version_id)
        result["entries"] = entries
        result["entry_count"] = len(entries)

    return result


@router.get("/{version_id}/entries")
async def get_version_entries(
    version_id: str,
    authenticated: dict = Depends(verify_auth),  # noqa: B008
) -> dict[str, Any]:
    """Get all memory entries for a specific version."""
    store = get_versioned_store()
    version = await store.get_version(version_id)

    if not version:
        raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")

    entries = await store.get_version_entries(version_id)

    return {"version_id": version.version_id, "entries": entries, "count": len(entries)}


@router.get("/diff/{from_version}/{to_version}")
async def diff_versions(
    from_version: str,
    to_version: str,
    authenticated: dict = Depends(verify_auth),  # noqa: B008
) -> dict[str, Any]:
    """
    Compute the diff between two versions.

    Shows entries that were added, removed, and the diff summary.
    """
    store = get_versioned_store()
    diff = await store.diff_versions(from_version, to_version)

    if diff is None:
        raise HTTPException(
            status_code=404,
            detail="Could not diff: one or both versions not found",
        )

    return {
        "from_version": diff.from_version,
        "to_version": diff.to_version,
        "added_count": len(diff.added),
        "removed_count": len(diff.removed),
        "changed_entry_count": diff.changed_entry_count,
        "unchanged_entry_count": diff.unchanged_entry_count,
        "diff_summary": diff.diff_summary,
        "added": diff.added[:20],  # Limit payload size
        "removed": diff.removed[:20],
    }


@router.post("/{version_id}/restore", status_code=201)
async def restore_version(
    version_id: str,
    authenticated: dict = Depends(verify_auth),  # noqa: B008
    message: Annotated[
        str | None, Query(description="Override message for the restore version")
    ] = None,
    branch: Annotated[str | None, Query(description="Branch to restore on")] = None,
) -> dict[str, Any]:
    """
    Restore memory to a previous version.

    Creates a new snapshot with the content of the target version.
    Does NOT delete history — the original versions are preserved.
    """
    store = get_versioned_store()

    try:
        new_version = await store.restore_version(
            version_id=version_id,
            message=message,
            branch=branch,
        )

        return {
            "restored_from": version_id,
            "new_version_id": new_version.id,
            "new_short_id": new_version.short_id,
            "message": new_version.message,
            "branch": new_version.branch,
            "total_entries": new_version.total_entries,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{version_id}/label/{label}")
async def label_version(
    version_id: str,
    label: str,
    authenticated: dict = Depends(verify_auth),  # noqa: B008
) -> dict[str, Any]:
    """
    Apply a label to a version.

    Labels are human-readable names for versions (like git tags).
    """
    store = get_versioned_store()
    success = await store.label_version(version_id, label)

    if not success:
        raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")

    return {"labeled": True, "version_id": version_id, "label": label}


@router.get("/label/{label}")
async def get_version_by_label(
    label: str,
    authenticated: dict = Depends(verify_auth),  # noqa: B008
) -> dict[str, Any]:
    """Get the version associated with a label."""
    store = get_versioned_store()
    version = await store.get_version_by_label(label)

    if not version:
        raise HTTPException(status_code=404, detail=f"No version found for label: {label}")

    return {
        "label": label,
        "version_id": version.id,
        "short_id": version.short_id,
        "version_number": version.version_id,
        "message": version.message,
    }


@router.get("/statistics")
async def get_version_statistics(
    authenticated: dict = Depends(verify_auth),  # noqa: B008
) -> dict[str, Any]:
    """Get version store statistics."""
    store = get_versioned_store()
    return store.get_statistics()
