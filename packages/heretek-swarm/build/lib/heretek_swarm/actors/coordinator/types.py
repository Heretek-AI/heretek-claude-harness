"""
Coordinator Types - Data Models and Enums for Coordination

Contains all type definitions extracted from coordinator.py.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TaskStatus(Enum):
    """Status of a coordinated task."""

    PENDING = "pending"
    READY = "ready"  # Dependencies satisfied
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"  # Waiting on external dependency
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DependencyType(Enum):
    """Type of task dependency."""

    SEQUENTIAL = "sequential"  # Must complete before next starts
    PARALLEL = "parallel"  # Can run concurrently
    CONDITIONAL = "conditional"  # Depends on condition being met
    RESOURCE = "resource"  # Competes for shared resource


@dataclass
class CoordinatedTask:
    """A task under coordination."""

    task_id: str
    name: str
    description: str
    assigned_agents: list[str]
    dependencies: list[str] = field(default_factory=list)
    dependency_type: DependencyType = DependencyType.SEQUENTIAL
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10 scale
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    progress: float = 0.0  # 0.0 to 1.0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "assigned_agents": self.assigned_agents,
            "dependencies": self.dependencies,
            "dependency_type": self.dependency_type.value,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
            "progress": self.progress,
            "error_message": self.error_message,
        }


@dataclass
class AgentState:
    """Current state of an agent in the coordination system."""

    agent_id: str
    status: str = "idle"  # idle, busy, offline
    current_task: str | None = None
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    load: float = 0.0  # 0.0 to 1.0
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "current_task": self.current_task,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "load": self.load,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }
