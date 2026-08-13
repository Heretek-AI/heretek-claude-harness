"""
Chronos Agent - Temporal & Scheduling Specialist.

This module contains the ChronosAgent class which inherits from:
- ChronosSchedulerMixin (5 scheduling methods)
- ChronosHandlersMixin (10 message handlers)
- ValidationMixin
- PatternMixin
- DeliberationMixin
- MemoryMixin
- LearningMixin
- AgentActor

INTG-04: Time perception & dilation integration included.
"""

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.actors.validation import validate_message

# Sentinel values for repeated error message literals
_MSG_TIME_PERCEPTION_NOT_ENABLED = "Time perception not enabled"
_MSG_INVALID_CONTEXT_ID = "Invalid context_id"

# INTG-04: Time Perception & Dilation
from heretek_swarm.coordination.time_dilation import (  # noqa: E402
    AnchorSource,
    ExecutionContext,
    OverloadDetector,
    TimeDilationCalculator,
    TimePerceptionManager,
)

from .handlers import ChronosHandlersMixin  # noqa: E402
from .scheduler import ChronosSchedulerMixin  # noqa: E402

if TYPE_CHECKING:
    from .types import Deadline, ScheduledTask

logger = structlog.get_logger(__name__)


class ChronosAgent(
    ChronosSchedulerMixin,
    ChronosHandlersMixin,
    ValidationMixin,
    PatternMixin,
    DeliberationMixin,
    MemoryMixin,
    LearningMixin,
    AgentActor,
):
    """
    Temporal & Scheduling Specialist.

    Responsibilities:
    - Schedule and execute time-based tasks
    - Manage deadlines and send warnings
    - Coordinate temporal activities across agents
    - Maintain calendars and timelines
    - Provide time-based analytics

    INTG-04 Time Perception Integration:
    - Execution context tracking
    - Time dilation calculation
    - Overload detection
    - Reality anchoring
    - Adaptive timeout

    Message Handlers:
    - schedule_task: Schedule a new task
    - cancel_task: Cancel a scheduled task
    - pause_task: Pause a scheduled task
    - resume_task: Resume a paused task
    - get_task_status: Get status of a scheduled task
    - set_deadline: Set a deadline
    - check_deadline: Check deadline status
    - get_timeline: Get timeline of scheduled items
    - get_schedule: Get schedule for time range
    - register_reminder: Register a time-based reminder
    """

    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(
            agent_id=agent_id or f"chronos_{uuid.uuid4().hex[:8]}",
            config=config or {},
        )

        self._config: dict[str, Any] = {}

        # Task scheduling
        self._tasks: dict[str, ScheduledTask] = {}
        self._task_queue: list[tuple[datetime, str]] = []  # (scheduled_at, task_id)
        self._max_tasks: int = self._config.get("max_tasks", 1000)

        # Deadlines
        self._deadlines: dict[str, Deadline] = {}
        self._max_deadlines: int = self._config.get("max_deadlines", 500)

        # Scheduler control
        self._scheduler_running: bool = False
        self._scheduler_task: asyncio.Task | None = None
        self._check_interval: float = self._config.get("check_interval", 1.0)  # seconds

        # Calendars
        self._calendars: dict[str, list[str]] = {}  # calendar_id -> task_ids

        # INTG-04: Time perception manager
        self._time_manager: TimePerceptionManager | None = None
        self._dilation_calculator: TimeDilationCalculator | None = None
        self._overload_detector: OverloadDetector | None = None
        self._execution_contexts: dict[str, ExecutionContext] = {}

        # INTG-04: Configuration
        self._enable_time_dilation: bool = self._config.get("enable_time_dilation", True)
        self._anchor_interval_seconds: float = self._config.get("anchor_interval", 300)
        self._overload_threshold: float = self._config.get("overload_threshold", 0.8)
        self._max_contexts: int = self._config.get("max_contexts", 500)

        # Register handlers
        self._register_handlers()

        logger.info(
            "chronos_initialized",
            agent_id=self.agent_id,
            max_tasks=self._max_tasks,
            check_interval=self._check_interval,
        )

    def _register_handlers(self) -> None:
        """Register all message handlers."""
        self._message_handlers = {
            # Task scheduling handlers
            "schedule_task": self._handle_schedule_task,
            "cancel_task": self._handle_cancel_task,
            "pause_task": self._handle_pause_task,
            "resume_task": self._handle_resume_task,
            "get_task_status": self._handle_get_task_status,
            # Tick generation
            "generate_ticks": self._handle_generate_ticks,
            # Deadline handlers
            "set_deadline": self._handle_set_deadline,
            "check_deadline": self._handle_check_deadline,
            # Timeline handlers
            "get_timeline": self._handle_get_timeline,
            "get_schedule": self._handle_get_schedule,
            "register_reminder": self._handle_register_reminder,
            # INTG-04: Time perception handlers
            "create_context": self._handle_create_context,
            "update_context": self._handle_update_context,
            "checkpoint_context": self._handle_checkpoint_context,
            "get_context_status": self._handle_get_context_status,
            "get_metrics": self._handle_get_metrics,
            "anchor_time": self._handle_anchor_time,
            "get_adaptive_timeout": self._handle_get_adaptive_timeout,
            "delegate_context": self._handle_delegate,
        }

    async def initialize(self) -> None:
        """Initialize the Chronos agent."""
        await super().initialize()

        # INTG-04: Initialize time perception components
        if self._enable_time_dilation:
            self._time_manager = TimePerceptionManager(
                max_contexts=self._max_contexts,
                drift_threshold_seconds=5.0,
                anchor_interval=timedelta(seconds=self._anchor_interval_seconds),
            )
            self._dilation_calculator = TimeDilationCalculator()
            self._overload_detector = OverloadDetector()
            self._execution_contexts = {}

        self._scheduler_running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        logger.info("chronos_scheduler_started")

    async def terminate(self) -> None:
        """Terminate the Chronos agent."""
        self._scheduler_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
            self._scheduler_task = None
            logger.info("chronos_scheduler_stopped")
        await super().terminate()

    async def _validate_message(self, message: ActorMessage) -> dict[str, Any]:
        """Validate incoming message content."""
        try:
            validated = validate_message(message.message_type, message.content)
            if hasattr(validated, "dict"):
                return validated.dict()
            return validated
        except Exception as e:
            logger.debug("chronos_message_parse_failed", error=str(e))
            return message.content

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

    # INTG-04: Time Perception Handlers

    async def _handle_create_context(self, message: ActorMessage) -> None:
        """
        Create a long-running execution context.

        Content: {
            "agent_id": str,
            "task_id": str,
            "expected_duration": str | None (ISO8601 timedelta),
            "deadline": str | None (ISO8601 datetime),
            "priority": int | None (1-5),
            "metadata": dict | None,
        }

        Returns: {
            "context": ExecutionContext.to_dict(),
            "context_id": str,
        }
        """
        try:
            content = await self._validate_message(message)

            if not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_TIME_PERCEPTION_NOT_ENABLED,
                    message.message_type,
                )
                return

            agent_id = content.get("agent_id", message.sender_id)
            task_id = content.get("task_id", f"task_{uuid.uuid4().hex[:12]}")

            expected_duration = None
            if content.get("expected_duration"):
                td_match = content["expected_duration"]
                if "hour" in td_match:
                    hours = float(td_match.replace("hour", "").strip())
                    expected_duration = timedelta(hours=hours)
                elif "minute" in td_match:
                    minutes = float(td_match.replace("minute", "").strip())
                    expected_duration = timedelta(minutes=minutes)
                elif "second" in td_match:
                    seconds = float(td_match.replace("second", "").strip())
                    expected_duration = timedelta(seconds=seconds)

            deadline = None
            if content.get("deadline"):
                deadline = datetime.fromisoformat(content["deadline"])

            metadata = content.get("metadata", {})
            metadata["priority"] = content.get("priority", 2)

            context = self._time_manager.create_context(
                agent_id=agent_id,
                task_id=task_id,
                expected_duration=expected_duration,
                deadline=deadline,
                metadata=metadata,
            )

            self._execution_contexts[context.context_id] = context

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="execution_context_created",
                    content={
                        "context": context.to_dict(),
                        "context_id": context.context_id,
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("create_context_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to create context: {e!s}",
                message.message_type,
            )

    async def _handle_update_context(self, message: ActorMessage) -> None:
        """
        Update execution context progress.

        Content: {
            "context_id": str,
            "progress_percent": float,
            "status": str | None,
            "time_dilation_factor": float | None,
            "metadata": dict | None,
        }
        """
        try:
            content = await self._validate_message(message)
            context_id = content.get("context_id")

            if not context_id or not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_INVALID_CONTEXT_ID,
                    message.message_type,
                )
                return

            updated = self._time_manager.update_context(
                context_id=context_id,
                progress_percent=content.get("progress_percent"),
                status=content.get("status"),
                time_dilation_factor=content.get("time_dilation_factor"),
                metadata=content.get("metadata"),
            )

            if updated:
                context = self._time_manager.get_context(context_id)
                if context:
                    self._execution_contexts[context_id] = context

                await self.send(
                    message.sender_id,
                    ActorMessage(
                        message_type="execution_context_updated",
                        content={"context_id": context_id, "success": True},
                        sender_id=self.agent_id,
                    ),
                )
            else:
                await self._send_error(
                    message.sender_id,
                    f"Context {context_id} not found",
                    message.message_type,
                )

        except Exception as e:
            logger.error("update_context_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to update context: {e!s}",
                message.message_type,
            )

    async def _handle_checkpoint_context(self, message: ActorMessage) -> None:
        """
        Create a checkpoint for context recovery.

        Content: {"context_id": str}

        Returns: Checkpoint data for persistence
        """
        try:
            content = await self._validate_message(message)
            context_id = content.get("context_id")

            if not context_id or not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_INVALID_CONTEXT_ID,
                    message.message_type,
                )
                return

            checkpoint = self._time_manager.checkpoint_context(context_id)

            if checkpoint:
                await self.send(
                    message.sender_id,
                    ActorMessage(
                        message_type="context_checkpoint",
                        content={"checkpoint": checkpoint},
                        sender_id=self.agent_id,
                    ),
                )
            else:
                await self._send_error(
                    message.sender_id,
                    f"Context {context_id} not found",
                    message.message_type,
                )

        except Exception as e:
            logger.error("checkpoint_context_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to checkpoint context: {e!s}",
                message.message_type,
            )

    async def _handle_get_context_status(self, message: ActorMessage) -> None:
        """
        Get status of an execution context.

        Content: {"context_id": str}

        Returns: {
            "context": ExecutionContext.to_dict(),
            "wallclock_elapsed": str,
            "subjective_elapsed": str,
            "time_remaining": str | None,
            "is_at_risk": bool,
        }
        """
        try:
            content = await self._validate_message(message)
            context_id = content.get("context_id")

            if not context_id or not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_INVALID_CONTEXT_ID,
                    message.message_type,
                )
                return

            context = self._time_manager.get_context(context_id)

            if context:
                await self.send(
                    message.sender_id,
                    ActorMessage(
                        message_type="context_status",
                        content={
                            "context": context.to_dict(),
                            "wallclock_elapsed": str(context.wallclock_elapsed),
                            "subjective_elapsed": str(context.subjective_elapsed),
                            "time_remaining": (
                                str(context.time_remaining) if context.time_remaining else None
                            ),
                            "is_at_risk": context.is_at_risk,
                        },
                        sender_id=self.agent_id,
                    ),
                )
            else:
                await self._send_error(
                    message.sender_id,
                    f"Context {context_id} not found",
                    message.message_type,
                )

        except Exception as e:
            logger.error("get_context_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get context status: {e!s}",
                message.message_type,
            )

    async def _handle_get_metrics(self, message: ActorMessage) -> None:
        """
        Get time perception metrics.

        Returns: TimePerceptionMetrics.to_dict()
        """
        try:
            if not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_TIME_PERCEPTION_NOT_ENABLED,
                    message.message_type,
                )
                return

            metrics = self._time_manager.get_perception_metrics()

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="time_perception_metrics",
                    content=metrics.to_dict(),
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_metrics_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get metrics: {e!s}",
                message.message_type,
            )

    async def _handle_anchor_time(self, message: ActorMessage) -> None:
        """
        Anchor time perception to external source.

        Content: {"source": str}  # system_clock, ntp_server, coordinator

        Returns: Anchoring result
        """
        try:
            content = await self._validate_message(message)
            source_str = content.get("source", "system_clock")

            try:
                source = AnchorSource(source_str)
            except ValueError:
                source = AnchorSource.SYSTEM_CLOCK

            if not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_TIME_PERCEPTION_NOT_ENABLED,
                    message.message_type,
                )
                return

            result = await self._time_manager.anchor_time(source)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="time_anchored",
                    content=result,
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("anchor_time_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to anchor time: {e!s}",
                message.message_type,
            )

    async def _handle_get_adaptive_timeout(self, message: ActorMessage) -> None:
        """
        Get adaptive timeout for an operation.

        Content: {
            "operation": str,
            "retry_count": int,
            "context_id": str | None,
        }

        Returns: {
            "timeout_seconds": float,
            "timeout_recommended": str,
        }
        """
        try:
            content = await self._validate_message(message)
            operation = content.get("operation", "default")
            retry_count = content.get("retry_count", 0)
            context_id = content.get("context_id")

            if not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_TIME_PERCEPTION_NOT_ENABLED,
                    message.message_type,
                )
                return

            timeout = self._time_manager.calculate_adaptive_timeout(
                operation=operation,
                retry_count=retry_count,
                context_id=context_id,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="adaptive_timeout",
                    content={
                        "timeout_seconds": timeout.total_seconds(),
                        "timeout_recommended": str(timeout),
                        "operation": operation,
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_adaptive_timeout_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get adaptive timeout: {e!s}",
                message.message_type,
            )

    async def _handle_delegate(self, message: ActorMessage) -> None:
        """
        Delegate context to Coordinator when overloaded.

        Content: {
            "context_id": str,
            "reason": str,
            "fallback_action": str | None,
        }
        """
        try:
            content = await self._validate_message(message)
            context_id = content.get("context_id")
            reason = content.get("reason", "Chronos overloaded")
            fallback_action = content.get("fallback_action", "reschedule")

            if not self._time_manager:
                await self._send_error(
                    message.sender_id,
                    _MSG_TIME_PERCEPTION_NOT_ENABLED,
                    message.message_type,
                )
                return

            result = await self._time_manager.delegate_to_coordinator(
                context_id=context_id,
                reason=reason,
                fallback_action=fallback_action,
            )

            if result.get("delegated") and context_id in self._execution_contexts:
                del self._execution_contexts[context_id]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="delegation_result",
                    content=result,
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("delegate_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to delegate: {e!s}",
                message.message_type,
            )

    # INTG-04: Helper Methods

    async def _check_context_deadlines(self) -> None:
        """Check execution context deadlines and send warnings."""
        if not self._time_manager:
            return

        for context in self._execution_contexts.values():
            if context.status != "running":
                continue

            if context.is_at_risk:
                await self._send_context_warning(context)

            if context.time_remaining and context.time_remaining.total_seconds() <= 0:
                await self._handle_context_deadline_miss(context)

    def _update_overload_state(self) -> None:
        """Update overload detection based on current load."""
        if not self._time_manager:
            return

        active_count = sum(1 for c in self._execution_contexts.values() if c.status == "running")
        load = active_count / self._max_contexts if self._max_contexts > 0 else 0

        self._time_manager.update_load(load)

    def _should_delegate(self) -> bool:
        """Check if delegation is needed."""
        if not self._time_manager:
            return False

        should_del, _ = self._time_manager.should_delegate()
        return bool(should_del)

    async def _handle_overload_delegation(self) -> None:
        """Delegate low-priority contexts to Coordinator."""
        if not self._time_manager:
            return

        delegatable = [
            c
            for c in self._execution_contexts.values()
            if c.status == "running" and c.metadata.get("priority", 2) <= 2
        ]

        if delegatable:
            context = delegatable[0]
            await self._time_manager.delegate_to_coordinator(
                context.context_id,
                "Chronos overloaded",
            )
            if context.context_id in self._execution_contexts:
                del self._execution_contexts[context.context_id]

    async def _send_context_warning(self, context: ExecutionContext) -> None:
        """Send warning about at-risk context."""
        await self.send(
            context.agent_id,
            ActorMessage(
                message_type="context_at_risk",
                content={
                    "context_id": context.context_id,
                    "task_id": context.task_id,
                    "time_remaining": str(context.time_remaining),
                    "progress_percent": context.progress_percent,
                    "deadline": (context.deadline.isoformat() if context.deadline else None),
                },
                sender_id=self.agent_id,
            ),
        )

    async def _handle_context_deadline_miss(self, context: ExecutionContext) -> None:
        """Handle a missed deadline for an execution context."""
        if self._time_manager:
            self._time_manager.fail_context(context.context_id, "Deadline missed")

        await self.send(
            context.agent_id,
            ActorMessage(
                message_type="context_deadline_missed",
                content={
                    "context_id": context.context_id,
                    "task_id": context.task_id,
                    "missed_at": datetime.now(UTC).isoformat(),
                },
                sender_id=self.agent_id,
            ),
        )

    def get_capabilities(self) -> list[str]:
        """Return list of capabilities this agent provides."""
        capabilities = [
            "task_scheduling",
            "deadline_management",
            "temporal_coordination",
            "calendar_management",
            "timeline_tracking",
            "reminder_service",
            "tick_generation",
        ]

        # INTG-04: Add time perception capabilities
        if self._enable_time_dilation:
            capabilities.extend(
                [
                    "execution_context_tracking",
                    "time_perception_management",
                    "adaptive_timeout",
                    "reality_anchoring",
                    "overload_detection",
                    "context_delegation",
                ]
            )

        return capabilities
