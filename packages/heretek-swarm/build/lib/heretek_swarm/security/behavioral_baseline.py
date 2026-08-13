"""
Behavioral Baseline Module for Heretek Swarm.

This module provides the behavioral baseline system that:
- Establishes normal behavior baselines for agents
- Detects deviations from established baselines
- Manages baseline updates with quorum approval
- Provides immutable audit trail for baseline changes
- Handles novel pattern detection

The baseline is the "immune memory" of the swarm - it contains patterns
that the system has learned to recognize as threats or normal behavior.

Key features:
- Baseline establishment from historical behavior
- Statistical anomaly detection (z-score based)
- Quorum-based baseline updates (prevents corruption)
- Immutable audit trail for all baseline changes
- Novel pattern detection and preservation
- Baseline integrity verification

Reference: Phase 2 Plan Task 2 (CONS-02), Task 3 (CONS-03)
"""

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger("behavioral_baseline")


class BaselineStatus(StrEnum):
    """Status of a baseline entry."""

    ESTABLISHING = "establishing"  # Not enough data yet
    ACTIVE = "active"  # Normal operation
    DEGRADED = "degraded"  # Below quality threshold
    CORRUPTED = "corrupted"  # Integrity check failed
    DEPRECATED = "deprecated"  # No longer in use


class BaselineChangeType(StrEnum):
    """Types of baseline changes."""

    PATTERN_ADDED = "pattern_added"
    PATTERN_REMOVED = "pattern_removed"
    THRESHOLD_ADJUSTED = "threshold_adjusted"
    BASELINE_RESET = "baseline_reset"
    BASELINE_MERGED = "baseline_merged"


class QuorumStatus(StrEnum):
    """Status of a baseline change quorum."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    TIMEOUT = "timeout"


@dataclass
class BaselinePattern:
    """
    A pattern in the behavioral baseline.

    Attributes:
        pattern_id: Unique identifier
        pattern_hash: Hash for integrity verification
        pattern_type: Type of pattern (e.g., "rate_deviation", "response_time")
        description: Human-readable description
        created_at: When pattern was added
        updated_at: When pattern was last updated
        approved: Whether approved by quorum
        approved_by: Agent(s) that approved
        evidence_count: Number of supporting observations
        confidence: Confidence level (0.0-1.0)
        false_positive_rate: Historical FP rate
        enabled: Whether pattern is active for detection
    """

    pattern_id: str
    pattern_hash: str
    pattern_type: str
    description: str
    created_at: datetime
    updated_at: datetime
    approved: bool = False
    approved_by: list[str] = field(default_factory=list)
    evidence_count: int = 0
    confidence: float = 0.0
    false_positive_rate: float = 0.0
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "approved": self.approved,
            "approved_by": self.approved_by,
            "evidence_count": self.evidence_count,
            "confidence": self.confidence,
            "false_positive_rate": self.false_positive_rate,
            "enabled": self.enabled,
        }


@dataclass
class BaselineMetrics:
    """
    Metrics that define a behavioral baseline.

    Attributes:
        metric_name: Name of the metric
        mean: Mean value
        std: Standard deviation
        samples: Number of samples
        min_value: Minimum observed
        max_value: Maximum observed
        percentiles: Dict of percentile values
    """

    metric_name: str
    mean: float = 0.0
    std: float = 0.0
    samples: int = 0
    min_value: float = 0.0
    max_value: float = 0.0
    percentiles: dict[str, float] = field(default_factory=dict)

    def calculate_z_score(self, value: float) -> float:
        """Calculate z-score for a value."""
        if self.std == 0:
            return 0.0
        return abs(value - self.mean) / self.std

    def is_anomaly(self, value: float, threshold: float = 3.0) -> bool:
        """Check if value is anomalous given threshold."""
        return self.calculate_z_score(value) >= threshold


@dataclass
class BaselineChangeRequest:
    """
    A request to change the behavioral baseline.

    Attributes:
        request_id: Unique identifier
        change_type: Type of change
        pattern_id: ID of pattern being changed
        proposed_value: New value being proposed
        reasoning: Why this change is needed
        requester_id: Agent requesting the change
        created_at: When request was created
        quorum_required: Whether quorum is required
        quorum_status: Current quorum status
        votes_for: Agents that voted for
        votes_against: Agents that voted against
        completed_at: When quorum completed
    """

    request_id: str
    change_type: BaselineChangeType
    pattern_id: str
    proposed_value: dict[str, Any]
    reasoning: str
    requester_id: str
    created_at: datetime
    quorum_required: bool = True
    quorum_status: QuorumStatus = QuorumStatus.PENDING
    votes_for: list[str] = field(default_factory=list)
    votes_against: list[str] = field(default_factory=list)
    completed_at: datetime | None = None

    def add_vote(self, agent_id: str, approve: bool) -> None:
        """Add a vote to the request."""
        if approve:
            if agent_id not in self.votes_for:
                self.votes_for.append(agent_id)
        else:
            if agent_id not in self.votes_against:
                self.votes_against.append(agent_id)

    def get_approval_ratio(self) -> float:
        """Get ratio of approvals to total votes."""
        total = len(self.votes_for) + len(self.votes_against)
        if total == 0:
            return 0.0
        return len(self.votes_for) / total


@dataclass
class BaselineAuditEntry:
    """
    An immutable audit trail entry for baseline changes.

    Attributes:
        entry_id: Unique identifier
        timestamp: When the entry was created
        event_type: Type of event
        pattern_id: Related pattern ID
        agent_id: Agent that triggered the event
        previous_hash: Hash of previous entry (chain integrity)
        entry_hash: Hash of this entry
        details: Event-specific details
    """

    entry_id: str
    timestamp: datetime
    event_type: str
    pattern_id: str | None
    agent_id: str | None
    previous_hash: str | None
    entry_hash: str
    details: dict[str, Any]


class BehavioralBaseline:
    """
    Behavioral Baseline management system.

    This class provides:
    - Baseline establishment and maintenance
    - Statistical anomaly detection
    - Quorum-based baseline changes
    - Immutable audit trail
    - Novel pattern detection

    The baseline is critical infrastructure - corruption of the baseline
    could allow attacks to go undetected. Therefore:
    - All changes require quorum approval
    - An immutable audit trail is maintained
    - Baseline integrity can be verified at any time
    """

    def __init__(
        self,
        min_samples_for_baseline: int = 30,
        z_score_threshold: float = 3.0,
        quorum_size: int = 3,
        quorum_threshold: float = 0.66,
        quorum_timeout_seconds: float = 300.0,
        max_baseline_age_days: int = 90,  # noqa: ARG002
    ):
        """
        Initialize the behavioral baseline.

        Args:
            min_samples_for_baseline: Min samples before baseline is valid
            z_score_threshold: Z-score for anomaly detection
            quorum_size: Number of agents required for quorum
            quorum_threshold: Ratio required for approval
            quorum_timeout_seconds: Time limit for quorum
            max_baseline_age_days: Max age before baseline refresh
        """
        self.min_samples_for_baseline = min_samples_for_baseline
        self.z_score_threshold = z_score_threshold
        self.quorum_size = quorum_size
        self.quorum_threshold = quorum_threshold
        self.quorum_timeout_seconds = quorum_timeout_seconds

        # Agent baselines - maps agent_id to their behavioral baseline
        self._agent_baselines: dict[str, dict[str, BaselineMetrics]] = defaultdict(dict)

        # Known patterns in baseline
        self._baseline_patterns: dict[str, BaselinePattern] = {}

        # Pending quorum requests
        self._pending_requests: dict[str, BaselineChangeRequest] = {}

        # Audit trail
        self._audit_trail: list[BaselineAuditEntry] = []

        # Observed values for baseline calculation
        self._observed_values: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Baseline status
        self._baseline_status: dict[str, BaselineStatus] = defaultdict(
            lambda: BaselineStatus.ESTABLISHING
        )

        logger.info(
            "behavioral_baseline_initialized",
            min_samples=min_samples_for_baseline,
            z_score_threshold=z_score_threshold,
            quorum_size=quorum_size,
        )

    def _generate_entry_id(self) -> str:
        """Generate unique audit entry ID."""
        timestamp = datetime.now(UTC).timestamp()
        return f"AUDIT_{int(timestamp)}_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"

    def _generate_pattern_id(self, pattern_type: str, content: dict[str, Any]) -> str:
        """Generate pattern ID from content."""
        content_str = str(sorted(content.items()))
        hash_val = hashlib.sha256(content_str.encode()).hexdigest()[:12]
        return f"BP_{pattern_type.upper()}_{hash_val}"

    def _calculate_entry_hash(self, entry: dict[str, Any]) -> str:
        """Calculate hash for an audit entry."""
        entry_str = str(sorted(entry.items()))
        return hashlib.sha256(entry_str.encode()).hexdigest()[:16]

    def _record_audit(
        self,
        event_type: str,
        pattern_id: str | None = None,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> BaselineAuditEntry:
        """
        Record an immutable audit trail entry.

        Args:
            event_type: Type of event
            pattern_id: Related pattern ID
            agent_id: Agent that triggered event
            details: Event details

        Returns:
            Created audit entry
        """
        previous_hash = None
        if self._audit_trail:
            previous_hash = self._audit_trail[-1].entry_hash

        entry_id = self._generate_entry_id()
        timestamp = datetime.now(UTC)

        entry_data = {
            "entry_id": entry_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "pattern_id": pattern_id,
            "agent_id": agent_id,
            "previous_hash": previous_hash,
            "details": details or {},
        }

        entry_hash = self._calculate_entry_hash(entry_data)

        entry = BaselineAuditEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            event_type=event_type,
            pattern_id=pattern_id,
            agent_id=agent_id,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            details=details or {},
        )

        self._audit_trail.append(entry)

        logger.debug(
            "baseline_audit_recorded",
            entry_id=entry_id,
            event_type=event_type,
            pattern_id=pattern_id,
        )

        return entry

    def establish_baseline(
        self,
        agent_id: str,
        metric_name: str,
        values: list[float],
    ) -> bool:
        """
        Establish a behavioral baseline for an agent's metric.

        Args:
            agent_id: ID of the agent
            metric_name: Name of the metric
            values: Historical values to establish baseline from

        Returns:
            True if baseline was established
        """
        if len(values) < self.min_samples_for_baseline:
            logger.warning(
                "insufficient_samples_for_baseline",
                agent_id=agent_id,
                metric=metric_name,
                samples=len(values),
                required=self.min_samples_for_baseline,
            )
            return False

        # Calculate statistics
        mean = np.mean(values)
        std = np.std(values)
        min_val = min(values)
        max_val = max(values)

        # Calculate percentiles
        percentiles = {}
        for p in [25, 50, 75, 90, 95, 99]:
            percentiles[str(p)] = float(np.percentile(values, p))

        # Store metrics
        metrics = BaselineMetrics(
            metric_name=metric_name,
            mean=mean,
            std=std,
            samples=len(values),
            min_value=min_val,
            max_value=max_val,
            percentiles=percentiles,
        )

        self._agent_baselines[agent_id][metric_name] = metrics

        # Store raw values for future reference
        self._observed_values[agent_id][metric_name] = values[-1000:]  # Keep last 1000

        # Update status
        self._baseline_status[agent_id] = BaselineStatus.ACTIVE

        # Record audit
        self._record_audit(
            event_type="baseline_established",
            agent_id=agent_id,
            details={
                "metric_name": metric_name,
                "samples": len(values),
                "mean": mean,
                "std": std,
            },
        )

        logger.info(
            "baseline_established",
            agent_id=agent_id,
            metric=metric_name,
            samples=len(values),
            mean=mean,
            std=std,
        )

        return True

    def update_baseline(
        self,
        agent_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """
        Update baseline with a new observation.

        Uses Welford's online algorithm for incremental statistics.

        Args:
            agent_id: ID of the agent
            metric_name: Name of the metric
            value: New observation value
        """
        # Get or create baseline metrics
        if (
            agent_id not in self._agent_baselines
            or metric_name not in self._agent_baselines[agent_id]
        ):
            self._agent_baselines[agent_id][metric_name] = BaselineMetrics(metric_name=metric_name)

        metrics = self._agent_baselines[agent_id][metric_name]

        # Store raw value
        if agent_id not in self._observed_values:
            self._observed_values[agent_id] = {}
        if metric_name not in self._observed_values[agent_id]:
            self._observed_values[agent_id][metric_name] = []

        self._observed_values[agent_id][metric_name].append(value)

        # Keep only last 1000 values
        if len(self._observed_values[agent_id][metric_name]) > 1000:
            self._observed_values[agent_id][metric_name] = self._observed_values[agent_id][
                metric_name
            ][-1000:]

        # Update statistics using Welford's online algorithm
        n = metrics.samples + 1
        if n == 1:
            metrics.mean = value
            metrics.std = 0.0
        else:
            old_mean = metrics.mean
            metrics.mean = old_mean + (value - old_mean) / n
            metrics.std = (
                math.sqrt(
                    max(
                        0,
                        ((n - 2) * metrics.std**2 + (value - old_mean) * (value - metrics.mean))
                        / (n - 1),
                    )
                )
                if n > 1
                else 0.0
            )

        metrics.samples = n
        metrics.min_value = min(metrics.min_value, value) if metrics.samples > 1 else value
        metrics.max_value = max(metrics.max_value, value) if metrics.samples > 1 else value

        # Update status
        if metrics.samples >= self.min_samples_for_baseline:
            self._baseline_status[agent_id] = BaselineStatus.ACTIVE

    def check_anomaly(
        self,
        agent_id: str,
        metric_name: str,
        value: float,
    ) -> tuple[bool, float]:
        """
        Check if a value is anomalous given the baseline.

        Args:
            agent_id: ID of the agent
            metric_name: Name of the metric
            value: Value to check

        Returns:
            Tuple of (is_anomaly, z_score)
        """
        if agent_id not in self._agent_baselines:
            return (False, 0.0)

        if metric_name not in self._agent_baselines[agent_id]:
            return (False, 0.0)

        metrics = self._agent_baselines[agent_id][metric_name]

        if metrics.samples < self.min_samples_for_baseline:
            return (False, 0.0)

        z_score = metrics.calculate_z_score(value)
        is_anomaly = z_score >= self.z_score_threshold

        return (is_anomaly, z_score)

    def adjust_z_score_threshold(
        self,
        delta: float,
        agent_id: str | None = None,
    ) -> float:
        """
        Adjust the z-score threshold for anomaly detection.

        The delta is rate-capped at ±0.1 sigma per call to prevent
        oscillation — values outside this range are silently clamped.
        The threshold is clamped to a minimum of 1.0.

        Each adjustment records an immutable audit entry and emits a
        structured log signal at INFO level.

        Args:
            delta: Amount to adjust the threshold (silently clamped to
                ``[-0.1, 0.1]``).
            agent_id: Optional ID of the agent triggering the adjustment.

        Returns:
            The new z_score_threshold value.
        """
        # Clamp delta to the rate-capped range
        clamped_delta = max(-0.1, min(0.1, delta))

        old_threshold = self.z_score_threshold
        new_threshold = old_threshold + clamped_delta

        # Enforce minimum sane threshold of 1.0
        if new_threshold < 1.0:
            new_threshold = 1.0
            clamped_delta = new_threshold - old_threshold

        self.z_score_threshold = new_threshold

        # Record immutable audit entry
        self._record_audit(
            event_type="baseline_threshold_adjusted",
            agent_id=agent_id,
            details={
                "previous_threshold": old_threshold,
                "new_threshold": new_threshold,
                "delta": clamped_delta,
            },
        )

        # Emit structured log signal
        logger.info(
            "baseline_threshold_adjusted",
            previous_threshold=old_threshold,
            new_threshold=new_threshold,
            delta=clamped_delta,
            agent_id=agent_id,
        )

        return new_threshold

    def add_baseline_pattern(
        self,
        pattern_type: str,
        description: str,
        content: dict[str, Any],
        confidence: float = 0.0,
        requester_id: str | None = None,
    ) -> str:
        """
        Add a new pattern to the baseline.

        Patterns require quorum approval before being considered trusted.

        Args:
            pattern_type: Type of pattern
            description: Human-readable description
            content: Pattern content
            confidence: Initial confidence level
            requester_id: Agent requesting the addition

        Returns:
            Pattern ID
        """
        pattern_id = self._generate_pattern_id(pattern_type, content)
        pattern_hash = hashlib.sha256(str(sorted(content.items())).encode()).hexdigest()[:16]
        timestamp = datetime.now(UTC)

        pattern = BaselinePattern(
            pattern_id=pattern_id,
            pattern_hash=pattern_hash,
            pattern_type=pattern_type,
            description=description,
            created_at=timestamp,
            updated_at=timestamp,
            confidence=confidence,
        )

        self._baseline_patterns[pattern_id] = pattern

        # Record audit
        self._record_audit(
            event_type="baseline_pattern_proposed",
            pattern_id=pattern_id,
            agent_id=requester_id,
            details={
                "pattern_type": pattern_type,
                "description": description,
                "confidence": confidence,
            },
        )

        logger.info(
            "baseline_pattern_proposed",
            pattern_id=pattern_id,
            pattern_type=pattern_type,
        )

        return pattern_id

    def request_baseline_change(
        self,
        change_type: BaselineChangeType,
        pattern_id: str,
        proposed_value: dict[str, Any],
        reasoning: str,
        requester_id: str,
    ) -> str:
        """
        Request a change to the baseline with quorum approval.

        This prevents baseline corruption by requiring multiple agents
        to approve changes.

        Args:
            change_type: Type of change
            pattern_id: ID of pattern being changed
            proposed_value: New value being proposed
            reasoning: Why this change is needed
            requester_id: Agent requesting the change

        Returns:
            Request ID
        """
        request_id = f"REQ_{int(datetime.now(UTC).timestamp())}_{hashlib.sha256(str(datetime.now(UTC).timestamp()).encode()).hexdigest()[:8]}"  # noqa: E501

        request = BaselineChangeRequest(
            request_id=request_id,
            change_type=change_type,
            pattern_id=pattern_id,
            proposed_value=proposed_value,
            reasoning=reasoning,
            requester_id=requester_id,
            created_at=datetime.now(UTC),
            quorum_required=True,
        )

        self._pending_requests[request_id] = request

        # Record audit
        self._record_audit(
            event_type="baseline_change_requested",
            pattern_id=pattern_id,
            agent_id=requester_id,
            details={
                "request_id": request_id,
                "change_type": change_type.value,
                "reasoning": reasoning,
            },
        )

        logger.info(
            "baseline_change_requested",
            request_id=request_id,
            change_type=change_type.value,
            pattern_id=pattern_id,
            requester=requester_id,
        )

        return request_id

    def submit_change_vote(
        self,
        request_id: str,
        agent_id: str,
        approve: bool,
    ) -> bool:
        """
        Submit a vote for a baseline change request.

        Args:
            request_id: ID of the change request
            agent_id: ID of voting agent
            approve: True to approve, False to reject

        Returns:
            True if vote was recorded
        """
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        request.add_vote(agent_id, approve)

        # Record audit
        self._record_audit(
            event_type="change_vote_submitted",
            pattern_id=request.pattern_id,
            agent_id=agent_id,
            details={
                "request_id": request_id,
                "approve": approve,
                "current_ratio": request.get_approval_ratio(),
            },
        )

        # Check if quorum is reached
        total_votes = len(request.votes_for) + len(request.votes_against)

        if total_votes >= self.quorum_size:
            if request.get_approval_ratio() >= self.quorum_threshold:
                request.quorum_status = QuorumStatus.APPROVED
                request.completed_at = datetime.now(UTC)
                self._apply_change(request)
            elif len(request.votes_against) >= self.quorum_size:
                request.quorum_status = QuorumStatus.REJECTED
                request.completed_at = datetime.now(UTC)

        # Check timeout
        elapsed = (datetime.now(UTC) - request.created_at).total_seconds()
        if elapsed > self.quorum_timeout_seconds and request.quorum_status == QuorumStatus.PENDING:
            request.quorum_status = QuorumStatus.TIMEOUT
            request.completed_at = datetime.now(UTC)

        logger.info(
            "change_vote_submitted",
            request_id=request_id,
            agent_id=agent_id,
            approve=approve,
            votes_for=len(request.votes_for),
            votes_against=len(request.votes_against),
            status=request.quorum_status.value,
        )

        return True

    def _apply_change(self, request: BaselineChangeRequest) -> None:
        """
        Apply an approved baseline change.

        Args:
            request: The approved change request
        """
        pattern = self._baseline_patterns.get(request.pattern_id)

        if pattern:
            if request.change_type == BaselineChangeType.PATTERN_ADDED:
                pattern.approved = True
                pattern.approved_by = request.votes_for
                pattern.updated_at = datetime.now(UTC)
            elif request.change_type == BaselineChangeType.PATTERN_REMOVED:
                pattern.enabled = False
                pattern.updated_at = datetime.now(UTC)
            elif request.change_type == BaselineChangeType.THRESHOLD_ADJUSTED:
                pattern.updated_at = datetime.now(UTC)
                if "confidence" in request.proposed_value:
                    pattern.confidence = request.proposed_value["confidence"]

        # Record audit
        self._record_audit(
            event_type="baseline_change_applied",
            pattern_id=request.pattern_id,
            agent_id=request.requester_id,
            details={
                "request_id": request.request_id,
                "change_type": request.change_type.value,
                "approved_by": request.votes_for,
            },
        )

        logger.info(
            "baseline_change_applied",
            request_id=request.request_id,
            change_type=request.change_type.value,
            pattern_id=request.pattern_id,
        )

    def get_baseline_status(self, agent_id: str) -> BaselineStatus:
        """
        Get the baseline status for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Current baseline status
        """
        return self._baseline_status.get(agent_id, BaselineStatus.ESTABLISHING)

    def get_agent_baseline(self, agent_id: str) -> dict[str, dict[str, Any]]:
        """
        Get the complete baseline for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary of metric baselines
        """
        if agent_id not in self._agent_baselines:
            return {}

        return {
            metric_name: {
                "mean": m.mean,
                "std": m.std,
                "samples": m.samples,
                "min": m.min_value,
                "max": m.max_value,
                "percentiles": m.percentiles,
            }
            for metric_name, m in self._agent_baselines[agent_id].items()
        }

    def get_baseline_patterns(
        self,
        approved_only: bool = False,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get baseline patterns.

        Args:
            approved_only: If True, only return approved patterns
            enabled_only: If True, only return enabled patterns

        Returns:
            List of pattern dictionaries
        """
        patterns = list(self._baseline_patterns.values())

        if approved_only:
            patterns = [p for p in patterns if p.approved]
        if enabled_only:
            patterns = [p for p in patterns if p.enabled]

        return [p.to_dict() for p in patterns]

    def verify_baseline_integrity(self) -> dict[str, Any]:
        """
        Verify the integrity of the baseline and audit trail.

        Returns:
            Verification results
        """
        results = {
            "valid": True,
            "baseline_patterns_count": len(self._baseline_patterns),
            "approved_patterns_count": sum(
                1 for p in self._baseline_patterns.values() if p.approved
            ),
            "pending_requests": len(self._pending_requests),
            "audit_trail_entries": len(self._audit_trail),
            "errors": [],
        }

        # Verify audit trail chain
        previous_hash = None
        for i, entry in enumerate(self._audit_trail):
            if entry.previous_hash != previous_hash:
                results["valid"] = False
                results["errors"].append(f"Chain broken at entry {i}")
            previous_hash = entry.entry_hash

        # Check for pending requests that should have completed
        now = datetime.now(UTC)
        for req in self._pending_requests.values():
            if req.quorum_status == QuorumStatus.PENDING:
                elapsed = (now - req.created_at).total_seconds()
                if elapsed > self.quorum_timeout_seconds:
                    results["errors"].append(f"Request {req.request_id} has exceeded timeout")

        return results

    def get_audit_trail(
        self,
        limit: int = 100,
        pattern_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get audit trail entries.

        Args:
            limit: Maximum entries to return
            pattern_id: Filter by pattern ID

        Returns:
            List of audit entries
        """
        entries = self._audit_trail

        if pattern_id:
            entries = [e for e in entries if e.pattern_id == pattern_id]

        return [
            {
                "entry_id": e.entry_id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "pattern_id": e.pattern_id,
                "agent_id": e.agent_id,
                "entry_hash": e.entry_hash,
                "details": e.details,
            }
            for e in entries[-limit:]
        ]

    def get_statistics(self) -> dict[str, Any]:
        """
        Get baseline statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_agents_with_baseline": len(self._agent_baselines),
            "total_baseline_patterns": len(self._baseline_patterns),
            "approved_patterns": sum(1 for p in self._baseline_patterns.values() if p.approved),
            "pending_change_requests": len(self._pending_requests),
            "audit_trail_entries": len(self._audit_trail),
            "baseline_status_distribution": {
                status.value: sum(1 for s in self._baseline_status.values() if s == status)
                for status in BaselineStatus
            },
        }


def validate_threshold_delta(delta: float) -> float:
    """
    Validate and return a threshold delta for use with
    ``adjust_z_score_threshold``.

    This is the input-validation layer — callers **must** use this before
    passing a delta if they want early rejection of out-of-range values.
    Values whose absolute magnitude exceeds the rate cap are rejected
    with ``ValueError``.

    Args:
        delta: Proposed delta value.

    Returns:
        The validated (possibly clamped) delta value.

    Raises:
        ValueError: If ``abs(delta) > 0.1``.
    """
    if delta < -0.1 or delta > 0.1:
        raise ValueError(
            f"delta={delta} exceeds rate cap of ±0.1 per call"
        )
    return max(-0.1, min(0.1, delta))


def create_behavioral_baseline(
    config: dict[str, Any] | None = None,
) -> BehavioralBaseline:
    """
    Create a configured behavioral baseline.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured BehavioralBaseline instance
    """
    if config is None:
        config = {}

    return BehavioralBaseline(
        min_samples_for_baseline=config.get("min_samples_for_baseline", 30),
        z_score_threshold=config.get("z_score_threshold", 3.0),
        quorum_size=config.get("quorum_size", 3),
        quorum_threshold=config.get("quorum_threshold", 0.66),
        quorum_timeout_seconds=config.get("quorum_timeout_seconds", 300.0),
    )
