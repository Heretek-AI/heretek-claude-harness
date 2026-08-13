"""
Sentinel Anomaly Monitor - Behavioral anomaly detection (SAFE-01).

This module provides the AnomalyMonitor class that encapsulates all
SAFE-01 anomaly detection state and methods previously inline in
SentinelAgent. It acts as a delegate, wrapping the BehavioralAnomalyDetector
and adding Sentinel-specific state management.

Key capabilities:
- Agent behavior monitoring with z-score based anomaly detection
- Rate anomaly detection
- Response time anomaly detection
- Validation anomaly detection
- Automated response within 30 seconds
- Sentinel-Prime escalation for backup monitoring
- Self-health monitoring

Reference: Phase 2 Plan Task 4 (SAFE-01)
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm_core.security.immune import ResponseOutcome
from heretek_swarm_core.security.anomaly_detection import (
    AnomalyDetectionConfig,
    AnomalyDetectionResult,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyType,
    ResponseStatus,
    create_anomaly_detector,
)

if TYPE_CHECKING:
    from heretek_swarm.actors.sentinel.types import AnomalyAlert
    from heretek_swarm_core.security.behavioral_baseline import BehavioralBaseline

logger = structlog.get_logger("AnomalyMonitor")


class AnomalyMonitor:
    """
    Behavioral anomaly detection monitor for SAFE-01.

    Encapsulates all anomaly detection state: the detector, response
    tracking, agent metrics, rate limiting, human notification, and
    Sentinel-Prime escalation.

    Designed to be instantiated by SentinelAgent.__init__ and used
    as a delegate for all anomaly-related methods.
    """

    def __init__(
        self,
        anomaly_config: AnomalyDetectionConfig,
        behavioral_baseline: BehavioralBaseline,
        agent_id: str | None = None,
        on_pattern_detected: Any = None,
        compute_tier_client: Any = None,
    ):
        """
        Initialize the anomaly monitor.

        Args:
            anomaly_config: Configuration for anomaly detection thresholds.
            behavioral_baseline: Baseline store for pattern management.
            agent_id: ID of the owning SentinelAgent (for self-monitoring).
            on_pattern_detected: Optional async callback(item_id, item_type, outcome, content)
                invoked after each anomaly is processed (for collective learning).
            compute_tier_client: Optional ComputeTierClient for tier-gated
                anomaly responses. When None, tier-gating is skipped and the
                full response path is used (backward-compatible default).
        """
        self.config = anomaly_config
        self._behavioral_baseline = behavioral_baseline
        self._agent_id = agent_id
        self._on_pattern_detected = on_pattern_detected
        self._compute_tier_client = compute_tier_client

        # Core anomaly detector
        self._anomaly_detector = create_anomaly_detector(anomaly_config)

        # Sentinel-Prime integration
        self._sentinel_prime_available = False
        self._sentinel_prime_client: Any = None

        # Anomaly response tracking
        self._active_responses: dict[str, AnomalyResponse] = {}
        self._anomaly_alerts: list[Any] = []  # AnomalyAlert instances
        self._max_alert_history = 1000

        # Agent metrics tracking for anomaly detection
        self._agent_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "request_count": 0.0,
                "total_request_rate": 0.0,
                "request_rate_samples": 0,
                "response_times": [],
                "validation_failures": 0,
                "validation_successes": 0,
            }
        )

        # Rate limiting state
        self._response_rate_limited_until: dict[str, float] = {}

        # Human notification state (for false positive cascade)
        self._human_notification_cooldown: dict[str, float] = {}
        self._human_notification_cooldown_seconds = 300  # 5 minutes

        # Anomaly escalation counter for Sentinel-Prime
        self._anomaly_escalation_count: dict[str, int] = defaultdict(int)

        # Sentinel self-health monitoring
        self._sentinel_self_check_interval = 60.0  # seconds
        self._last_sentinel_self_check = 0.0
        self._sentinel_self_health = "healthy"

        # Pending outcome tracking for immune learning
        self._pending_outcome_tracking: dict[str, dict[str, Any]] = {}

        # FP-rate tracking window (last-100-response outcomes)
        self._response_window: list[bool] = []  # True = FP, False = not FP
        self._response_window_max = 100
        # Minimum entries before FP rate is considered statistically meaningful
        self._response_window_eligibility = 50

        # Hysteresis configuration for adaptive threshold drift
        self.fp_rate_drift_threshold = 0.05   # 5% FP rate triggers upward drift
        self.drift_consecutive_windows = 3    # must be sustained for 3 windows
        self.drift_delta_per_step = 0.05      # sigma to drift per step

        # Hysteresis counters — reset when FP rate falls between thresholds
        self._consecutive_elevated_fp_windows: int = 0
        self._consecutive_zero_fp_windows: int = 0

        logger.info(
            "AnomalyMonitor_initialized",
            response_deadline=anomaly_config.response_deadline_seconds,
            z_score_threshold=anomaly_config.z_score_threshold,
        )

    # ---- Public API --------------------------------------------------------

    async def monitor_agent_behavior(
        self,
        agent_id: str,
        metrics: dict[str, float],
        context: dict[str, Any] | None = None,
    ) -> list[Any]:
        """
        Monitor agent behavior and detect anomalies.

        This is the primary entry point for SAFE-01 behavioral anomaly detection.

        Args:
            agent_id: ID of the agent to monitor.
            metrics: Dictionary of metrics (request_rate, response_time_ms, etc.).
            context: Optional context information.

        Returns:
            List of anomaly alerts (empty if no anomalies detected).
        """
        alerts: list[AnomalyAlert] = []

        # Analyze behavior
        anomalies = await self._anomaly_detector.analyze_agent_behavior(
            agent_id=agent_id,
            metrics=metrics,
            context=context,
        )

        # Process each anomaly
        for anomaly in anomalies:
            alert = await self._process_anomaly(anomaly)
            if alert:
                alerts.append(alert)

        # Update agent metrics
        self._update_agent_metrics(agent_id, metrics)

        return alerts

    async def check_agent_rate(
        self,
        agent_id: str,
        current_rate: float,
        time_window: float = 1.0,
    ) -> Any | None:
        """
        Check if an agent's request rate is anomalous.

        Args:
            agent_id: ID of the agent.
            current_rate: Current requests per time window.
            time_window: Time window in seconds.

        Returns:
            Anomaly alert or None if rate is normal.
        """
        anomaly = await self._anomaly_detector.detect_rate_anomaly(
            agent_id=agent_id,
            current_rate=current_rate,
            time_window=time_window,
            context={"check_type": "rate"},
        )

        if anomaly:
            return await self._process_anomaly(anomaly)

        return None

    async def check_agent_response_time(
        self,
        agent_id: str,
        response_time_ms: float,
    ) -> Any | None:
        """
        Check if an agent's response time is anomalous.

        Args:
            agent_id: ID of the agent.
            response_time_ms: Response time in milliseconds.

        Returns:
            Anomaly alert or None if response time is normal.
        """
        anomaly = await self._anomaly_detector.detect_response_time_anomaly(
            agent_id=agent_id,
            response_time_ms=response_time_ms,
            context={"check_type": "response_time"},
        )

        if anomaly:
            return await self._process_anomaly(anomaly)

        return None

    async def check_agent_validation(
        self,
        agent_id: str,
        validation_success: bool,
        failure_reason: str | None = None,
    ) -> Any | None:
        """
        Check if an agent's validation failures indicate an anomaly.

        Args:
            agent_id: ID of the agent.
            validation_success: Whether validation passed.
            failure_reason: Optional reason for failure.

        Returns:
            Anomaly alert or None if no anomaly.
        """
        anomaly = await self._anomaly_detector.detect_validation_anomaly(
            agent_id=agent_id,
            validation_success=validation_success,
            failure_reason=failure_reason,
            context={"check_type": "validation"},
        )

        if anomaly:
            return await self._process_anomaly(anomaly)

        return None

    async def report_false_positive(self, anomaly_id: str) -> bool:
        """
        Report an anomaly as a false positive.

        Args:
            anomaly_id: ID of the anomaly to mark as FP.

        Returns:
            True if the anomaly was found and marked.
        """
        await self._anomaly_detector.report_false_positive(anomaly_id)

        # Track outcome for immune learning
        self._pending_outcome_tracking[anomaly_id] = {
            "outcome": ResponseOutcome.FALSE_POSITIVE,
        }

        # Record outcome in FP-rate window
        self._record_response_outcome(anomaly_id, is_fp=True)

        # Evaluate hysteresis: sustained FP rate may trigger threshold drift
        self._maybe_drift_threshold()

        # Update any pending alert
        for alert in self._anomaly_alerts:
            if alert.anomaly_id == anomaly_id:
                alert.false_positive = True
                logger.info(
                    "false_positive_recorded",
                    anomaly_id=anomaly_id,
                    agent_id=alert.agent_id,
                )
                return True

        return False

    def set_sentinel_prime_client(self, client: Any) -> None:
        """
        Set Sentinel-Prime client for backup monitoring and escalation.

        Args:
            client: Sentinel-Prime agent client.
        """
        self._sentinel_prime_client = client
        self._sentinel_prime_available = client is not None
        self._anomaly_detector.set_sentinel_prime_client(client)

        logger.info(
            "sentinel_prime_client_configured",
            available=self._sentinel_prime_available,
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        detector_stats = self._anomaly_detector.get_statistics()

        return {
            "detector": detector_stats,
            "active_responses": len(self._active_responses),
            "alert_history_size": len(self._anomaly_alerts),
            "sentinel_prime_available": self._sentinel_prime_available,
            "sentinel_self_health": self._sentinel_self_health,
            "precision_target_met": detector_stats.get("precision", 0) >= 0.99,
        }

    def get_anomaly_alerts(self) -> list[Any]:
        """Get all anomaly alerts."""
        return list(self._anomaly_alerts)

    def get_pending_outcome_tracking(self) -> dict[str, dict[str, Any]]:
        """Get pending outcome tracking dict for immune learning."""
        return self._pending_outcome_tracking

    def clear_pending_outcome(self, anomaly_id: str) -> None:
        """Remove a pending outcome tracking entry."""
        self._pending_outcome_tracking.pop(anomaly_id, None)

    # ---- FP-rate tracking window -------------------------------------------

    def _record_response_outcome(self, anomaly_id: str, is_fp: bool) -> None:
        """
        Record a response outcome in the sliding FP-rate window.

        Args:
            anomaly_id: ID of the anomaly.
            is_fp: True if the response was a false positive.
        """
        self._response_window.append(is_fp)
        if len(self._response_window) > self._response_window_max:
            self._response_window = self._response_window[
                -self._response_window_max:
            ]
        logger.debug(
            "response_outcome_recorded",
            anomaly_id=anomaly_id,
            is_fp=is_fp,
            window_size=len(self._response_window),
        )

    def get_fp_rate(self) -> float:
        """
        Compute the false-positive rate over the response window.

        Returns:
            FP rate as a float in [0.0, 1.0]; 0.0 if the window is empty.
        """
        if not self._response_window:
            return 0.0
        return sum(self._response_window) / len(self._response_window)

    def get_fp_rate_window_stats(self) -> dict[str, Any]:
        """
        Return window-level FP-rate statistics for hysteresis logic.

        Returns:
            Dict with keys:
            - window_size: number of entries currently in the window.
            - fp_count: number of false positives in the window.
            - fp_rate: current FP rate (0.0 if empty).
            - is_eligible: True when window has enough entries for
              statistically meaningful FP rate.
        """
        window_size = len(self._response_window)
        fp_count = sum(self._response_window)
        return {
            "window_size": window_size,
            "fp_count": fp_count,
            "fp_rate": fp_count / window_size if window_size > 0 else 0.0,
            "is_eligible": window_size >= self._response_window_eligibility,
        }

    # ---- Hysteresis: threshold drift based on sustained FP rate -------------

    def _maybe_drift_threshold(self) -> None:
        """
        Evaluate the FP-rate window and adjust z_score_threshold if
        the FP rate has been elevated or zero for enough consecutive
        windows to satisfy hysteresis.

        Drift is rate-capped at ``drift_delta_per_step`` (default 0.05 sigma)
        and further clamped by ``BehavioralBaseline.adjust_z_score_threshold``
        to ±0.1 sigma per call.
        """
        stats = self.get_fp_rate_window_stats()
        fp_rate = stats["fp_rate"]

        if fp_rate > self.fp_rate_drift_threshold:
            # Elevated FP rate — count toward upward drift
            self._consecutive_elevated_fp_windows += 1
            self._consecutive_zero_fp_windows = 0

            if (self._consecutive_elevated_fp_windows >= self.drift_consecutive_windows
                    and stats["is_eligible"]):
                old_threshold = self._behavioral_baseline.z_score_threshold
                new_threshold = self._behavioral_baseline.adjust_z_score_threshold(
                    +self.drift_delta_per_step,
                    agent_id=self._agent_id,
                )
                self._consecutive_elevated_fp_windows = 0
                logger.warning(
                    "threshold_drift_upward",
                    fp_rate=fp_rate,
                    consecutive_windows=self.drift_consecutive_windows,
                    previous_threshold=old_threshold,
                    new_threshold=new_threshold,
                    agent_id=self._agent_id,
                )

        elif fp_rate == 0.0:
            # Zero FP rate — count toward downward drift
            self._consecutive_zero_fp_windows += 1
            self._consecutive_elevated_fp_windows = 0

            if (self._consecutive_zero_fp_windows >= self.drift_consecutive_windows
                    and stats["is_eligible"]):
                old_threshold = self._behavioral_baseline.z_score_threshold
                new_threshold = self._behavioral_baseline.adjust_z_score_threshold(
                    -self.drift_delta_per_step,
                    agent_id=self._agent_id,
                )
                self._consecutive_zero_fp_windows = 0
                logger.warning(
                    "threshold_drift_downward",
                    fp_rate=fp_rate,
                    consecutive_windows=self.drift_consecutive_windows,
                    previous_threshold=old_threshold,
                    new_threshold=new_threshold,
                    agent_id=self._agent_id,
                )

        else:
            # Intermediate FP rate — reset both counters (not sustained)
            self._consecutive_elevated_fp_windows = 0
            self._consecutive_zero_fp_windows = 0

    # ---- Self-monitoring ---------------------------------------------------

    async def sentinel_self_monitoring(self) -> None:
        """
        Perform self-health check of Sentinel.

        Checks precision, escalates to Sentinel-Prime if precision drops.
        """
        now = time.time()

        if now - self._last_sentinel_self_check < self._sentinel_self_check_interval:
            return

        self._last_sentinel_self_check = now

        # Check precision from anomaly detector
        precision = self._anomaly_detector.calculate_precision()
        if precision < 0.99:
            self._sentinel_self_health = "degraded"
            logger.warning(
                "sentinel_precision_below_target",
                precision=precision,
                target=0.99,
            )

            # Notify Sentinel-Prime
            if self._sentinel_prime_available:
                await self._escalate_to_sentinel_prime(
                    AnomalyDetectionResult(
                        anomaly_id=self._generate_anomaly_id(),
                        agent_id=self._agent_id or "sentinel",
                        anomaly_type=AnomalyType.BEHAVIORAL_DRIFT,
                        severity=AnomalySeverity.HIGH,
                        timestamp=datetime.now(UTC),
                        z_score=3.0,
                        trigger_metric="sentinel_precision",
                        expected_value=0.99,
                        observed_value=precision,
                        confidence=0.95,
                    )
                )
        else:
            self._sentinel_self_health = "healthy"

    # ---- Internal ----------------------------------------------------------

    async def _process_anomaly(
        self, anomaly: AnomalyDetectionResult
    ) -> Any | None:
        """
        Process a detected anomaly and execute automated response.

        Implements the 30-second response deadline requirement.
        Also records the response for immune learning.

        Tier-gating: when a ComputeTierClient is available, the response
        path is chosen based on the host's compute capacity (Tier 1, 2, or 3).

        Args:
            anomaly: The detected anomaly.

        Returns:
            Anomaly alert with response details.
        """
        from heretek_swarm.actors.sentinel.types import AnomalyAlert

        start_time = time.perf_counter()

        # Check rate limiting
        if self._is_response_rate_limited(anomaly.agent_id):
            logger.warning(
                "anomaly_response_rate_limited",
                anomaly_id=anomaly.anomaly_id,
                agent_id=anomaly.agent_id,
            )

            # Send to human notification instead
            await self._notify_human(anomaly)

            alert = AnomalyAlert(
                alert_id=self._generate_alert_id(),
                anomaly_id=anomaly.anomaly_id,
                agent_id=anomaly.agent_id,
                anomaly_type=anomaly.anomaly_type,
                severity=anomaly.severity,
                timestamp=anomaly.timestamp,
                response_status=ResponseStatus.RATE_LIMITED,
                response_latency_ms=(time.perf_counter() - start_time) * 1000,
                sentinel_prime_escalated=False,
                false_positive=False,
            )
            self._anomaly_alerts.append(alert)
            return alert

        # ── Tier-gated response ────────────────────────────────────
        # Query compute tier if a client is available; skip if None.
        tier_result = None
        if self._compute_tier_client is not None:
            tier_result = await self._compute_tier_client.get_tier()

        if tier_result is not None:
            tier = tier_result.tier
            cpu_count = tier_result.cpu_count
            total_ram_gb = tier_result.total_ram_gb
            gpu_available = tier_result.gpu_available

            if tier == 1:
                # Tier 1 — hard freeze: skip automated response entirely
                logger.warning(
                    "anomaly_response",
                    anomaly_id=anomaly.anomaly_id,
                    agent_id=anomaly.agent_id,
                    anomaly_type=anomaly.anomaly_type.value,
                    severity=anomaly.severity.value,
                    tier=tier,
                    response_mode="hard_freeze",
                    cpu_count=cpu_count,
                    total_ram_gb=total_ram_gb,
                    gpu_available=gpu_available,
                )

                alert = AnomalyAlert(
                    alert_id=self._generate_alert_id(),
                    anomaly_id=anomaly.anomaly_id,
                    agent_id=anomaly.agent_id,
                    anomaly_type=anomaly.anomaly_type,
                    severity=anomaly.severity,
                    timestamp=anomaly.timestamp,
                    response_status=ResponseStatus.BLOCKED,
                    response_latency_ms=(time.perf_counter() - start_time) * 1000,
                    sentinel_prime_escalated=False,
                    false_positive=False,
                )
                self._anomaly_alerts.append(alert)
                return alert

            if tier == 2:
                # Tier 2 — fast-track: execute response with reduced metadata
                logger.warning(
                    "anomaly_response",
                    anomaly_id=anomaly.anomaly_id,
                    agent_id=anomaly.agent_id,
                    anomaly_type=anomaly.anomaly_type.value,
                    severity=anomaly.severity.value,
                    tier=tier,
                    response_mode="fast_track",
                    cpu_count=cpu_count,
                    total_ram_gb=total_ram_gb,
                    gpu_available=gpu_available,
                )
                # Execute response (the existing path)
                response = await self._anomaly_detector.execute_automated_response(anomaly)
                self._active_responses[response.response_id] = response

            else:
                # Tier 3 — full: execute full response (existing behavior)
                logger.warning(
                    "anomaly_response",
                    anomaly_id=anomaly.anomaly_id,
                    agent_id=anomaly.agent_id,
                    anomaly_type=anomaly.anomaly_type.value,
                    severity=anomaly.severity.value,
                    tier=tier,
                    response_mode="full",
                    cpu_count=cpu_count,
                    total_ram_gb=total_ram_gb,
                    gpu_available=gpu_available,
                )
                # Execute full response (existing path)
                response = await self._anomaly_detector.execute_automated_response(anomaly)
                self._active_responses[response.response_id] = response

        else:
            # No tier client — execute full response (backward compatible)
            response = await self._anomaly_detector.execute_automated_response(anomaly)
            self._active_responses[response.response_id] = response

        # Track escalation count for Sentinel-Prime
        if response.status == ResponseStatus.EXECUTED:
            self._anomaly_escalation_count[anomaly.agent_id] += 1

            # Check if we need to escalate to Sentinel-Prime
            if (
                self._anomaly_escalation_count[anomaly.agent_id]
                >= self.config.sentinel_prime_escalation_threshold
            ):
                await self._escalate_to_sentinel_prime(anomaly)

        # Update response status in anomaly
        anomaly.response_status = response.status

        # Check response latency
        latency_ms = (time.perf_counter() - start_time) * 1000
        if latency_ms > (self.config.response_deadline_seconds * 1000):
            logger.warning(
                "response_deadline_exceeded",
                anomaly_id=anomaly.anomaly_id,
                latency_ms=latency_ms,
                deadline_ms=self.config.response_deadline_seconds * 1000,
            )

        # Create alert
        escalation_threshold = self.config.sentinel_prime_escalation_threshold
        alert = AnomalyAlert(
            alert_id=self._generate_alert_id(),
            anomaly_id=anomaly.anomaly_id,
            agent_id=anomaly.agent_id,
            anomaly_type=anomaly.anomaly_type,
            severity=anomaly.severity,
            timestamp=anomaly.timestamp,
            response_status=response.status,
            response_latency_ms=latency_ms,
            sentinel_prime_escalated=(
                self._anomaly_escalation_count[anomaly.agent_id] >= escalation_threshold
            ),
            false_positive=False,
        )
        self._anomaly_alerts.append(alert)

        # Prune old alerts
        if len(self._anomaly_alerts) > self._max_alert_history:
            self._anomaly_alerts = self._anomaly_alerts[-self._max_alert_history:]

        # Store pattern content for immune learning
        pattern_content = {
            "anomaly_type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "agent_id": anomaly.agent_id,
            "z_score": anomaly.z_score,
            "trigger_metric": anomaly.trigger_metric,
        }

        self._pending_outcome_tracking[anomaly.anomaly_id] = {
            "response_id": response.response_id,
            "pattern_content": pattern_content,
            "pattern_type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "response_time_ms": latency_ms,
        }

        logger.warning(
            "anomaly_processed",
            anomaly_id=anomaly.anomaly_id,
            agent_id=anomaly.agent_id,
            anomaly_type=anomaly.anomaly_type.value,
            severity=anomaly.severity.value,
            response_status=response.status.value,
            latency_ms=latency_ms,
        )

        # Emit pattern for collective learning (via callback from agent)
        if self._on_pattern_detected:
            await self._on_pattern_detected(
                item_id=anomaly.anomaly_id,
                item_type="anomaly_detection",
                outcome="detected",
                content=pattern_content,
            )

        # Record outcome in FP-rate window (not FP at creation —
        # FPs are reported later via report_false_positive)
        self._record_response_outcome(anomaly.anomaly_id, is_fp=False)

        # Evaluate hysteresis: sustained zero-FP rate may trigger downward drift
        self._maybe_drift_threshold()

        return alert

    def _is_response_rate_limited(self, agent_id: str) -> bool:
        """Check if responses for this agent are rate limited."""
        now = time.time()

        # Check cooldown
        if agent_id in self._response_rate_limited_until:
            if now < self._response_rate_limited_until[agent_id]:
                return True
            del self._response_rate_limited_until[agent_id]

        # Check if too many recent responses for this agent
        recent_count = sum(
            1
            for alert in self._anomaly_alerts[-100:]
            if alert.agent_id == agent_id and (now - alert.timestamp.timestamp()) < 60
        )

        if recent_count >= self.config.max_auto_responses_per_minute:
            self._response_rate_limited_until[agent_id] = now + 60
            return True

        return False

    async def _notify_human(self, anomaly: AnomalyDetectionResult) -> None:
        """
        Notify human operator of an anomaly requiring attention.

        Args:
            anomaly: The anomaly requiring human attention.
        """
        # Check cooldown
        now = time.time()
        if anomaly.agent_id in self._human_notification_cooldown:
            if now < self._human_notification_cooldown[anomaly.agent_id]:
                return
        else:
            self._human_notification_cooldown[anomaly.agent_id] = (
                now + self._human_notification_cooldown_seconds
            )

        logger.warning(
            "human_notification_required",
            anomaly_id=anomaly.anomaly_id,
            agent_id=anomaly.agent_id,
            anomaly_type=anomaly.anomaly_type.value,
            severity=anomaly.severity.value,
            reason="rate_limited_or_deadline_exceeded",
        )

    async def _escalate_to_sentinel_prime(
        self, anomaly: AnomalyDetectionResult
    ) -> None:
        """
        Escalate anomaly to Sentinel-Prime for backup monitoring.

        Args:
            anomaly: The anomaly to escalate.
        """
        if not self._sentinel_prime_available or not self._sentinel_prime_client:
            logger.warning(
                "sentinel_prime_not_available_for_escalation",
                anomaly_id=anomaly.anomaly_id,
                agent_id=anomaly.agent_id,
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
            self._anomaly_escalation_count[anomaly.agent_id] = 0

            logger.warning(
                "escalating_to_sentinel_prime",
                anomaly_id=anomaly.anomaly_id,
                agent_id=anomaly.agent_id,
                escalation_count=0,
            )
        except Exception as e:
            logger.error(
                "sentinel_prime_escalation_failed",
                anomaly_id=anomaly.anomaly_id,
                error=str(e),
            )

    def _update_agent_metrics(
        self, agent_id: str, metrics: dict[str, float]
    ) -> None:
        """Update internal metrics tracking for an agent."""
        agent_metrics = self._agent_metrics[agent_id]

        if "request_rate" in metrics:
            rate = metrics["request_rate"]
            agent_metrics["total_request_rate"] += rate
            agent_metrics["request_rate_samples"] += 1
            agent_metrics["avg_request_rate"] = (
                agent_metrics["total_request_rate"] / agent_metrics["request_rate_samples"]
            )

        if "response_time_ms" in metrics:
            response_time = metrics["response_time_ms"]
            agent_metrics["response_times"].append(response_time)
            # Keep last 100 samples
            if len(agent_metrics["response_times"]) > 100:
                agent_metrics["response_times"] = agent_metrics["response_times"][-100:]

        if "validation_success" in metrics:
            if metrics["validation_success"]:
                agent_metrics["validation_successes"] += 1
            else:
                agent_metrics["validation_failures"] += 1

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.now(UTC).timestamp()
        return (
            f"ALERT_{int(timestamp)}_"
            f"{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"
        )

    def _generate_anomaly_id(self) -> str:
        """Generate unique anomaly ID."""
        timestamp = datetime.now(UTC).timestamp()
        return (
            f"ANOM_{int(timestamp)}_"
            f"{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"
        )
