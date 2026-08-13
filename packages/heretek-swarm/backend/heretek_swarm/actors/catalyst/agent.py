"""
Catalyst Agent - Change Management Specialist

Tier 5 Coordination Agent responsible for:
- Change detection and impact analysis
- Transition planning and execution
- Version management and migration
- Rollback coordination
- Change communication and stakeholder notification

Author: Heretek Swarm Collective
Date: 2026-04-06
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor

if TYPE_CHECKING:
    from heretek_swarm.collective.learning import PatternExtractor
    from heretek_swarm_core.consensus.swarm_deliberation import SwarmDeliberationEngine
    from heretek_swarm_core.memory.access_patterns import AccessPatternAnalyzer
    from heretek_swarm_core.security.zero_trust import ZeroTrustValidator
from heretek_swarm.actors.catalyst.types import (
    ChangeNotification,
    ChangeRequest,
    ChangeStatus,
    ChangeType,
    ImpactLevel,
)
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.actors.validation import validate_message
from heretek_swarm.coordination.paradigm_detection import (
    ChangeRequest as PDChangeRequest,
)
from heretek_swarm.coordination.paradigm_detection import (
    ChangeType as PDChangeType,
)
from heretek_swarm.coordination.paradigm_detection import (
    ParadigmDetector,
    ParadigmShift,
    ShiftStatus,
)

logger = structlog.get_logger(__name__)

# Error message constant
_PARADIGM_NOT_INITIALIZED = "ParadigmDetector not initialized"


class CatalystAgent(
    ValidationMixin, DeliberationMixin, PatternMixin, MemoryMixin, LearningMixin, AgentActor
):
    """
    Change Management Specialist.

    Responsibilities:
    - Detect and analyze proposed changes
    - Plan and schedule transitions
    - Manage version migrations
    - Coordinate rollbacks when needed
    - Notify stakeholders of changes

    Message Handlers:
    - propose_change: Propose a new change request
    - analyze_change: Analyze change impact
    - approve_change: Approve a change request
    - schedule_change: Schedule approved change
    - execute_change: Execute scheduled change
    - request_rollback: Initiate rollback
    - execute_rollback: Execute rollback procedure
    - get_change_status: Get status of a change
    - get_change_history: Get change history
    - notify_stakeholders: Send change notifications
    """

    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
        # Session 44: Integration components
        pattern_extractor: PatternExtractor | None = None,
        deliberation_engine: SwarmDeliberationEngine | None = None,
        access_analyzer: AccessPatternAnalyzer | None = None,
        zero_trust_validator: ZeroTrustValidator | None = None,
    ):
        super().__init__(
            agent_id=agent_id or f"catalyst_{uuid.uuid4().hex[:8]}",
            config=config or {},
        )

        self._config: dict[str, Any] = {}

        # Change management
        self._changes: dict[str, ChangeRequest] = {}
        self._max_changes: int = self._config.get("max_changes", 500)

        # Notifications
        self._notifications: dict[str, ChangeNotification] = {}
        self._max_notifications: int = self._config.get("max_notifications", 1000)

        # Stakeholders
        self._stakeholders: set[str] = set()

        # Change history
        self._history: list[dict[str, Any]] = []
        self._max_history: int = self._config.get("max_history", 1000)

        # INTG-03: Paradigm Shift Detection
        self._paradigm_detector: ParadigmDetector | None = None
        self._paradigm_shifts: dict[str, ParadigmShift] = {}
        self._shift_rate_limiter: dict[str, datetime] = {}
        self._min_shift_interval_seconds: int = 300
        self._change_timestamps: list[datetime] = []

        logger.info(
            "catalyst_initialized",
            agent_id=self.agent_id,
            max_changes=self._max_changes,
        )

    async def initialize(self) -> None:
        """Initialize the Catalyst agent with paradigm detection."""
        await super().initialize()
        self._paradigm_detector = ParadigmDetector(
            beta_agent_id="beta",
            steward_agent_id="steward",
            indicator_threshold=3,
            velocity_threshold=2.0,
        )
        self._register_handlers()
        logger.info("catalyst_intg03_initialized")

    def _register_handlers(self) -> None:
        """Register INTG-03 paradigm detection message handlers."""
        self._message_handlers = {
            "propose_change": self._handle_propose_change,
            "analyze_change": self._handle_analyze_change,
            "approve_change": self._handle_approve_change,
            "schedule_change": self._handle_schedule_change,
            "execute_change": self._handle_execute_change,
            "request_rollback": self._handle_request_rollback,
            "execute_rollback": self._handle_execute_rollback,
            "get_change_status": self._handle_get_change_status,
            "get_change_history": self._handle_get_change_history,
            "notify_stakeholders": self._handle_notify_stakeholders,
            "detect_paradigm_shift": self._handle_detect_paradigm_shift,
            "get_paradigm_shift_status": self._handle_get_paradigm_shift_status,
            "validate_paradigm_shift": self._handle_validate_paradigm_shift,
            "get_shift_velocity": self._handle_get_shift_velocity,
            "get_cumulative_impact": self._handle_get_cumulative_impact,
        }

    async def _validate_message(self, message: ActorMessage) -> dict[str, Any]:
        """Validate incoming message content."""
        try:
            validated = validate_message(message.message_type, message.content)
            if hasattr(validated, "dict"):
                return validated.dict()
            return validated
        except Exception as e:
            logger.debug("catalyst_message_parse_failed", error=str(e))
            return message.content

    async def _handle_propose_change(self, message: ActorMessage) -> None:
        """
        Propose a new change request.

        Content:
        - change_id: Optional[str]
        - title: str
        - description: str
        - change_type: str (configuration|deployment|migration|upgrade|patch|hotfix|rollback)
        - affected_components: List[str]
        - rollback_plan: str
        - impact_level: Optional[str] (low|medium|high|critical)
        - required_approvals: Optional[int]
        - metadata: Optional[Dict]
        """
        try:
            content = await self._validate_message(message)

            if len(self._changes) >= self._max_changes:
                await self._send_error(
                    message.sender_id,
                    f"Change limit reached ({self._max_changes})",
                    message.message_type,
                )
                return

            change_id = content.get("change_id") or f"change_{uuid.uuid4().hex[:12]}"

            if change_id in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} already exists",
                    message.message_type,
                )
                return

            change_type = ChangeType(content.get("change_type", "configuration"))
            impact_level = ImpactLevel(content.get("impact_level", "medium"))

            change = ChangeRequest(
                change_id=change_id,
                title=content.get("title", "Untitled Change"),
                description=content.get("description", ""),
                change_type=change_type,
                impact_level=impact_level,
                requested_by=message.sender_id,
                affected_components=content.get("affected_components", []),
                rollback_plan=content.get("rollback_plan", ""),
                required_approvals=content.get("required_approvals", 1),
                metadata=content.get("metadata", {}),
            )

            self._changes[change_id] = change

            logger.info(
                "change_proposed",
                change_id=change_id,
                title=change.title,
                type=change_type.value,
                impact=impact_level.value,
            )

            # Notify stakeholders
            await self._notify_stakeholders(change_id, f"Change proposed: {change.title}")

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_proposed",
                    content={"change": change.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("propose_change_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to propose change: {e!s}",
                message.message_type,
            )

    async def _handle_analyze_change(self, message: ActorMessage) -> None:
        """
        Analyze change impact.

        Content:
        - change_id: str
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]
            change.status = ChangeStatus.ANALYZING

            # Perform impact analysis
            analysis = {
                "change_id": change_id,
                "impact_assessment": {
                    "affected_components": change.affected_components,
                    "component_count": len(change.affected_components),
                    "impact_level": change.impact_level.value,
                    "risk_score": self._calculate_risk_score(change),
                },
                "dependencies": {
                    "internal": change.dependencies,
                    "external": [],  # Can be extended
                },
                "recommendations": self._generate_recommendations(change),
            }

            change.status = ChangeStatus.PROPOSED  # Back to proposed after analysis

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_analyzed",
                    content={"analysis": analysis},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("analyze_change_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to analyze change: {e!s}",
                message.message_type,
            )

    async def _handle_approve_change(self, message: ActorMessage) -> None:
        """
        Approve a change request.

        Content:
        - change_id: str
        - approver_id: str
        - approved: bool
        - comments: Optional[str]
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")
            approver_id = content.get("approver_id", message.sender_id)
            approved = content.get("approved", False)

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]
            change.approval_status[approver_id] = approved

            approval_count = sum(1 for v in change.approval_status.values() if v)
            needs_more_approvals = approval_count < change.required_approvals

            if approved and not needs_more_approvals:
                change.status = ChangeStatus.APPROVED
                logger.info(
                    "change_approved",
                    change_id=change_id,
                    approver=approver_id,
                    approval_count=approval_count,
                )
            elif approved:
                logger.info(
                    "change_partial_approval",
                    change_id=change_id,
                    approver=approver_id,
                    approval_count=approval_count,
                    needed=change.required_approvals,
                )
            else:
                logger.info(
                    "change_rejected",
                    change_id=change_id,
                    approver=approver_id,
                )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_approval_recorded",
                    content={
                        "change_id": change_id,
                        "approved": approved,
                        "approval_count": approval_count,
                        "required": change.required_approvals,
                        "status": change.status.value,
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("approve_change_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to record approval: {e!s}",
                message.message_type,
            )

    async def _handle_schedule_change(self, message: ActorMessage) -> None:
        """
        Schedule an approved change.

        Content:
        - change_id: str
        - scheduled_at: str (ISO8601)
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")
            scheduled_at = content.get("scheduled_at")

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]

            if change.status != ChangeStatus.APPROVED:
                await self._send_error(
                    message.sender_id,
                    f"Change must be approved before scheduling (current: {change.status.value})",
                    message.message_type,
                )
                return

            change.scheduled_at = (
                datetime.fromisoformat(scheduled_at) if scheduled_at else datetime.now(UTC)
            )
            change.status = ChangeStatus.SCHEDULED

            logger.info(
                "change_scheduled",
                change_id=change_id,
                scheduled_at=change.scheduled_at.isoformat(),
            )

            await self._notify_stakeholders(change_id, f"Change scheduled: {change.title}")

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_scheduled",
                    content={"change": change.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("schedule_change_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to schedule change: {e!s}",
                message.message_type,
            )

    async def _handle_execute_change(self, message: ActorMessage) -> None:
        """
        Execute a scheduled change.

        Content:
        - change_id: str
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]
            change.status = ChangeStatus.IN_PROGRESS
            change.started_at = datetime.now(UTC)

            logger.info(
                "change_started",
                change_id=change_id,
                title=change.title,
            )

            # Simulate execution (would be extended for real implementation)
            # In production, this would coordinate with actual deployment systems

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_started",
                    content={"change": change.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("execute_change_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to execute change: {e!s}",
                message.message_type,
            )

    async def _handle_request_rollback(self, message: ActorMessage) -> None:
        """
        Request a rollback of a change.

        Content:
        - change_id: str
        - reason: str
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")
            reason = content.get("reason", "Unspecified")

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]

            if change.status not in (
                ChangeStatus.COMPLETED,
                ChangeStatus.IN_PROGRESS,
                ChangeStatus.FAILED,
            ):
                await self._send_error(
                    message.sender_id,
                    f"Cannot rollback change in {change.status.value} state",
                    message.message_type,
                )
                return

            # Create rollback change request
            rollback_id = f"rollback_{change_id}"
            rollback = ChangeRequest(
                change_id=rollback_id,
                title=f"Rollback: {change.title}",
                description=f"Rolling back {change_id} due to: {reason}",
                change_type=ChangeType.ROLLBACK,
                impact_level=change.impact_level,
                requested_by=message.sender_id,
                affected_components=change.affected_components,
                rollback_plan="",  # Rollback of a rollback
                metadata={"original_change_id": change_id, "rollback_reason": reason},
            )

            self._changes[rollback_id] = rollback

            logger.info(
                "rollback_requested",
                change_id=change_id,
                rollback_id=rollback_id,
                reason=reason,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="rollback_requested",
                    content={"rollback": rollback.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("request_rollback_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to request rollback: {e!s}",
                message.message_type,
            )

    async def _handle_execute_rollback(self, message: ActorMessage) -> None:
        """
        Execute a rollback.

        Content:
        - change_id: str (original change to rollback)
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]
            change.status = ChangeStatus.ROLLED_BACK
            change.completed_at = datetime.now(UTC)

            # Record in history
            self._record_change_event(change_id, "rolled_back")

            logger.info(
                "rollback_executed",
                change_id=change_id,
            )

            await self._notify_stakeholders(change_id, f"Change rolled back: {change.title}")

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="rollback_executed",
                    content={"change": change.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("execute_rollback_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to execute rollback: {e!s}",
                message.message_type,
            )

    async def _handle_get_change_status(self, message: ActorMessage) -> None:
        """
        Get status of a change.

        Content:
        - change_id: str
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            change = self._changes[change_id]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_status",
                    content={"change": change.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_change_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get change status: {e!s}",
                message.message_type,
            )

    async def _handle_get_change_history(self, message: ActorMessage) -> None:
        """
        Get change history.

        Content:
        - limit: Optional[int]
        - change_type: Optional[str]
        - status: Optional[str]
        """
        try:
            content = await self._validate_message(message)
            limit = min(content.get("limit", 50), 100)
            change_type = content.get("change_type")
            status = content.get("status")

            history = self._history.copy()

            # Filter by change_type
            if change_type:
                history = [h for h in history if h.get("change_type") == change_type]

            # Filter by status
            if status:
                history = [h for h in history if h.get("status") == status]

            # Limit results
            history = history[-limit:]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="change_history",
                    content={"history": history, "count": len(history)},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_change_history_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get change history: {e!s}",
                message.message_type,
            )

    async def _handle_notify_stakeholders(self, message: ActorMessage) -> None:
        """
        Send notifications to stakeholders.

        Content:
        - change_id: str
        - message: str
        - recipients: Optional[List[str]]
        """
        try:
            content = await self._validate_message(message)
            change_id = content.get("change_id")
            notification_message = content.get("message", "")
            recipients = content.get("recipients", list(self._stakeholders))

            if not change_id or change_id not in self._changes:
                await self._send_error(
                    message.sender_id,
                    f"Change {change_id} not found",
                    message.message_type,
                )
                return

            notification_id = f"notif_{uuid.uuid4().hex[:12]}"
            notification = ChangeNotification(
                notification_id=notification_id,
                change_id=change_id,
                recipients=recipients,
                message=notification_message,
            )

            self._notifications[notification_id] = notification

            # Trim notifications if needed
            if len(self._notifications) > self._max_notifications:
                oldest = min(self._notifications)
                del self._notifications[oldest]

            logger.info(
                "stakeholders_notified",
                notification_id=notification_id,
                change_id=change_id,
                recipient_count=len(recipients),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="notification_sent",
                    content={"notification": notification.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("notify_stakeholders_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to notify stakeholders: {e!s}",
                message.message_type,
            )

    async def _notify_stakeholders(self, change_id: str, message: str) -> None:
        """Internal helper to notify all stakeholders."""
        if not self._stakeholders:
            return

        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        notification = ChangeNotification(
            notification_id=notification_id,
            change_id=change_id,
            recipients=list(self._stakeholders),
            message=message,
        )

        self._notifications[notification_id] = notification

        # Trim if needed
        if len(self._notifications) > self._max_notifications:
            oldest = min(self._notifications)
            del self._notifications[oldest]

    def _calculate_risk_score(self, change: ChangeRequest) -> float:
        """Calculate risk score for a change (0.0-1.0)."""
        base_scores = {
            ImpactLevel.LOW: 0.1,
            ImpactLevel.MEDIUM: 0.3,
            ImpactLevel.HIGH: 0.6,
            ImpactLevel.CRITICAL: 0.9,
        }

        score = base_scores.get(change.impact_level, 0.3)

        # Increase score based on affected components
        component_factor = min(len(change.affected_components) * 0.05, 0.2)
        score += component_factor

        # Increase score for complex change types
        complex_types = {ChangeType.DEPLOYMENT, ChangeType.MIGRATION, ChangeType.UPGRADE}
        if change.change_type in complex_types:
            score += 0.1

        return min(score, 1.0)

    def _generate_recommendations(self, change: ChangeRequest) -> list[str]:
        """Generate recommendations for a change."""
        recommendations = []

        if change.impact_level == ImpactLevel.CRITICAL:
            recommendations.append("Consider breaking this change into smaller increments")
            recommendations.append("Ensure rollback plan is thoroughly tested")

        if len(change.affected_components) > 5:
            recommendations.append("High component count - consider phased rollout")

        if change.change_type == ChangeType.MIGRATION:
            recommendations.append("Create backup before migration")
            recommendations.append("Test migration on staging environment first")

        if not change.rollback_plan:
            recommendations.append("Document detailed rollback procedure")

        if change.required_approvals < 2 and change.impact_level in (
            ImpactLevel.HIGH,
            ImpactLevel.CRITICAL,
        ):
            recommendations.append(
                "Consider requiring additional approvals for high-impact changes"
            )

        return recommendations

    def _record_change_event(self, change_id: str, event_type: str) -> None:
        """Record a change event in history."""
        change = self._changes.get(change_id)
        if not change:
            return

        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "change_id": change_id,
            "change_type": change.change_type.value,
            "event_type": event_type,
            "status": change.status.value,
            "title": change.title,
        }

        self._history.append(event)

        # Trim history if needed
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    async def _send_error(
        self,
        recipient: str,
        error_message: str,
        original_type: str,
    ) -> None:
        """Send error response."""
        await self.send(
            recipient,
            ActorMessage(
                message_type="error",
                content={"error": error_message, "original_type": original_type},
                sender_id=self.agent_id,
            ),
        )

    async def _handle_detect_paradigm_shift(self, message: ActorMessage) -> None:
        """Detect paradigm shift from change patterns."""
        if not self._paradigm_detector:
            await self._send_error(
                message.sender_id, _PARADIGM_NOT_INITIALIZED, message.message_type
            )
            return
        try:
            content = message.content or {}
            change_id = content.get("change_id")
            if change_id and change_id in self._changes:
                change = self._changes[change_id]
                pd_change = PDChangeRequest(
                    change_id=change.change_id,
                    title=change.title,
                    description=change.description,
                    change_type=PDChangeType(change.change_type.value),
                    requested_by=change.requested_by,
                    affected_components=change.affected_components,
                    metadata=change.metadata,
                )
                await self._paradigm_detector.record_change(pd_change)
            velocity = await self._paradigm_detector.analyze_change_velocity()
            shifts = list(self._paradigm_shifts.values())
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="paradigm_shift_detected",
                    content={
                        "shift_detected": len(shifts) > 0,
                        "shifts": [s.to_dict() for s in shifts],
                        "velocity": velocity,
                    },
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("detect_paradigm_shift_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to detect shift: {e!s}", message.message_type
            )

    async def _handle_get_paradigm_shift_status(self, message: ActorMessage) -> None:
        """Get status of paradigm shifts."""
        if not self._paradigm_detector:
            await self._send_error(
                message.sender_id, _PARADIGM_NOT_INITIALIZED, message.message_type
            )
            return
        try:
            content = message.content or {}
            shift_id = content.get("shift_id")
            if shift_id:
                shifts = (
                    [self._paradigm_shifts.get(shift_id)]
                    if shift_id in self._paradigm_shifts
                    else []
                )
            else:
                shifts = list(self._paradigm_shifts.values())
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="paradigm_shift_status",
                    content={"shifts": [s.to_dict() for s in shifts if s], "count": len(shifts)},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("get_paradigm_shift_status_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get status: {e!s}", message.message_type
            )

    async def _handle_validate_paradigm_shift(self, message: ActorMessage) -> None:
        """Handle Beta validation result for false positive check."""
        if not self._paradigm_detector:
            await self._send_error(
                message.sender_id, _PARADIGM_NOT_INITIALIZED, message.message_type
            )
            return
        try:
            content = message.content or {}
            shift_id = content.get("shift_id")
            is_false_positive = content.get("is_false_positive", False)
            validation_details = content.get("validation_details")
            await self._paradigm_detector.handle_validation_result(
                shift_id, is_false_positive, validation_details
            )
            if shift_id in self._paradigm_shifts:
                self._paradigm_shifts[shift_id].status = (
                    ShiftStatus.FALSE_POSITIVE if is_false_positive else ShiftStatus.CONFIRMED
                )
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="paradigm_shift_validated",
                    content={"shift_id": shift_id},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("validate_paradigm_shift_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to validate: {e!s}", message.message_type
            )

    async def _handle_get_shift_velocity(self, message: ActorMessage) -> None:
        """Get current change velocity metrics."""
        if not self._paradigm_detector:
            await self._send_error(
                message.sender_id, _PARADIGM_NOT_INITIALIZED, message.message_type
            )
            return
        try:
            velocity = await self._paradigm_detector.analyze_change_velocity()
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="shift_velocity", content=velocity, sender_id=self.agent_id
                ),
            )
        except Exception as e:
            logger.error("get_shift_velocity_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get velocity: {e!s}", message.message_type
            )

    async def _handle_get_cumulative_impact(self, message: ActorMessage) -> None:
        """Get cumulative impact for a shift."""
        if not self._paradigm_detector:
            await self._send_error(
                message.sender_id, _PARADIGM_NOT_INITIALIZED, message.message_type
            )
            return
        try:
            content = message.content or {}
            shift_id = content.get("shift_id")
            if not shift_id:
                await self._send_error(message.sender_id, "shift_id required", message.message_type)
                return
            impact = await self._paradigm_detector.get_cumulative_impact(shift_id)
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="cumulative_impact", content=impact, sender_id=self.agent_id
                ),
            )
        except Exception as e:
            logger.error("get_cumulative_impact_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get impact: {e!s}", message.message_type
            )

    def get_capabilities(self) -> list[str]:
        """Return list of capabilities this agent provides."""
        return [
            "change_management",
            "impact_analysis",
            "transition_planning",
            "version_management",
            "rollback_coordination",
            "stakeholder_notification",
        ]
