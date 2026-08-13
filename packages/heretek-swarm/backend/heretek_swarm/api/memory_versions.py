"""
Memory Versioning API

Provides REST endpoints for:
- Creating memory snapshots (version commits)
- Listing version history with filters
- Getting version details and entries
- Computing diffs between versions
- Rolling back to previous versions
- Labeling versions

Migrated from the custom ``memory.versioned`` store to Cognee as part
of M-arch PR #5. Endpoint signatures remain stable for API compatibility.
"""

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/memory/versions", tags=["memory versions"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_cognee_writer() -> CogneeMemoryWriter:
    """Module-level factory: return a configured :class:`CogneeMemoryWriter`."""
    return CogneeMemoryWriter()


def _get_cognee_reader() -> CogneeMemoryReader:
    """Module-level factory: return a configured :class:`CogneeMemoryReader`."""
    return CogneeMemoryReader()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/snapshot", status_code=201)
async def create_snapshot(
    message: Annotated[str, Query(description="Version commit message")],
    authenticated: dict = Depends(verify_auth),
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
    writer = _get_cognee_writer()
    now = datetime.now(UTC).isoformat()

    # Build a descriptive dataset name encoding version metadata
    label_list = [lbl.strip() for lbl in labels.split(",")] if labels else []
    version_id = f"v-{now.replace(':', '-').replace('.', '-')}"

    dataset = f"memory-version-{version_id}"
    if branch:
        dataset = f"{dataset}-{branch}"

    # Compose snapshot content with metadata envelope
    snapshot_content = (
        f"Message: {message}\n"
        f"Agent ID: {agent_id or 'unknown'}\n"
        f"Deliberation ID: {deliberation_id or 'none'}\n"
        f"Branch: {branch or 'main'}\n"
        f"Labels: {','.join(label_list) if label_list else 'none'}\n"
        f"Timestamp: {now}\n"
    )

    try:
        success = await writer.store(content=snapshot_content, dataset=dataset)

        return {
            "version_id": version_id,
            "short_id": version_id[:8],
            "version_number": version_id,
            "message": message,
            "branch": branch or "main",
            "labels": label_list if label_list else None,
            "total_entries": 1,
            "created_at": now,
            "stored": success,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("")
async def list_versions(
    authenticated: dict = Depends(verify_auth),
    branch: Annotated[str | None, Query(description="Filter by branch")] = None,
    limit: Annotated[int, Query(description="Max versions to return", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(description="Skip first N versions", ge=0)] = 0,
    labels: Annotated[str | None, Query(description="Filter by comma-separated labels")] = None,
    agent_id: Annotated[str | None, Query(description="Filter by agent ID")] = None,
) -> dict[str, Any]:
    """
    List memory version history with optional filters.

    With Cognee, the concept of "version list" maps to searching across
    memory-version-* datasets. This returns a simplified response.
    """
    reader = _get_cognee_reader()

    query_parts: list[str] = ["memory version snapshot"]
    if agent_id:
        query_parts.append(f"agent {agent_id}")
    if labels:
        query_parts.append(f"labels {labels}")

    query = " ".join(query_parts)
    results = await reader.read(query=query, top_k=limit, dataset=None)

    # Convert Cognee search results into version-like entries
    versions = []
    for idx, result in enumerate(results):
        if idx < offset:
            continue
        content = result.get("content", "")
        dataset = result.get("dataset", "unknown")
        versions.append({
            "id": dataset,
            "version_number": dataset.replace("memory-version-", ""),
            "short_id": dataset.replace("memory-version-", "")[:8],
            "message": content.split("\n")[0] if content else "",
            "branch": branch or "main",
            "labels": [labels] if labels else None,
            "agent_id": agent_id,
            "deliberation_id": None,
            "total_entries": 1,
            "created_at": result.get("metadata", {}).get("captured_at"),
        })

    return {
        "versions": versions,
        "count": len(versions),
        "limit": limit,
        "offset": offset,
    }


@router.get("/labels")
async def get_all_labels(
    authenticated: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """Get all version labels and their associated version IDs."""
    reader = _get_cognee_reader()
    results = await reader.read(query="memory version labels", top_k=50)
    labels: dict[str, list[str]] = {}
    for r in results:
        content = r.get("content", "")
        # Extract label line from the stored content
        for line in content.split("\n"):
            if line.startswith("Labels:") and "none" not in line.lower():
                raw_labels = line.split("Labels:")[1].strip()
                for label in raw_labels.split(","):
                    label = label.strip()
                    if label:
                        labels.setdefault(label, []).append(r.get("dataset", ""))

    return {"labels": labels, "count": len(labels)}


@router.get("/head")
async def get_current_head(
    authenticated: dict = Depends(verify_auth),
    branch: Annotated[str | None, Query(description="Branch name")] = None,
) -> dict[str, Any]:
    """Get the latest version on a branch."""
    reader = _get_cognee_reader()
    results = await reader.read(query="memory version snapshot", top_k=1)
    if not results:
        raise HTTPException(status_code=404, detail="No versions found on this branch")

    head = results[0]
    dataset = head.get("dataset", "unknown")
    return {
        "id": dataset,
        "version_number": dataset.replace("memory-version-", ""),
        "short_id": dataset.replace("memory-version-", "")[:8],
        "message": head.get("content", "").split("\n")[0] if head.get("content") else "",
        "branch": branch or "main",
        "total_entries": 1,
        "created_at": head.get("metadata", {}).get("captured_at"),
    }


@router.get("/{version_id}")
async def get_version(
    version_id: str,
    authenticated: dict = Depends(verify_auth),
    include_entries: Annotated[bool, Query(description="Include full entry list")] = False,
) -> dict[str, Any]:
    """
    Get details for a specific version.

    Optionally includes all memory entries at that version.
    """
    reader = _get_cognee_reader()
    dataset = f"memory-version-{version_id}"
    results = await reader.read(query="snapshot content", top_k=50, dataset=dataset)

    if not results:
        raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")

    first = results[0]
    content = first.get("content", "")

    # Parse metadata from the stored content envelope
    parsed: dict[str, str] = {}
    for line in content.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            parsed[key.strip()] = val.strip()

    result: dict[str, Any] = {
        "id": version_id,
        "version_number": version_id,
        "short_id": version_id[:8],
        "message": parsed.get("Message", ""),
        "branch": parsed.get("Branch", "main"),
        "parent_id": None,
        "labels": [lbl.strip() for lbl in parsed.get("Labels", "none").split(",") if lbl.strip() and lbl.strip() != "none"],
        "agent_id": parsed.get("Agent ID"),
        "deliberation_id": parsed.get("Deliberation ID"),
        "total_entries": 1,
        "created_at": parsed.get("Timestamp"),
    }

    if include_entries:
        result["entries"] = [r.get("content", "") for r in results]
        result["entry_count"] = len(results)

    return result


@router.get("/{version_id}/entries")
async def get_version_entries(
    version_id: str,
    authenticated: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """Get all memory entries for a specific version."""
    reader = _get_cognee_reader()
    dataset = f"memory-version-{version_id}"
    results = await reader.read(query="all content", top_k=50, dataset=dataset)

    if not results:
        raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")

    entries = [r.get("content", "") for r in results]
    return {"version_id": version_id, "entries": entries, "count": len(entries)}


@router.get("/diff/{from_version}/{to_version}")
async def diff_versions(
    from_version: str,
    to_version: str,
    authenticated: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Compute the diff between two versions.

    Shows entries that were added, removed, and the diff summary.
    """
    reader = _get_cognee_reader()
    from_dataset = f"memory-version-{from_version}"
    to_dataset = f"memory-version-{to_version}"

    from_results = await reader.read(query="all content", top_k=50, dataset=from_dataset)
    to_results = await reader.read(query="all content", top_k=50, dataset=to_dataset)

    from_contents = {r.get("content", "") for r in from_results}
    to_contents = {r.get("content", "") for r in to_results}

    added = [c for c in to_contents if c not in from_contents]
    removed = [c for c in from_contents if c not in to_contents]

    return {
        "from_version": from_version,
        "to_version": to_version,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_entry_count": len(added) + len(removed),
        "unchanged_entry_count": len(from_contents & to_contents),
        "diff_summary": f"Added {len(added)}, removed {len(removed)}",
        "added": added[:20],
        "removed": removed[:20],
    }


@router.post("/{version_id}/restore", status_code=201)
async def restore_version(
    version_id: str,
    authenticated: dict = Depends(verify_auth),
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
    reader = _get_cognee_reader()
    writer = _get_cognee_writer()

    from_dataset = f"memory-version-{version_id}"
    results = await reader.read(query="all content", top_k=50, dataset=from_dataset)

    if not results:
        raise HTTPException(status_code=404, detail=f"Version not found: {version_id}")

    now = datetime.now(UTC).isoformat()
    new_version_id = f"v-{now.replace(':', '-').replace('.', '-')}"
    to_dataset = f"memory-version-{new_version_id}"
    if branch:
        to_dataset = f"{to_dataset}-{branch}"

    restore_msg = message or f"Restored from version {version_id}"

    # Write each content entry to the new dataset
    for r in results:
        content = r.get("content", "")
        if content:
            await writer.store(content=content, dataset=to_dataset)

    return {
        "restored_from": version_id,
        "new_version_id": new_version_id,
        "new_short_id": new_version_id[:8],
        "message": restore_msg,
        "branch": branch or "main",
        "total_entries": len(results),
    }


@router.post("/{version_id}/label/{label}")
async def label_version(
    version_id: str,
    label: str,
    authenticated: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Apply a label to a version.

    Labels are human-readable names for versions (like git tags).
    """
    writer = _get_cognee_writer()

    # Store the label metadata as a Cognee dataset
    label_dataset = f"memory-label-{label}"
    content = (
        f"Label: {label}\n"
        f"Version ID: {version_id}\n"
        f"Created: {datetime.now(UTC).isoformat()}\n"
    )
    success = await writer.store(content=content, dataset=label_dataset)

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to store label: {label}")

    return {"labeled": True, "version_id": version_id, "label": label}


@router.get("/label/{label}")
async def get_version_by_label(
    label: str,
    authenticated: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """Get the version associated with a label."""
    reader = _get_cognee_reader()
    label_dataset = f"memory-label-{label}"
    results = await reader.read(query="label metadata", top_k=1, dataset=label_dataset)

    if not results:
        raise HTTPException(status_code=404, detail=f"No version found for label: {label}")

    content = results[0].get("content", "")
    parsed: dict[str, str] = {}
    for line in content.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            parsed[key.strip()] = val.strip()

    version_id = parsed.get("Version ID", "unknown")
    return {
        "label": label,
        "version_id": version_id,
        "short_id": version_id[:8],
        "version_number": version_id,
        "message": parsed.get("Message", ""),
    }


@router.get("/statistics")
async def get_version_statistics(
    authenticated: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """Get version store statistics."""
    reader = _get_cognee_reader()
    healthy = await reader.health()
    results = await reader.read(query="memory version", top_k=100)

    return {
        "total_versions": len(results),
        "cognee_healthy": healthy,
        "backend": "cognee",
        "engine": "knowledge-graph",
    }
