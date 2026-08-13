"""
File-based workflow persistence store.

Persists workflow definitions to a JSON file on disk using atomic writes
(.tmp → flush → fsync → os.replace) following the project's existing pattern
for crash-safe, concurrent-safe file I/O.

Workflows are stored as a dict keyed by workflow ID, each entry containing
the full workflow definition plus metadata (created_at, updated_at, name).
"""

import contextlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default storage path: ~/.heretek-swarm/workflows.json
_DEFAULT_STORE_DIR = Path.home() / ".heretek-swarm"
_DEFAULT_STORE_FILE = _DEFAULT_STORE_DIR / "workflows.json"


class FileWorkflowStore:
    """File-backed workflow persistence with atomic writes.

    Stores all workflows in a single JSON file keyed by workflow ID.
    Each entry holds the raw workflow definition dict plus metadata
    (``created_at``, ``updated_at``, ``name``).

    Thread-safe via a reentrant lock around read-modify-write cycles.
    Crash-safe via atomic ``.tmp → fsync → os.replace`` writes.
    """

    def __init__(self, store_path: Path | str | None = None) -> None:
        self._path = Path(store_path) if store_path else _DEFAULT_STORE_FILE
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, workflow_id: str, definition: dict[str, Any]) -> None:
        """Create or replace a workflow definition on disk.

        Args:
            workflow_id: Unique workflow identifier.
            definition: Full workflow definition dict (nodes, edges, metadata, etc.).
        """
        with self._lock:
            data = self._read_all()
            now = datetime.now(UTC).isoformat()
            existing = data.get(workflow_id, {})
            data[workflow_id] = {
                **definition,
                "id": workflow_id,
                "name": definition.get("name", existing.get("name", "Untitled Workflow")),
                "created_at": existing.get("created_at", now),
                "updated_at": now,
            }
            self._write_all(data)
            logger.info("workflow_persisted", workflow_id=workflow_id)

    def load(self, workflow_id: str) -> dict[str, Any] | None:
        """Load a single workflow definition from disk.

        Returns None if the workflow does not exist.
        """
        data = self._read_all()
        return data.get(workflow_id)

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Load all persisted workflow definitions.

        Returns a dict keyed by workflow ID.
        """
        return self._read_all()

    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow from the store.

        Returns True if the workflow existed and was deleted, False otherwise.
        """
        with self._lock:
            data = self._read_all()
            if workflow_id not in data:
                return False
            del data[workflow_id]
            self._write_all(data)
            logger.info("workflow_deleted_from_store", workflow_id=workflow_id)
            return True

    def exists(self, workflow_id: str) -> bool:
        """Check whether a workflow is persisted."""
        data = self._read_all()
        return workflow_id in data

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _read_all(self) -> dict[str, dict[str, Any]]:
        """Read the full store file. Returns empty dict if file missing."""
        if not self._path.exists():
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:  # noqa: PTH123
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "workflow_store_read_error",
                path=str(self._path),
                error=str(exc),
            )
            return {}

    def _write_all(self, data: dict[str, dict[str, Any]]) -> None:
        """Atomically write the full store dict to disk.

        Uses the project's standard pattern: write to .tmp, flush, fsync,
        then os.replace for a crash-safe rename.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:  # noqa: PTH123
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(self._path)
        except OSError as exc:
            logger.error(
                "workflow_store_write_error",
                path=str(self._path),
                error=str(exc),
            )
            # Clean up partial tmp file
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise
