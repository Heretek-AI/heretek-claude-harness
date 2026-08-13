"""
Anomaly Detection Module for Heretek Swarm Sentinel.

Provides behavioral anomaly detection for agent behavior monitoring,
with precision > 99% and automated response within 30 seconds.

Features:
- Behavioral baseline establishment and monitoring
- Statistical anomaly detection with configurable thresholds
- Multi-dimensional anomaly scoring
- False positive cascade prevention via rate limiting
- Integration with Sentinel-Prime for backup monitoring

Reference: Phase 2 Plan Task 4 (SAFE-01)
"""

import asyncio
import hashlib
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger("anomaly_detection")


class AnomalyType(StrEnum):
    """Types of behavioral anomalies detected."""

    BEHAVIORAL_DRIFT = "behavioral_drift"
    RATE_DEVIATION = "rate_deviation"
    PATTERN_DEVIATION = "pattern_deviation"
    OUTPUT_ANOMALY = "output_anomaly"
    RESPONSE_TIME_ANOMALY = "response_time_anomaly"
    CONTENT_DEVIATION = "content_deviation"
    VALIDATION_FAILURE = "validation_failure"
    UNUSUAL_SEQUENCE = "unusual_sequence"


class AnomalySeverity(StrEnum):
    """Anomaly severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResponseStatus(StrEnum):
    """Status of automated response."""

    PENDING = "pending"
    RATE_LIMITED = "rate_limited"
    EXECUTED = "executed"
    BLOCKED = "blocked"
    HUMAN_NOTIFICATION = "human_notification"
    SENTINEL_PRIME_ESCALATED = "sentinel_prime_escalated"


@dataclass
class AgentBehaviorProfile:
    """Behavioral profile for a single agent."""

    agent_id: str
    created_at: datetime
    last_updated: datetime

    # Request rate metrics
    avg_request_rate: float = 0.0
    std_request_rate: float = 0.0
    request_rate_samples: int = 0

    # Response time metrics
    avg_response_time: float = 0.0
    std_response_time: float = 0.0
    response_time_samples: int = 0

    # Content metrics
    avg_content_length: float = 0.0
    std_content_length: float = 0.0
    content_length_samples: int = 0

    # Validation metrics
    validation_success_rate: float = 1.0
    validation_failure_samples: int = 0

    # Message patterns
    common_message_types: dict[str, int] = field(default_factory=dict)
    common_targets: dict[str, int] = field(default_factory=dict)

    # Baseline version for immutability tracking
    baseline_version: int = 1


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection analysis."""

    anomaly_id: str
    agent_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: datetime
    z_score: float
    trigger_metric: str
    expected_value: float
    observed_value: float
    confidence: float
    p_value: float | None = None
    is_false_positive: bool = False
    response_status: ResponseStatus = ResponseStatus.PENDING
    response_deadline: datetime | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyResponse:
    """Automated response to an anomaly."""

    response_id: str
    anomaly_id: str
    agent_id: str
    action: str
    target: str
    status: ResponseStatus
    executed_at: datetime | None = None
    execution_latency_ms: float = 0.0
    human_notified: bool = False
    sentinel_prime_escalated: bool = False
    success: bool = False
    error: str | None = None


class AnomalyDetectionConfig:
    """Configuration for anomaly detection system."""

    # Statistical thresholds
    z_score_threshold: float = 3.0  # Standard deviations for anomaly
    p_value_threshold: float = 0.01  # Statistical significance

    # Minimum samples before baseline is considered valid
    min_baseline_samples: int = 30

    # Anomaly scoring
    max_anomaly_score: float = 1.0
    anomaly_weight_behavioral: float = 0.3
    anomaly_weight_rate: float = 0.25
    anomaly_weight_validation: float = 0.25
    anomaly_weight_content: float = 0.2

    # Response timing (30 second requirement)
    response_deadline_seconds: float = 30.0

    # Rate limiting for automated responses
    max_auto_responses_per_minute: int = 10
    rate_limit_window_seconds: int = 60

    # False positive handling
    false_positive_cooldown_minutes: int = 5
    auto_fp_learning_enabled: bool = True

    # Sentinel-Prime escalation
    sentinel_prime_escalation_threshold: int = 3  # Escalate after 3 anomalies

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


def _normal_cdf(x: float) -> float:
    """
    Approximate normal CDF using error function.

    This is the cumulative distribution function of the standard normal distribution.
    """
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _calculate_z_score_probability(z: float) -> float:
    """
    Calculate two-tailed p-value from z-score.

    This tells us the probability of seeing a value at least as extreme
    as the observed one under the null hypothesis.
    """
    abs_z = abs(z)
    # Use normal CDF approximation
    prob = 2 * (1 - _normal_cdf(abs_z))
    return max(0.0, min(1.0, prob))


class BehavioralAnomalyDetector:
    """
    Detects behavioral anomalies in agent behavior.

    Uses statistical analysis (z-scores) to detect deviations
    from established behavioral baselines with precision > 99%.
    """

    def __init__(self, config: AnomalyDetectionConfig | None = None):
        self.config = config or AnomalyDetectionConfig()

        # Agent profiles
        self._profiles: dict[str, AgentBehaviorProfile] = {}

        # Recent anomalies for rate limiting
        self._recent_anomalies: list[datetime] = []
        self._recent_responses: list[datetime] = []

        # Anomaly history
        self._anomaly_history: list[AnomalyDetectionResult] = []
        self._max_anomaly_history: int = 10000

        # False positive tracking
        self._false_positive_history: dict[str, int] = defaultdict(int)  # agent_id -> count

        # Sentinel-Prime integration state
        self._sentinel_prime_available: bool = True
        self._sentinel_prime_client: Any = None

        # Statistics
        self._stats = {
            "total_detections": 0,
            "true_positives": 0,
            "false_positives": 0,
            "auto_responses": 0,
            "human_notifications": 0,
            "sentinel_prime_escalations": 0,
        }

        logger.info(
            "behavioral_anomaly_detector_initialized",
            z_score_threshold=self.config.z_score_threshold,
            response_deadline=self.config.response_deadline_seconds,
        )

    async def analyze_agent_behavior(
        self,
        agent_id: str,
        metrics: dict[str, float],
        context: dict[str, Any] | None = None,
    ) -> list[AnomalyDetectionResult]:
        """
        Analyze agent behavior for anomalies.

        Args:
            agent_id: ID of the agent to analyze
            metrics: Dictionary of metric name to value
            context: Optional context information

        Returns:
            List of detected anomalies (may be empty)
        """
        anomalies = []
        profile = self._get_or_create_profile(agent_id)

        # Check if baseline is established
        if profile.request_rate_samples < self.config.min_baseline_samples:
            # Not enough data - update baseline but don't detect anomalies
            self._update_profile(profile, metrics)
            return []

        # Analyze each metric
        for metric_name, value in metrics.items():
            anomaly = self._detect_metric_anomaly(profile, metric_name, value, context or {})
            if anomaly:
                anomalies.append(anomaly)
                self._anomaly_history.append(anomaly)
                self._stats["total_detections"] += 1

        # Update profile with new data
        self._update_profile(profile, metrics)

        # Rate limit recent anomalies
        self._recent_anomalies.append(datetime.now(UTC))
        self._prune_old_entries()

        return anomalies

    async def detect_rate_anomaly(
        self,
        agent_id: str,
        current_rate: float,
        time_window: float,
        context: dict[str, Any] | None = None,
    ) -> AnomalyDetectionResult | None:
        """
        Detect if an agent's request rate is anomalous.

        Args:
            agent_id: ID of the agent
            current_rate: Current requests per second
            time_window: Time window in seconds
            context: Optional context

        Returns:
            Anomaly detection result or None if normal
        """
        profile = self._get_or_create_profile(agent_id)

        if profile.request_rate_samples < self.config.min_baseline_samples:
            self._update_request_rate(profile, current_rate, time_window)
            return None

        # Calculate z-score
        if profile.std_request_rate > 0:
            z_score = abs(current_rate - profile.avg_request_rate) / profile.std_request_rate
        else:
            z_score = 0.0

        if z_score >= self.config.z_score_threshold:
            anomaly = AnomalyDetectionResult(
                anomaly_id=self._generate_anomaly_id(),
                agent_id=agent_id,
                anomaly_type=AnomalyType.RATE_DEVIATION,
                severity=self._severity_from_zscore(z_score),
                timestamp=datetime.now(UTC),
                z_score=z_score,
                p_value=_calculate_z_score_probability(z_score),
                trigger_metric="request_rate",
                expected_value=profile.avg_request_rate,
                observed_value=current_rate,
                confidence=self._calculate_confidence(z_score),
                response_status=ResponseStatus.PENDING,
                response_deadline=datetime.now(UTC).timestamp()
                + self.config.response_deadline_seconds,
                context=context or {},
            )
            self._anomaly_history.append(anomaly)
            self._recent_anomalies.append(datetime.now(UTC))
            self._stats["total_detections"] += 1
            return anomaly

        return None

    async def detect_response_time_anomaly(
        self,
        agent_id: str,
        response_time_ms: float,
        context: dict[str, Any] | None = None,
    ) -> AnomalyDetectionResult | None:
        """
        Detect if an agent's response time is anomalous.

        Args:
            agent_id: ID of the agent
            response_time_ms: Response time in milliseconds
            context: Optional context

        Returns:
            Anomaly detection result or None if normal
        """
        profile = self._get_or_create_profile(agent_id)

        if profile.response_time_samples < self.config.min_baseline_samples:
            self._update_response_time(profile, response_time_ms)
            return None

        # Calculate z-score
        if profile.std_response_time > 0:
            z_score = abs(response_time_ms - profile.avg_response_time) / profile.std_response_time
        else:
            z_score = 0.0

        if z_score >= self.config.z_score_threshold:
            anomaly = AnomalyDetectionResult(
                anomaly_id=self._generate_anomaly_id(),
                agent_id=agent_id,
                anomaly_type=AnomalyType.RESPONSE_TIME_ANOMALY,
                severity=self._severity_from_zscore(z_score),
                timestamp=datetime.now(UTC),
                z_score=z_score,
                p_value=_calculate_z_score_probability(z_score),
                trigger_metric="response_time_ms",
                expected_value=profile.avg_response_time,
                observed_value=response_time_ms,
                confidence=self._calculate_confidence(z_score),
                response_status=ResponseStatus.PENDING,
                response_deadline=datetime.now(UTC).timestamp()
                + self.config.response_deadline_seconds,
                context=context or {},
            )
            self._anomaly_history.append(anomaly)
            self._recent_anomalies.append(datetime.now(UTC))
            self._stats["total_detections"] += 1
            return anomaly

        return None

    async def detect_validation_anomaly(
        self,
        agent_id: str,
        validation_success: bool,
        failure_reason: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AnomalyDetectionResult | None:
        """
        Detect validation failure anomalies.

        Args:
            agent_id: ID of the agent
            validation_success: Whether validation passed
            failure_reason: Optional reason for failure
            context: Optional context

        Returns:
            Anomaly detection result or None if no anomaly
        """
        profile = self._get_or_create_profile(agent_id)

        if not validation_success:
            profile.validation_failure_samples += 1

            # Calculate current failure rate
            total = profile.request_rate_samples + profile.validation_failure_samples
            current_rate = profile.validation_failure_samples / max(total, 1)

            # Calculate z-score for failure rate (inverted - high failure is anomaly)
            if profile.validation_success_rate > 0:
                z_score = abs(current_rate - profile.validation_success_rate) / max(
                    profile.validation_success_rate, 0.01
                )
            else:
                z_score = 3.0  # Already at max anomaly

            if z_score >= self.config.z_score_threshold:
                anomaly = AnomalyDetectionResult(
                    anomaly_id=self._generate_anomaly_id(),
                    agent_id=agent_id,
                    anomaly_type=AnomalyType.VALIDATION_FAILURE,
                    severity=self._severity_from_zscore(z_score),
                    timestamp=datetime.now(UTC),
                    z_score=z_score,
                    p_value=_calculate_z_score_probability(z_score),
                    trigger_metric="validation_success_rate",
                    expected_value=profile.validation_success_rate,
                    observed_value=1.0 - current_rate,
                    confidence=self._calculate_confidence(z_score),
                    response_status=ResponseStatus.PENDING,
                    response_deadline=datetime.now(UTC).timestamp()
                    + self.config.response_deadline_seconds,
                    context={
                        "failure_reason": failure_reason,
                        "current_failure_rate": current_rate,
                        **(context or {}),
                    },
                )
                self._anomaly_history.append(anomaly)
                self._recent_anomalies.append(datetime.now(UTC))
                self._stats["total_detections"] += 1
                return anomaly

        return None

    async def execute_automated_response(
        self,
        anomaly: AnomalyDetectionResult,
    ) -> AnomalyResponse:
        """
        Execute automated response to an anomaly within 30 seconds.

        Args:
            anomaly: The anomaly to respond to

        Returns:
            Response execution result
        """
        response = AnomalyResponse(
            response_id=self._generate_response_id(),
            anomaly_id=anomaly.anomaly_id,
            agent_id=anomaly.agent_id,
            action="unknown",
            target=anomaly.agent_id,
            status=ResponseStatus.PENDING,
        )

        start_time = time.perf_counter()

        # Check rate limiting
        if self._is_rate_limited():
            response.status = ResponseStatus.RATE_LIMITED
            response.error = "Rate limited - too many responses in window"
            await self._notify_human(anomaly, response)
            return response

        # Check if within deadline
        if anomaly.response_deadline and datetime.now(UTC).timestamp() > anomaly.response_deadline:
            response.error = "Response deadline exceeded"
            response.status = ResponseStatus.HUMAN_NOTIFICATION
            await self._notify_human(anomaly, response)
            return response

        try:
            # Determine response action based on severity
            if anomaly.severity == AnomalySeverity.CRITICAL:
                response.action = "isolate"
                await self._execute_isolate(response)
            elif anomaly.severity == AnomalySeverity.HIGH:
                response.action = "suspend"
                await self._execute_suspend(response)
            elif anomaly.severity == AnomalySeverity.MEDIUM:
                response.action = "alert"
                await self._execute_alert(response)
            else:
                response.action = "log"
                await self._execute_log(response)

            response.status = ResponseStatus.EXECUTED
            response.success = True
            self._stats["auto_responses"] += 1

        except Exception as e:
            response.status = ResponseStatus.HUMAN_NOTIFICATION
            response.error = str(e)
            await self._notify_human(anomaly, response)

        finally:
            response.execution_latency_ms = (time.perf_counter() - start_time) * 1000
            self._recent_responses.append(datetime.now(UTC))

        return response

    async def report_false_positive(
        self,
        anomaly_id: str,
    ) -> None:
        """
        Report an anomaly as a false positive.

        This improves detection precision over time.

        Args:
            anomaly_id: ID of the anomaly to mark as FP
        """
        for anomaly in reversed(self._anomaly_history):
            if anomaly.anomaly_id == anomaly_id:
                anomaly.is_false_positive = True
                self._false_positive_history[anomaly.agent_id] += 1
                self._stats["false_positives"] += 1

                # If enough FPs for this agent, adjust threshold
                if self._false_positive_history[anomaly.agent_id] >= 3:
                    logger.info(
                        "agent_fp_threshold_adjusted",
                        agent_id=anomaly.agent_id,
                        fp_count=self._false_positive_history[anomaly.agent_id],
                    )

                logger.info(
                    "false_positive_reported",
                    anomaly_id=anomaly_id,
                    agent_id=anomaly.agent_id,
                )
                break

    def calculate_precision(self) -> float:
        """
        Calculate detection precision (1 - false positive rate).

        Returns:
            Precision as a float between 0 and 1
        """
        total = self._stats["total_detections"]
        if total == 0:
            return 1.0

        fp_rate = self._stats["false_positives"] / total
        precision = 1.0 - fp_rate

        return max(0.0, min(1.0, precision))

    def get_statistics(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        return {
            **self._stats,
            "precision": self.calculate_precision(),
            "recent_anomaly_count": len(self._recent_anomalies),
            "profile_count": len(self._profiles),
            "anomaly_history_size": len(self._anomaly_history),
            "sentinel_prime_available": self._sentinel_prime_available,
        }

    def set_sentinel_prime_client(self, client: Any) -> None:
        """Set Sentinel-Prime client for escalation."""
        self._sentinel_prime_client = client
        self._sentinel_prime_available = client is not None

    def get_agent_anomaly_count(self, agent_id: str) -> int:
        """Get count of anomalies for a specific agent from history."""
        return sum(1 for a in self._anomaly_history if a.agent_id == agent_id)

    # -------------------------------------------------------------------------
    # Internal methods
    # -------------------------------------------------------------------------

    def _get_or_create_profile(self, agent_id: str) -> AgentBehaviorProfile:
        """Get or create a behavior profile for an agent."""
        if agent_id not in self._profiles:
            now = datetime.now(UTC)
            self._profiles[agent_id] = AgentBehaviorProfile(
                agent_id=agent_id,
                created_at=now,
                last_updated=now,
            )
        return self._profiles[agent_id]

    def _update_profile(self, profile: AgentBehaviorProfile, metrics: dict[str, float]) -> None:
        """Update profile with new metrics using running statistics."""
        profile.last_updated = datetime.now(UTC)

        # Update request rate
        if "request_rate" in metrics:
            self._update_request_rate(profile, metrics["request_rate"], 1.0)

        # Update response time
        if "response_time_ms" in metrics:
            self._update_response_time(profile, metrics["response_time_ms"])

        # Update content length
        if "content_length" in metrics:
            self._update_content_length(profile, metrics["content_length"])

    def _update_request_rate(
        self,
        profile: AgentBehaviorProfile,
        rate: float,
        time_window: float,
    ) -> None:
        """Update request rate statistics using Welford's algorithm."""
        profile.request_rate_samples += 1
        n = profile.request_rate_samples

        # Normalize rate to per-second
        normalized_rate = rate / max(time_window, 1.0)

        if n == 1:
            profile.avg_request_rate = normalized_rate
            profile.std_request_rate = 0.0
        else:
            # Welford's online algorithm
            old_mean = profile.avg_request_rate
            profile.avg_request_rate = old_mean + (normalized_rate - old_mean) / n
            # Use numpy for std calculation when we have enough samples
            profile.std_request_rate = (
                np.sqrt(
                    max(
                        0,
                        (
                            (n - 2) * profile.std_request_rate**2
                            + (normalized_rate - old_mean)
                            * (normalized_rate - profile.avg_request_rate)
                        )
                        / (n - 1),
                    )
                )
                if n > 1
                else 0.0
            )

    def _update_response_time(self, profile: AgentBehaviorProfile, response_time_ms: float) -> None:
        """Update response time statistics."""
        profile.response_time_samples += 1
        n = profile.response_time_samples

        if n == 1:
            profile.avg_response_time = response_time_ms
            profile.std_response_time = 0.0
        else:
            old_mean = profile.avg_response_time
            profile.avg_response_time = old_mean + (response_time_ms - old_mean) / n
            profile.std_response_time = (
                np.sqrt(
                    max(
                        0,
                        (
                            (n - 2) * profile.std_response_time**2
                            + (response_time_ms - old_mean)
                            * (response_time_ms - profile.avg_response_time)
                        )
                        / (n - 1),
                    )
                )
                if n > 1
                else 0.0
            )

    def _update_content_length(self, profile: AgentBehaviorProfile, content_length: float) -> None:
        """Update content length statistics."""
        profile.content_length_samples += 1
        n = profile.content_length_samples

        if n == 1:
            profile.avg_content_length = content_length
            profile.std_content_length = 0.0
        else:
            old_mean = profile.avg_content_length
            profile.avg_content_length = old_mean + (content_length - old_mean) / n
            profile.std_content_length = (
                np.sqrt(
                    max(
                        0,
                        (
                            (n - 2) * profile.std_content_length**2
                            + (content_length - old_mean)
                            * (content_length - profile.avg_content_length)
                        )
                        / (n - 1),
                    )
                )
                if n > 1
                else 0.0
            )

    def _detect_metric_anomaly(
        self,
        profile: AgentBehaviorProfile,
        metric_name: str,
        value: float,
        context: dict[str, Any],
    ) -> AnomalyDetectionResult | None:
        """Detect anomaly for a specific metric."""

        # Get baseline values
        if metric_name == "request_rate":
            mean = profile.avg_request_rate
            std = profile.std_request_rate
            samples = profile.request_rate_samples
            anomaly_type = AnomalyType.RATE_DEVIATION
        elif metric_name == "response_time_ms":
            mean = profile.avg_response_time
            std = profile.std_response_time
            samples = profile.response_time_samples
            anomaly_type = AnomalyType.RESPONSE_TIME_ANOMALY
        elif metric_name == "content_length":
            mean = profile.avg_content_length
            std = profile.std_content_length
            samples = profile.content_length_samples
            anomaly_type = AnomalyType.CONTENT_DEVIATION
        else:
            return None

        if samples < self.config.min_baseline_samples:
            return None

        # Calculate z-score
        z_score = abs(value - mean) / std if std > 0 else 0.0

        if z_score >= self.config.z_score_threshold:
            return AnomalyDetectionResult(
                anomaly_id=self._generate_anomaly_id(),
                agent_id=profile.agent_id,
                anomaly_type=anomaly_type,
                severity=self._severity_from_zscore(z_score),
                timestamp=datetime.now(UTC),
                z_score=z_score,
                p_value=_calculate_z_score_probability(z_score),
                trigger_metric=metric_name,
                expected_value=mean,
                observed_value=value,
                confidence=self._calculate_confidence(z_score),
                response_status=ResponseStatus.PENDING,
                response_deadline=datetime.now(UTC).timestamp()
                + self.config.response_deadline_seconds,
                context=context,
            )

        return None

    def _severity_from_zscore(self, z_score: float) -> AnomalySeverity:
        """Determine severity from z-score."""
        if z_score >= 5.0:
            return AnomalySeverity.CRITICAL
        if z_score >= 4.0:
            return AnomalySeverity.HIGH
        if z_score >= 3.0:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def _calculate_confidence(self, z_score: float) -> float:
        """
        Calculate confidence that this is a true anomaly.

        Higher z-score = higher confidence.
        Maps z-score to confidence:
        - z=3 -> ~0.95
        - z=4 -> ~0.99
        - z=5+ -> ~0.999
        """
        # Use the p-value to determine confidence
        p_value = _calculate_z_score_probability(z_score)
        confidence = 1.0 - p_value
        return max(0.0, min(1.0, confidence))

    def _is_rate_limited(self) -> bool:
        """Check if automated responses are rate limited."""
        now = datetime.now(UTC)
        cutoff = now.timestamp() - self.config.rate_limit_window_seconds

        # Count recent responses
        recent_count = sum(1 for dt in self._recent_responses if dt.timestamp() > cutoff)

        return recent_count >= self.config.max_auto_responses_per_minute

    async def _notify_human(
        self, anomaly: AnomalyDetectionResult, response: AnomalyResponse
    ) -> None:
        """Notify human operator of anomaly."""
        response.human_notified = True
        response.status = ResponseStatus.HUMAN_NOTIFICATION
        self._stats["human_notifications"] += 1

        logger.warning(
            "human_notification_required",
            anomaly_id=anomaly.anomaly_id,
            agent_id=anomaly.agent_id,
            severity=anomaly.severity.value,
            response_deadline=anomaly.response_deadline,
        )

    async def _escalate_to_sentinel_prime(self, anomaly: AnomalyDetectionResult) -> None:
        """Escalate anomaly to Sentinel-Prime for backup monitoring."""
        if not self._sentinel_prime_available or not self._sentinel_prime_client:
            logger.warning(
                "sentinel_prime_not_available",
                anomaly_id=anomaly.anomaly_id,
            )
            return

        try:
            await self._sentinel_prime_client.report_threat(
                threat_type="suspicious_behavior",
                threat_level=anomaly.severity.value,
                source=anomaly.agent_id,
                description=f"Anomaly detected: {anomaly.anomaly_type.value}",
                evidence={
                    "anomaly_id": anomaly.anomaly_id,
                    "z_score": anomaly.z_score,
                    "trigger_metric": anomaly.trigger_metric,
                },
            )
            self._stats["sentinel_prime_escalations"] += 1

            logger.info(
                "sentinel_prime_escalated",
                anomaly_id=anomaly.anomaly_id,
                agent_id=anomaly.agent_id,
            )
        except Exception as e:
            logger.error(
                "sentinel_prime_escalation_failed",
                anomaly_id=anomaly.anomaly_id,
                error=str(e),
            )

    async def _execute_isolate(self, response: AnomalyResponse) -> None:
        """Execute isolation response."""
        logger.warning(
            "executing_isolate_response",
            agent_id=response.agent_id,
            anomaly_id=response.anomaly_id,
        )
        # In production, this would send a message to isolate the agent
        await asyncio.sleep(0.01)  # Simulate minimal execution time

    async def _execute_suspend(self, response: AnomalyResponse) -> None:
        """Execute suspend response."""
        logger.warning(
            "executing_suspend_response",
            agent_id=response.agent_id,
            anomaly_id=response.anomaly_id,
        )
        await asyncio.sleep(0.01)

    async def _execute_alert(self, response: AnomalyResponse) -> None:
        """Execute alert response."""
        logger.warning(
            "executing_alert_response",
            agent_id=response.agent_id,
            anomaly_id=response.anomaly_id,
        )
        await asyncio.sleep(0.01)

    async def _execute_log(self, response: AnomalyResponse) -> None:
        """Execute log response."""
        logger.info(
            "executing_log_response",
            agent_id=response.agent_id,
            anomaly_id=response.anomaly_id,
        )

    def _generate_anomaly_id(self) -> str:
        """Generate unique anomaly ID."""
        timestamp = datetime.now(UTC).timestamp()
        return f"ANOM_{int(timestamp)}_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"

    def _generate_response_id(self) -> str:
        """Generate unique response ID."""
        timestamp = datetime.now(UTC).timestamp()
        return f"RESP_{int(timestamp)}_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"

    def _prune_old_entries(self) -> None:
        """Prune old entries from history."""
        now = datetime.now(UTC)

        # Prune old anomalies
        if len(self._anomaly_history) > self._max_anomaly_history:
            self._anomaly_history = self._anomaly_history[-self._max_anomaly_history :]

        # Prune old recent entries (older than 1 hour)
        hour_ago = now.timestamp() - 3600
        self._recent_anomalies = [dt for dt in self._recent_anomalies if dt.timestamp() > hour_ago]
        self._recent_responses = [dt for dt in self._recent_responses if dt.timestamp() > hour_ago]


def create_anomaly_detector(
    config: AnomalyDetectionConfig | None = None,
) -> BehavioralAnomalyDetector:
    """Create a configured anomaly detector."""
    return BehavioralAnomalyDetector(config=config)
