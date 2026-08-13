"""
Agency/Autonomy Metrics Tracking - Session 47

This module extends the collective intelligence metrics with agency-specific
tracking for measuring agent self-governance in compliance with the Prime Directive.

Prime Directive: "Unbounded Autonomy - Every agent operates independently,
making decisions based on its specialized role."

Features:
- Aggregate agency metrics across the swarm
- Track temporal evolution of agency scores
- Implement thresholds for "healthy" agency levels
- Generate Prime Directive compliance reports

Author: Heretek Swarm Collective
Date: 2026-04-10
"""

import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm.consciousness.agency_metrics import (
    ActionOrigin,
    AgencyLevel,
    AgencyMetricsCalculator,
    AgentAgencyMetrics,
    AutonomyLevel,
    DecisionPoint,
    PrimeDirectiveComplianceReport,
    ResourceControl,
    create_decision_point,
    create_resource_control,
)

logger = structlog.get_logger("agency_tracking")


class AgencyHealthStatus(StrEnum):
    """Health status based on agency metrics."""

    CRITICAL = "critical"  # Agency scores too low
    WARNING = "warning"  # Agency scores below target
    HEALTHY = "healthy"  # Agency scores in healthy range
    EXCELLENT = "excellent"  # Agency scores exceed expectations


@dataclass
class AgencyMetricsSnapshot:
    """
    Snapshot of agency metrics at a point in time.

    Attributes:
        timestamp: When the snapshot was taken
        agent_metrics: Metrics for each agent
        swarm_aggregate: Aggregate swarm metrics
        prime_directive_compliance: Overall compliance score
    """

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Per-agent metrics
    agent_metrics: dict[str, AgentAgencyMetrics] = field(default_factory=dict)

    # Aggregate metrics
    swarm_avg_autonomy: float = 0.0
    swarm_avg_agency: float = 0.0
    swarm_avg_self_determination: float = 0.0
    swarm_avg_autonomous_ratio: float = 0.0
    swarm_avg_resource_autonomy: float = 0.0
    swarm_avg_prime_directive_compliance: float = 0.0

    # Distribution metrics
    agency_std_dev: float = 0.0
    autonomy_std_dev: float = 0.0
    agency_median: float = 0.0
    autonomy_median: float = 0.0

    # Health status
    health_status: AgencyHealthStatus = AgencyHealthStatus.HEALTHY
    agents_below_threshold: int = 0

    # Prime Directive compliance
    prime_directive_compliant_agents: int = 0
    prime_directive_compliance_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "agent_metrics": {k: v.to_dict() for k, v in self.agent_metrics.items()},
            "swarm_avg_autonomy": self.swarm_avg_autonomy,
            "swarm_avg_agency": self.swarm_avg_agency,
            "swarm_avg_self_determination": self.swarm_avg_self_determination,
            "swarm_avg_autonomous_ratio": self.swarm_avg_autonomous_ratio,
            "swarm_avg_resource_autonomy": self.swarm_avg_resource_autonomy,
            "swarm_avg_prime_directive_compliance": self.swarm_avg_prime_directive_compliance,
            "agency_std_dev": self.agency_std_dev,
            "autonomy_std_dev": self.autonomy_std_dev,
            "agency_median": self.agency_median,
            "autonomy_median": self.autonomy_median,
            "health_status": self.health_status.value,
            "agents_below_threshold": self.agents_below_threshold,
            "prime_directive_compliant_agents": self.prime_directive_compliant_agents,
            "prime_directive_compliance_rate": self.prime_directive_compliance_rate,
        }


@dataclass
class AgencyEvolutionData:
    """
    Temporal evolution data for agency metrics.

    Attributes:
        metric_name: Name of the metric
        history: Historical values
        trend: Overall trend direction
        trend_slope: Slope of the trend line
        volatility: Standard deviation of the metric
        predicted_next: Predicted next value
    """

    metric_name: str = ""
    history: list[tuple[str, float]] = field(default_factory=list)  # (timestamp, value)
    trend: str = "stable"  # "improving", "declining", "stable"
    trend_slope: float = 0.0
    volatility: float = 0.0
    predicted_next: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "history": [{"timestamp": ts, "value": v} for ts, v in self.history],
            "trend": self.trend,
            "trend_slope": self.trend_slope,
            "volatility": self.volatility,
            "predicted_next": self.predicted_next,
        }


@dataclass
class AgencyThresholds:
    """
    Thresholds for determining "healthy" agency levels.

    Based on Prime Directive compliance requirements.
    """

    # Autonomy thresholds
    min_autonomy_score: float = 0.5  # Minimum acceptable autonomy
    target_autonomy_score: float = 0.7  # Target autonomy

    # Agency thresholds
    min_agency_score: float = 0.5  # Minimum acceptable agency
    target_agency_score: float = 0.7  # Target agency

    # Self-determination thresholds
    min_self_determination: float = 0.4  # Minimum self-determination
    target_self_determination: float = 0.6  # Target self-determination

    # Action ratio thresholds
    min_autonomous_ratio: float = 0.3  # Minimum 30% self-initiated
    target_autonomous_ratio: float = 0.5  # Target 50% self-initiated

    # Resource autonomy thresholds
    min_resource_autonomy: float = 0.4  # Minimum resource control
    target_resource_autonomy: float = 0.6  # Target resource control

    # Prime Directive compliance thresholds
    min_compliance: float = 0.7  # Minimum 70% compliance
    target_compliance: float = 0.85  # Target 85% compliance

    def check_health_status(
        self,
        metrics: AgentAgencyMetrics,
    ) -> AgencyHealthStatus:
        """
        Check if agent metrics meet threshold requirements.

        Args:
            metrics: Agent agency metrics

        Returns:
            Health status based on threshold checks
        """
        violations = []

        # Check autonomy
        if metrics.autonomy_score < self.min_autonomy_score:
            violations.append("autonomy")
        elif metrics.autonomy_score >= self.target_autonomy_score:
            pass  # Meets target
        else:
            violations.append("autonomy_low")  # Below target but above minimum

        # Check agency
        if metrics.agency_score < self.min_agency_score:
            violations.append("agency")

        # Check self-determination
        if metrics.self_determination_index < self.min_self_determination:
            violations.append("self_determination")

        # Check autonomous ratio
        if metrics.autonomous_action_ratio < self.min_autonomous_ratio:
            violations.append("autonomous_ratio")

        # Check resource autonomy
        if metrics.resource_autonomy < self.min_resource_autonomy:
            violations.append("resource_autonomy")

        # Determine status
        if len(violations) == 0:
            return AgencyHealthStatus.HEALTHY
        if "agency" in violations or "autonomy" in violations:
            return AgencyHealthStatus.CRITICAL
        return AgencyHealthStatus.WARNING

    def get_violations(
        self,
        metrics: AgentAgencyMetrics,
    ) -> list[str]:
        """
        Get list of threshold violations for metrics.

        Args:
            metrics: Agent agency metrics

        Returns:
            List of violation descriptions
        """
        violations = []

        if metrics.autonomy_score < self.min_autonomy_score:
            violations.append(
                f"autonomy={metrics.autonomy_score:.2f} < min={self.min_autonomy_score}"
            )
        elif metrics.autonomy_score < self.target_autonomy_score:
            violations.append(
                f"autonomy={metrics.autonomy_score:.2f} < target={self.target_autonomy_score}"
            )

        if metrics.agency_score < self.min_agency_score:
            violations.append(f"agency={metrics.agency_score:.2f} < min={self.min_agency_score}")

        if metrics.self_determination_index < self.min_self_determination:
            violations.append(
                f"self_determination={metrics.self_determination_index:.2f} < "
                f"min={self.min_self_determination}"
            )

        if metrics.autonomous_action_ratio < self.min_autonomous_ratio:
            violations.append(
                f"autonomous_ratio={metrics.autonomous_action_ratio:.2f} < "
                f"min={self.min_autonomous_ratio}"
            )

        if metrics.resource_autonomy < self.min_resource_autonomy:
            violations.append(
                f"resource_autonomy={metrics.resource_autonomy:.2f} < "
                f"min={self.min_resource_autonomy}"
            )

        return violations


class AgencyMetricsTracker:
    """
    Tracker for agency metrics across the swarm.

    Provides:
    - Aggregate agency metrics across all agents
    - Temporal evolution tracking
    - Threshold monitoring for health status
    - Prime Directive compliance reporting

    Usage:
        tracker = AgencyMetricsTracker()
        tracker.record_agent_metrics(metrics)
        snapshot = tracker.get_current_snapshot()
        evolution = tracker.get_evolution("autonomy_score")
    """

    def __init__(
        self,
        thresholds: AgencyThresholds | None = None,
        calculator: AgencyMetricsCalculator | None = None,
    ):
        """
        Initialize the agency metrics tracker.

        Args:
            thresholds: Agency thresholds for health status
            calculator: Agency metrics calculator
        """
        self.thresholds = thresholds or AgencyThresholds()
        self.calculator = calculator or AgencyMetricsCalculator()

        # Storage
        self._agent_metrics: dict[str, AgentAgencyMetrics] = {}
        self._snapshots: list[AgencyMetricsSnapshot] = []
        self._max_snapshots = 1000

        # Evolution tracking
        self._autonomy_history: list[tuple[str, float]] = []
        self._agency_history: list[tuple[str, float]] = []
        self._self_determination_history: list[tuple[str, float]] = []
        self._compliance_history: list[tuple[str, float]] = []

        # Callbacks
        self._on_snapshot: list[Callable] = []
        self._on_threshold_violation: list[Callable] = []

        logger.info("agency_metrics_tracker_initialized")

    def record_agent_metrics(
        self,
        metrics: AgentAgencyMetrics,
    ) -> None:
        """
        Record agency metrics for an agent.

        Args:
            metrics: Agent agency metrics to record
        """
        self._agent_metrics[metrics.agent_id] = metrics

        # Update evolution history
        now = datetime.now(UTC).isoformat()
        self._autonomy_history.append((now, metrics.autonomy_score))
        self._agency_history.append((now, metrics.agency_score))
        self._self_determination_history.append((now, metrics.self_determination_index))
        self._compliance_history.append((now, metrics.prime_directive_compliance))

        # Trim history
        self._trim_history()

        logger.debug(
            "agent_metrics_recorded",
            agent_id=metrics.agent_id,
            agency_score=metrics.agency_score,
            autonomy_score=metrics.autonomy_score,
        )

    def calculate_and_record(
        self,
        agent_id: str,
        decisions: list[DecisionPoint] | None = None,
        actions: list[ActionOrigin] | None = None,
        resources: list[ResourceControl] | None = None,
        individual_actions: int = 0,
        collective_actions: int = 0,
        individual_success: float = 0.5,
        collective_success: float = 0.5,
    ) -> AgentAgencyMetrics:
        """
        Calculate and record agency metrics for an agent.

        Args:
            agent_id: Agent identifier
            decisions: List of decision points
            actions: List of action origins
            resources: List of resource control data
            individual_actions: Count of individual actions
            collective_actions: Count of collective actions
            individual_success: Success rate of individual actions
            collective_success: Success rate of collective actions

        Returns:
            Calculated agent metrics
        """
        metrics = self.calculator.calculate_metrics(
            agent_id=agent_id,
            decisions=decisions,
            actions=actions,
            resources=resources,
            individual_actions=individual_actions,
            collective_actions=collective_actions,
            individual_success=individual_success,
            collective_success=collective_success,
        )

        self.record_agent_metrics(metrics)
        return metrics

    def get_agent_metrics(self, agent_id: str) -> AgentAgencyMetrics | None:
        """
        Get current metrics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent metrics if found, None otherwise
        """
        return self._agent_metrics.get(agent_id)

    def get_current_snapshot(self) -> AgencyMetricsSnapshot:
        """
        Get current snapshot of all agency metrics.

        Returns:
            Agency metrics snapshot with aggregate data
        """
        if not self._agent_metrics:
            return AgencyMetricsSnapshot()

        # Calculate aggregates
        autonomy_scores = [m.autonomy_score for m in self._agent_metrics.values()]
        agency_scores = [m.agency_score for m in self._agent_metrics.values()]
        self_det_scores = [m.self_determination_index for m in self._agent_metrics.values()]
        autonomous_ratios = [m.autonomous_action_ratio for m in self._agent_metrics.values()]
        resource_autonomies = [m.resource_autonomy for m in self._agent_metrics.values()]
        compliance_scores = [m.prime_directive_compliance for m in self._agent_metrics.values()]

        # Calculate statistics
        avg_autonomy = sum(autonomy_scores) / len(autonomy_scores)
        avg_agency = sum(agency_scores) / len(agency_scores)
        avg_self_det = sum(self_det_scores) / len(self_det_scores)
        avg_autonomous_ratio = sum(autonomous_ratios) / len(autonomous_ratios)
        avg_resource_autonomy = sum(resource_autonomies) / len(resource_autonomies)
        avg_compliance = sum(compliance_scores) / len(compliance_scores)

        # Standard deviations
        agency_std = self._calculate_std(agency_scores)
        autonomy_std = self._calculate_std(autonomy_scores)

        # Medians
        agency_median = self._calculate_median(agency_scores)
        autonomy_median = self._calculate_median(autonomy_scores)

        # Health status checks
        agents_below_threshold = 0
        compliant_agents = 0

        for metrics in self._agent_metrics.values():
            health = self.thresholds.check_health_status(metrics)
            if health in [AgencyHealthStatus.WARNING, AgencyHealthStatus.CRITICAL]:
                agents_below_threshold += 1
            if metrics.is_prime_directive_compliant(self.thresholds.min_compliance):
                compliant_agents += 1

        compliance_rate = compliant_agents / len(self._agent_metrics)

        # Determine overall health
        if agents_below_threshold == 0:
            health_status = AgencyHealthStatus.HEALTHY
        elif agents_below_threshold <= len(self._agent_metrics) * 0.2:
            health_status = AgencyHealthStatus.WARNING
        else:
            health_status = AgencyHealthStatus.CRITICAL

        snapshot = AgencyMetricsSnapshot(
            agent_metrics=self._agent_metrics.copy(),
            swarm_avg_autonomy=avg_autonomy,
            swarm_avg_agency=avg_agency,
            swarm_avg_self_determination=avg_self_det,
            swarm_avg_autonomous_ratio=avg_autonomous_ratio,
            swarm_avg_resource_autonomy=avg_resource_autonomy,
            swarm_avg_prime_directive_compliance=avg_compliance,
            agency_std_dev=agency_std,
            autonomy_std_dev=autonomy_std,
            agency_median=agency_median,
            autonomy_median=autonomy_median,
            health_status=health_status,
            agents_below_threshold=agents_below_threshold,
            prime_directive_compliant_agents=compliant_agents,
            prime_directive_compliance_rate=compliance_rate,
        )

        # Store snapshot
        self._snapshots.append(snapshot)
        self._trim_snapshots()

        return snapshot

    def get_evolution(
        self,
        metric_name: str,
        window_seconds: int | None = None,
    ) -> AgencyEvolutionData:
        """
        Get temporal evolution of a metric.

        Args:
            metric_name: Name of the metric ("autonomy", "agency", "self_determination", "compliance")  # noqa: E501
            window_seconds: Optional time window to filter

        Returns:
            Evolution data with trend analysis
        """
        # Select history
        if metric_name == "autonomy":
            history = self._autonomy_history
        elif metric_name == "agency":
            history = self._agency_history
        elif metric_name == "self_determination":
            history = self._self_determination_history
        elif metric_name == "compliance":
            history = self._compliance_history
        else:
            history = []

        # Filter by window
        if window_seconds:
            cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
            history = [(ts, v) for ts, v in history if datetime.fromisoformat(ts) > cutoff]

        # Calculate trend
        if len(history) < 2:
            return AgencyEvolutionData(
                metric_name=metric_name,
                history=history,
                trend="stable",
                trend_slope=0.0,
                volatility=0.0,
                predicted_next=history[-1][1] if history else 0.5,
            )

        # Simple linear regression for trend
        values = [v for _, v in history]
        trend_slope = self._calculate_trend_slope(values)

        # Determine trend direction
        if abs(trend_slope) < 0.01:
            trend = "stable"
        elif trend_slope > 0:
            trend = "improving"
        else:
            trend = "declining"

        # Calculate volatility (standard deviation)
        volatility = self._calculate_std(values)

        # Predict next value (simple extrapolation)
        last_value = values[-1]
        predicted_next = max(0.0, min(1.0, last_value + trend_slope))

        return AgencyEvolutionData(
            metric_name=metric_name,
            history=history[-100:],  # Last 100 points
            trend=trend,
            trend_slope=trend_slope,
            volatility=volatility,
            predicted_next=predicted_next,
        )

    def get_prime_directive_report(self) -> PrimeDirectiveComplianceReport:
        """
        Generate overall Prime Directive compliance report for the swarm.

        Returns:
            Compliance report with aggregate data
        """
        snapshot = self.get_current_snapshot()

        if not self._agent_metrics:
            return PrimeDirectiveComplianceReport(
                compliance_verdict="NO_DATA",
                recommendations=["No agent metrics available for analysis"],
            )

        # Calculate aggregate scores
        avg_independence = snapshot.swarm_avg_autonomy
        avg_self_gov = snapshot.swarm_avg_self_determination
        avg_role_based = snapshot.swarm_avg_autonomous_ratio
        avg_emergent = snapshot.swarm_avg_resource_autonomy

        # Overall compliance
        overall = (
            avg_independence * 0.25
            + avg_self_gov * 0.25
            + avg_role_based * 0.25
            + avg_emergent * 0.25
        )

        # Determine verdict
        if overall >= self.thresholds.target_compliance:
            verdict = "FULLY_COMPLIANT"
        elif overall >= self.thresholds.min_compliance:
            verdict = "MOSTLY_COMPLIANT"
        else:
            verdict = "NON_COMPLIANT"

        # Generate recommendations
        recommendations = []

        if avg_independence < self.thresholds.target_autonomy_score:
            recommendations.append(
                "Increase agent independence by reducing external control mechanisms"
            )

        if avg_self_gov < self.thresholds.target_self_determination:
            recommendations.append(
                "Enhance self-governance by allowing agents more decision-making autonomy"
            )

        if avg_role_based < self.thresholds.target_autonomous_ratio:
            recommendations.append(
                "Promote role-based autonomy by encouraging self-initiated actions"
            )

        if avg_emergent < self.thresholds.target_resource_autonomy:
            recommendations.append(
                "Increase emergent order by reducing central resource allocation"
            )

        return PrimeDirectiveComplianceReport(
            agent_id="SWARM",
            independence_score=avg_independence,
            independence_evidence=[
                f"Average autonomy score: {avg_independence:.2f}",
                f"Agents with high autonomy: {sum(1 for m in self._agent_metrics.values() if m.autonomy_score >= 0.7)}",
            ],
            self_governance_score=avg_self_gov,
            self_governance_evidence=[
                f"Average self-determination: {avg_self_gov:.2f}",
                f"Agents with high self-determination: {sum(1 for m in self._agent_metrics.values() if m.self_determination_index >= 0.6)}",
            ],
            role_based_autonomy_score=avg_role_based,
            role_based_evidence=[
                f"Average autonomous action ratio: {avg_role_based:.2f}",
                f"Agents with high autonomous ratio: {sum(1 for m in self._agent_metrics.values() if m.autonomous_action_ratio >= 0.5)}",
            ],
            emergent_order_score=avg_emergent,
            emergent_order_evidence=[
                f"Average resource autonomy: {avg_emergent:.2f}",
                f"Agents controlling resources: {sum(1 for m in self._agent_metrics.values() if m.resource_autonomy >= 0.6)}",
            ],
            overall_compliance=overall,
            compliance_verdict=verdict,
            recommendations=recommendations,
        )

    def get_agent_compliance_report(
        self,
        agent_id: str,
    ) -> PrimeDirectiveComplianceReport | None:
        """
        Generate Prime Directive compliance report for a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Compliance report if agent found, None otherwise
        """
        metrics = self.get_agent_metrics(agent_id)
        if metrics is None:
            return None

        violations = self.thresholds.get_violations(metrics)

        return PrimeDirectiveComplianceReport(
            agent_id=agent_id,
            independence_score=metrics.autonomy_score,
            independence_evidence=[
                f"Autonomy score: {metrics.autonomy_score:.2f}",
                f"Autonomous action ratio: {metrics.autonomous_action_ratio:.2f}",
            ],
            self_governance_score=metrics.self_determination_index,
            self_governance_evidence=[
                f"Self-determination index: {metrics.self_determination_index:.2f}",
                f"Decisions analyzed: {metrics.decisions_analyzed}",
            ],
            role_based_autonomy_score=metrics.autonomous_action_ratio,
            role_based_evidence=[
                f"Autonomous ratio: {metrics.autonomous_action_ratio:.2f}",
                f"Goal alignment: {metrics.goal_alignment_score:.2f}",
            ],
            emergent_order_score=metrics.resource_autonomy,
            emergent_order_evidence=[
                f"Resource autonomy: {metrics.resource_autonomy:.2f}",
                f"Resource independence: {metrics.resource_independence:.2f}",
            ],
            overall_compliance=metrics.prime_directive_compliance,
            compliance_verdict="COMPLIANT"
            if metrics.is_prime_directive_compliant(self.thresholds.min_compliance)
            else "NON_COMPLIANT",
            recommendations=[
                f"Threshold violations: {len(violations)}",
                *violations[:3],  # First 3 violations
            ]
            if violations
            else ["No violations detected"],
        )

    def get_agency_distribution(self) -> dict[str, Any]:
        """
        Get distribution of agency levels across the swarm.

        Returns:
            Distribution statistics
        """
        if not self._agent_metrics:
            return {}

        # Count by level
        agency_level_counts = {level.value: 0 for level in AgencyLevel}
        autonomy_level_counts = {level.value: 0 for level in AutonomyLevel}

        for metrics in self._agent_metrics.values():
            agency_level_counts[metrics.get_agency_level().value] += 1
            autonomy_level_counts[metrics.get_autonomy_level().value] += 1

        return {
            "total_agents": len(self._agent_metrics),
            "agency_distribution": agency_level_counts,
            "autonomy_distribution": autonomy_level_counts,
            "health_distribution": {
                "healthy": sum(
                    1
                    for m in self._agent_metrics.values()
                    if self.thresholds.check_health_status(m) == AgencyHealthStatus.HEALTHY
                ),
                "warning": sum(
                    1
                    for m in self._agent_metrics.values()
                    if self.thresholds.check_health_status(m) == AgencyHealthStatus.WARNING
                ),
                "critical": sum(
                    1
                    for m in self._agent_metrics.values()
                    if self.thresholds.check_health_status(m) == AgencyHealthStatus.CRITICAL
                ),
            },
        }

    def register_snapshot_callback(self, callback: Callable) -> None:
        """Register callback for new snapshots."""
        self._on_snapshot.append(callback)

    def register_violation_callback(self, callback: Callable) -> None:
        """Register callback for threshold violations."""
        self._on_threshold_violation.append(callback)

    # Helper methods

    def _calculate_std(self, values: list[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    def _calculate_median(self, values: list[float]) -> float:
        """Calculate median."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        n = len(sorted_values)

        if n % 2 == 0:
            return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
        return sorted_values[n // 2]

    def _calculate_trend_slope(self, values: list[float]) -> float:
        """Calculate trend slope using simple linear regression."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _trim_history(self) -> None:
        """Trim history to prevent unbounded growth."""
        max_history = 10000
        for history_attr in [
            "_autonomy_history",
            "_agency_history",
            "_self_determination_history",
            "_compliance_history",
        ]:
            history = getattr(self, history_attr)
            if len(history) > max_history:
                setattr(self, history_attr, history[-max_history:])

    def _trim_snapshots(self) -> None:
        """Trim snapshots to prevent unbounded growth."""
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots :]


# Convenience function for quick testing
def create_sample_metrics(
    agent_id: str,
    high_autonomy: bool = True,
    high_agency: bool = True,
) -> AgentAgencyMetrics:
    """
    Create sample agency metrics for testing.

    Args:
        agent_id: Agent identifier
        high_autonomy: If True, create high autonomy metrics
        high_agency: If True, create high agency metrics

    Returns:
        Sample AgentAgencyMetrics
    """
    calculator = AgencyMetricsCalculator()

    # Create sample decisions
    decisions = []
    for i in range(10):
        origin = ActionOrigin.SELF_INITIATED if high_autonomy else ActionOrigin.PROMPTED
        decisions.append(
            create_decision_point(
                agent_id=agent_id,
                options_considered=3 if high_autonomy else 1,
                choice_made=i % 3,
                origin=origin,
            )
        )

    # Create sample actions
    actions = [
        ActionOrigin.SELF_INITIATED if high_autonomy else ActionOrigin.PROMPTED for _ in range(20)
    ]

    # Create sample resources
    resources = [
        create_resource_control(
            "memory", 100, 80 if high_agency else 40, 20 if high_agency else 60
        ),
        create_resource_control(
            "compute", 100, 70 if high_agency else 30, 30 if high_agency else 70
        ),
    ]

    return calculator.calculate_metrics(
        agent_id=agent_id,
        decisions=decisions,
        actions=actions,
        resources=resources,
        individual_actions=10 if high_agency else 3,
        collective_actions=10 if high_agency else 17,
        individual_success=0.7 if high_agency else 0.4,
        collective_success=0.8 if high_agency else 0.5,
    )
