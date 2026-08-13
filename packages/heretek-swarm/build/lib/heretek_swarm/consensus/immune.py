"""
Immune Response Building Module for Heretek Swarm.

This module implements the "immune system" of the swarm - the ability to:
- Learn from anomaly responses (like an immune system learning from infection)
- Build persistent immunity to attack patterns
- Detect and reject novel attack patterns
- Maintain false positive rate < 1%

The immune system works by:
1. Sentinel detects an anomaly and responds
2. If the response is successful (agent survives, threat neutralized), the
   pattern is considered for addition to the baseline
3. Novel patterns that haven't been seen before are preserved for human review
4. Patterns that pass quorum approval are added to the behavioral baseline

Key features:
- Pattern validation with minimum occurrence threshold
- Quorum-based baseline updates (prevents baseline corruption)
- Novel attack pattern preservation for human review
- Immutable audit trail for all immune responses
- False positive tracking and threshold adjustment

Reference: Phase 2 Plan Task 2 (CONS-02)
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.collective.learning import PatternStatus

if TYPE_CHECKING:
    from heretek_swarm.security.behavioral_baseline import BaselineChangeType

logger = structlog.get_logger("immune_response")


class ImmuneStatus(StrEnum):
    """Status of an immune response."""

    NAIVE = "naive"  # No exposure to pattern
    EXPOSED = "exposed"  # Pattern detected, response in progress
    IMMUNE = "immune"  # Pattern recognized and blocked
    ANERGIC = "anergic"  # Pattern detected but response failed
    UNKNOWN = "unknown"  # Insufficient data


class PatternClassification(StrEnum):
    """Classification of detected patterns."""

    KNOWN_BENIGN = "known_benign"  # Normal behavior, no action needed
    KNOWN_MALICIOUS = "known_malicious"  # Known attack pattern
    NOVEL_BENIGN = "novel_benign"  # New behavior, needs monitoring
    NOVEL_MALICIOUS = "novel_malicious"  # New attack pattern
    UNCLASSIFIED = "unclassified"  # Insufficient data


class ResponseOutcome(StrEnum):
    """Outcome of an anomaly response."""

    SUCCESS = "success"  # Threat neutralized, agent healthy
    FAILURE = "failure"  # Response failed, threat persisted
    PARTIAL = "partial"  # Partial success, some threat remains
    ESCALATED = "escalated"  # Required human intervention
    FALSE_POSITIVE = "false_positive"  # Was not an actual threat


@dataclass
class ImmunePattern:
    """
    A pattern that the immune system has learned to recognize.

    Attributes:
        pattern_id: Unique identifier for this pattern
        pattern_hash: Hash of the pattern for integrity
        pattern_type: Type of anomaly this pattern represents
        severity: Typical severity when detected
        first_seen: When this pattern was first observed
        last_seen: When this pattern was last observed
        occurrence_count: Number of times pattern has been observed
        block_count: Number of times pattern has been blocked
        false_positive_count: Number of false positives for this pattern
        false_positive_rate: Calculated FP rate for this pattern
        status: Current immune status for this pattern
        confidence: Confidence that this is a true threat pattern
        approved: Whether this pattern has been approved for baseline
        approved_by: Agent ID that approved (if approved)
        approved_at: Timestamp of approval
        evidence: List of evidence IDs supporting this pattern
    """

    pattern_id: str
    pattern_hash: str
    pattern_type: str
    severity: str
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = 0
    block_count: int = 0
    false_positive_count: int = 0
    false_positive_rate: float = 0.0
    status: ImmuneStatus = ImmuneStatus.NAIVE
    confidence: float = 0.0
    approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    evidence: list[str] = field(default_factory=list)

    def calculate_false_positive_rate(self) -> float:
        """Calculate false positive rate for this pattern."""
        if self.occurrence_count == 0:
            return 0.0
        return self.false_positive_count / self.occurrence_count

    def is_trustworthy(self, min_confidence: float = 0.7, max_fp_rate: float = 0.01) -> bool:
        """Check if pattern is trustworthy for auto-blocking."""
        return (
            self.confidence >= min_confidence
            and self.false_positive_rate <= max_fp_rate
            and self.approved
        )


@dataclass
class ImmuneResponse:
    """
    Record of an immune response to a detected pattern.

    Attributes:
        response_id: Unique identifier
        pattern_id: ID of the pattern responded to
        agent_id: Agent that was targeted
        anomaly_id: ID of the anomaly that triggered response
        outcome: Result of the response
        response_time_ms: Time taken to respond
        timestamp: When the response occurred
        pattern_snapshot: Hash of pattern at time of response
        learned_pattern: Whether this response taught us something new
    """

    response_id: str
    pattern_id: str
    agent_id: str
    anomaly_id: str
    outcome: ResponseOutcome
    response_time_ms: float
    timestamp: datetime
    pattern_snapshot: str
    learned_pattern: bool = False


@dataclass
class NovelPatternPreservation:
    """
    Preservation record for novel attack patterns awaiting human review.

    Attributes:
        preservation_id: Unique identifier
        pattern_content: The actual pattern content
        pattern_hash: Hash for integrity
        pattern_type: Type of pattern
        first_observed: When first seen
        occurrence_count: Number of occurrences
        context: Context information about the pattern
        reviewed: Whether a human has reviewed this
        reviewed_by: Human reviewer ID (if reviewed)
        review_notes: Notes from human review
        disposition: What to do with pattern (approve/reject/investigate)
    """

    preservation_id: str
    pattern_content: dict[str, Any]
    pattern_hash: str
    pattern_type: str
    first_observed: datetime
    last_observed: datetime
    occurrence_count: int = 1
    context: dict[str, Any] = field(default_factory=dict)
    reviewed: bool = False
    reviewed_by: str | None = None
    review_notes: str | None = None
    disposition: str | None = None


@dataclass
class ImmuneQuorum:
    """
    Quorum configuration for baseline changes.

    Attributes:
        required_agents: Number of agents required to approve
        total_agents: Total number of agents in the quorum pool
        approval_threshold: Ratio of approvals required (0.0-1.0)
        timeout_seconds: Time limit for reaching quorum
        current_approvals: Current approval count
        rejection_count: Current rejection count
        started_at: When quorum process started
        completed_at: When quorum was reached (if complete)
    """

    required_agents: int = 3
    total_agents: int = 5
    approval_threshold: float = 0.6
    timeout_seconds: float = 300.0
    current_approvals: int = 0
    rejection_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def is_complete(self) -> bool:
        """Check if quorum has been reached."""
        if self.completed_at is not None:
            return True
        total_votes = self.current_approvals + self.rejection_count
        if total_votes >= self.required_agents:
            return True
        if self.started_at is None:
            return False
        elapsed = (datetime.now(UTC) - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds

    def is_approved(self) -> bool | None:
        """Check if quorum approved. Returns None if incomplete or inconclusive."""
        if not self.is_complete():
            return None
        if self.completed_at is not None:
            return self.current_approvals > self.rejection_count
        # Timeout occurred - if no votes cast, return None (inconclusive)
        total_votes = self.current_approvals + self.rejection_count
        if total_votes == 0:
            return None
        return self.current_approvals > self.rejection_count

    def get_approval_ratio(self) -> float:
        """Get the current approval ratio (approvals / total votes)."""
        total_votes = self.current_approvals + self.rejection_count
        if total_votes == 0:
            return 0.0
        return self.current_approvals / total_votes


class ImmuneResponseBuilding:
    """
    Immune Response Building system for the Heretek Swarm.

    This class implements the immune system analogy:
    - Patterns are antigens
    - Successful responses create immunity
    - The behavioral baseline is the immune memory
    - Novel patterns trigger antibody production (human review)

    Key methods:
        record_response: Record an immune response to an anomaly
        learn_from_response: Update immune memory based on response outcome
        request_baseline_update: Request quorum approval for baseline change
        check_pattern_immunity: Check if a pattern is recognized
        preserve_novel_pattern: Store a novel pattern for human review
        calculate_false_positive_rate: Calculate system-wide FP rate
    """

    def __init__(
        self,
        min_occurrences_for_immunity: int = 3,
        min_confidence_for_baseline: float = 0.7,
        max_false_positive_rate: float = 0.01,
        quorum_required_agents: int = 3,
        novel_pattern_retention_days: int = 30,
    ):
        """
        Initialize the immune response building system.

        Args:
            min_occurrences_for_immunity: Min times pattern must be seen before immunity
            min_confidence_for_baseline: Min confidence before baseline consideration
            max_false_positive_rate: Max FP rate for auto-approval to baseline
            quorum_required_agents: Agents required for baseline change quorum
            novel_pattern_retention_days: Days to preserve novel patterns
        """
        self.min_occurrences_for_immunity = min_occurrences_for_immunity
        self.min_confidence_for_baseline = min_confidence_for_baseline
        self.max_false_positive_rate = max_false_positive_rate
        self.quorum_required_agents = quorum_required_agents

        # Immune memory - patterns we've learned
        self._immune_memory: dict[str, ImmunePattern] = {}

        # Response history
        self._response_history: list[ImmuneResponse] = []
        self._max_response_history = 10000

        # Novel patterns awaiting human review
        self._novel_patterns: dict[str, NovelPatternPreservation] = {}
        self._novel_pattern_retention_days = novel_pattern_retention_days

        # Pending quorum requests for baseline updates
        self._pending_quorums: dict[str, ImmuneQuorum] = {}

        # Statistics
        self._stats = {
            "total_responses": 0,
            "successful_responses": 0,
            "failed_responses": 0,
            "patterns_learned": 0,
            "baseline_updates_approved": 0,
            "baseline_updates_rejected": 0,
            "novel_patterns_preserved": 0,
            "false_positives_reported": 0,
        }

        # Audit trail for immutable logging
        self._audit_trail: list[dict[str, Any]] = []

        logger.info(
            "immune_response_building_initialized",
            min_occurrences=self.min_occurrences_for_immunity,
            min_confidence=self.min_confidence_for_baseline,
            max_fp_rate=self.max_false_positive_rate,
        )

    def _generate_pattern_hash(self, pattern_content: dict[str, Any]) -> str:
        """Generate a hash for pattern integrity."""
        content_str = str(sorted(pattern_content.items()))
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def _generate_response_id(self) -> str:
        """Generate unique response ID."""
        timestamp = datetime.now(UTC).timestamp()
        return f"IMMUNE_RESP_{int(timestamp)}_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"  # noqa: E501

    def _generate_pattern_id(self, pattern_hash: str) -> str:
        """Generate pattern ID from hash."""
        return f"PATTERN_{pattern_hash}"

    def record_response(
        self,
        pattern_content: dict[str, Any],
        anomaly_id: str,
        agent_id: str,
        outcome: ResponseOutcome,
        response_time_ms: float,
    ) -> ImmuneResponse:
        """
        Record an immune response to an anomaly.

        This should be called after Sentinel has responded to an anomaly.
        The response is analyzed to determine if we learned anything.

        Args:
            pattern_content: Content of the detected pattern
            anomaly_id: ID of the anomaly that triggered response
            agent_id: ID of the agent that was targeted
            outcome: Result of the response
            response_time_ms: Time taken to respond

        Returns:
            The recorded immune response
        """
        pattern_hash = self._generate_pattern_hash(pattern_content)
        pattern_id = self._generate_pattern_id(pattern_hash)
        timestamp = datetime.now(UTC)

        response = ImmuneResponse(
            response_id=self._generate_response_id(),
            pattern_id=pattern_id,
            agent_id=agent_id,
            anomaly_id=anomaly_id,
            outcome=outcome,
            response_time_ms=response_time_ms,
            timestamp=timestamp,
            pattern_snapshot=pattern_hash,
        )

        self._response_history.append(response)
        self._stats["total_responses"] += 1

        if outcome == ResponseOutcome.SUCCESS:
            self._stats["successful_responses"] += 1
        elif outcome == ResponseOutcome.FAILURE:
            self._stats["failed_responses"] += 1
        elif outcome == ResponseOutcome.FALSE_POSITIVE:
            self._stats["false_positives_reported"] += 1

        # Prune old responses
        if len(self._response_history) > self._max_response_history:
            self._response_history = self._response_history[-self._max_response_history :]

        # Record to audit trail
        self._record_audit_event(
            event_type="immune_response_recorded",
            pattern_id=pattern_id,
            agent_id=agent_id,
            outcome=outcome.value,
        )

        logger.info(
            "immune_response_recorded",
            response_id=response.response_id,
            pattern_id=pattern_id,
            agent_id=agent_id,
            outcome=outcome.value,
        )

        return response

    def learn_from_response(
        self,
        response: ImmuneResponse,
        pattern_content: dict[str, Any],  # noqa: ARG002
        pattern_type: str,
        severity: str,
    ) -> bool:
        """
        Learn from an immune response and update immune memory.

        This implements the core learning algorithm:
        - Successful responses to a pattern increase its block count
        - False positives decrease confidence
        - Patterns meeting thresholds are flagged for baseline consideration

        Args:
            response: The recorded immune response
            pattern_content: Content of the pattern
            pattern_type: Type of anomaly
            severity: Typical severity

        Returns:
            True if pattern was learned (immunity acquired)
        """
        pattern_hash = response.pattern_snapshot
        pattern_id = response.pattern_id
        timestamp = datetime.now(UTC)

        # Get or create immune pattern
        if pattern_id not in self._immune_memory:
            self._immune_memory[pattern_id] = ImmunePattern(
                pattern_id=pattern_id,
                pattern_hash=pattern_hash,
                pattern_type=pattern_type,
                severity=severity,
                first_seen=timestamp,
                last_seen=timestamp,
            )

        immune_pattern = self._immune_memory[pattern_id]
        immune_pattern.last_seen = timestamp
        immune_pattern.occurrence_count += 1

        # Update based on outcome
        if response.outcome == ResponseOutcome.SUCCESS:
            immune_pattern.block_count += 1
            immune_pattern.status = ImmuneStatus.IMMUNE
        elif response.outcome == ResponseOutcome.FALSE_POSITIVE:
            immune_pattern.false_positive_count += 1
            immune_pattern.status = ImmuneStatus.ANERGIC
        elif response.outcome == ResponseOutcome.FAILURE:
            immune_pattern.status = ImmuneStatus.ANERGIC

        # Recalculate false positive rate
        immune_pattern.false_positive_rate = immune_pattern.calculate_false_positive_rate()

        # Update confidence based on successful blocks vs false positives
        if immune_pattern.occurrence_count > 0:
            successful_blocks = immune_pattern.block_count - immune_pattern.false_positive_count
            immune_pattern.confidence = max(
                0.0, min(1.0, successful_blocks / immune_pattern.occurrence_count)
            )

        # Add evidence
        if response.anomaly_id not in immune_pattern.evidence:
            immune_pattern.evidence.append(response.anomaly_id)

        # Check if immunity threshold reached
        immunity_acquired = (
            immune_pattern.status == ImmuneStatus.IMMUNE
            and immune_pattern.occurrence_count >= self.min_occurrences_for_immunity
            and immune_pattern.false_positive_rate <= self.max_false_positive_rate
        )

        if immunity_acquired and not immune_pattern.approved:
            self._stats["patterns_learned"] += 1
            logger.info(
                "pattern_immunity_acquired",
                pattern_id=pattern_id,
                occurrence_count=immune_pattern.occurrence_count,
                confidence=immune_pattern.confidence,
            )

        # Record to audit trail
        self._record_audit_event(
            event_type="immune_pattern_learned",
            pattern_id=pattern_id,
            outcome=response.outcome.value,
            immunity_acquired=immunity_acquired,
        )

        return immunity_acquired

    def request_baseline_update(
        self,
        pattern_id: str,
        requesting_agent_id: str,
    ) -> str | None:
        """
        Request quorum approval for adding a pattern to the baseline.

        Args:
            pattern_id: ID of pattern to add to baseline
            requesting_agent_id: Agent requesting the update

        Returns:
            Quorum ID if request was created, None if pattern not found
        """
        if pattern_id not in self._immune_memory:
            logger.warning("baseline_update_requested_for_unknown_pattern", pattern_id=pattern_id)
            return None

        immune_pattern = self._immune_memory[pattern_id]

        # Check if pattern meets minimum requirements
        if immune_pattern.occurrence_count < self.min_occurrences_for_immunity:
            logger.info(
                "pattern_below_occurrence_threshold",
                pattern_id=pattern_id,
                occurrences=immune_pattern.occurrence_count,
                required=self.min_occurrences_for_immunity,
            )
            return None

        # Create quorum
        quorum_id = f"QUORUM_{pattern_id}_{int(datetime.now(UTC).timestamp())}"
        quorum = ImmuneQuorum(
            required_agents=self.quorum_required_agents,
            started_at=datetime.now(UTC),
        )

        self._pending_quorums[quorum_id] = quorum

        # Record to audit trail
        self._record_audit_event(
            event_type="baseline_update_quorum_requested",
            pattern_id=pattern_id,
            quorum_id=quorum_id,
            requesting_agent=requesting_agent_id,
        )

        logger.info(
            "baseline_update_quorum_initiated",
            pattern_id=pattern_id,
            quorum_id=quorum_id,
        )

        return quorum_id

    def submit_quorum_vote(
        self,
        quorum_id: str,
        agent_id: str,
        approve: bool,
    ) -> bool:
        """
        Submit a vote for a baseline update quorum.

        Args:
            quorum_id: ID of the quorum
            agent_id: ID of voting agent
            approve: True to approve, False to reject

        Returns:
            True if vote was recorded
        """
        if quorum_id not in self._pending_quorums:
            return False

        quorum = self._pending_quorums[quorum_id]

        if approve:
            quorum.current_approvals += 1
        else:
            quorum.rejection_count += 1

        # Check if quorum is complete
        if quorum.is_complete():
            quorum.completed_at = datetime.now(UTC)

            # Apply result to pattern - extract pattern_id from quorum_id
            # quorum_id format: "QUORUM_<pattern_id>_<timestamp>"
            # Use maxsplit=1 to get everything after "QUORUM" as the pattern_id_timestamp
            parts = quorum_id.split("_", 1)
            if len(parts) > 1:

                # Extract pattern_id by removing the trailing timestamp
                pattern_id_with_ts = parts[1]
                # Find the last underscore and use everything before it as pattern_id
                last_underscore = pattern_id_with_ts.rfind("_")
                if last_underscore > 0:
                    pattern_id = pattern_id_with_ts[:last_underscore]
                else:
                    pattern_id = pattern_id_with_ts
            else:
                pattern_id = None

            if pattern_id and pattern_id in self._immune_memory:
                immune_pattern = self._immune_memory[pattern_id]

                if quorum.is_approved():
                    immune_pattern.approved = True
                    immune_pattern.approved_by = "quorum"
                    immune_pattern.approved_at = datetime.now(UTC)
                    self._stats["baseline_updates_approved"] += 1
                    logger.info("baseline_update_approved_by_quorum", pattern_id=pattern_id)
                else:
                    self._stats["baseline_updates_rejected"] += 1
                    logger.info("baseline_update_rejected_by_quorum", pattern_id=pattern_id)

            # Record to audit trail
            self._record_audit_event(
                event_type="baseline_update_quorum_completed",
                quorum_id=quorum_id,
                approved=quorum.is_approved(),
                approvals=quorum.current_approvals,
                rejections=quorum.rejection_count,
            )

        # Record vote to audit trail
        self._record_audit_event(
            event_type="quorum_vote_submitted",
            quorum_id=quorum_id,
            agent_id=agent_id,
            approve=approve,
        )

        return True

    def check_pattern_immunity(
        self,
        pattern_content: dict[str, Any],
    ) -> tuple[PatternClassification, ImmunePattern | None]:
        """
        Check if a pattern is recognized by the immune system.

        Args:
            pattern_content: Content of the pattern to check

        Returns:
            Tuple of (classification, immune_pattern if found)
        """
        pattern_hash = self._generate_pattern_hash(pattern_content)
        pattern_id = self._generate_pattern_id(pattern_hash)

        if pattern_id not in self._immune_memory:
            return (PatternClassification.NOVEL_MALICIOUS, None)

        immune_pattern = self._immune_memory[pattern_id]

        if immune_pattern.approved:
            return (PatternClassification.KNOWN_MALICIOUS, immune_pattern)
        if immune_pattern.false_positive_rate > self.max_false_positive_rate:
            return (PatternClassification.KNOWN_BENIGN, immune_pattern)
        return (PatternClassification.UNCLASSIFIED, immune_pattern)

    def preserve_novel_pattern(
        self,
        pattern_content: dict[str, Any],
        pattern_type: str,
        context: dict[str, Any],
    ) -> str:
        """
        Preserve a novel pattern for human review.

        Novel patterns are attack patterns that haven't been seen before
        and aren't in the baseline. They are preserved so that humans
        can review them and decide whether to add them to the baseline.

        Args:
            pattern_content: Content of the novel pattern
            pattern_type: Type of pattern
            context: Context information

        Returns:
            Preservation ID for tracking
        """
        timestamp = datetime.now(UTC)
        pattern_hash = self._generate_pattern_hash(pattern_content)
        preservation_id = f"NOVEL_{pattern_hash}_{int(timestamp.timestamp())}"

        preservation = NovelPatternPreservation(
            preservation_id=preservation_id,
            pattern_content=pattern_content,
            pattern_hash=pattern_hash,
            pattern_type=pattern_type,
            first_observed=timestamp,
            last_observed=timestamp,
            context=context,
        )

        self._novel_patterns[preservation_id] = preservation
        self._stats["novel_patterns_preserved"] += 1

        # Record to audit trail
        self._record_audit_event(
            event_type="novel_pattern_preserved",
            preservation_id=preservation_id,
            pattern_type=pattern_type,
        )

        logger.info(
            "novel_pattern_preserved_for_review",
            preservation_id=preservation_id,
            pattern_type=pattern_type,
        )

        return preservation_id

    def get_novel_patterns_for_review(
        self,
        limit: int = 50,
        unreviewed_only: bool = True,
    ) -> list[NovelPatternPreservation]:
        """
        Get novel patterns awaiting human review.

        Args:
            limit: Maximum patterns to return
            unreviewed_only: If True, only return unreviewed patterns

        Returns:
            List of novel pattern preservation records
        """
        patterns = list(self._novel_patterns.values())

        if unreviewed_only:
            patterns = [p for p in patterns if not p.reviewed]

        # Sort by occurrence count (most frequent first)
        patterns.sort(key=lambda p: p.occurrence_count, reverse=True)

        return patterns[:limit]

    def record_human_review(
        self,
        preservation_id: str,
        reviewer_id: str,
        disposition: str,
        notes: str | None = None,
    ) -> bool:
        """
        Record human review of a novel pattern.

        Args:
            preservation_id: ID of the preservation record
            reviewer_id: ID of the human reviewer
            disposition: Decision (approve/reject/investigate)
            notes: Optional review notes

        Returns:
            True if review was recorded
        """
        if preservation_id not in self._novel_patterns:
            return False

        pattern = self._novel_patterns[preservation_id]
        pattern.reviewed = True
        pattern.reviewed_by = reviewer_id
        pattern.review_notes = notes
        pattern.disposition = disposition

        # If approved, add to immune memory
        if disposition == "approve":
            pattern_id = self._generate_pattern_id(pattern.pattern_hash)
            timestamp = datetime.now(UTC)

            self._immune_memory[pattern_id] = ImmunePattern(
                pattern_id=pattern_id,
                pattern_hash=pattern.pattern_hash,
                pattern_type=pattern.pattern_type,
                severity="high",
                first_seen=pattern.first_observed,
                last_seen=timestamp,
                occurrence_count=pattern.occurrence_count,
                approved=True,
                approved_by=reviewer_id,
                approved_at=timestamp,
            )

            self._stats["patterns_learned"] += 1

        # Record to audit trail
        self._record_audit_event(
            event_type="novel_pattern_reviewed",
            preservation_id=preservation_id,
            reviewer_id=reviewer_id,
            disposition=disposition,
        )

        return True

    def calculate_false_positive_rate(self) -> float:
        """
        Calculate the system-wide false positive rate.

        Returns:
            FP rate as a float (e.g., 0.005 = 0.5%)
        """
        total = self._stats["total_responses"]
        if total == 0:
            return 0.0

        fp_count = self._stats["false_positives_reported"]
        return fp_count / total

    def get_precision(self) -> float:
        """
        Calculate detection precision (1 - false positive rate).

        Returns:
            Precision as a float between 0 and 1
        """
        return 1.0 - self.calculate_false_positive_rate()

    def _record_audit_event(
        self,
        event_type: str,
        **kwargs: Any,
    ) -> None:
        """
        Record an event to the immutable audit trail.

        The audit trail is append-only and cannot be modified.
        Each event includes a timestamp and hash of previous event.

        Args:
            event_type: Type of event
            **kwargs: Event data
        """
        previous_hash = None
        if self._audit_trail:
            previous_hash = self._audit_trail[-1].get("hash")

        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "data": kwargs,
            "previous_hash": previous_hash,
        }

        # Calculate event hash
        event_str = str(sorted(event.items()))
        event["hash"] = hashlib.sha256(event_str.encode()).hexdigest()[:16]

        self._audit_trail.append(event)

    def get_audit_trail(
        self,
        limit: int = 100,
        event_type_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get audit trail entries.

        Args:
            limit: Maximum entries to return
            event_type_filter: Filter by event type

        Returns:
            List of audit trail entries
        """
        events = self._audit_trail

        if event_type_filter:
            events = [e for e in events if e["event_type"] == event_type_filter]

        return events[-limit:]

    def get_immune_memory_snapshot(self) -> dict[str, dict[str, Any]]:
        """
        Get a snapshot of the current immune memory.

        Returns:
            Dictionary of pattern_id to pattern info
        """
        return {
            pattern_id: {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type,
                "status": p.status.value,
                "occurrence_count": p.occurrence_count,
                "block_count": p.block_count,
                "false_positive_rate": p.false_positive_rate,
                "confidence": p.confidence,
                "approved": p.approved,
                "first_seen": p.first_seen.isoformat(),
                "last_seen": p.last_seen.isoformat(),
            }
            for pattern_id, p in self._immune_memory.items()
        }

    def get_statistics(self) -> dict[str, Any]:
        """
        Get immune response building statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            **self._stats,
            "immune_memory_size": len(self._immune_memory),
            "approved_patterns": sum(1 for p in self._immune_memory.values() if p.approved),
            "pending_quorums": len(self._pending_quorums),
            "novel_patterns_pending_review": len(
                [p for p in self._novel_patterns.values() if not p.reviewed]
            ),
            "false_positive_rate": self.calculate_false_positive_rate(),
            "precision": self.get_precision(),
            "precision_target_met": self.get_precision() >= 0.99,
        }


class ResponseAction(StrEnum):
    """Action taken by Sentinel in response to an anomaly."""

    BLOCKED = "blocked"
    FLAGGED = "flagged"
    ALLOWED = "allowed"


@dataclass
class AnomalyResponse:
    """
    Record of how Sentinel responded to an anomaly.

    Attributes:
        response_id: Unique identifier
        anomaly_type: Type of anomaly detected
        detection_signature: Signature that detected the anomaly
        action_taken: Response action taken
        was_correct: Whether the response was correct (None = unconfirmed)
        timestamp: When response occurred
        agent_id: Sentinel agent that responded
        false_positive: Whether this was flagged as false positive
    """

    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_type: str = "unknown"
    detection_signature: str = ""
    action_taken: ResponseAction = ResponseAction.FLAGGED
    was_correct: bool | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    agent_id: str | None = None
    false_positive: bool = False


@dataclass
class ImmuneLearningResult:
    """
    Result of immune learning analysis.

    Attributes:
        new_patterns_proposed: Number of new patterns proposed
        patterns_confirmed: Number of patterns confirmed
        false_positives_identified: Number of false positives found
        novel_attacks_flagged: Number of novel attacks flagged for review
        false_positive_rate: Current false positive rate
    """

    new_patterns_proposed: int = 0
    patterns_confirmed: int = 0
    false_positives_identified: int = 0
    novel_attacks_flagged: int = 0
    false_positive_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "new_patterns_proposed": self.new_patterns_proposed,
            "patterns_confirmed": self.patterns_confirmed,
            "false_positives_identified": self.false_positives_identified,
            "novel_attacks_flagged": self.novel_attacks_flagged,
            "false_positive_rate": self.false_positive_rate,
        }


class ImmuneResponseEngine:
    """
    Sentinel's immune response system - learns from past anomalies.

    This engine tracks how Sentinel responds to anomalies over time,
    identifies patterns that work well vs those that cause false positives,
    and proposes new patterns to the baseline store for quorum approval.

    Attributes:
        baseline_store: Store for security patterns
        deliberation_engine: Optional deliberation engine for quorum
        confirmation_threshold: Confirmations needed to propose pattern
        false_positive_rate_window: Window for FP rate calculation
        novel_attack_threshold: Confidence to flag as novel attack
    """

    def __init__(
        self,
        baseline_store: Any = None,
        deliberation_engine: Any = None,
        confirmation_threshold: int = 3,
        false_positive_rate_window: int = 1000,
        novel_attack_threshold: float = 0.85,
    ) -> None:
        """
        Initialize the immune response engine.

        Args:
            baseline_store: Store for security patterns
            deliberation_engine: Optional deliberation engine
            confirmation_threshold: Confirmations to propose pattern
            false_positive_rate_window: Window for FP rate
            novel_attack_threshold: Confidence for novel attack flag
        """
        self._baseline_store = baseline_store
        self._deliberation_engine = deliberation_engine

        self._confirmation_threshold = confirmation_threshold
        self._false_positive_rate_window = false_positive_rate_window
        self._novel_attack_threshold = novel_attack_threshold

        self._responses: list[AnomalyResponse] = []
        self._max_response_history = 10000

        self._stats = {
            "total_responses_recorded": 0,
            "detections_confirmed": 0,
            "false_positives_reported": 0,
            "patterns_proposed": 0,
            "novel_attacks_flagged": 0,
        }

        logger.info(
            "ImmuneResponseEngine initialized",
            confirmation_threshold=confirmation_threshold,
            fp_window=false_positive_rate_window,
            novel_attack_threshold=novel_attack_threshold,
        )

    async def record_response(
        self,
        anomaly_type: str,
        detection_signature: str,
        action: ResponseAction,
        agent_id: str | None = None,
    ) -> str:
        """
        Record how Sentinel responded to an anomaly.

        Args:
            anomaly_type: Type of anomaly detected
            detection_signature: Signature that detected it
            action: Action taken (BLOCKED, FLAGGED, ALLOWED)
            agent_id: Sentinel agent that responded

        Returns:
            Response ID
        """
        response = AnomalyResponse(
            anomaly_type=anomaly_type,
            detection_signature=detection_signature,
            action_taken=action,
            agent_id=agent_id,
        )

        self._responses.append(response)
        self._stats["total_responses_recorded"] += 1

        if len(self._responses) > self._max_response_history:
            self._responses = self._responses[-self._max_response_history :]

        logger.debug(
            "response_recorded",
            response_id=response.response_id,
            anomaly_type=anomaly_type,
            action=action.value,
        )

        return response.response_id

    async def confirm_detection(
        self,
        response_id: str,
        was_correct: bool,
    ) -> bool:
        """
        Confirm whether a detection was correct.

        If was_correct=False: likely false positive
        If was_correct=True and action=BLOCKED: confirms attack pattern

        Args:
            response_id: ID of response to confirm
            was_correct: Whether detection was correct

        Returns:
            True if response was found and updated
        """
        response = next(
            (r for r in self._responses if r.response_id == response_id),
            None,
        )

        if not response:
            logger.warning("response_not_found", response_id=response_id)
            return False

        response.was_correct = was_correct

        if was_correct:
            self._stats["detections_confirmed"] += 1
            logger.debug(
                "detection_confirmed",
                response_id=response_id,
                anomaly_type=response.anomaly_type,
            )
        else:
            response.false_positive = True
            self._stats["false_positives_reported"] += 1
            logger.debug(
                "false_positive_reported",
                response_id=response_id,
                anomaly_type=response.anomaly_type,
            )

        return True

    async def analyze_and_learn(self) -> ImmuneLearningResult:
        """
        Analyze response history and update baseline.

        Returns:
            ImmuneLearningResult with learning metrics
        """
        result = ImmuneLearningResult()

        result.false_positive_rate = self.calculate_false_positive_rate()

        recent_responses = self._get_recent_responses(self._false_positive_rate_window)

        # Group responses by pattern
        pattern_confirmations: dict[str, list[AnomalyResponse]] = {}
        for response in recent_responses:
            if response.was_correct is None:
                continue

            key = self._get_pattern_key(response)
            if key not in pattern_confirmations:
                pattern_confirmations[key] = []
            pattern_confirmations[key].append(response)

        # Classify each pattern and update baseline
        for pattern_key, responses in pattern_confirmations.items():
            self._classify_pattern_confirmation(pattern_key, responses, result)

        logger.info(
            "immune_analysis_complete",
            new_patterns=result.new_patterns_proposed,
            confirmed=result.patterns_confirmed,
            false_positives=result.false_positives_identified,
            novel_attacks=result.novel_attacks_flagged,
            fp_rate=result.false_positive_rate,
        )

        return result

    def _classify_pattern_confirmation(
        self,
        pattern_key: str,
        responses: list[AnomalyResponse],
        result: ImmuneLearningResult,
    ) -> None:
        """
        Classify a pattern confirmation and update baseline.

        Args:
            pattern_key: Pattern key identifier
            responses: List of responses for this pattern
            result: Learning result to update
        """
        correct = sum(1 for r in responses if r.was_correct)
        incorrect = sum(1 for r in responses if not r.was_correct)

        if incorrect > correct:
            result.false_positives_identified += 1
            pattern_id = self._find_matching_pattern(responses[0])
            if pattern_id and self._baseline_store:
                self._baseline_store.record_false_positive(pattern_id)
            return

        if correct >= self._confirmation_threshold:
            pattern = self._create_pattern_from_responses(pattern_key, responses)
            if pattern and self._baseline_store:
                existing = self._baseline_store.get_pattern(pattern.pattern_id)
                if not existing:
                    self._handle_new_pattern(pattern, responses, result)
                else:
                    self._handle_existing_pattern(pattern, correct, result)

    def _handle_new_pattern(
        self,
        pattern: ImmunePattern,
        responses: list[AnomalyResponse],
        result: ImmuneLearningResult,
    ) -> None:
        """Handle a newly discovered pattern."""
        self._baseline_store.add_provisional_pattern(pattern)
        result.new_patterns_proposed += 1
        self._stats["patterns_proposed"] += 1

        pattern_high_confidence = all(r.was_correct for r in responses[-3:])
        if pattern_high_confidence and pattern.confidence >= self._novel_attack_threshold:
            self._baseline_store.request_human_review(pattern.pattern_id)
            result.novel_attacks_flagged += 1
            self._stats["novel_attacks_flagged"] += 1

    def _handle_existing_pattern(
        self,
        pattern: ImmunePattern,
        correct: int,
        result: ImmuneLearningResult,
    ) -> None:
        """Handle confirmation of an existing pattern."""
        for _ in range(correct):
            self._baseline_store.confirm_pattern(pattern.pattern_id)
        result.patterns_confirmed += 1

    def calculate_false_positive_rate(self) -> float:
        """
        Calculate current false positive rate.

        Returns:
            False positive rate (0.0-1.0)
        """
        recent = self._get_recent_responses(self._false_positive_rate_window)

        confirmed = [r for r in recent if r.was_correct is not None]
        if not confirmed:
            return 0.0

        false_positives = sum(1 for r in confirmed if not r.was_correct)
        return false_positives / len(confirmed)

    def get_pattern_recommendations(self) -> list[dict[str, Any]]:
        """
        Get patterns recommended for baseline addition.

        Returns patterns with confirmation_count >= threshold.
        """
        recommendations = []
        if not self._baseline_store:
            return recommendations

        all_patterns = self._baseline_store.get_all_patterns()

        for pattern in all_patterns:
            if pattern.status == PatternStatus.PROVISIONAL:  # noqa: SIM102
                if pattern.confirmation_count >= self._confirmation_threshold:
                    recommendations.append(
                        {
                            "pattern_id": pattern.pattern_id,
                            "pattern_type": pattern.pattern_type,
                            "signature": pattern.signature,
                            "description": pattern.description,
                            "confidence": pattern.confidence,
                            "confirmation_count": pattern.confirmation_count,
                            "confirmation_rate": pattern.confirmation_rate(),
                            "recommendation": "promote_to_proven",
                        }
                    )

        return recommendations

    async def request_baseline_change(
        self,
        pattern_id: str,
        change_type: "BaselineChangeType",
    ) -> str | None:
        """
        Request a baseline change through deliberation.

        Args:
            pattern_id: ID of pattern to change
            change_type: Type of change

        Returns:
            Change ID if proposal created
        """
        if not self._baseline_store:
            return None

        change = self._baseline_store.propose_baseline_change(
            pattern_id=pattern_id,
            action=change_type,
        )

        if change and self._deliberation_engine:
            try:
                deliberation_id = self._deliberation_engine.start_deliberation(
                    topic=f"Baseline change: {change_type.value} pattern {pattern_id}",
                    participants=["sentinel", "arbiter", "steward"],
                    domain="security",
                )
                logger.info(
                    "baseline_change_deliberation_started",
                    change_id=change.change_id,
                    deliberation_id=deliberation_id,
                )
            except Exception as e:
                logger.warning(
                    "deliberation_start_failed",
                    change_id=change.change_id,
                    error=str(e),
                )

        return change.change_id if change else None

    def _get_recent_responses(
        self,
        count: int,
    ) -> list[AnomalyResponse]:
        """Get most recent responses."""
        return self._responses[-count:] if self._responses else []

    def _get_pattern_key(self, response: AnomalyResponse) -> str:
        """Generate a pattern key from response."""
        data = f"{response.anomaly_type}:{response.detection_signature}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _find_matching_pattern(self, response: AnomalyResponse) -> str | None:
        """Find existing pattern matching the response."""
        if not self._baseline_store:
            return None

        patterns = self._baseline_store.get_all_patterns()
        for pattern in patterns:
            if pattern.signature == response.detection_signature:
                return pattern.pattern_id
        return None

    def _create_pattern_from_responses(
        self,
        pattern_key: str,
        responses: list[AnomalyResponse],
    ) -> ImmunePattern | None:
        """Create a new pattern from confirmed responses."""
        if not responses:
            return None

        first_response = responses[0]
        correct_count = sum(1 for r in responses if r.was_correct)

        return ImmunePattern(
            pattern_id=f"pattern-{pattern_key}",
            pattern_hash="",  # Required field
            pattern_type=first_response.anomaly_type,  # Required field
            description=f"Auto-learned pattern from {correct_count} confirmations",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            evidence_count=correct_count,
            confidence=correct_count / len(responses) if responses else 0.5,
            source="immune_response",
        )

    def get_response_history(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent response history."""
        recent = self._get_recent_responses(limit)
        return [
            {
                "response_id": r.response_id,
                "anomaly_type": r.anomaly_type,
                "detection_signature": r.detection_signature,
                "action_taken": r.action_taken.value,
                "was_correct": r.was_correct,
                "timestamp": r.timestamp.isoformat(),
                "agent_id": r.agent_id,
                "false_positive": r.false_positive,
            }
            for r in recent
        ]

    def get_statistics(self) -> dict[str, Any]:
        """Get immune engine statistics."""
        stats = {
            **self._stats,
            "total_responses_tracked": len(self._responses),
            "confirmation_threshold": self._confirmation_threshold,
            "fp_rate_window": self._false_positive_rate_window,
            "current_fp_rate": self.calculate_false_positive_rate(),
        }

        if self._baseline_store:
            stats["patterns_in_baseline"] = len(self._baseline_store.get_all_patterns())
            stats["blocking_patterns"] = len(self._baseline_store.get_blocking_patterns())
            stats["proposed_changes_pending"] = len(self._baseline_store.get_proposed_changes())

        return stats

    def check_false_positive_cascade(self) -> dict[str, Any]:
        """
        Check if a false positive cascade is occurring.

        Returns:
            Dictionary with cascade detection results
        """
        fp_rate = self.calculate_false_positive_rate()

        recent = self._get_recent_responses(100)
        recent_fps = [r for r in recent if r.false_positive]

        pattern_fp_counts: dict[str, int] = {}
        for fp_response in recent_fps:
            key = self._get_pattern_key(fp_response)
            pattern_fp_counts[key] = pattern_fp_counts.get(key, 0) + 1

        cascade_detected = fp_rate > 0.01 or any(count >= 5 for count in pattern_fp_counts.values())

        return {
            "cascade_detected": cascade_detected,
            "current_fp_rate": fp_rate,
            "recent_fp_count": len(recent_fps),
            "pattern_fp_counts": pattern_fp_counts,
            "threshold_exceeded": fp_rate > 0.01,
            "same_pattern_triggers": any(count >= 5 for count in pattern_fp_counts.values()),
        }

    def get_unconfirmed_responses(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get responses that haven't been confirmed yet."""
        unconfirmed = [r for r in self._responses[-limit:] if r.was_correct is None]

        return [
            {
                "response_id": r.response_id,
                "anomaly_type": r.anomaly_type,
                "detection_signature": r.detection_signature,
                "action_taken": r.action_taken.value,
                "timestamp": r.timestamp.isoformat(),
                "agent_id": r.agent_id,
            }
            for r in unconfirmed
        ]
