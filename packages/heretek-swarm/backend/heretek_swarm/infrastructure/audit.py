"""Audit logging infrastructure for Zero-Trust comprehensive audit trails (ZERO-03).

This module provides immutable audit logging for all agent actions, including:
- Message send/receive events
- Decision made events
- State change events
- Validation events

Features:
- Append-only audit log with cryptographic chain integrity
- Ring buffer for in-memory storage (1M entries max)
- Periodic flush to persistent store
- Queryable by actor ID, time range, action type
- Tamper detection via hash chain
"""

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger("AuditLogger")


@dataclass
class AuditEntry:
    """Single audit log entry."""

    entry_id: str
    timestamp: str
    actor_id: str
    action_type: str
    input_hash: str | None = None
    output_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    previous_hash: str | None = None
    entry_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "action_type": self.action_type,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "metadata": self.metadata,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


class AuditLogger:
    """
    ZERO-03: Comprehensive audit logging service.

    All agent actions are logged with:
    - Timestamp (ISO8601)
    - Actor ID
    - Action type
    - Input hash (for data integrity)
    - Output hash (for result integrity)
    - Cryptographic hash chain (tamper detection)

    The audit log is append-only and supports:
    - In-memory ring buffer (1M entries max)
    - Periodic flush to persistent store
    - Query by actor ID, time range, action type
    """

    def __init__(
        self,
        max_entries: int = 1_000_000,
        flush_interval_entries: int = 1000,
        flush_interval_seconds: int = 60,
    ):
        self.max_entries = max_entries
        self.flush_interval_entries = flush_interval_entries
        self.flush_interval_seconds = flush_interval_seconds

        # Ring buffer for in-memory storage
        self._log: deque[AuditEntry] = deque(maxlen=max_entries)

        # Chain integrity
        self._last_hash: str | None = None
        self._entry_count = 0

        # Flush tracking
        self._entries_since_flush = 0
        self._last_flush_time = datetime.now(UTC)

        # Persistent storage callback (set by supervisor)
        self._persist_callback = None

        # Statistics
        self._stats = {
            "total_entries": 0,
            "entries_by_action": {},
            "entries_by_actor": {},
            "flushes": 0,
            "tamper_detections": 0,
        }

        logger.info(
            "audit_logger_initialized",
            max_entries=max_entries,
            flush_interval_entries=flush_interval_entries,
            flush_interval_seconds=flush_interval_seconds,
        )

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute SHA-256 hash of data."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _compute_entry_hash(self, entry: AuditEntry) -> str:
        """Compute hash of entry for chain integrity."""
        entry_data = {
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp,
            "actor_id": entry.actor_id,
            "action_type": entry.action_type,
            "input_hash": entry.input_hash,
            "output_hash": entry.output_hash,
            "metadata": entry.metadata,
            "previous_hash": entry.previous_hash,
        }
        return self._compute_hash(entry_data)

    def log(
        self,
        actor_id: str,
        action_type: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """
        Log an agent action to the audit trail.

        Args:
            actor_id: ID of the actor performing the action
            action_type: Type of action (e.g., "message_received", "decision_made")
            input_data: Optional input data (hashed for integrity)
            output_data: Optional output data (hashed for integrity)
            metadata: Optional additional metadata

        Returns:
            The created AuditEntry
        """
        # Compute hashes for data integrity
        input_hash = self._compute_hash({"data": input_data}) if input_data is not None else None
        output_hash = self._compute_hash({"data": output_data}) if output_data is not None else None

        # Create entry
        entry = AuditEntry(
            entry_id=f"audit_{self._entry_count:012d}",
            timestamp=datetime.now(UTC).isoformat(),
            actor_id=actor_id,
            action_type=action_type,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=metadata or {},
            previous_hash=self._last_hash,
        )

        # Compute entry hash (includes previous_hash for chain)
        entry.entry_hash = self._compute_entry_hash(entry)
        self._last_hash = entry.entry_hash

        # Add to ring buffer
        self._log.append(entry)

        # Update statistics
        self._entry_count += 1
        self._stats["total_entries"] += 1
        self._stats["entries_by_action"][action_type] = (
            self._stats["entries_by_action"].get(action_type, 0) + 1
        )
        self._stats["entries_by_actor"][actor_id] = (
            self._stats["entries_by_actor"].get(actor_id, 0) + 1
        )
        self._entries_since_flush += 1

        # Check if flush needed
        self._check_flush_needed()

        return entry

    def _check_flush_needed(self) -> None:
        """Check if flush to persistent store is needed."""
        now = datetime.now(UTC)
        time_since_flush = (now - self._last_flush_time).total_seconds()

        if (
            self._entries_since_flush >= self.flush_interval_entries
            or time_since_flush >= self.flush_interval_seconds
        ):
            self._flush()

    def _flush(self) -> None:
        """Flush audit log to persistent store."""
        if self._entries_since_flush == 0:
            return

        entries_to_flush = list(self._log)[-self._entries_since_flush :]

        if self._persist_callback:
            try:
                self._persist_callback(entries_to_flush)
                logger.info(
                    "audit_log_flushed",
                    entries_flushed=self._entries_since_flush,
                )
            except Exception:
                logger.error("audit_log_flush_failed: {e}")

        self._entries_since_flush = 0
        self._last_flush_time = datetime.now(UTC)
        self._stats["flushes"] += 1

    def set_persist_callback(self, callback: callable) -> None:
        """Set callback for persistent storage flush."""
        self._persist_callback = callback

    def verify_chain_integrity(self) -> tuple[bool, list[str]]:
        """
        Verify cryptographic chain integrity.

        Returns:
            Tuple of (is_valid, list_of_broken_entry_ids)
        """
        broken_entries = []
        previous_hash = None

        for entry in self._log:
            if entry.previous_hash != previous_hash:
                broken_entries.append(entry.entry_id)
                self._stats["tamper_detections"] += 1

            # Verify entry hash
            expected_hash = self._compute_entry_hash(entry)
            if entry.entry_hash != expected_hash:
                broken_entries.append(f"{entry.entry_id}_hash_mismatch")
                self._stats["tamper_detections"] += 1

            previous_hash = entry.entry_hash

        is_valid = len(broken_entries) == 0
        if not is_valid:
            logger.error(
                "audit_chain_integrity_violation",
                broken_entries=broken_entries,
            )

        return is_valid, broken_entries

    def query(
        self,
        actor_id: str | None = None,
        action_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query audit log by criteria.

        Args:
            actor_id: Filter by actor ID
            action_type: Filter by action type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum results to return

        Returns:
            List of matching audit entries as dicts
        """
        results = []

        for entry in self._log:
            # Apply filters
            if actor_id and entry.actor_id != actor_id:
                continue
            if action_type and entry.action_type != action_type:
                continue
            if start_time:
                entry_time = datetime.fromisoformat(entry.timestamp)
                if entry_time < start_time:
                    continue
            if end_time:
                entry_time = datetime.fromisoformat(entry.timestamp)
                if entry_time > end_time:
                    continue

            results.append(entry.to_dict())

            if len(results) >= limit:
                break

        return results

    def get_statistics(self) -> dict[str, Any]:
        """Get audit log statistics."""
        return {
            **self._stats,
            "current_buffer_size": len(self._log),
            "max_buffer_size": self.max_entries,
            "last_flush_time": self._last_flush_time.isoformat(),
            "entries_since_flush": self._entries_since_flush,
            "chain_integrity": self.verify_chain_integrity()[0],
        }

    def get_activity_rate(self, actor_id: str, window_seconds: int = 60) -> float:
        """
        Get activity rate for an actor over a time window.

        Args:
            actor_id: Actor ID to check
            window_seconds: Time window in seconds

        Returns:
            Entries per second
        """
        now = datetime.now(UTC)
        window_start = now.timestamp() - window_seconds

        count = 0
        for entry in self._log:
            entry_time = datetime.fromisoformat(entry.timestamp).timestamp()
            if entry_time > window_start and entry.actor_id == actor_id:
                count += 1

        return count / window_seconds if window_seconds > 0 else 0.0


# Global audit logger instance (managed by supervisor)
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    if _audit_logger is None:
        raise RuntimeError("Audit logger not initialized")
    return _audit_logger


def init_audit_logger(
    max_entries: int = 1_000_000,
    flush_interval_entries: int = 1000,
    flush_interval_seconds: int = 60,
) -> AuditLogger:
    """Initialize the global audit logger."""
    global _audit_logger
    _audit_logger = AuditLogger(
        max_entries=max_entries,
        flush_interval_entries=flush_interval_entries,
        flush_interval_seconds=flush_interval_seconds,
    )
    return _audit_logger
