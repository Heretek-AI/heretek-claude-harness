"""Catalyst types — Change management data structures."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class ChangeStatus(Enum):
    """Status of a change request."""

    PROPOSED = "proposed"
    ANALYZING = "analyzing"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

class ChangeType(Enum):
    """Type of change."""

    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"
    MIGRATION = "migration"
    UPGRADE = "upgrade"
    PATCH = "patch"
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"

class ImpactLevel(Enum):
    """Change impact level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ChangeRequest:
    """A change request under management."""

    change_id: str
    title: str
    description: str
    change_type: ChangeType
    status: ChangeStatus = ChangeStatus.PROPOSED
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    requested_by: str = ""
    affected_components: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    approval_status: dict[str, bool] = field(default_factory=dict)
    required_approvals: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "change_id": self.change_id,
            "title": self.title,
            "description": self.description,
            "change_type": self.change_type.value,
            "status": self.status.value,
            "impact_level": self.impact_level.value,
            "requested_by": self.requested_by,
            "affected_components": self.affected_components,
            "dependencies": self.dependencies,
            "rollback_plan": self.rollback_plan,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
            "approval_status": self.approval_status,
            "required_approvals": self.required_approvals,
            "approval_count": sum(1 for v in self.approval_status.values() if v),
        }

@dataclass
class ChangeNotification:
    """A change notification to stakeholders."""

    notification_id: str
    change_id: str
    recipients: list[str]
    message: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged_by: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "notification_id": self.notification_id,
            "change_id": self.change_id,
            "recipients": self.recipients,
            "message": self.message,
            "sent_at": self.sent_at.isoformat(),
            "acknowledged_by": list(self.acknowledged_by),
            "acknowledgment_count": len(self.acknowledged_by),
        }
