"""
Chronos types - Enums and dataclasses for temporal & scheduling management.

Extracted from chronos.py (INTG-04).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog


@dataclass
class BulkOperation:
    """A single operation within a bulk_schedule_adjust request.

    Attributes:
        op: Operation type: create, cancel, update_priority, or update_interval
        operation_id: Unique identifier for this operation within the batch
        task_id: Target task ID (required for cancel, update_priority, update_interval)
        name: Task name (create only)
        description: Task description (create only)
        scheduled_at: ISO8601 datetime (create only)
        priority: Task priority 1-5 (create only)
        new_priority: New priority value 1-5 (update_priority only)
        recurrence: Recurrence pattern (create only)
        recurrence_config: Recurrence config dict (create only)
        interval_seconds: New interval in seconds (update_interval only)
        target_agents: List of target agent IDs (create only)
        action: Action name (create only)
        payload: Action payload dict (create only)
        deadline: ISO8601 deadline (create only)
        max_runs: Maximum execution count (create only)
        metadata: Additional metadata (create only)
    """

    op: str  # create | cancel | update_priority | update_interval
    operation_id: str
    task_id: str | None = None
    # create operation fields
    name: str | None = None
    description: str | None = None
    scheduled_at: str | None = None
    priority: int | None = None
    new_priority: int | None = None  # update_priority
    recurrence: str | None = None
    recurrence_config: dict[str, Any] | None = None
    interval_seconds: int | None = None  # update_interval
    target_agents: list[str] | None = None
    action: str | None = None
    payload: dict[str, Any] | None = None
    deadline: str | None = None
    max_runs: int | None = None
    metadata: dict[str, Any] | None = None


logger = structlog.get_logger(__name__)


class ScheduleStatus(Enum):
    """Status of a scheduled item."""

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"
    FAILED = "failed"


class RecurrenceType(Enum):
    """Type of recurrence pattern."""

    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CRON = "cron"
    INTERVAL = "interval"


class Priority(Enum):
    """Task priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class ScheduledTask:
    """A scheduled task."""

    task_id: str
    name: str
    description: str
    scheduled_at: datetime
    status: ScheduleStatus = ScheduleStatus.PENDING
    priority: Priority = Priority.NORMAL
    recurrence: RecurrenceType | None = None
    recurrence_config: dict[str, Any] = field(default_factory=dict)
    target_agents: list[str] = field(default_factory=list)
    action: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    deadline: datetime | None = None
    completed_at: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    max_runs: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "scheduled_at": self.scheduled_at.isoformat(),
            "status": self.status.value,
            "priority": self.priority.value,
            "recurrence": self.recurrence.value if self.recurrence else None,
            "recurrence_config": self.recurrence_config,
            "target_agents": self.target_agents,
            "action": self.action,
            "payload": self.payload,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Tick:
    """A tick represents a single unit of work dispatched by the scheduler.

    Ticks are created by ``generate_ticks()`` when a due ``ScheduledTask``
    is found in PENDING state.  The source task is advanced to ACTIVE after
    the tick is produced.
    """

    tick_id: str
    agent_id: str
    action: str
    scheduled_at: datetime
    status: ScheduleStatus = ScheduleStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tick_id": self.tick_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "scheduled_at": self.scheduled_at.isoformat(),
            "status": self.status.value,
        }


@dataclass
class Deadline:
    """A deadline tracking entry."""

    deadline_id: str
    name: str
    due_at: datetime
    assigned_to: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, met, missed
    warning_thresholds: list[timedelta] = field(default_factory=list)
    warnings_sent: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "deadline_id": self.deadline_id,
            "name": self.name,
            "due_at": self.due_at.isoformat(),
            "assigned_to": self.assigned_to,
            "status": self.status,
            "warning_thresholds": [str(t) for t in self.warning_thresholds],
            "warnings_sent": list(self.warnings_sent),
            "metadata": self.metadata,
            "time_remaining": str(self.due_at - datetime.now(UTC)),
        }
