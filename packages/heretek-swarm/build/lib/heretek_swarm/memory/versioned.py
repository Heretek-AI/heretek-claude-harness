"""
Versioned Memory Store — Snapshot, Diff, and Rollback for Memory Datasets

.. deprecated::
    Custom dataset versioning is being replaced by Cognee's built-in
    timeline control plane as part of M-arch PR #5 (see PLAN.md §M-arch).
    This module remains in place for backward compatibility and will
    be deleted in a follow-up PR after 1 week of Cognee sidecar parity.

Provides dataset versioning semantics for memory entries:
- Snapshot: capture a point-in-time dump of all memory entries
- Version metadata: commit message, labels, branch, parent version
- Diff: compute additions and removals between two versions
- Rollback: restore memory state to a previous version
- Branch: named pointers to version history

Inspired by Deep Lake's dataset versioning model.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MemorySnapshot:
    """
    Point-in-time snapshot of memory entries.

    Captured at a specific moment and stored as an immutable version.
    """

    id: str
    version_id: str
    entries: list[dict[str, Any]]  # Serialized memory entries
    total_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    captured_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class MemoryVersion:
    """
    Version metadata for a memory snapshot.

    Tracks the commit-like metadata around when a snapshot was taken.
    """

    id: str  # Same as snapshot.id
    version_id: str  # Sequential or hash-based version identifier
    message: str  # Commit message describing what changed
    parent_id: str | None  # Previous version ID (for linear history)
    branch: str  # Branch name (default: "main")
    agent_id: str | None  # Agent that triggered the snapshot
    deliberation_id: str | None  # Associated deliberation round
    total_entries: int  # Number of entries at this version
    labels: list[str] = field(default_factory=list)  # User-defined tags
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    snapshot_id: str | None = None  # Reference to the snapshot data

    @property
    def short_id(self) -> str:
        """Abbreviated version ID for display."""
        return self.version_id[:8]


@dataclass
class MemoryDiff:
    """
    Diff between two memory versions.

    Shows what entries were added, removed, or modified.
    """

    from_version: str
    to_version: str
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    changed_entry_count: int = 0
    unchanged_entry_count: int = 0
    diff_summary: str = ""


# Type alias for memory backend compatibility
MemoryBackend = Any


class VersionedMemoryStore:
    """
    Version-controlled memory store with snapshot and rollback.

    Wraps a memory backend (PersistentMemory, Mem0Backend) and adds
    versioning on top. Each commit creates an immutable snapshot of
    the current memory state. Versions can be diffed, labeled, and restored.

    Example:
        store = VersionedMemoryStore(backend=persistent_memory)

        # Create a snapshot after a decision
        version = await store.create_snapshot(
            message="Post-deliberation checkpoint",
            agent_id="alpha",
            deliberation_id="del_123",
        )

        # List version history
        versions = await store.list_versions(branch="main")

        # Diff two versions
        diff = await store.diff_versions(v1.id, v2.id)

        # Restore to a previous version
        await store.restore_version(version_id)
    """

    def __init__(
        self,
        backend: MemoryBackend | None = None,
        default_branch: str = "main",
        max_versions: int = 100,
    ) -> None:
        """
        Initialize the versioned memory store.

        Args:
            backend: Memory backend to wrap (PersistentMemory, Mem0Backend, etc.)
                    If None, uses in-memory storage only.
            default_branch: Default branch name
            max_versions: Maximum versions to retain per branch
        """
        self._backend = backend
        self._default_branch = default_branch
        self._max_versions = max_versions

        # In-memory version store (for when backend is unavailable)
        self._versions: dict[str, MemoryVersion] = {}
        self._snapshots: dict[str, MemorySnapshot] = {}
        self._branches: dict[str, list[str]] = {default_branch: []}  # branch -> version_ids
        self._labels: dict[str, str] = {}  # label -> version_id
        self._head: dict[str, str] = {default_branch: ""}  # branch -> latest version_id
        self._lock = asyncio.Lock()

        self._version_counter = 0

        logger.info(
            "[VersionedMemoryStore] Initialized",
            default_branch=default_branch,
            max_versions=max_versions,
            has_backend=backend is not None,
        )

    # -------------------------------------------------------------------------
    # Snapshot creation
    # -------------------------------------------------------------------------

    async def create_snapshot(
        self,
        message: str,
        agent_id: str | None = None,
        deliberation_id: str | None = None,
        branch: str | None = None,
        labels: list[str] | None = None,
        snapshot_entries: list[dict[str, Any]] | None = None,
    ) -> MemoryVersion:
        """
        Create a new version snapshot of the current memory state.

        Args:
            message: Commit message describing this version
            agent_id: Agent that triggered the snapshot
            deliberation_id: Associated deliberation round
            branch: Branch name (defaults to default_branch)
            labels: Optional labels to apply
            snapshot_entries: Pre-fetched entries to snapshot.
                            If None, fetches from backend.

        Returns:
            MemoryVersion metadata for the new snapshot
        """
        async with self._lock:
            branch = branch or self._default_branch
            labels = labels or []

            # Fetch current entries from backend
            if snapshot_entries is not None:
                entries = snapshot_entries
            elif self._backend is not None:
                entries = await self._fetch_all_entries()
            else:
                entries = []

            # Generate version ID
            self._version_counter += 1
            version_id = f"v{self._version_counter:04d}"
            snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
            version_uuid = f"ver_{uuid.uuid4().hex[:12]}"

            # Get parent version
            parent_id = self._head.get(branch, None)

            # Create snapshot
            snapshot = MemorySnapshot(
                id=snapshot_id,
                version_id=version_id,
                entries=entries,
                total_count=len(entries),
                metadata={
                    "message": message,
                    "agent_id": agent_id,
                    "deliberation_id": deliberation_id,
                },
            )
            self._snapshots[snapshot_id] = snapshot

            # Create version metadata
            version = MemoryVersion(
                id=version_uuid,
                version_id=version_id,
                message=message,
                parent_id=parent_id,
                branch=branch,
                labels=labels,
                agent_id=agent_id,
                deliberation_id=deliberation_id,
                total_entries=len(entries),
                snapshot_id=snapshot_id,
            )
            self._versions[version_uuid] = version

            # Update branch history
            if branch not in self._branches:
                self._branches[branch] = []
            self._branches[branch].append(version_uuid)
            self._head[branch] = version_uuid

            # Enforce max versions
            await self._prune_branch(branch)

            # Store labels
            for label in labels:
                self._labels[label] = version_uuid

            logger.info(
                "[VersionedMemoryStore] Snapshot created",
                version_id=version_id,
                snapshot_id=snapshot_id,
                branch=branch,
                entries=len(entries),
                agent_id=agent_id,
            )

            return version

    async def _fetch_all_entries(self) -> list[dict[str, Any]]:
        """Fetch all entries from the backend memory store."""
        if self._backend is None:
            return []

        try:
            # Try the Mem0Backend interface
            if hasattr(self._backend, "get_all"):
                return await self._backend.get_all()
            if hasattr(self._backend, "search"):
                # Get all by searching with empty query
                result = await self._backend.search("", limit=10000)
                return result.get("results", [])
        except Exception as e:
            logger.warning(
                "[VersionedMemoryStore] Backend fetch failed",
                error=str(e),
            )

        return []

    # -------------------------------------------------------------------------
    # Version query
    # -------------------------------------------------------------------------

    async def list_versions(
        self,
        branch: str | None = None,
        limit: int = 20,
        offset: int = 0,
        labels: list[str] | None = None,
        agent_id: str | None = None,
    ) -> list[MemoryVersion]:
        """
        List versions with optional filters.

        Args:
            branch: Filter by branch
            limit: Maximum versions to return
            offset: Skip first N versions
            labels: Filter by labels
            agent_id: Filter by triggering agent

        Returns:
            List of MemoryVersion objects
        """
        branch = branch or self._default_branch
        version_ids = self._branches.get(branch, [])

        # Apply filters
        results: list[MemoryVersion] = []
        for vid in version_ids:
            v = self._versions.get(vid)
            if not v:
                continue

            if labels and not any(l in v.labels for l in labels):  # noqa: E741
                continue
            if agent_id and v.agent_id != agent_id:
                continue

            results.append(v)

        # Sort by creation time (newest first)
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def get_version(self, version_id: str) -> MemoryVersion | None:
        """Get version metadata by ID."""
        return self._versions.get(version_id)

    async def get_snapshot(self, snapshot_id: str) -> MemorySnapshot | None:
        """Get the full snapshot data for a version."""
        return self._snapshots.get(snapshot_id)

    async def get_version_entries(
        self,
        version_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get all memory entries for a specific version.

        Args:
            version_id: Version identifier

        Returns:
            List of memory entry dicts
        """
        version = self._versions.get(version_id)
        if not version or not version.snapshot_id:
            return []

        snapshot = self._snapshots.get(version.snapshot_id)
        if snapshot:
            return snapshot.entries

        return []

    async def get_labels(self) -> dict[str, str]:
        """Get all version labels (label -> version_id mapping)."""
        return dict(self._labels)

    async def get_current_head(
        self,
        branch: str | None = None,
    ) -> MemoryVersion | None:
        """Get the latest version on a branch."""
        branch = branch or self._default_branch
        head_id = self._head.get(branch)
        if head_id:
            return self._versions.get(head_id)
        return None

    # -------------------------------------------------------------------------
    # Diff
    # -------------------------------------------------------------------------

    async def diff_versions(
        self,
        from_version_id: str,
        to_version_id: str,
    ) -> MemoryDiff | None:
        """
        Compute the diff between two versions.

        Args:
            from_version_id: Starting version
            to_version_id: Ending version

        Returns:
            MemoryDiff or None if either version not found
        """
        from_entries = await self.get_version_entries(from_version_id)
        to_entries = await self.get_version_entries(to_version_id)

        if from_entries is None or to_entries is None:
            return None

        # Compute diff by entry ID
        from_ids = {e.get("id", str(i)) for i, e in enumerate(from_entries)}
        to_ids = {e.get("id", str(i)) for i, e in enumerate(to_entries)}

        added_ids = to_ids - from_ids
        removed_ids = from_ids - to_ids

        added = [e for i, e in enumerate(to_entries) if e.get("id", str(i)) in added_ids]
        removed = [e for i, e in enumerate(from_entries) if e.get("id", str(i)) in removed_ids]

        total = len(to_entries)
        unchanged = total - len(added)

        summary = f"+{len(added)} -{len(removed)} ~{max(0, unchanged)}"

        return MemoryDiff(
            from_version=from_version_id,
            to_version=to_version_id,
            added=added,
            removed=removed,
            changed_entry_count=len(added) + len(removed),
            unchanged_entry_count=max(0, unchanged),
            diff_summary=summary,
        )

    # -------------------------------------------------------------------------
    # Rollback
    # -------------------------------------------------------------------------

    async def restore_version(
        self,
        version_id: str,
        message: str | None = None,
        branch: str | None = None,
    ) -> MemoryVersion:
        """
        Create a new version by restoring from a previous version's entries.

        Restoring does NOT delete history — it creates a new snapshot
        with the content of the target version.

        Args:
            version_id: Version to restore
            message: Optional override message (default: "Restore to {short_id}")
            branch: Branch to restore on (defaults to default_branch)

        Returns:
            MemoryVersion for the newly created restore snapshot
        """
        branch = branch or self._default_branch
        source_version = self._versions.get(version_id)

        if not source_version:
            raise ValueError(f"Version not found: {version_id}")

        # Get entries from the source snapshot
        entries = await self.get_version_entries(version_id)

        msg = message or f"Restore to {source_version.short_id}"
        labels = [f"restore:{source_version.short_id}"]

        new_version = await self.create_snapshot(
            message=msg,
            labels=labels,
            branch=branch,
            snapshot_entries=entries,
        )

        logger.info(
            "[VersionedMemoryStore] Version restored",
            restored_to=source_version.short_id,
            new_version=new_version.version_id,
            branch=branch,
        )

        return new_version

    # -------------------------------------------------------------------------
    # Labels
    # -------------------------------------------------------------------------

    async def label_version(
        self,
        version_id: str,
        label: str,
    ) -> bool:
        """
        Apply a label to a version.

        Args:
            version_id: Version to label
            label: Label string

        Returns:
            True if labeled, False if version not found
        """
        version = self._versions.get(version_id)
        if not version:
            return False

        if label not in version.labels:
            version.labels.append(label)
        self._labels[label] = version_id

        logger.info(
            "[VersionedMemoryStore] Version labeled",
            version_id=version.short_id,
            label=label,
        )
        return True

    async def get_version_by_label(
        self,
        label: str,
    ) -> MemoryVersion | None:
        """Get the version associated with a label."""
        version_id = self._labels.get(label)
        if version_id:
            return self._versions.get(version_id)
        return None

    # -------------------------------------------------------------------------
    # Pruning
    # -------------------------------------------------------------------------

    async def _prune_branch(self, branch: str) -> None:
        """Remove old versions beyond max_versions."""
        versions = self._branches.get(branch, [])
        if len(versions) <= self._max_versions:
            return

        to_remove = versions[: len(versions) - self._max_versions]
        for vid in to_remove:
            # Don't remove snapshot data — just unlink from branch
            if vid in versions:
                versions.remove(vid)
            # Keep version metadata — can still be referenced by label

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        """Get version store statistics."""
        total_versions = len(self._versions)
        total_snapshots = len(self._snapshots)
        branches = list(self._branches.keys())
        total_labels = len(self._labels)

        branch_stats = {branch: len(vids) for branch, vids in self._branches.items()}

        return {
            "total_versions": total_versions,
            "total_snapshots": total_snapshots,
            "branches": branches,
            "branch_stats": branch_stats,
            "total_labels": total_labels,
            "default_branch": self._default_branch,
            "max_versions": self._max_versions,
        }


# ---------------------------------------------------------------------------
# Global store instance
# ---------------------------------------------------------------------------

_versioned_store: VersionedMemoryStore | None = None


def get_versioned_store() -> VersionedMemoryStore:
    """
    Get the global versioned memory store instance.

    Returns:
        VersionedMemoryStore singleton
    """
    global _versioned_store
    if _versioned_store is None:
        _versioned_store = VersionedMemoryStore()
    return _versioned_store
