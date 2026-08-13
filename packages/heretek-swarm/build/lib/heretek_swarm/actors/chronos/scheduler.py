"""
Chronos Scheduler - Scheduling methods for temporal management.

Extracted from chronos.py (INTG-04).
Contains scheduling loop and task execution methods as a mixin for cooperative MRO.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from heretek_swarm.actors.base import ActorMessage

from .types import Deadline, RecurrenceType, ScheduledTask, ScheduleStatus, Tick

if TYPE_CHECKING:
    from datetime import datetime

logger = structlog.get_logger("ChronosSchedulerMixin")


class ChronosSchedulerMixin:
    """
    Scheduler methods mixin for ChronosAgent.

    Provides scheduling loop, task execution, recurrence handling,
    deadline checking, and warning notifications.
    Uses cooperative MRO with super().__init__().
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _run_scheduler(self) -> None:
        """Main scheduler loop - checks and executes due tasks."""
        while self._scheduler_running:
            try:
                now = self._get_current_time()

                # Check for due tasks
                due_tasks = []
                remaining_queue = []

                for scheduled_at, task_id in self._task_queue:
                    if task_id in self._tasks:
                        task = self._tasks[task_id]
                        if task.status == ScheduleStatus.PENDING and scheduled_at <= now:
                            due_tasks.append(task)
                        else:
                            remaining_queue.append((scheduled_at, task_id))

                self._task_queue = remaining_queue

                # Execute due tasks
                for task in due_tasks:
                    await self._execute_task(task)

                # Check deadlines
                await self._check_deadlines()

                # INTG-04: Periodic anchoring check
                if self._time_manager and self._enable_time_dilation:
                    await self._time_manager.check_and_anchor()

                # INTG-04: Check context deadlines and update metrics
                await self._check_context_deadlines()

                # INTG-04: Update overload state
                self._update_overload_state()

                # INTG-04: Check if delegation needed
                if self._should_delegate():
                    await self._handle_overload_delegation()

                # Sort queue by time
                self._task_queue.sort(key=lambda x: x[0])

            except Exception as e:
                logger.error("scheduler_error", error=str(e))

            await asyncio.sleep(self._check_interval)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task."""
        try:
            task.status = ScheduleStatus.ACTIVE
            task.run_count += 1

            logger.info(
                "executing_scheduled_task",
                task_id=task.task_id,
                name=task.name,
                run_count=task.run_count,
            )

            # Notify target agents
            for agent_id in task.target_agents:
                await self.send(
                    agent_id,
                    ActorMessage(
                        message_type=task.action or "scheduled_task",
                        content={
                            "task_id": task.task_id,
                            "name": task.name,
                            "payload": task.payload,
                            "scheduled_at": task.scheduled_at.isoformat(),
                        },
                        sender_id=self.agent_id,
                    ),
                )

            task.status = ScheduleStatus.COMPLETED
            task.completed_at = self._get_current_time()

            # Handle recurrence
            if task.recurrence:
                await self._schedule_next_run(task)
            else:
                # Remove from queue if not recurring
                if task.task_id in self._task_queue:
                    self._task_queue.remove((task.scheduled_at, task.task_id))

        except Exception as e:
            logger.error("task_execution_failed", task_id=task.task_id, error=str(e))
            task.status = ScheduleStatus.FAILED

    async def _schedule_next_run(self, task: ScheduledTask) -> None:
        """Schedule the next run for a recurring task."""
        if not task.recurrence:
            return

        # Check max runs
        if task.max_runs and task.run_count >= task.max_runs:
            task.status = ScheduleStatus.COMPLETED
            return

        # Calculate next run time
        now = self._get_current_time()

        if task.recurrence == RecurrenceType.HOURLY:
            task.next_run = now + self._get_time_delta(hours=1)
        elif task.recurrence == RecurrenceType.DAILY:
            task.next_run = now + self._get_time_delta(days=1)
        elif task.recurrence == RecurrenceType.WEEKLY:
            task.next_run = now + self._get_time_delta(weeks=1)
        elif task.recurrence == RecurrenceType.MONTHLY:
            # Approximate: add 30 days
            task.next_run = now + self._get_time_delta(days=30)
        elif task.recurrence == RecurrenceType.YEARLY:
            task.next_run = now + self._get_time_delta(days=365)
        elif task.recurrence == RecurrenceType.INTERVAL:
            interval_seconds = task.recurrence_config.get("interval_seconds", 3600)
            task.next_run = now + self._get_time_delta(seconds=interval_seconds)
        elif task.recurrence == RecurrenceType.CRON:
            # Simple cron - would need full implementation for production
            task.next_run = now + self._get_time_delta(hours=1)

        if task.next_run:
            task.status = ScheduleStatus.PENDING
            task.scheduled_at = task.next_run
            self._task_queue.append((task.next_run, task.task_id))
            logger.info(
                "task_rescheduled",
                task_id=task.task_id,
                next_run=task.next_run.isoformat(),
            )

    async def _check_deadlines(self) -> None:
        """Check deadlines and send warnings."""
        now = self._get_current_time()

        for deadline in self._deadlines.values():
            if deadline.status != "pending":
                continue

            time_remaining = deadline.due_at - now

            if time_remaining.total_seconds() <= 0:
                deadline.status = "missed"
                logger.warning("deadline_missed", deadline_id=deadline.deadline_id)
                continue

            # Check warning thresholds
            for threshold in deadline.warning_thresholds:
                threshold_key = str(threshold)
                if threshold_key not in deadline.warnings_sent and time_remaining <= threshold:
                    deadline.warnings_sent.add(threshold_key)
                    await self._send_deadline_warning(deadline, threshold)

    async def _send_deadline_warning(self, deadline: Deadline, threshold) -> None:
        """Send deadline warning notification."""
        for agent_id in deadline.assigned_to:
            await self.send(
                agent_id,
                ActorMessage(
                    message_type="deadline_warning",
                    content={
                        "deadline_id": deadline.deadline_id,
                        "name": deadline.name,
                        "due_at": deadline.due_at.isoformat(),
                        "threshold": str(threshold),
                        "time_remaining": str(deadline.due_at - self._get_current_time()),
                    },
                    sender_id=self.agent_id,
                ),
            )

    async def generate_ticks(self) -> list[Tick]:
        """Generate ticks from due PENDING tasks.

        Iterates ``_task_queue``, finds tasks whose ``scheduled_at`` ≤ now
        and whose status is PENDING, converts each to a ``Tick``, marks the
        source task as ACTIVE, and returns the ticks ordered by
        ``scheduled_at``.

        Returns:
            An empty list when ``_task_queue`` is empty or no tasks are due.
        """
        from .types import ScheduleStatus, Tick

        now = self._get_current_time()
        ticks: list[Tick] = []
        remaining: list[tuple[datetime, str]] = []

        for scheduled_at, task_id in self._task_queue:
            task = self._tasks.get(task_id)
            if task is None:
                continue
            if task.status == ScheduleStatus.PENDING and scheduled_at <= now:
                tick = Tick(
                    tick_id=task.task_id,
                    agent_id=(task.target_agents[0] if task.target_agents else self.agent_id),
                    action=task.action or "scheduled_task",
                    scheduled_at=task.scheduled_at,
                    status=ScheduleStatus.PENDING,
                )
                task.status = ScheduleStatus.ACTIVE
                ticks.append(tick)
            else:
                remaining.append((scheduled_at, task_id))

        self._task_queue = remaining
        ticks.sort(key=lambda t: t.scheduled_at)
        return ticks

    # Helper methods for time access (allows override for testing)
    def _get_current_time(self):
        """Get current UTC time. Override in tests."""
        from datetime import UTC, datetime

        return datetime.now(UTC)

    def _get_time_delta(self, days=0, hours=0, minutes=0, seconds=0, weeks=0):
        """Get a timedelta. Override in tests."""
        from datetime import timedelta

        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds, weeks=weeks)
