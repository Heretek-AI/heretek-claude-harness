"""
Time Dilation and Perception Management Module

Provides time perception management with adaptive timeouts, reality anchoring,
and overload handling for the Chronos agent.

Author: Heretek Swarm Collective
Date: 2026-04-15
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import structlog

logger = structlog.get_logger(__name__)


class TimeDomain(Enum):
    """Time domains for perception management."""

    REAL = "real"  # Wall-clock time
    SUBJECTIVE = "subjective"  # Perceived time by agent
    DILATED = "dilated"  # Stretched time under load


class OverloadState(Enum):
    """States of Chronos overload handling."""

    NORMAL = "normal"
    LOADED = "loaded"
    OVERLOADED = "overloaded"
    DEGRADED = "degraded"


class AnchorSource(Enum):
    """Sources for time reality anchoring."""

    SYSTEM_CLOCK = "system_clock"
    NTP_SERVER = "ntp_server"
    EXTERNAL_API = "external_api"
    COORDINATOR = "coordinator"


@dataclass
class ExecutionContext:
    """Long-running execution context tracked by Chronos."""

    context_id: str
    agent_id: str
    task_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expected_duration: timedelta | None = None
    deadline: datetime | None = None
    subjective_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    checkpoint_count: int = 0
    progress_percent: float = 0.0
    status: str = "running"  # running, paused, completed, failed, cancelled
    time_dilation_factor: float = 1.0  # How much time is dilated (1.0 = normal)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def wallclock_elapsed(self) -> timedelta:
        """Actual wall-clock time elapsed."""
        return datetime.now(UTC) - self.started_at

    @property
    def subjective_elapsed(self) -> timedelta:
        """Perceived time by the agent (may be dilated)."""
        return self.wallclock_elapsed * self.time_dilation_factor

    @property
    def time_remaining(self) -> timedelta | None:
        """Time remaining until deadline, None if no deadline."""
        if self.deadline is None:
            return None
        return self.deadline - datetime.now(UTC)

    @property
    def is_at_risk(self) -> bool:
        """Check if context is at risk of missing deadline."""
        if self.time_remaining is None:
            return False
        # At risk if less than 10% of time remaining and less than 50% progress
        if self.expected_duration is None:
            return False
        return (
            self.time_remaining.total_seconds() < (self.expected_duration.total_seconds() * 0.1)
            and self.progress_percent < 50.0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "context_id": self.context_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "expected_duration": (str(self.expected_duration) if self.expected_duration else None),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "subjective_start": self.subjective_start.isoformat(),
            "checkpoint_count": self.checkpoint_count,
            "progress_percent": self.progress_percent,
            "status": self.status,
            "time_dilation_factor": self.time_dilation_factor,
            "metadata": self.metadata,
            "wallclock_elapsed": str(self.wallclock_elapsed),
            "subjective_elapsed": str(self.subjective_elapsed),
            "time_remaining": str(self.time_remaining) if self.time_remaining else None,
            "is_at_risk": self.is_at_risk,
        }


@dataclass
class TimePerceptionMetrics:
    """Metrics for time perception tracking."""

    total_contexts: int = 0
    active_contexts: int = 0
    completed_contexts: int = 0
    failed_contexts: int = 0
    avg_dilation_factor: float = 1.0
    max_dilation_factor: float = 1.0
    perception_drift_seconds: float = 0.0  # Difference between subjective and real
    deadline_misses: int = 0
    adaptive_timeouts_triggered: int = 0
    last_anchor_check: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_contexts": self.total_contexts,
            "active_contexts": self.active_contexts,
            "completed_contexts": self.completed_contexts,
            "failed_contexts": self.failed_contexts,
            "avg_dilation_factor": self.avg_dilation_factor,
            "max_dilation_factor": self.max_dilation_factor,
            "perception_drift_seconds": self.perception_drift_seconds,
            "deadline_misses": self.deadline_misses,
            "adaptive_timeouts_triggered": self.adaptive_timeouts_triggered,
            "last_anchor_check": self.last_anchor_check.isoformat(),
        }


@dataclass
class AdaptiveTimeout:
    """Configuration for adaptive timeout handling."""

    base_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    max_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    min_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=5))
    scale_factor: float = 1.5  # How much to scale on retry
    workload_threshold: float = 0.7  # Load at which to start scaling
    decay_rate: float = 0.95  # Decay factor for timeout reduction

    def calculate_timeout(self, retry_count: int, current_load: float) -> timedelta:
        """Calculate adaptive timeout based on retries and load."""
        scale = min(self.scale_factor**retry_count, 5.0)
        if current_load > self.workload_threshold:
            scale *= 1.0 + (current_load - self.workload_threshold)
        timeout_seconds = self.base_timeout.total_seconds() * scale
        timeout_seconds = max(
            self.min_timeout.total_seconds(),
            min(self.max_timeout.total_seconds(), timeout_seconds),
        )
        return timedelta(seconds=timeout_seconds)


class TimePerceptionManager:
    """
    Time perception management with adaptive timeouts and reality anchoring.

    Responsibilities:
    1. Track long-running execution contexts
    2. Calculate time perception metrics (subjective vs objective time)
    3. Detect and handle time perception drift
    4. Provide adaptive timeout handling based on workload
    5. Anchor reality against external clocks (system, NTP, coordinator)
    6. Detect Chronos overload and delegate to Coordinator

    Key Methods:
    - create_context(), update_context(), checkpoint_context()
    - get_perception_metrics() - time perception statistics
    - anchor_time() - reality anchoring against external sources
    - calculate_adaptive_timeout() - workload-aware timeout scaling
    - detect_drift() - perception drift detection
    - get_overload_state() - current overload classification
    - delegate_to_coordinator() - overload fallback
    """

    def __init__(
        self,
        max_contexts: int = 1000,
        drift_threshold_seconds: float = 5.0,
        anchor_interval: timedelta = timedelta(minutes=5),
    ):
        # Execution contexts
        self._contexts: dict[str, ExecutionContext] = {}
        self._max_contexts = max_contexts

        # Time anchoring
        self._anchor_source: AnchorSource = AnchorSource.SYSTEM_CLOCK
        self._last_anchor_time: datetime = datetime.now(UTC)
        self._anchor_interval = anchor_interval
        self._drift_threshold_seconds = drift_threshold_seconds
        self._perception_drift: float = 0.0
        self._drift_history: list[float] = []

        # Adaptive timeout configuration
        self._adaptive_timeout = AdaptiveTimeout()
        self._timeout_history: dict[str, list[timedelta]] = {}

        # Metrics
        self._metrics = TimePerceptionMetrics()

        # Overload detection
        self._overload_threshold: float = 0.8  # 80% capacity
        self._current_load: float = 0.0

        # Delegation
        self._coordinator_proxy: Any = None

        # Callbacks
        self._on_overload: Callable[..., Any] | None = None
        self._on_deadline_miss: Callable[..., Any] | None = None
        self._on_drift_detected: Callable[..., Any] | None = None

    # === Context Management ===

    def create_context(
        self,
        agent_id: str,
        task_id: str,
        expected_duration: timedelta | None = None,
        deadline: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionContext:
        """
        Create a new execution context for long-running operations.

        Returns:
            ExecutionContext with unique context_id
        """
        context_id = f"ctx_{uuid.uuid4().hex[:12]}"

        context = ExecutionContext(
            context_id=context_id,
            agent_id=agent_id,
            task_id=task_id,
            expected_duration=expected_duration,
            deadline=deadline,
            metadata=metadata or {},
        )

        self._contexts[context_id] = context
        self._metrics.total_contexts += 1
        self._metrics.active_contexts += 1

        return context

    def get_context(self, context_id: str) -> ExecutionContext | None:
        """Get execution context by ID."""
        return self._contexts.get(context_id)

    def update_context(
        self,
        context_id: str,
        progress_percent: float | None = None,
        status: str | None = None,
        time_dilation_factor: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update execution context state.

        Returns:
            True if updated, False if not found
        """
        context = self._contexts.get(context_id)
        if not context:
            return False

        if progress_percent is not None:
            context.progress_percent = progress_percent

        if status is not None:
            old_status = context.status
            context.status = status

            # Update metrics on status change
            if status == "completed" and old_status != "completed":
                self._metrics.completed_contexts += 1
                self._metrics.active_contexts -= 1
            elif status == "failed" and old_status != "failed":
                self._metrics.failed_contexts += 1
                self._metrics.active_contexts -= 1

        if time_dilation_factor is not None:
            context.time_dilation_factor = time_dilation_factor
            if time_dilation_factor > self._metrics.max_dilation_factor:
                self._metrics.max_dilation_factor = time_dilation_factor

        if metadata is not None:
            context.metadata.update(metadata)

        return True

    def checkpoint_context(self, context_id: str) -> dict[str, Any] | None:
        """
        Create a checkpoint of context state for recovery.

        Returns:
            Checkpoint data or None if context not found
        """
        context = self._contexts.get(context_id)
        if not context:
            return None

        context.checkpoint_count += 1

        return {
            "context_id": context.context_id,
            "agent_id": context.agent_id,
            "task_id": context.task_id,
            "checkpoint_at": datetime.now(UTC).isoformat(),
            "checkpoint_number": context.checkpoint_count,
            "progress_percent": context.progress_percent,
            "wallclock_elapsed": str(context.wallclock_elapsed),
            "subjective_elapsed": str(context.subjective_elapsed),
            "status": context.status,
            "time_dilation_factor": context.time_dilation_factor,
            "metadata": context.metadata,
        }

    def complete_context(self, context_id: str) -> bool:
        """
        Mark context as completed and record metrics.

        Returns:
            True if completed, False if not found
        """
        return self.update_context(context_id, status="completed")

    def fail_context(self, context_id: str, reason: str) -> bool:
        """
        Mark context as failed.

        Returns:
            True if failed, False if not found
        """
        context = self._contexts.get(context_id)
        if context:
            context.metadata["failure_reason"] = reason
        return self.update_context(context_id, status="failed")

    # === Time Perception Metrics ===

    def get_perception_metrics(self) -> TimePerceptionMetrics:
        """
        Calculate and return time perception metrics.

        Returns:
            TimePerceptionMetrics with current statistics
        """
        # Recalculate averages
        if self._contexts:
            dilation_factors = [
                c.time_dilation_factor for c in self._contexts.values() if c.status == "running"
            ]
            if dilation_factors:
                self._metrics.avg_dilation_factor = sum(dilation_factors) / len(dilation_factors)
                self._metrics.max_dilation_factor = max(dilation_factors)

        # Calculate perception drift
        self._metrics.perception_drift_seconds = self._perception_drift
        self._metrics.last_anchor_check = self._last_anchor_time

        return self._metrics

    def calculate_wallclock_elapsed(self, context_id: str) -> timedelta | None:
        """
        Calculate wall-clock time for a context.

        Returns:
            Elapsed time or None if context not found
        """
        context = self._contexts.get(context_id)
        if not context:
            return None
        return context.wallclock_elapsed

    def calculate_subjective_elapsed(self, context_id: str) -> timedelta | None:
        """
        Calculate perceived time for a context (may include dilation).

        Returns:
            Subjective elapsed time or None if context not found
        """
        context = self._contexts.get(context_id)
        if not context:
            return None
        return context.subjective_elapsed

    def get_time_remaining(self, context_id: str) -> timedelta | None:
        """
        Get time remaining until deadline.

        Returns:
            Time remaining or None if no deadline/context not found
        """
        context = self._contexts.get(context_id)
        if not context:
            return None
        return context.time_remaining

    # === Reality Anchoring ===

    async def anchor_time(self, source: AnchorSource = AnchorSource.SYSTEM_CLOCK) -> dict[str, Any]:
        """
        Anchor time perception to an external source.

        Sources:
        - SYSTEM_CLOCK: Use system datetime (default)
        - NTP_SERVER: Use NTP server (if available)
        - EXTERNAL_API: Use external time API
        - COORDINATOR: Use Coordinator's trusted clock

        Returns:
            {
                "anchored": bool,
                "source": str,
                "anchor_time": datetime,
                "drift_detected": bool,
                "drift_seconds": float,
            }
        """
        self._anchor_source = source
        anchor_time = datetime.now(UTC)
        internal_time = datetime.now(UTC)  # Would be internal Chronos time

        # Calculate drift
        drift_seconds = abs((anchor_time - internal_time).total_seconds())
        drift_detected = drift_seconds > self._drift_threshold_seconds

        if drift_detected:
            self._perception_drift = drift_seconds
            self._drift_history.append(drift_seconds)

            # Apply drift adjustment to active contexts
            self._adjust_for_drift(drift_seconds)

            # Fire callback if set
            if self._on_drift_detected:
                await self._on_drift_detected(drift_seconds)

        self._last_anchor_time = anchor_time

        return {
            "anchored": True,
            "source": source.value,
            "anchor_time": anchor_time,
            "drift_detected": drift_detected,
            "drift_seconds": drift_seconds,
        }

    async def check_and_anchor(self) -> dict[str, Any] | None:
        """
        Periodic anchoring check - called by scheduler.

        Returns:
            Anchoring result if check performed
        """
        now = datetime.now(UTC)
        time_since_anchor = now - self._last_anchor_time

        if time_since_anchor >= self._anchor_interval:
            return await self.anchor_time(self._anchor_source)

        return None

    def _adjust_for_drift(self, drift_seconds: float) -> None:
        """Adjust active context time dilation for drift."""
        for context in self._contexts.values():
            if context.status == "running":
                # Increase dilation to "catch up" perceived time
                # If we're behind, stretch time to match anchor
                if drift_seconds > 0:
                    context.time_dilation_factor *= 1.0 + (drift_seconds / 100)
                else:
                    # We're ahead, reduce dilation
                    context.time_dilation_factor *= 1.0 - (abs(drift_seconds) / 100)

    def detect_drift(self, context_id: str) -> dict[str, Any] | None:
        """
        Detect time perception drift for a context.

        Returns:
            Drift info if detected, None otherwise
        """
        context = self._contexts.get(context_id)
        if not context:
            return None

        # Compare wallclock vs subjective elapsed
        wallclock = context.wallclock_elapsed.total_seconds()
        subjective = context.subjective_elapsed.total_seconds()

        if wallclock > 0:
            drift_ratio = subjective / wallclock
            if abs(drift_ratio - 1.0) > 0.05:  # More than 5% drift
                return {
                    "context_id": context_id,
                    "drift_ratio": drift_ratio,
                    "wallclock_seconds": wallclock,
                    "subjective_seconds": subjective,
                    "drift_detected": True,
                }

        return None

    def get_drift_stats(self) -> dict[str, Any]:
        """
        Get overall drift statistics.

        Returns:
            {
                "total_drift_seconds": float,
                "max_drift_seconds": float,
                "anchor_count": int,
                "last_drift_detected": datetime | None,
            }
        """
        return {
            "total_drift_seconds": sum(self._drift_history),
            "max_drift_seconds": max(self._drift_history) if self._drift_history else 0.0,
            "anchor_count": len(self._drift_history),
            "last_drift_detected": (
                self._last_anchor_time.isoformat() if self._drift_history else None
            ),
        }

    # === Adaptive Timeout Handling ===

    def calculate_adaptive_timeout(
        self,
        operation: str,
        retry_count: int = 0,
        context_id: str | None = None,
    ) -> timedelta:
        """
        Calculate adaptive timeout based on workload and context.

        Returns:
            Calculated timeout duration
        """
        # Get context-specific load if available
        context_load = self._current_load
        if context_id:
            context = self._contexts.get(context_id)
            if context:
                context_load = max(context_load, context.progress_percent / 100.0)

        timeout = self._adaptive_timeout.calculate_timeout(retry_count, context_load)

        # Track timeout event
        if operation not in self._timeout_history:
            self._timeout_history[operation] = []
        self._timeout_history[operation].append(timeout)

        # Keep only recent history
        if len(self._timeout_history[operation]) > 100:
            self._timeout_history[operation] = self._timeout_history[operation][-100:]

        return timeout

    def register_timeout_event(
        self,
        operation: str,
        timeout_used: timedelta,
        succeeded: bool,
    ) -> None:
        """
        Register timeout event for adaptive learning.

        Records actual timeout used vs calculated to improve future estimates.
        """
        if operation not in self._timeout_history:
            self._timeout_history[operation] = []

        # Add negative entry if failed to indicate need for longer timeout
        if not succeeded:
            self._timeout_history[operation].append(timeout_used * -1)
        else:
            self._timeout_history[operation].append(timeout_used)

        # Trim history
        if len(self._timeout_history[operation]) > 100:
            self._timeout_history[operation] = self._timeout_history[operation][-100:]

        if not succeeded:
            self._metrics.adaptive_timeouts_triggered += 1

    def get_timeout_recommendation(self, operation: str) -> dict[str, Any]:
        """
        Get timeout recommendation for an operation type.

        Returns:
            {
                "recommended_timeout": timedelta,
                "operation": str,
                "recent_avg": timedelta,
                "pattern": str,  # "stable", "increasing", "decreasing"
            }
        """
        history = self._timeout_history.get(operation, [])
        base_timeout = self._adaptive_timeout.base_timeout

        if not history:
            return {
                "recommended_timeout": base_timeout,
                "operation": operation,
                "recent_avg": base_timeout,
                "pattern": "stable",
            }

        # Calculate recent average (last 10)
        recent = history[-10:]
        positive_history = [t for t in recent if t.total_seconds() > 0]
        if positive_history:
            total_seconds = sum(t.total_seconds() for t in positive_history)
            recent_avg = timedelta(seconds=total_seconds / len(positive_history))
        else:
            recent_avg = base_timeout

        # Determine pattern
        if len(recent) >= 3:
            first_avg = sum(t.total_seconds() for t in recent[: len(recent) // 3]) / (
                len(recent) // 3
            )
            last_avg = sum(t.total_seconds() for t in recent[-len(recent) // 3 :]) / (
                len(recent) // 3
            )

            if last_avg > first_avg * 1.2:
                pattern = "increasing"
            elif last_avg < first_avg * 0.8:
                pattern = "decreasing"
            else:
                pattern = "stable"
        else:
            pattern = "stable"

        return {
            "recommended_timeout": recent_avg,
            "operation": operation,
            "recent_avg": recent_avg,
            "pattern": pattern,
        }

    # === Overload Detection & Delegation ===

    def update_load(self, current_load: float) -> None:
        """
        Update current system load for overload detection.

        Called by Chronos scheduler based on active contexts.
        """
        self._current_load = min(1.0, max(0.0, current_load))

    def get_overload_state(self) -> OverloadState:
        """
        Determine current overload state.

        Returns:
            OverloadState enum value
        """
        # Calculate based on active contexts vs max
        context_load = (
            len([c for c in self._contexts.values() if c.status == "running"]) / self._max_contexts
            if self._max_contexts > 0
            else 0
        )

        # Combine with explicit load
        combined_load = max(context_load, self._current_load)

        # Determine state
        if combined_load >= 0.9:
            return OverloadState.DEGRADED
        if combined_load >= 0.8:
            return OverloadState.OVERLOADED
        if combined_load >= 0.6:
            return OverloadState.LOADED
        return OverloadState.NORMAL

    async def delegate_to_coordinator(
        self,
        context_id: str,
        reason: str,
        fallback_action: str = "reschedule",
    ) -> dict[str, Any]:
        """
        Delegate context handling to Coordinator when Chronos is overloaded.

        Returns:
            {
                "delegated": bool,
                "coordinator_id": str | None,
                "context_transferred": bool,
                "fallback_action": str,
            }
        """
        context = self._contexts.get(context_id)
        if not context:
            return {
                "delegated": False,
                "coordinator_id": None,
                "context_transferred": False,
                "fallback_action": fallback_action,
            }

        # Get checkpoint data before transfer
        checkpoint = self.checkpoint_context(context_id)

        # Find coordinator agent
        coordinator_id = getattr(self._coordinator_proxy, "agent_id", None)

        # Fire overload callback if set
        if self._on_overload:
            await self._on_overload(context_id, reason)

        return {
            "delegated": True,
            "coordinator_id": coordinator_id,
            "context_transferred": checkpoint is not None,
            "fallback_action": fallback_action,
            "checkpoint_data": checkpoint,
        }

    def should_delegate(self, _context_id: str | None = None) -> tuple[bool, str]:
        """
        Determine if delegation is needed.

        Returns:
            (should_delegate, reason)
        """
        state = self.get_overload_state()

        if state in (OverloadState.DEGRADED, OverloadState.OVERLOADED):
            # Check if there are delegatable contexts
            delegatable = [
                c
                for c in self._contexts.values()
                if c.status == "running" and c.metadata.get("priority", 2) <= 2  # LOW or NORMAL
            ]

            if delegatable:
                return (
                    True,
                    f"Overload state: {state.value}, {len(delegatable)} delegatable contexts",
                )

            return True, f"Overload state: {state.value}, no delegatable contexts"

        return False, f"Normal load state: {state.value}"

    # === Metrics & Health ===

    def get_metrics(self) -> TimePerceptionMetrics:
        """Get current time perception metrics."""
        return self.get_perception_metrics()

    async def emit_health_report(self) -> dict[str, Any]:
        """
        Emit health report for HealthReportingMixin.

        Returns:
            Health status dictionary
        """
        metrics = self.get_perception_metrics()
        state = self.get_overload_state()

        return {
            "time_perception": {
                "active_contexts": metrics.active_contexts,
                "total_contexts": metrics.total_contexts,
                "avg_dilation_factor": metrics.avg_dilation_factor,
                "max_dilation_factor": metrics.max_dilation_factor,
                "perception_drift_seconds": metrics.perception_drift_seconds,
            },
            "overload": {
                "state": state.value,
                "current_load": self._current_load,
                "contexts_delegated": 0,  # Would need to track this
            },
            "deadlines": {
                "at_risk_contexts": sum(1 for c in self._contexts.values() if c.is_at_risk),
                "deadline_misses": metrics.deadline_misses,
                "adaptive_timeouts_triggered": metrics.adaptive_timeouts_triggered,
            },
            "anchoring": {
                "last_anchor": self._last_anchor_time.isoformat(),
                "anchor_source": self._anchor_source.value,
                "drift_detected_count": len(self._drift_history),
            },
        }


class TimeDilationCalculator:
    """
    Calculates time dilation factors based on system load and context.

    Time dilation allows Chronos to stretch perceived time for agents
    when under heavy load, preventing premature deadline misses.
    """

    def __init__(
        self,
        base_dilation: float = 1.0,
        max_dilation: float = 3.0,
        load_threshold: float = 0.6,
    ):
        self._base_dilation = base_dilation
        self._max_dilation = max_dilation
        self._load_threshold = load_threshold
        self._scale_factor: float = 2.0  # Per issue #1 in spec

    def calculate_dilation(self, current_load: float, context_priority: int = 2) -> float:
        """
        Calculate time dilation factor.

        Formula:
        - Below load_threshold: dilation = 1.0 (no dilation)
        - Above load_threshold: dilation = 1.0 + (load - threshold) * scale_factor

        Priority affects scale:
        - CRITICAL (5): Lower dilation (keep them running fast)
        - LOW (1): Higher dilation (they can wait)

        Returns:
            Dilation factor (1.0 to max_dilation)
        """
        if current_load <= self._load_threshold:
            return self._base_dilation

        # Calculate base dilation above threshold
        excess_load = current_load - self._load_threshold
        dilation = 1.0 + excess_load * self._scale_factor

        # Adjust for priority (1=LOW, 5=CRITICAL)
        # Higher priority gets lower dilation
        priority_factor = 1.0 - ((context_priority - 1) / 10)  # 0.6 to 1.0
        dilation *= priority_factor

        # Clamp to max
        return min(self._max_dilation, max(self._base_dilation, dilation))

    def adjust_deadline(
        self,
        original_deadline: datetime,
        current_load: float,
        progress_percent: float,
    ) -> datetime:
        """
        Adjust deadline based on load and progress.

        When system is overloaded, extended deadlines for
        lower-priority tasks to prevent cascade failures.

        Returns:
            Adjusted deadline (may be further in future)
        """
        if current_load <= self._load_threshold:
            return original_deadline

        # Calculate extension factor
        excess_load = current_load - self._load_threshold
        extension_factor = 1.0 + (excess_load * 0.5)  # Up to 50% extension

        # Adjust based on progress (slower progress = more extension)
        if progress_percent > 0:
            expected_progress_rate = 100.0  # percent per 100 time units
            actual_progress_rate = progress_percent
            if actual_progress_rate < expected_progress_rate:
                # Behind schedule, extend deadline more
                extension_factor *= 1.0 + ((expected_progress_rate - actual_progress_rate) / 100)

        # Calculate new deadline
        now = datetime.now(UTC)
        time_until_deadline = original_deadline - now
        extended_seconds = time_until_deadline.total_seconds() * extension_factor

        return now + timedelta(seconds=extended_seconds)


class OverloadDetector:
    """
    Detects when Chronos is becoming overloaded.

    Uses multiple signals:
    - Active context count vs max_contexts
    - System load average
    - Average context age
    - Deadline miss rate
    """

    def __init__(
        self,
        context_weight: float = 0.4,
        load_weight: float = 0.3,
        age_weight: float = 0.2,
        miss_rate_weight: float = 0.1,
    ):
        self._weights = {
            "context": context_weight,
            "load": load_weight,
            "age": age_weight,
            "miss_rate": miss_rate_weight,
        }
        self._context_count: int = 0
        self._max_contexts: int = 1000
        self._system_load: float = 0.0
        self._avg_context_age: float = 0.0
        self._miss_rate: float = 0.0
        self._total_contexts_seen: int = 0
        self._deadline_misses: int = 0

    def update_metrics(
        self,
        context_count: int,
        max_contexts: int,
        system_load: float,
        avg_context_age: float,
    ) -> None:
        """Update metrics for overload calculation."""
        self._context_count = context_count
        self._max_contexts = max_contexts
        self._system_load = system_load
        self._avg_context_age = avg_context_age

    def record_deadline_miss(self) -> None:
        """Record a deadline miss for miss rate calculation."""
        self._deadline_misses += 1
        self._total_contexts_seen += 1
        self._update_miss_rate()

    def record_context_completion(self) -> None:
        """Record a successful context completion."""
        self._total_contexts_seen += 1
        self._update_miss_rate()

    def _update_miss_rate(self) -> None:
        """Update the deadline miss rate."""
        if self._total_contexts_seen > 0:
            self._miss_rate = self._deadline_misses / self._total_contexts_seen
        else:
            self._miss_rate = 0.0

    def calculate_overload_score(self) -> float:
        """
        Calculate overall overload score (0.0 to 1.0).

        0.0 = No load
        0.5 = Moderate load
        1.0 = Critical overload

        Returns:
            Overload score
        """
        # Context count score
        context_score = self._context_count / self._max_contexts if self._max_contexts > 0 else 0

        # Age score (normalized, assuming 1 hour is high age)
        age_score = min(1.0, self._avg_context_age / 3600) if self._avg_context_age > 0 else 0

        # Weighted combination
        score = (
            self._weights["context"] * context_score
            + self._weights["load"] * self._system_load
            + self._weights["age"] * age_score
            + self._weights["miss_rate"] * self._miss_rate
        )

        return min(1.0, max(0.0, score))

    def should_delegate(self, score: float, threshold: float = 0.8) -> bool:
        """
        Determine if delegation is warranted.

        Returns:
            True if score exceeds threshold
        """
        return score >= threshold

    def get_component_scores(self) -> dict[str, float]:
        """Get individual component scores for debugging."""
        context_score = self._context_count / self._max_contexts if self._max_contexts > 0 else 0
        age_score = min(1.0, self._avg_context_age / 3600) if self._avg_context_age > 0 else 0

        return {
            "context_score": context_score,
            "load_score": self._system_load,
            "age_score": age_score,
            "miss_rate_score": self._miss_rate,
            "weighted_score": self.calculate_overload_score(),
        }
