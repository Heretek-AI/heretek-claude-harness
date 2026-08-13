"""
Behavior Profiling System for Heretek Swarm Actors.

Source Pattern: Code Forge Temple (agentic signal profiling)

This module provides comprehensive behavior profiling for agents:
- Track agent behavior patterns over time
- Detect anomalies in agent behavior
- Generate behavior profiles for each agent type
- Export profiling metrics to Prometheus
- Alert on significant behavior changes

Features:
- Per-agent behavior tracking
- Statistical anomaly detection
- Behavior pattern analysis
- Prometheus metrics export
- Real-time alerting

Usage:
    from heretek_swarm.actors.profiling import (
        BehaviorProfiler,
        ProfilingConfig,
        BehaviorProfile,
        AnomalyDetector,
    )

    config = ProfilingConfig()
    profiler = BehaviorProfiler(config)

    # Track agent activity
    profiler.record_activity(
        agent_id="alpha-1",
        action="message_sent",
        metadata={"channel": "tasks", "size": 1024},
    )

    # Get behavior profile
    profile = profiler.get_profile("alpha-1")

    # Check for anomalies
    anomalies = profiler.detect_anomalies("alpha-1")
"""

import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm.actors.base import AgentActor
from heretek_swarm.actors.mixins import HealthReportingMixin, PatternMixin, ValidationMixin
from heretek_swarm.collective.learning import PatternExtractor

logger = structlog.get_logger(__name__)


class ActionType(StrEnum):
    """Types of agent actions."""

    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    STATE_CHANGED = "state_changed"
    ERROR_OCCURRED = "error_occurred"
    TOOL_CALLED = "tool_called"
    DECISION_MADE = "decision_made"
    LEARNING_EVENT = "learning_event"
    CUSTOM = "custom"


class AnomalyType(StrEnum):
    """Types of detected anomalies."""

    FREQUENCY_SPIKE = "frequency_spike"  # Unusual activity rate
    FREQUENCY_DROP = "frequency_drop"  # Unusual inactivity
    ERROR_RATE_HIGH = "error_rate_high"  # High error rate
    TASK_FAILURE_RATE_HIGH = "task_failure_rate_high"
    RESPONSE_TIME_HIGH = "response_time_high"  # Slow responses
    PATTERN_DEVIATION = "pattern_deviation"  # Deviation from normal pattern
    STATE_ANOMALY = "state_anomaly"  # Unusual state transitions
    RESOURCE_USAGE_HIGH = "resource_usage_high"


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ActivityRecord:
    """Record of a single agent activity."""

    timestamp: datetime
    agent_id: str
    action: ActionType
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "action": self.action.value,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


@dataclass
class BehaviorMetrics:
    """Computed behavior metrics for an agent."""

    agent_id: str
    window_start: datetime
    window_end: datetime

    # Activity metrics
    total_actions: int = 0
    actions_per_minute: float = 0.0
    message_sent_count: int = 0
    message_received_count: int = 0

    # Task metrics
    tasks_started: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    task_success_rate: float = 0.0
    # Phase 2A.3 cutover: this field is now updated from the
    # activity log (see _update_metrics below) instead of the
    # rolling-100 actor-execution window that lived in the
    # deleted SwarmMetricsCollector. The statistical sample is
    # different (activity-log means vs rolling-100 mean of
    # perf_counter deltas) but the field is still live.
    avg_task_duration_ms: float = 0.0

    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0

    # Timing metrics
    avg_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    response_time_stddev: float = 0.0

    # State metrics
    state_changes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_actions": self.total_actions,
            "actions_per_minute": self.actions_per_minute,
            "message_sent_count": self.message_sent_count,
            "message_received_count": self.message_received_count,
            "tasks_started": self.tasks_started,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "task_success_rate": self.task_success_rate,
            "avg_task_duration_ms": self.avg_task_duration_ms,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "avg_response_time_ms": self.avg_response_time_ms,
            "max_response_time_ms": self.max_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms,
            "response_time_stddev": self.response_time_stddev,
            "state_changes": self.state_changes,
        }


@dataclass
class BehaviorProfile:
    """
    Behavior profile for an agent type.

    Contains baseline behavior patterns and statistical bounds
    for normal behavior.
    """

    agent_type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Baseline metrics (averages)
    baseline_actions_per_minute: float = 0.0
    baseline_task_success_rate: float = 1.0
    baseline_avg_task_duration_ms: float = 0.0
    baseline_error_rate: float = 0.0
    baseline_response_time_ms: float = 0.0

    # Statistical bounds (standard deviations)
    actions_per_minute_std: float = 0.0
    task_success_rate_std: float = 0.0
    task_duration_std: float = 0.0
    error_rate_std: float = 0.0
    response_time_std: float = 0.0

    # Sample count for confidence
    sample_count: int = 0

    # Common state transitions
    common_state_transitions: list[tuple[str, str]] = field(default_factory=list)

    def update_from_metrics(self, metrics: BehaviorMetrics) -> None:
        """Update profile with new metrics using exponential moving average."""
        alpha = 0.1  # Smoothing factor

        if self.sample_count == 0:
            # First sample - use direct values
            self.baseline_actions_per_minute = metrics.actions_per_minute
            self.baseline_task_success_rate = metrics.task_success_rate
            self.baseline_avg_task_duration_ms = metrics.avg_task_duration_ms
            self.baseline_error_rate = metrics.error_rate
            self.baseline_response_time_ms = metrics.avg_response_time_ms
        else:
            # Exponential moving average
            self.baseline_actions_per_minute = (
                alpha * metrics.actions_per_minute + (1 - alpha) * self.baseline_actions_per_minute
            )
            self.baseline_task_success_rate = (
                alpha * metrics.task_success_rate + (1 - alpha) * self.baseline_task_success_rate
            )
            self.baseline_avg_task_duration_ms = (
                alpha * metrics.avg_task_duration_ms
                + (1 - alpha) * self.baseline_avg_task_duration_ms
            )
            self.baseline_error_rate = (
                alpha * metrics.error_rate + (1 - alpha) * self.baseline_error_rate
            )
            self.baseline_response_time_ms = (
                alpha * metrics.avg_response_time_ms + (1 - alpha) * self.baseline_response_time_ms
            )

        self.sample_count += 1
        self.updated_at = datetime.now(UTC)

    def is_within_normal_bounds(
        self,
        metrics: BehaviorMetrics,
        std_threshold: float = 3.0,
    ) -> tuple[bool, list[str]]:
        """
        Check if metrics are within normal bounds.

        Args:
            metrics: Current behavior metrics
            std_threshold: Number of standard deviations for bounds

        Returns:
            Tuple of (is_normal, list of anomalies)
        """
        anomalies = []

        # Check actions per minute
        if self.actions_per_minute_std > 0:
            z_score = (
                abs(metrics.actions_per_minute - self.baseline_actions_per_minute)
                / self.actions_per_minute_std
            )
            if z_score > std_threshold:
                anomalies.append(f"actions_per_minute_z_score_{z_score:.2f}")

        # Check task success rate
        if self.task_success_rate_std > 0:
            z_score = (
                abs(metrics.task_success_rate - self.baseline_task_success_rate)
                / self.task_success_rate_std
            )
            if z_score > std_threshold:
                anomalies.append(f"task_success_rate_z_score_{z_score:.2f}")

        # Check error rate
        if self.error_rate_std > 0:
            z_score = abs(metrics.error_rate - self.baseline_error_rate) / self.error_rate_std
            if z_score > std_threshold:
                anomalies.append(f"error_rate_z_score_{z_score:.2f}")

        # Check response time
        if self.response_time_std > 0:
            z_score = (
                abs(metrics.avg_response_time_ms - self.baseline_response_time_ms)
                / self.response_time_std
            )
            if z_score > std_threshold:
                anomalies.append(f"response_time_z_score_{z_score:.2f}")

        return len(anomalies) == 0, anomalies

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "baseline_actions_per_minute": self.baseline_actions_per_minute,
            "baseline_task_success_rate": self.baseline_task_success_rate,
            "baseline_avg_task_duration_ms": self.baseline_avg_task_duration_ms,
            "baseline_error_rate": self.baseline_error_rate,
            "baseline_response_time_ms": self.baseline_response_time_ms,
            "actions_per_minute_std": self.actions_per_minute_std,
            "task_success_rate_std": self.task_success_rate_std,
            "task_duration_std": self.task_duration_std,
            "error_rate_std": self.error_rate_std,
            "response_time_std": self.response_time_std,
            "sample_count": self.sample_count,
            "common_state_transitions": self.common_state_transitions,
        }


@dataclass
class Anomaly:
    """Detected anomaly in agent behavior."""

    timestamp: datetime
    agent_id: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    description: str
    metrics: dict[str, Any] = field(default_factory=dict)
    threshold_exceeded: float = 0.0
    expected_value: float = 0.0
    actual_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "metrics": self.metrics,
            "threshold_exceeded": self.threshold_exceeded,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
        }


@dataclass
class Alert:
    """Alert generated from anomaly detection."""

    timestamp: datetime
    agent_id: str
    anomaly: Anomaly
    message: str
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "anomaly": self.anomaly.to_dict(),
            "message": self.message,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
        }


@dataclass
class ProfilingConfig:
    """Configuration for behavior profiling."""

    # Window settings
    analysis_window_minutes: int = 5
    baseline_window_hours: int = 24
    profile_update_interval_minutes: int = 15

    # Anomaly detection thresholds
    frequency_spike_threshold: float = 3.0  # Standard deviations
    frequency_drop_threshold: float = 0.1  # Fraction of baseline
    error_rate_threshold: float = 0.2  # 20% error rate
    task_failure_threshold: float = 0.3  # 30% failure rate
    response_time_threshold: float = 3.0  # Standard deviations
    pattern_deviation_threshold: float = 3.0  # Standard deviations

    # Alert settings
    alert_on_anomaly: bool = True
    alert_cooldown_minutes: int = 10  # Minimum time between same alerts
    max_alerts_per_hour: int = 10

    # Metrics settings
    enable_prometheus_export: bool = True
    metrics_retention_hours: int = 24

    # Storage settings
    activity_buffer_size: int = 10000  # Max activities per agent
    profile_sample_min: int = 30  # Minimum samples for profile


class AnomalyDetector:
    """
    Statistical anomaly detection for agent behavior.

    Uses z-score based detection and other statistical methods
    to identify anomalous behavior patterns.
    """

    def __init__(self, config: ProfilingConfig):
        self.config = config
        self._agent_baselines: dict[str, dict[str, float]] = {}
        self._agent_stds: dict[str, dict[str, float]] = {}

    def update_baseline(self, agent_id: str, metrics: dict[str, float]) -> None:
        """Update baseline statistics for an agent."""
        if agent_id not in self._agent_baselines:
            self._agent_baselines[agent_id] = {}
            self._agent_stds[agent_id] = {}

        for key, value in metrics.items():
            # Skip non-numeric values (e.g., metadata dict, agent_id string)
            if not isinstance(value, (int, float)):
                continue

            if key not in self._agent_baselines[agent_id]:
                self._agent_baselines[agent_id][key] = float(value)
                self._agent_stds[agent_id][key] = 0.0
            else:
                # Exponential moving average for baseline
                alpha = 0.1
                old_baseline = self._agent_baselines[agent_id][key]
                self._agent_baselines[agent_id][key] = (
                    alpha * float(value) + (1 - alpha) * old_baseline
                )

                # Update standard deviation estimate
                old_std = self._agent_stds[agent_id][key]
                deviation = abs(float(value) - old_baseline)
                self._agent_stds[agent_id][key] = 0.9 * old_std + 0.1 * deviation

    def detect_anomalies(
        self,
        agent_id: str,
        metrics: BehaviorMetrics,
        profile: BehaviorProfile | None = None,
    ) -> list[Anomaly]:
        """
        Detect anomalies in current metrics.

        Args:
            agent_id: Agent identifier
            metrics: Current behavior metrics
            profile: Optional behavior profile for agent type

        Returns:
            List of detected anomalies
        """
        anomalies = []
        now = datetime.now(UTC)

        # Get baseline (prefer profile baseline, fall back to agent-specific)
        baseline = {}
        stds = {}

        if profile:
            baseline = {
                "actions_per_minute": profile.baseline_actions_per_minute,
                "task_success_rate": profile.baseline_task_success_rate,
                "error_rate": profile.baseline_error_rate,
                "response_time_ms": profile.baseline_response_time_ms,
                "task_duration_ms": profile.baseline_avg_task_duration_ms,
            }
            stds = {
                "actions_per_minute": profile.actions_per_minute_std,
                "task_success_rate": profile.task_success_rate_std,
                "error_rate": profile.error_rate_std,
                "response_time_ms": profile.response_time_std,
                "task_duration_ms": profile.task_duration_std,
            }
        elif agent_id in self._agent_baselines:
            baseline = self._agent_baselines[agent_id]
            stds = self._agent_stds[agent_id]

        # Check frequency spike/drop
        if "actions_per_minute" in baseline and baseline["actions_per_minute"] > 0:
            ratio = metrics.actions_per_minute / baseline["actions_per_minute"]

            if ratio > self.config.frequency_spike_threshold:
                anomalies.append(
                    Anomaly(
                        timestamp=now,
                        agent_id=agent_id,
                        anomaly_type=AnomalyType.FREQUENCY_SPIKE,
                        severity=AlertSeverity.MEDIUM,
                        description=f"Activity spike detected: {ratio:.2f}x normal rate",
                        metrics={"actions_per_minute": metrics.actions_per_minute},
                        threshold_exceeded=self.config.frequency_spike_threshold,
                        expected_value=baseline["actions_per_minute"],
                        actual_value=metrics.actions_per_minute,
                    )
                )

            if ratio < self.config.frequency_drop_threshold:
                anomalies.append(
                    Anomaly(
                        timestamp=now,
                        agent_id=agent_id,
                        anomaly_type=AnomalyType.FREQUENCY_DROP,
                        severity=AlertSeverity.HIGH,
                        description=f"Activity drop detected: {ratio:.2f}x normal rate",
                        metrics={"actions_per_minute": metrics.actions_per_minute},
                        threshold_exceeded=self.config.frequency_drop_threshold,
                        expected_value=baseline["actions_per_minute"],
                        actual_value=metrics.actions_per_minute,
                    )
                )

        # Check error rate
        if metrics.error_rate > self.config.error_rate_threshold:
            severity = AlertSeverity.HIGH if metrics.error_rate > 0.5 else AlertSeverity.MEDIUM
            anomalies.append(
                Anomaly(
                    timestamp=now,
                    agent_id=agent_id,
                    anomaly_type=AnomalyType.ERROR_RATE_HIGH,
                    severity=severity,
                    description=f"High error rate: {metrics.error_rate:.2%}",
                    metrics={"error_rate": metrics.error_rate, "error_count": metrics.error_count},
                    threshold_exceeded=self.config.error_rate_threshold,
                    expected_value=profile.baseline_error_rate if profile else 0.0,
                    actual_value=metrics.error_rate,
                )
            )

        # Check task failure rate
        if metrics.task_success_rate < (1 - self.config.task_failure_threshold):
            severity = (
                AlertSeverity.HIGH if metrics.task_success_rate < 0.5 else AlertSeverity.MEDIUM
            )
            anomalies.append(
                Anomaly(
                    timestamp=now,
                    agent_id=agent_id,
                    anomaly_type=AnomalyType.TASK_FAILURE_RATE_HIGH,
                    severity=severity,
                    description=f"High task failure rate: {1 - metrics.task_success_rate:.2%}",
                    metrics={
                        "task_success_rate": metrics.task_success_rate,
                        "tasks_failed": metrics.tasks_failed,
                        "tasks_completed": metrics.tasks_completed,
                    },
                    threshold_exceeded=self.config.task_failure_threshold,
                    expected_value=profile.baseline_task_success_rate if profile else 1.0,
                    actual_value=metrics.task_success_rate,
                )
            )

        # Check response time (z-score)
        if "response_time_ms" in stds and stds["response_time_ms"] > 0:
            z_score = (metrics.avg_response_time_ms - baseline.get("response_time_ms", 0)) / stds[
                "response_time_ms"
            ]
            if z_score > self.config.response_time_threshold:
                anomalies.append(
                    Anomaly(
                        timestamp=now,
                        agent_id=agent_id,
                        anomaly_type=AnomalyType.RESPONSE_TIME_HIGH,
                        severity=AlertSeverity.MEDIUM,
                        description=f"High response time: z-score {z_score:.2f}",
                        metrics={
                            "avg_response_time_ms": metrics.avg_response_time_ms,
                            "z_score": z_score,
                        },
                        threshold_exceeded=self.config.response_time_threshold,
                        expected_value=baseline.get("response_time_ms", 0),
                        actual_value=metrics.avg_response_time_ms,
                    )
                )

        # Check pattern deviation using profile
        if profile:
            is_normal, deviation_details = profile.is_within_normal_bounds(
                metrics,
                self.config.pattern_deviation_threshold,
            )
            if not is_normal:
                anomalies.append(
                    Anomaly(
                        timestamp=now,
                        agent_id=agent_id,
                        anomaly_type=AnomalyType.PATTERN_DEVIATION,
                        severity=AlertSeverity.LOW,
                        description=f"Pattern deviation detected: {', '.join(deviation_details)}",
                        metrics={"deviations": deviation_details},
                        threshold_exceeded=self.config.pattern_deviation_threshold,
                    )
                )

        return anomalies


class BehaviorProfiler(ValidationMixin, PatternMixin, HealthReportingMixin, AgentActor):
    """
    Main behavior profiling system for agents.

    Inherits from:
    - ValidationMixin: ZERO-02 Zero-Trust validation
    - PatternMixin: Collective pattern emission and consumption
    - HealthReportingMixin: Health status and error reporting
    - AgentActor: Base actor with message passing and lifecycle

    Features:
    - Activity tracking and recording
    - Behavior metrics computation
    - Profile generation and updates
    - Anomaly detection
    - Alert management
    - Prometheus metrics export
    """

    actor_type: str = "BehaviorProfiler"

    def __init__(
        self,
        config: ProfilingConfig | None = None,
        *args: Any,
        pattern_extractor: PatternExtractor | None = None,
        agent_id: str | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the behavior profiler.

        Args:
            config: Profiling configuration (can be first positional arg)
            *args: Additional positional arguments (passed to super)
            pattern_extractor: Optional PatternExtractor for collective learning
            agent_id: Agent identifier (default: auto-generated)
            name: Human-readable name
            **kwargs: Additional keyword arguments (passed to super)
        """
        # Extract config if passed as first positional (before *args)
        # This handles BehaviorProfiler(config) where config is first arg
        effective_config = config
        remaining_args = args

        # Check if first arg in remaining_args is a ProfilingConfig
        if args and isinstance(args[0], ProfilingConfig):
            effective_config = args[0]
            remaining_args = args[1:]

        effective_config = effective_config or ProfilingConfig()
        effective_pattern_extractor = pattern_extractor or PatternExtractor()

        # Initialize pattern emission tracking before super().__init__
        self._pattern_emitted: set[str] = set()
        self.pattern_extractor = effective_pattern_extractor

        # Call super().__init__ with AgentActor identity parameters
        super().__init__(
            agent_id=agent_id or "BehaviorProfiler",
            name=name or "BehaviorProfiler",
            *remaining_args,
            **kwargs,
        )

        # Store configuration
        self.config = effective_config

        # Activity storage
        self._activities: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.config.activity_buffer_size)
        )

        # Profiles by agent type
        self._profiles: dict[str, BehaviorProfile] = {}

        # Current metrics by agent
        self._current_metrics: dict[str, BehaviorMetrics] = {}

        # Anomaly detector
        self._anomaly_detector = AnomalyDetector(self.config)

        # Alerts
        self._alerts: list[Alert] = []
        self._alert_history: dict[str, datetime] = {}  # Last alert time per agent/type

        # Statistics
        self._stats = {
            "total_activities_recorded": 0,
            "total_anomalies_detected": 0,
            "total_alerts_generated": 0,
            "profiles_created": 0,
        }

        logger.info("behavior_profiler_initialized", config=self.config.__dict__)

    def record_activity(
        self,
        agent_id: str,
        action: ActionType,
        metadata: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """
        Record an agent activity.

        Args:
            agent_id: Agent identifier
            action: Type of action
            metadata: Additional action metadata
            duration_ms: Action duration in milliseconds
            success: Whether action was successful
        """
        now = datetime.now(UTC)

        record = ActivityRecord(
            timestamp=now,
            agent_id=agent_id,
            action=action,
            metadata=metadata or {},
            duration_ms=duration_ms,
            success=success,
        )

        self._activities[agent_id].append(record)
        self._stats["total_activities_recorded"] += 1

        logger.debug("activity_recorded", agent_id=agent_id, action=action.value)

    def compute_metrics(self, agent_id: str) -> BehaviorMetrics | None:
        """
        Compute behavior metrics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Computed behavior metrics or None if no data
        """
        activities = list(self._activities.get(agent_id, []))

        if not activities:
            return None

        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=self.config.analysis_window_minutes)

        # Filter to analysis window
        recent_activities = [a for a in activities if a.timestamp >= window_start]

        if not recent_activities:
            return None

        # Compute metrics
        metrics = BehaviorMetrics(
            agent_id=agent_id,
            window_start=window_start,
            window_end=now,
        )

        # Activity metrics
        metrics.total_actions = len(recent_activities)
        window_minutes = self.config.analysis_window_minutes
        metrics.actions_per_minute = metrics.total_actions / window_minutes

        for activity in recent_activities:
            if activity.action == ActionType.MESSAGE_SENT:
                metrics.message_sent_count += 1
            elif activity.action == ActionType.MESSAGE_RECEIVED:
                metrics.message_received_count += 1
            elif activity.action == ActionType.TASK_STARTED:
                metrics.tasks_started += 1
            elif activity.action == ActionType.TASK_COMPLETED:
                metrics.tasks_completed += 1
            elif activity.action == ActionType.TASK_FAILED:
                metrics.tasks_failed += 1
            elif activity.action == ActionType.ERROR_OCCURRED:
                metrics.error_count += 1
            elif activity.action == ActionType.STATE_CHANGED:
                metrics.state_changes += 1

        # Task metrics
        total_tasks = metrics.tasks_completed + metrics.tasks_failed
        if total_tasks > 0:
            metrics.task_success_rate = metrics.tasks_completed / total_tasks

        # Calculate task duration from activities with duration
        task_durations = [
            a.duration_ms
            for a in recent_activities
            if a.action in [ActionType.TASK_COMPLETED, ActionType.TASK_FAILED] and a.duration_ms > 0
        ]
        if task_durations:
            metrics.avg_task_duration_ms = statistics.mean(task_durations)

        # Error metrics
        if metrics.total_actions > 0:
            metrics.error_rate = metrics.error_count / metrics.total_actions

        # Response time metrics (from message activities)
        response_times = [a.duration_ms for a in recent_activities if a.duration_ms > 0]
        if response_times:
            metrics.avg_response_time_ms = statistics.mean(response_times)
            metrics.max_response_time_ms = max(response_times)
            metrics.min_response_time_ms = min(response_times)
            if len(response_times) > 1:
                metrics.response_time_stddev = statistics.stdev(response_times)

        self._current_metrics[agent_id] = metrics

        # Update baseline in anomaly detector
        self._anomaly_detector.update_baseline(agent_id, metrics.to_dict())

        return metrics

    def get_profile(self, agent_type: str) -> BehaviorProfile | None:
        """Get behavior profile for an agent type."""
        return self._profiles.get(agent_type)

    def update_profile(
        self,
        agent_type: str,
        agent_id: str,
    ) -> BehaviorProfile | None:
        """
        Update behavior profile for an agent type.

        Args:
            agent_type: Agent type
            agent_id: Specific agent instance

        Returns:
            Updated profile or None if insufficient data
        """
        metrics = self.compute_metrics(agent_id)

        # Use configurable minimum threshold instead of hardcoded 10
        min_samples = getattr(self.config, "profile_sample_min", 10)
        if not metrics or metrics.total_actions < min_samples:
            return None

        if agent_type not in self._profiles:
            self._profiles[agent_type] = BehaviorProfile(agent_type=agent_type)
            self._stats["profiles_created"] += 1

        profile = self._profiles[agent_type]
        profile.update_from_metrics(metrics)

        logger.debug("profile_updated", agent_type=agent_type, sample_count=profile.sample_count)

        return profile

    def detect_anomalies(self, agent_id: str) -> list[Anomaly]:
        """
        Detect anomalies for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of detected anomalies
        """
        metrics = self.compute_metrics(agent_id)

        if not metrics:
            return []

        # Get agent type from agent_id (assuming format "type-id")
        agent_type = agent_id.split("-")[0] if "-" in agent_id else agent_id
        profile = self._profiles.get(agent_type)

        anomalies = self._anomaly_detector.detect_anomalies(agent_id, metrics, profile)

        self._stats["total_anomalies_detected"] += len(anomalies)

        # Generate alerts for significant anomalies
        for anomaly in anomalies:
            self._generate_alert(agent_id, anomaly)

        return anomalies

    def _generate_alert(self, agent_id: str, anomaly: Anomaly) -> Alert | None:
        """
        Generate an alert from an anomaly.

        Args:
            agent_id: Agent identifier
            anomaly: Detected anomaly

        Returns:
            Generated alert or None if suppressed
        """
        if not self.config.alert_on_anomaly:
            return None

        now = datetime.now(UTC)
        alert_key = f"{agent_id}_{anomaly.anomaly_type.value}"

        # Check cooldown
        last_alert_time = self._alert_history.get(alert_key)
        if last_alert_time:
            cooldown = timedelta(minutes=self.config.alert_cooldown_minutes)
            if now - last_alert_time < cooldown:
                logger.debug(
                    "alert_suppressed_cooldown",
                    agent_id=agent_id,
                    anomaly_type=anomaly.anomaly_type.value,
                )
                return None

        # Check rate limit
        hour_ago = now - timedelta(hours=1)
        recent_alerts = sum(
            1
            for alert in self._alerts
            if alert.agent_id == agent_id and alert.timestamp >= hour_ago
        )
        if recent_alerts >= self.config.max_alerts_per_hour:
            logger.debug("alert_suppressed_rate_limit", agent_id=agent_id)
            return None

        # Create alert
        alert = Alert(
            timestamp=now,
            agent_id=agent_id,
            anomaly=anomaly,
            message=f"[{anomaly.severity.value.upper()}] {anomaly.description}",
        )

        self._alerts.append(alert)
        self._alert_history[alert_key] = now
        self._stats["total_alerts_generated"] += 1

        logger.warning(
            "alert_generated",
            agent_id=agent_id,
            anomaly_type=anomaly.anomaly_type.value,
            severity=anomaly.severity.value,
        )

        return alert

    def get_alerts(
        self,
        agent_id: str | None = None,
        severity: AlertSeverity | None = None,
        unacknowledged_only: bool = False,
    ) -> list[Alert]:
        """Get alerts with optional filtering."""
        if not (agent_id or severity or unacknowledged_only):
            return self._alerts
        return sorted(
            self._filter_alerts(agent_id, severity, unacknowledged_only),
            key=lambda a: a.timestamp, reverse=True,
        )

    def _filter_alerts(
        self, agent_id: str | None, severity: AlertSeverity | None, unacknowledged_only: bool
    ) -> list[Alert]:
        alerts: list[Alert] = []
        for a in self._alerts:
            if agent_id and a.agent_id != agent_id:
                continue
            if severity and a.anomaly.severity != severity:
                continue
            if unacknowledged_only and a.acknowledged:
                continue
            alerts.append(a)
        return alerts

    def acknowledge_alert(self, alert_index: int, acknowledged_by: str) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_index: Index in alerts list
            acknowledged_by: User/system acknowledging

        Returns:
            True if acknowledged successfully
        """
        if 0 <= alert_index < len(self._alerts):
            alert = self._alerts[alert_index]
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now(UTC)
            alert.acknowledged_by = acknowledged_by
            return True
        return False

    def get_agent_metrics(self, agent_id: str) -> BehaviorMetrics | None:
        """Get current metrics for an agent."""
        return self._current_metrics.get(agent_id)

    def get_all_profiles(self) -> dict[str, BehaviorProfile]:
        """Get all behavior profiles."""
        return self._profiles.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get profiler statistics."""
        return {
            **self._stats,
            "active_agents": len(self._activities),
            "profiles_count": len(self._profiles),
            "alerts_count": len([a for a in self._alerts if not a.acknowledged]),
            "config": {
                "analysis_window_minutes": self.config.analysis_window_minutes,
                "error_rate_threshold": self.config.error_rate_threshold,
                "alert_on_anomaly": self.config.alert_on_anomaly,
            },
        }

    def export_prometheus_metrics(self) -> str:
        """
        Export profiling metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        if not self.config.enable_prometheus_export:
            return "# Prometheus export disabled\n"

        lines = [
            "# Heretek Swarm Behavior Profiling Metrics",
            "",
            "# HELP heretek_profiler_total_activities Total activities recorded",
            "# TYPE heretek_profiler_total_activities counter",
            f"heretek_profiler_total_activities {self._stats['total_activities_recorded']}",
            "",
            "# HELP heretek_profiler_total_anomalies Total anomalies detected",
            "# TYPE heretek_profiler_total_anomalies counter",
            f"heretek_profiler_total_anomalies {self._stats['total_anomalies_detected']}",
            "",
            "# HELP heretek_profiler_total_alerts Total alerts generated",
            "# TYPE heretek_profiler_total_alerts counter",
            f"heretek_profiler_total_alerts {self._stats['total_alerts_generated']}",
            "",
            "# HELP heretek_profiler_profiles_count Number of behavior profiles",
            "# TYPE heretek_profiler_profiles_count gauge",
            f"heretek_profiler_profiles_count {len(self._profiles)}",
            "",
            "# HELP heretek_profiler_unacknowledged_alerts Unacknowledged alerts count",
            "# TYPE heretek_profiler_unacknowledged_alerts gauge",
            f"heretek_profiler_unacknowledged_alerts {len([a for a in self._alerts if not a.acknowledged])}",
            "",
        ]

        # Per-agent metrics
        for agent_id, metrics in self._current_metrics.items():
            safe_agent_id = agent_id.replace("-", "_").replace(".", "_")

            lines.extend(
                [
                    f"# HELP heretek_agent_{safe_agent_id}_actions_per_minute Actions per minute",
                    f"# TYPE heretek_agent_{safe_agent_id}_actions_per_minute gauge",
                    f"heretek_agent_{safe_agent_id}_actions_per_minute {metrics.actions_per_minute}",
                    "",
                    f"# HELP heretek_agent_{safe_agent_id}_error_rate Error rate",
                    f"# TYPE heretek_agent_{safe_agent_id}_error_rate gauge",
                    f"heretek_agent_{safe_agent_id}_error_rate {metrics.error_rate}",
                    "",
                    f"# HELP heretek_agent_{safe_agent_id}_task_success_rate Task success rate",
                    f"# TYPE heretek_agent_{safe_agent_id}_task_success_rate gauge",
                    f"heretek_agent_{safe_agent_id}_task_success_rate {metrics.task_success_rate}",
                    "",
                    f"# HELP heretek_agent_{safe_agent_id}_avg_response_time_ms Average response time",
                    f"# TYPE heretek_agent_{safe_agent_id}_avg_response_time_ms gauge",
                    f"heretek_agent_{safe_agent_id}_avg_response_time_ms {metrics.avg_response_time_ms}",
                    "",
                ]
            )

        # Per-profile metrics
        for agent_type, profile in self._profiles.items():
            safe_type = agent_type.replace("-", "_").replace(".", "_")

            lines.extend(
                [
                    f"# HELP heretek_profile_{safe_type}_baseline_actions_per_minute Baseline actions per minute",
                    f"# TYPE heretek_profile_{safe_type}_baseline_actions_per_minute gauge",
                    f"heretek_profile_{safe_type}_baseline_actions_per_minute {profile.baseline_actions_per_minute}",
                    "",
                    f"# HELP heretek_profile_{safe_type}_baseline_error_rate Baseline error rate",
                    f"# TYPE heretek_profile_{safe_type}_baseline_error_rate gauge",
                    f"heretek_profile_{safe_type}_baseline_error_rate {profile.baseline_error_rate}",
                    "",
                    f"# HELP heretek_profile_{safe_type}_sample_count Profile sample count",
                    f"# TYPE heretek_profile_{safe_type}_sample_count gauge",
                    f"heretek_profile_{safe_type}_sample_count {profile.sample_count}",
                    "",
                ]
            )

        return "\n".join(lines)

    def cleanup_old_data(self) -> int:
        """
        Clean up old data beyond retention period.

        Returns:
            Number of records cleaned up
        """
        # This is a placeholder - in production would implement
        # actual cleanup based on metrics_retention_hours
        return 0


# Global profiler instance
_global_profiler: BehaviorProfiler | None = None


def get_profiler() -> BehaviorProfiler:
    """Get or create the global behavior profiler."""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = BehaviorProfiler()
    return _global_profiler


def initialize_profiler(config: ProfilingConfig | None = None) -> BehaviorProfiler:
    """Initialize the global profiler with configuration."""
    global _global_profiler
    _global_profiler = BehaviorProfiler(config or ProfilingConfig())
    return _global_profiler
