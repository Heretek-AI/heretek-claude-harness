"""
Audit Data Models - Shared types for the consensus audit system.

This module contains all dataclasses and enums used by both
audit_trail.py and audit_query.py.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""

    CONSENSUS_INITIATED = "consensus_initiated"
    VOTE_SUBMITTED = "vote_submitted"
    ARGUMENT_SUBMITTED = "argument_submitted"
    POSITION_CHANGED = "position_changed"
    CONSENSUS_REACHED = "consensus_reached"
    CONSENSUS_FAILED = "consensus_failed"
    DECISION_ROLLED_BACK = "decision_rolled_back"
    DECISION_EXPORTED = "decision_exported"
    AUDIT_QUERY = "audit_query"


class DecisionOutcome(Enum):
    """Possible decision outcomes."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class AuditEvent:
    """Single audit event in the trail."""

    event_id: str
    event_type: AuditEventType
    timestamp: str
    consensus_id: str
    agent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    hash: str | None = None
    previous_hash: str | None = None

    def __post_init__(self) -> None:
        """Generate hash after initialization."""
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate cryptographic hash of event."""
        import hashlib
        import json

        data = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "consensus_id": self.consensus_id,
            "agent_id": self.agent_id,
            "data": self.data,
            "previous_hash": self.previous_hash,
        }
        data_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_json.encode()).hexdigest()


@dataclass
class VoteRecord:
    """Complete record of a single vote."""

    vote_id: str
    consensus_id: str
    agent_id: str
    decision: str
    confidence: float
    reasoning: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArgumentRecord:
    """Record of an argument submitted during deliberation."""

    argument_id: str
    consensus_id: str
    agent_id: str
    position: str
    content: str
    supports: list[str] = field(default_factory=list)
    rebuttals: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DecisionRecord:
    """Complete record of a consensus decision."""

    decision_id: str
    consensus_id: str
    proposal: str
    decision: str
    confidence: float
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    participants: list[str] = field(default_factory=list)
    votes: list[VoteRecord] = field(default_factory=list)
    arguments: list[ArgumentRecord] = field(default_factory=list)
    reasoning_summary: str | None = None
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of an audit query."""

    query: dict[str, Any]
    total_results: int
    results: list[dict[str, Any]]
    execution_time_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DeliberationRoundRecord:
    """Record of a single deliberation round."""

    round_id: str
    round_number: int
    consensus_id: str
    arguments_submitted: list[str] = field(default_factory=list)
    positions: dict[str, str] = field(default_factory=dict)
    consensus_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DecisionAudit:
    """Comprehensive decision audit record with full deliberation history."""

    audit_id: str = field(default_factory=lambda: f"audit-{datetime.now(UTC).isoformat()}")
    decision_id: str = ""
    consensus_id: str = ""
    deliberation_rounds: list[DeliberationRoundRecord] = field(default_factory=list)
    votes_with_reasoning: list[VoteRecord] = field(default_factory=list)
    final_decision: str = ""
    consensus_method: str = "unknown"
    confidence_score: float = 0.5
    confidence_breakdown: dict[str, float] = field(default_factory=dict)
    dissenting_agents: list[str] = field(default_factory=list)
    minority_report: str | None = None
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    outcome_recorded_at: str | None = None
    outcome_verified_at: str | None = None
    provenance_hash: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Generate provenance hash after initialization."""
        if not self.provenance_hash:
            self.provenance_hash = self._generate_provenance_hash()

    def _generate_provenance_hash(self) -> str:
        """Generate cryptographic hash for immutability."""
        import hashlib
        import json

        data = {
            "audit_id": self.audit_id,
            "decision_id": self.decision_id,
            "consensus_id": self.consensus_id,
            "deliberation_rounds": [
                {
                    "round_id": r.round_id,
                    "round_number": r.round_number,
                    "arguments": r.arguments_submitted,
                    "positions": r.positions,
                    "consensus_score": r.consensus_score,
                }
                for r in self.deliberation_rounds
            ],
            "votes": [
                {
                    "vote_id": v.vote_id,
                    "agent_id": v.agent_id,
                    "decision": v.decision,
                    "confidence": v.confidence,
                    "reasoning": v.reasoning,
                }
                for v in self.votes_with_reasoning
            ],
            "final_decision": self.final_decision,
            "consensus_method": self.consensus_method,
            "confidence_score": self.confidence_score,
            "dissenting_agents": self.dissenting_agents,
            "outcome": self.outcome.value,
            "created_at": self.created_at,
        }
        data_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_json.encode()).hexdigest()

    def update_outcome(self, outcome: DecisionOutcome, verified: bool = False) -> None:
        """Update decision outcome and recalculate provenance hash."""
        self.outcome = outcome
        self.outcome_recorded_at = datetime.now(UTC).isoformat()
        if verified:
            self.outcome_verified_at = self.outcome_recorded_at
        self.updated_at = self.outcome_recorded_at
        self.provenance_hash = self._generate_provenance_hash()

    def add_deliberation_round(self, round_record: DeliberationRoundRecord) -> None:
        """Add a deliberation round record and update hash."""
        self.deliberation_rounds.append(round_record)
        self.updated_at = datetime.now(UTC).isoformat()
        self.provenance_hash = self._generate_provenance_hash()

    def verify_integrity(self) -> bool:
        """Verify integrity by comparing hashes."""
        return self._generate_provenance_hash() == self.provenance_hash

    def to_dict(self) -> dict[str, Any]:
        """Convert audit record to dictionary for export."""
        return {
            "audit_id": self.audit_id,
            "decision_id": self.decision_id,
            "consensus_id": self.consensus_id,
            "deliberation_rounds": [
                {
                    "round_id": r.round_id,
                    "round_number": r.round_number,
                    "arguments_submitted": r.arguments_submitted,
                    "positions": r.positions,
                    "consensus_score": r.consensus_score,
                    "timestamp": r.timestamp,
                }
                for r in self.deliberation_rounds
            ],
            "votes_with_reasoning": [
                {
                    "vote_id": v.vote_id,
                    "agent_id": v.agent_id,
                    "decision": v.decision,
                    "confidence": v.confidence,
                    "reasoning": v.reasoning,
                    "timestamp": v.timestamp,
                }
                for v in self.votes_with_reasoning
            ],
            "final_decision": self.final_decision,
            "consensus_method": self.consensus_method,
            "confidence_score": self.confidence_score,
            "confidence_breakdown": self.confidence_breakdown,
            "dissenting_agents": self.dissenting_agents,
            "minority_report": self.minority_report,
            "outcome": self.outcome.value,
            "outcome_recorded_at": self.outcome_recorded_at,
            "outcome_verified_at": self.outcome_verified_at,
            "provenance_hash": self.provenance_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
