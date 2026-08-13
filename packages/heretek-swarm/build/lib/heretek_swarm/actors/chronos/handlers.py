"""
Chronos Handlers - Message handlers for temporal & scheduling management.

Extracted from chronos.py (INTG-04).
Contains 10 handlers organized as a mixin for cooperative MRO.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog

from heretek_swarm.actors.base import ActorMessage

logger = structlog.get_logger("ChronosHandlersMixin")


class ChronosHandlersMixin:
    """
    Message handler mixin for ChronosAgent.

    Provides all 10 handlers for task scheduling, deadline management,
    and timeline operations. Uses cooperative MRO with super().__init__().
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _handle_schedule_task(self, message: ActorMessage) -> None:
        """
        Schedule a new task.

        Content:
        - task_id: Optional[str]
        - name: str
        - description: str
        - scheduled_at: str (ISO8601)
        - priority: Optional[int] (1-5)
        - recurrence: Optional[str] (once|hourly|daily|weekly|monthly|yearly|interval|cron)
        - recurrence_config: Optional[Dict]
        - target_agents: Optional[List[str]]
        - action: Optional[str]
        - payload: Optional[Dict]
        - deadline: Optional[str] (ISO8601)
        - max_runs: Optional[int]
        - metadata: Optional[Dict]
        """
        try:
            content = await self._validate_message(message)

            if len(self._tasks) >= self._max_tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task limit reached ({self._max_tasks})",
                    message.message_type,
                )
                return

            task_id = content.get("task_id") or f"task_{uuid.uuid4().hex[:12]}"

            if task_id in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} already exists",
                    message.message_type,
                )
                return

            scheduled_at_str = content.get("scheduled_at")
            scheduled_at = (
                datetime.fromisoformat(scheduled_at_str) if scheduled_at_str else datetime.now(UTC)
            )

            from .types import Priority, RecurrenceType, ScheduledTask

            recurrence_str = content.get("recurrence")
            recurrence = RecurrenceType(recurrence_str) if recurrence_str else RecurrenceType.ONCE

            priority_value = content.get("priority", 2)
            priority = Priority(min(max(priority_value, 1), 5))

            task = ScheduledTask(
                task_id=task_id,
                name=content.get("name", "Untitled Task"),
                description=content.get("description", ""),
                scheduled_at=scheduled_at,
                priority=priority,
                recurrence=recurrence,
                recurrence_config=content.get("recurrence_config", {}),
                target_agents=content.get("target_agents", []),
                action=content.get("action", "scheduled_task"),
                payload=content.get("payload", {}),
                deadline=datetime.fromisoformat(content["deadline"])
                if content.get("deadline")
                else None,
                max_runs=content.get("max_runs"),
                metadata=content.get("metadata", {}),
            )

            self._tasks[task_id] = task
            self._task_queue.append((scheduled_at, task_id))

            logger.info(
                "task_scheduled",
                task_id=task_id,
                name=task.name,
                scheduled_at=scheduled_at.isoformat(),
                recurrence=recurrence.value,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_scheduled",
                    content={"task": task.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("schedule_task_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to schedule task: {e!s}",
                message.message_type,
            )

    async def _handle_cancel_task(self, message: ActorMessage) -> None:
        """
        Cancel a scheduled task.

        Content:
        - task_id: str
        """
        try:
            content = await self._validate_message(message)
            task_id = content.get("task_id")

            from .types import ScheduleStatus

            if not task_id or task_id not in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} not found",
                    message.message_type,
                )
                return

            task = self._tasks[task_id]

            if task.status in (ScheduleStatus.COMPLETED, ScheduleStatus.CANCELLED):
                await self._send_error(
                    message.sender_id,
                    f"Task already in {task.status.value} state",
                    message.message_type,
                )
                return

            task.status = ScheduleStatus.CANCELLED

            # Remove from queue
            self._task_queue = [(t, tid) for t, tid in self._task_queue if tid != task_id]

            logger.info("task_cancelled", task_id=task_id)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_cancelled",
                    content={"task_id": task_id},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("cancel_task_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to cancel task: {e!s}",
                message.message_type,
            )

    async def _handle_pause_task(self, message: ActorMessage) -> None:
        """
        Pause a scheduled task.

        Content:
        - task_id: str
        """
        try:
            content = await self._validate_message(message)
            task_id = content.get("task_id")

            from .types import ScheduleStatus

            if not task_id or task_id not in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} not found",
                    message.message_type,
                )
                return

            task = self._tasks[task_id]

            if task.status not in (ScheduleStatus.PENDING, ScheduleStatus.ACTIVE):
                await self._send_error(
                    message.sender_id,
                    f"Cannot pause task in {task.status.value} state",
                    message.message_type,
                )
                return

            task.status = ScheduleStatus.PAUSED

            # Remove from queue while paused
            self._task_queue = [(t, tid) for t, tid in self._task_queue if tid != task_id]

            logger.info("task_paused", task_id=task_id)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_paused",
                    content={"task_id": task_id},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("pause_task_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to pause task: {e!s}",
                message.message_type,
            )

    async def _handle_resume_task(self, message: ActorMessage) -> None:
        """
        Resume a paused task.

        Content:
        - task_id: str
        """
        try:
            content = await self._validate_message(message)
            task_id = content.get("task_id")

            from .types import ScheduleStatus

            if not task_id or task_id not in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} not found",
                    message.message_type,
                )
                return

            task = self._tasks[task_id]

            if task.status != ScheduleStatus.PAUSED:
                await self._send_error(
                    message.sender_id,
                    f"Task is not paused (current: {task.status.value})",
                    message.message_type,
                )
                return

            task.status = ScheduleStatus.PENDING
            self._task_queue.append((task.scheduled_at, task_id))

            logger.info("task_resumed", task_id=task_id)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_resumed",
                    content={"task_id": task_id},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("resume_task_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to resume task: {e!s}",
                message.message_type,
            )

    async def _handle_get_task_status(self, message: ActorMessage) -> None:
        """
        Get status of a scheduled task.

        Content:
        - task_id: str
        """
        try:
            content = await self._validate_message(message)
            task_id = content.get("task_id")

            if not task_id or task_id not in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} not found",
                    message.message_type,
                )
                return

            task = self._tasks[task_id]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_status",
                    content={"task": task.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_task_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get task status: {e!s}",
                message.message_type,
            )

    async def _handle_set_deadline(self, message: ActorMessage) -> None:
        """
        Set a deadline.

        Content:
        - deadline_id: Optional[str]
        - name: str
        - due_at: str (ISO8601)
        - assigned_to: Optional[List[str]]
        - warning_thresholds: Optional[List[str]] (e.g., ["1 day", "1 hour"])
        - metadata: Optional[Dict]
        """
        try:
            content = await self._validate_message(message)

            if len(self._deadlines) >= self._max_deadlines:
                await self._send_error(
                    message.sender_id,
                    f"Deadline limit reached ({self._max_deadlines})",
                    message.message_type,
                )
                return

            deadline_id = content.get("deadline_id") or f"deadline_{uuid.uuid4().hex[:12]}"

            if deadline_id in self._deadlines:
                await self._send_error(
                    message.sender_id,
                    f"Deadline {deadline_id} already exists",
                    message.message_type,
                )
                return

            from .types import Deadline

            due_at = datetime.fromisoformat(content.get("due_at", datetime.now(UTC).isoformat()))

            # Parse warning thresholds
            thresholds = []
            for threshold_str in content.get("warning_thresholds", ["1 hour"]):
                # Simple parsing - would need more robust implementation for production
                if "day" in threshold_str:
                    days = int(threshold_str.split()[0])
                    thresholds.append(timedelta(days=days))
                elif "hour" in threshold_str:
                    hours = int(threshold_str.split()[0])
                    thresholds.append(timedelta(hours=hours))
                elif "minute" in threshold_str:
                    minutes = int(threshold_str.split()[0])
                    thresholds.append(timedelta(minutes=minutes))

            deadline = Deadline(
                deadline_id=deadline_id,
                name=content.get("name", "Untitled Deadline"),
                due_at=due_at,
                assigned_to=content.get("assigned_to", []),
                warning_thresholds=thresholds,
                metadata=content.get("metadata", {}),
            )

            self._deadlines[deadline_id] = deadline

            logger.info(
                "deadline_set",
                deadline_id=deadline_id,
                name=deadline.name,
                due_at=due_at.isoformat(),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="deadline_set",
                    content={"deadline": deadline.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("set_deadline_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to set deadline: {e!s}",
                message.message_type,
            )

    async def _handle_check_deadline(self, message: ActorMessage) -> None:
        """
        Check deadline status.

        Content:
        - deadline_id: str
        """
        try:
            content = await self._validate_message(message)
            deadline_id = content.get("deadline_id")

            if not deadline_id or deadline_id not in self._deadlines:
                await self._send_error(
                    message.sender_id,
                    f"Deadline {deadline_id} not found",
                    message.message_type,
                )
                return

            deadline = self._deadlines[deadline_id]
            now = datetime.now(UTC)
            time_remaining = deadline.due_at - now

            # Update status
            if time_remaining.total_seconds() <= 0:
                deadline.status = "missed"
            else:
                deadline.status = "pending"

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="deadline_status",
                    content={
                        "deadline": deadline.to_dict(),
                        "time_remaining_seconds": time_remaining.total_seconds(),
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("check_deadline_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to check deadline: {e!s}",
                message.message_type,
            )

    async def _handle_get_timeline(self, message: ActorMessage) -> None:
        """
        Get timeline of scheduled items.

        Content:
        - limit: Optional[int]
        - status: Optional[str]
        """
        try:
            content = await self._validate_message(message)
            limit = min(content.get("limit", 50), 100)
            status_filter = content.get("status")

            from .types import ScheduleStatus

            tasks = list(self._tasks.values())

            # Filter by status
            if status_filter:
                try:
                    status = ScheduleStatus(status_filter)
                    tasks = [t for t in tasks if t.status == status]
                except ValueError:
                    logger.debug("Chronos handler value parsing fallback", exc_info=True)

            # Sort by scheduled_at
            tasks.sort(key=lambda t: t.scheduled_at)

            # Limit results
            tasks = tasks[:limit]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="timeline",
                    content={
                        "tasks": [t.to_dict() for t in tasks],
                        "count": len(tasks),
                        "total": len(self._tasks),
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_timeline_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get timeline: {e!s}",
                message.message_type,
            )

    async def _handle_get_schedule(self, message: ActorMessage) -> None:
        """
        Get schedule for a time range.

        Content:
        - start: str (ISO8601)
        - end: str (ISO8601)
        """
        try:
            content = await self._validate_message(message)
            start_str = content.get("start")
            end_str = content.get("end")

            start = datetime.fromisoformat(start_str) if start_str else datetime.now(UTC)
            end = datetime.fromisoformat(end_str) if end_str else start + timedelta(days=1)

            # Find tasks in range
            scheduled = [
                t.to_dict() for t in self._tasks.values() if start <= t.scheduled_at <= end
            ]

            scheduled.sort(key=lambda t: t["scheduled_at"])

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="schedule",
                    content={
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "tasks": scheduled,
                        "count": len(scheduled),
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_schedule_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get schedule: {e!s}",
                message.message_type,
            )

    async def _handle_register_reminder(self, message: ActorMessage) -> None:
        """
        Register a time-based reminder.

        Content:
        - reminder_id: Optional[str]
        - message: str
        - remind_at: str (ISO8601)
        - target_agents: Optional[List[str]]
        """
        try:
            content = await self._validate_message(message)

            from .types import ScheduledTask

            reminder_id = content.get("reminder_id") or f"reminder_{uuid.uuid4().hex[:12]}"
            remind_at_str = content.get("remind_at")
            remind_at = (
                datetime.fromisoformat(remind_at_str) if remind_at_str else datetime.now(UTC)
            )
            target_agents = content.get("target_agents", [message.sender_id])

            # Create as a scheduled task
            task = ScheduledTask(
                task_id=reminder_id,
                name="Reminder",
                description=content.get("message", ""),
                scheduled_at=remind_at,
                target_agents=target_agents,
                action="reminder",
                payload={"message": content.get("message", "")},
            )

            self._tasks[reminder_id] = task
            self._task_queue.append((remind_at, reminder_id))

            logger.info(
                "reminder_registered",
                reminder_id=reminder_id,
                remind_at=remind_at.isoformat(),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="reminder_registered",
                    content={"reminder": task.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("register_reminder_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to register reminder: {e!s}",
                message.message_type,
            )

    async def _handle_generate_ticks(self, message: ActorMessage) -> None:
        """
        Generate ticks from due PENDING tasks and return them.

        Receives no required payload.  Delegates to ``generate_ticks()``
        on the scheduler mixin and returns the serialised tick list.

        Returns:
            {"ticks": [tick.to_dict() for tick in ticks]}
        """
        try:
            ticks = await self.generate_ticks()
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="generate_ticks_result",
                    content={"ticks": [t.to_dict() for t in ticks]},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("generate_ticks_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to generate ticks: {e!s}",
                message.message_type,
            )
