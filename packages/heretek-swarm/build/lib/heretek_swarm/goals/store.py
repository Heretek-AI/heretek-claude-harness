"""
File-based goal persistence store.

Persists Goal objects to a JSON file on disk using atomic writes
(.tmp → flush → fsync → os.replace) following the project's standard pattern.

Goals are stored as a dict keyed by goal ID.  Each entry is the full
Goal.to_dict() representation for lossless round-trip serialization.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from .models import Goal, Vote

logger = structlog.get_logger(__name__)

# Default storage path: ~/.heretek-swarm/goals.json
_DEFAULT_STORE_DIR = Path.home() / ".heretek-swarm"
_DEFAULT_STORE_FILE = _DEFAULT_STORE_DIR / "goals.json"


class FileGoalStore:
    """File-backed goal persistence with atomic writes.

    Stores all goals in a single JSON file keyed by goal ID.
    Thread-safe via a reentrant lock around read-modify-write cycles.
    Crash-safe via atomic ``.tmp → fsync → os.replace`` writes.
    """

    def __init__(self, store_path: Path | str | None = None) -> None:
        self._path = Path(store_path) if store_path else _DEFAULT_STORE_FILE
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, goal: Goal) -> None:
        """Create or replace a goal on disk.

        Args:
            goal: The Goal object to persist.
        """
        with self._lock:
            data = self._read_all()
            now = datetime.now(UTC).isoformat()
            goal.updated_at = now
            if not goal.created_at:
                goal.created_at = now
            data[goal.id] = goal.to_dict()
            self._write_all(data)
            logger.info("goal_persisted", goal_id=goal.id, status=goal.status)

    def load(self, goal_id: str) -> Goal | None:
        """Load a single goal from disk.

        Returns ``None`` if the goal does not exist.
        """
        data = self._read_all()
        entry = data.get(goal_id)
        if entry is None:
            return None
        return Goal.from_dict(entry)

    def load_all(self) -> list[Goal]:
        """Load all persisted goals, ordered by creation time (oldest first)."""
        data = self._read_all()
        goals = [Goal.from_dict(entry) for entry in data.values()]
        goals.sort(key=lambda g: g.created_at)
        return goals

    def update_status(self, goal_id: str, new_status: str) -> Goal | None:
        """Atomically update a goal's status.

        Args:
            goal_id: The goal to update.
            new_status: One of ``"proposed"`` / ``"voting"`` / ``"accepted"`` / ``"rejected"``.

        Returns the updated Goal, or ``None`` if the goal was not found.
        """
        with self._lock:
            data = self._read_all()
            entry = data.get(goal_id)
            if entry is None:
                return None
            entry["status"] = new_status
            entry["updated_at"] = datetime.now(UTC).isoformat()
            data[goal_id] = entry
            self._write_all(data)
            logger.info(
                "goal_status_updated",
                goal_id=goal_id,
                new_status=new_status,
            )
            return Goal.from_dict(entry)

    def add_vote(self, goal_id: str, vote: Vote) -> Goal | None:
        """Atomically append a vote to a goal.

        Args:
            goal_id: The goal to vote on.
            vote: The Vote to append.

        Returns the updated Goal, or ``None`` if the goal was not found.
        """
        with self._lock:
            data = self._read_all()
            entry = data.get(goal_id)
            if entry is None:
                return None
            from dataclasses import asdict

            entry.setdefault("votes", []).append(asdict(vote))
            entry["updated_at"] = datetime.now(UTC).isoformat()
            data[goal_id] = entry
            self._write_all(data)
            logger.info(
                "goal_vote_added",
                goal_id=goal_id,
                agent_id=vote.agent_id,
                decision=vote.decision,
            )
            return Goal.from_dict(entry)

    def delete(self, goal_id: str) -> bool:
        """Delete a goal from the store.

        Returns ``True`` if the goal existed and was deleted.
        """
        with self._lock:
            data = self._read_all()
            if goal_id not in data:
                return False
            del data[goal_id]
            self._write_all(data)
            logger.info("goal_deleted", goal_id=goal_id)
            return True

    def exists(self, goal_id: str) -> bool:
        """Check whether a goal is persisted."""
        return goal_id in self._read_all()

    def count(self) -> int:
        """Return the number of persisted goals."""
        return len(self._read_all())

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _read_all(self) -> dict[str, dict[str, Any]]:
        """Read the full store file. Returns empty dict if missing/corrupt."""
        if not self._path.exists():
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:  # noqa: PTH123
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "goal_store_read_error",
                path=str(self._path),
                error=str(exc),
            )
            return {}

    def _write_all(self, data: dict[str, dict[str, Any]]) -> None:
        """Atomically write the full store dict to disk.

        Standard project pattern: write to .tmp, flush, fsync,
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
                "goal_store_write_error",
                path=str(self._path),
                error=str(exc),
            )
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise
