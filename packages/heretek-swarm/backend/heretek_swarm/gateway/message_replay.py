"""
Message Replay & Time Travel Debugging for Heretek Swarm.

This module provides comprehensive message replay capabilities:
- Replay messages from specific sequence number
- Replay messages within time range
- Filter replay by subject pattern
- Replay to different destination (for debugging)
- Track replay progress and completion
- Time travel debugging with state reconstruction

Replay API:
    POST /api/events/replay
    {
        "stream_name": "AGENT_EVENTS",
        "start_sequence": 1000,
        "end_sequence": 2000,
        "subject_filter": "agent.*.status",
        "destination_stream": "REPLAY_EVENTS",
        "replay_speed": 1.0  # 1.0 = real-time, 10.0 = 10x speed
    }
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class ReplayStatus(StrEnum):
    """Replay job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReplayJob:
    """
    Message replay job configuration and state.

    Attributes:
        job_id: Unique job identifier
        stream_name: Source stream name
        start_sequence: Start sequence number
        end_sequence: End sequence number
        subject_filter: Subject pattern filter
        destination_stream: Destination stream (for debugging)
        replay_speed: Speed multiplier (1.0 = real-time)
        status: Current job status
        progress: Current progress (messages replayed)
        total: Total messages to replay
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        error: Error message if failed
        metadata: Additional job metadata
    """

    job_id: str
    stream_name: str
    start_sequence: int | None
    end_sequence: int | None
    subject_filter: str | None
    destination_stream: str | None
    replay_speed: float
    status: ReplayStatus = ReplayStatus.PENDING
    progress: int = 0
    total: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "stream_name": self.stream_name,
            "start_sequence": self.start_sequence,
            "end_sequence": self.end_sequence,
            "subject_filter": self.subject_filter,
            "destination_stream": self.destination_stream,
            "replay_speed": self.replay_speed,
            "status": self.status.value,
            "progress": self.progress,
            "total": self.total,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def create(
        cls,
        stream_name: str,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        subject_filter: str | None = None,
        destination_stream: str | None = None,
        replay_speed: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> "ReplayJob":
        """Create a new replay job."""
        return cls(
            job_id=str(uuid4()),
            stream_name=stream_name,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            subject_filter=subject_filter,
            destination_stream=destination_stream,
            replay_speed=replay_speed,
            metadata=metadata or {},
        )

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total == 0:
            return 0.0
        return (self.progress / self.total) * 100.0


@dataclass
class TimeTravelRequest:
    """
    Time travel debugging request.

    Attributes:
        request_id: Unique request identifier
        entity_id: Entity to reconstruct
        entity_type: Entity type (agent, workflow)
        target_time: Target timestamp for reconstruction
        source_stream: Source stream name
        include_snapshots: Use snapshots if available
        destination: Replay destination (optional)
    """

    request_id: str
    entity_id: str
    entity_type: str
    target_time: datetime
    source_stream: str
    include_snapshots: bool = True
    destination: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "target_time": self.target_time.isoformat(),
            "source_stream": self.source_stream,
            "include_snapshots": self.include_snapshots,
            "destination": self.destination,
            "metadata": self.metadata,
        }

    @classmethod
    def create(
        cls,
        entity_id: str,
        entity_type: str,
        target_time: datetime,
        source_stream: str,
        include_snapshots: bool = True,
        destination: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "TimeTravelRequest":
        """Create a new time travel request."""
        return cls(
            request_id=str(uuid4()),
            entity_id=entity_id,
            entity_type=entity_type,
            target_time=target_time,
            source_stream=source_stream,
            include_snapshots=include_snapshots,
            destination=destination,
            metadata=metadata or {},
        )


class MessageReplayManager:
    """
    Message replay and time travel debugging manager.

    Provides:
    - Create and manage replay jobs
    - Time-based and sequence-based replay
    - Subject filtering
    - Replay to alternate destinations
    - Progress tracking
    - Time travel state reconstruction
    - Zero-trust security integration

    Example:
        ```python
        manager = MessageReplayManager(jetstream_manager)

        # Create replay job
        job = ReplayJob.create(
            stream_name="AGENT_EVENTS",
            start_sequence=1000,
            end_sequence=2000,
            subject_filter="agent.*.status",
            replay_speed=10.0,
        )

        # Execute replay
        await manager.execute_replay(job, callback)

        # Time travel debugging
        request = TimeTravelRequest.create(
            entity_id="agent-1",
            entity_type="Agent",
            target_time=datetime(2024, 1, 1, 12, 0),
            source_stream="AGENT_EVENTS",
        )
        state = await manager.time_travel(request, applier)
        ```
    """

    def __init__(
        self,
        jetstream_manager: Any | None = None,
        event_store: Any | None = None,
        zero_trust_enabled: bool = True,
    ):
        """
        Initialize message replay manager.

        Args:
            jetstream_manager: JetStream manager instance
            event_store: Event store instance
            zero_trust_enabled: Enable zero-trust security
        """
        self._js_manager = jetstream_manager
        self._event_store = event_store
        self._zero_trust_enabled = zero_trust_enabled

        # Active jobs
        self._jobs: dict[str, ReplayJob] = {}
        self._time_travel_requests: dict[str, TimeTravelRequest] = {}

        # Replay tasks
        self._replay_tasks: dict[str, asyncio.Task] = {}

        # Statistics
        self._stats = {
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "messages_replayed": 0,
            "time_travel_requests": 0,
        }

        logger.info("MessageReplayManager initialized")

    @property
    def active_jobs(self) -> list[ReplayJob]:
        """Get active replay jobs."""
        return [
            job
            for job in self._jobs.values()
            if job.status in (ReplayStatus.PENDING, ReplayStatus.RUNNING, ReplayStatus.PAUSED)
        ]

    @property
    def job_count(self) -> int:
        """Get total job count."""
        return len(self._jobs)

    async def create_replay_job(
        self,
        stream_name: str,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        subject_filter: str | None = None,
        destination_stream: str | None = None,
        replay_speed: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> ReplayJob:
        """
        Create a new replay job.

        Args:
            stream_name: Source stream name
            start_sequence: Start sequence number
            end_sequence: End sequence number
            start_time: Start timestamp (alternative to sequence)
            end_time: End timestamp (alternative to sequence)
            subject_filter: Subject pattern filter
            destination_stream: Destination for replay
            replay_speed: Speed multiplier
            metadata: Additional metadata

        Returns:
            Created replay job
        """
        job = ReplayJob.create(
            stream_name=stream_name,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            subject_filter=subject_filter,
            destination_stream=destination_stream,
            replay_speed=replay_speed,
            metadata=metadata,
        )

        # Add time-based filtering to metadata
        if start_time:
            job.metadata["start_time"] = start_time.isoformat()
        if end_time:
            job.metadata["end_time"] = end_time.isoformat()

        self._jobs[job.job_id] = job
        self._stats["jobs_created"] += 1

        logger.info(
            "Replay job created",
            job_id=job.job_id,
            stream=stream_name,
        )

        return job

    async def execute_replay(
        self,
        job: ReplayJob,
        message_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> bool:
        """
        Execute a replay job.

        Args:
            job: Replay job to execute
            message_callback: Optional callback for each message

        Returns:
            True if completed successfully
        """
        if job.job_id not in self._jobs:
            logger.error("Job not found: {job.job_id}")
            return False

        # Update job status
        job.status = ReplayStatus.RUNNING
        job.started_at = datetime.now(UTC)

        try:
            # Get messages to replay
            messages = await self._fetch_messages(job)
            job.total = len(messages)

            logger.info(
                "Replay started",
                job_id=job.job_id,
                total_messages=len(messages),
            )

            # Calculate delay based on replay speed
            base_delay = 0.1  # 100ms between messages at 1.0x speed
            delay = base_delay / job.replay_speed

            # Process messages
            for i, msg in enumerate(messages):
                if job.status == ReplayStatus.CANCELLED:
                    logger.info("Replay cancelled: {job.job_id}")
                    job.status = ReplayStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                    return False

                if job.status == ReplayStatus.PAUSED:
                    # Wait while paused
                    while job.status == ReplayStatus.PAUSED:
                        await asyncio.sleep(0.5)

                # Process message
                await self._process_message(job, msg, message_callback)
                job.progress = i + 1

                # Apply delay
                if delay > 0:
                    await asyncio.sleep(delay)

            # Complete job
            job.status = ReplayStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            self._stats["jobs_completed"] += 1
            self._stats["messages_replayed"] += len(messages)

            logger.info(
                "Replay completed",
                job_id=job.job_id,
                messages_replayed=len(messages),
            )

            return True

        except Exception as e:
            job.status = ReplayStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(UTC)
            self._stats["jobs_failed"] += 1

            logger.error(
                f"Replay failed: {job.job_id}",
                error=str(e),
            )
            return False

    async def _fetch_messages(self, job: ReplayJob) -> list[dict[str, Any]]:
        """Fetch messages for replay job."""
        if not self._js_manager:
            logger.warning("JetStream manager not available")
            return []

        # Use time-based filtering if specified
        start_time = None
        end_time = None

        if "start_time" in job.metadata:
            start_time = datetime.fromisoformat(job.metadata["start_time"])
        if "end_time" in job.metadata:
            end_time = datetime.fromisoformat(job.metadata["end_time"])

        # Fetch from JetStream
        messages = await self._js_manager.replay_messages(
            stream_name=job.stream_name,
            start_sequence=job.start_sequence,
            end_sequence=job.end_sequence,
            subject_filter=job.subject_filter,
        )

        # Apply time filtering if needed
        if start_time or end_time:
            filtered = []
            for msg in messages:
                msg_time = None
                if "timestamp" in msg:
                    msg_time = datetime.fromisoformat(msg["timestamp"])

                if start_time and msg_time and msg_time < start_time:
                    continue
                if end_time and msg_time and msg_time > end_time:
                    continue

                filtered.append(msg)

            messages = filtered

        return messages

    async def _process_message(
        self,
        job: ReplayJob,
        message: dict[str, Any],
        callback: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        """Process a single replay message."""
        subject = message.get("subject", "")
        data = message.get("data", {})

        # Publish to destination if specified
        if job.destination_stream and self._js_manager:
            dest_subject = f"replay.{subject}"
            await self._js_manager.publish(
                stream_name=job.destination_stream,
                subject=dest_subject,
                data={
                    "original_subject": subject,
                    "original_data": data,
                    "replay_job_id": job.job_id,
                    "replay_timestamp": datetime.now(UTC).isoformat(),
                },
            )

        # Call callback if provided
        if callback:
            if asyncio.iscoroutinefunction(callback):
                await callback(subject, data)
            else:
                callback(subject, data)

    async def pause_replay(self, job_id: str) -> bool:
        """Pause a running replay job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        if job.status == ReplayStatus.RUNNING:
            job.status = ReplayStatus.PAUSED
            logger.info("Replay paused: {job_id}")
            return True

        return False

    async def resume_replay(self, job_id: str) -> bool:
        """Resume a paused replay job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        if job.status == ReplayStatus.PAUSED:
            job.status = ReplayStatus.RUNNING
            logger.info("Replay resumed: {job_id}")
            return True

        return False

    async def cancel_replay(self, job_id: str) -> bool:
        """Cancel a replay job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        if job.status in (ReplayStatus.PENDING, ReplayStatus.RUNNING, ReplayStatus.PAUSED):
            job.status = ReplayStatus.CANCELLED
            job.completed_at = datetime.now(UTC)
            logger.info("Replay cancelled: {job_id}")
            return True

        return False

    def get_job(self, job_id: str) -> ReplayJob | None:
        """Get replay job by ID."""
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[ReplayJob]:
        """Get all replay jobs."""
        return list(self._jobs.values())

    async def create_time_travel_request(
        self,
        entity_id: str,
        entity_type: str,
        target_time: datetime,
        source_stream: str,
        include_snapshots: bool = True,
        destination: str | None = None,
    ) -> TimeTravelRequest:
        """
        Create a time travel debugging request.

        Args:
            entity_id: Entity to reconstruct
            entity_type: Entity type
            target_time: Target timestamp
            source_stream: Source stream
            include_snapshots: Use snapshots
            destination: Optional destination

        Returns:
            Created time travel request
        """
        request = TimeTravelRequest.create(
            entity_id=entity_id,
            entity_type=entity_type,
            target_time=target_time,
            source_stream=source_stream,
            include_snapshots=include_snapshots,
            destination=destination,
        )

        self._time_travel_requests[request.request_id] = request
        self._stats["time_travel_requests"] += 1

        logger.info(
            "Time travel request created",
            request_id=request.request_id,
            entity_id=entity_id,
            target_time=target_time,
        )

        return request

    async def execute_time_travel(
        self,
        request: TimeTravelRequest,
        state_applier: Callable[[dict[str, Any], Any], dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Execute time travel state reconstruction.

        Args:
            request: Time travel request
            state_applier: Function to apply events to state

        Returns:
            Reconstructed state at target time
        """
        if not self._event_store:
            logger.warning("Event store not available for time travel")
            return {}

        logger.info(
            "Time travel started",
            request_id=request.request_id,
            entity_id=request.entity_id,
            target_time=request.target_time,
        )

        # Get snapshot if available and requested
        initial_state = {}
        from_version = 0

        if request.include_snapshots:
            snapshot = await self._event_store.get_snapshot(request.entity_id)
            if snapshot and snapshot.created_at <= request.target_time:
                initial_state = snapshot.state.copy()
                from_version = snapshot.version
                logger.debug(
                    "Using snapshot",
                    version=from_version,
                    time=snapshot.created_at,
                )

        # Get events up to target time
        events = await self._event_store.get_events(
            request.entity_id,
            from_version=from_version,
        )

        # Filter events by target time
        filtered_events = [e for e in events if e.timestamp <= request.target_time]

        # Apply events
        state = initial_state
        for event in filtered_events:
            state = state_applier(state, event)

        logger.info(
            "Time travel completed",
            request_id=request.request_id,
            events_applied=len(filtered_events),
        )

        return state

    async def get_stats(self) -> dict[str, Any]:
        """Get replay manager statistics."""
        return {
            **self._stats,
            "active_jobs": len(self.active_jobs),
            "total_jobs": self.job_count,
            "time_travel_requests": len(self._time_travel_requests),
        }


# Module singleton
_replay_manager: MessageReplayManager | None = None


def get_replay_manager() -> MessageReplayManager | None:
    """Get or create the replay manager singleton.

    Phase 2A.3 cutover: this used to live in
    ``api/observability/__init__.py``; relocated to ``gateway.message_replay``
    so the api package stops depending on the deleted SwarmMetricsCollector
    (it lived in the same __init__.py and forced the import order).

    On first call, the manager is created and (if available) wired up
    with the JetStream manager and event store. Returns ``None`` if the
    optional dependencies are missing in the test environment.
    """
    global _replay_manager
    if _replay_manager is None:
        _replay_manager = MessageReplayManager()
        try:
            from heretek_swarm.gateway.jetstream_manager import get_jetstream_manager
            from heretek_swarm.state.event_store import get_event_store

            _replay_manager._js_manager = get_jetstream_manager()
            _replay_manager._event_store = get_event_store()
        except ImportError:
            # Some test environments don't have these wired up.
            pass
    return _replay_manager


async def setup_replay_manager(
    jetstream_manager: Any | None = None,
    event_store: Any | None = None,
) -> MessageReplayManager:
    """
    Setup and initialize replay manager.

    Args:
        jetstream_manager: JetStream manager instance
        event_store: Event store instance

    Returns:
        Initialized MessageReplayManager
    """
    global _replay_manager
    _replay_manager = MessageReplayManager(
        jetstream_manager=jetstream_manager,
        event_store=event_store,
    )
    return _replay_manager
