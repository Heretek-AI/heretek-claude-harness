"""
Type definitions for the immune-response engine.

The data classes and enums here are pure value objects used by
ImmuneResponseBuilding and ImmuneResponseEngine (in
immune_engine.py). They were extracted as part of Phase 2.11
of PLAN.md — the engine itself remains two large classes
(ImmuneResponseBuilding and ImmuneResponseEngine) but the
pure value-object surface is no longer interleaved with the
algorithm code.

The types module imports nothing from the engine. New code that
only needs the value objects (e.g. UI code that displays an
AnomalyResponse or an ImmuneQuorum) can import from
here to avoid the heavier transitive dependency on the engines.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from heretek_swarm.collective.learning import PatternStatus

if TYPE_CHECKING:
    from heretek_swarm_core.security.behavioral_baseline import BaselineChangeType


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

