"""
Baseline Update Module for Heretek Swarm.

This module provides baseline update management with quorum approval,
rollback capability, and drift detection for the behavioral baseline system.

Components:
- BaselineRollbackManager: Snapshots and rollback for baseline changes
- BaselineTribunal: Quorum-based approval for baseline modifications
- Drift detection for gradual unauthorized changes

Key features:
- Immutable audit trail (hash chain)
- Emergency reset with Charlie approval
- Baseline drift detection and alerting
- CONS-03 quorum approval (3+ agents)

Reference: Phase 2 Plan Task 3 (CONS-03)
"""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("baseline_update")


# =============================================================================
# Enums
# =============================================================================


class RollbackReason(StrEnum):
    """Reasons for baseline rollback."""

    QUORUM_FAILED = "quorum_failed"
    EMERGENCY_RESET = "emergency_reset"
    CORRUPTION_DETECTED = "corruption_detected"
    MANUAL_OVERRIDE = "manual_override"
    DRIFT_DETECTED = "drift_detected"


class RollbackStatus(StrEnum):
    """Status of a rollback operation."""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class BaselineChangeType(StrEnum):
    """Types of baseline changes requiring approval."""

    PATTERN_ADD = "pattern_add"
    PATTERN_REMOVE = "pattern_remove"
    PATTERN_MODIFY = "pattern_modify"
    PATTERN_PROMOTE = "pattern_promote"
    PATTERN_DEMOTE = "pattern_demote"
    BASELINE_RESET = "baseline_reset"
    EMERGENCY_RESET = "emergency_reset"


class VoteDecision(StrEnum):
    """Voting decisions."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class BaselineChangeStatus(StrEnum):
    """Status of a baseline change proposal."""

    PROPOSED = "proposed"
    VOTING = "voting"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"
    ROLLED_BACK = "rolled_back"


class BaselineChangeOutcome(StrEnum):
    """Outcome of a baseline change process."""

    RESOLVED_BINDING = "resolved_binding"
    RESOLVED_CONSENSUS = "resolved_consensus"
    ESCALATED_CORE_TRIAD = "escalated_core_triad"
    ESCALATED_HUMAN = "escalated_human"
    FAILED = "failed"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class BaselineSnapshot:
    """Point-in-time snapshot of baseline state."""

    snapshot_id: str
    timestamp: str
    baseline_hash: str
    pattern_count: int
    patterns_summary: dict[str, int]
    change_history_ids: list[str]
    previous_snapshot_hash: str | None = None
    hash: str | None = None

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        data = {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "baseline_hash": self.baseline_hash,
            "pattern_count": self.pattern_count,
            "patterns_summary": self.patterns_summary,
            "change_history_ids": self.change_history_ids,
            "previous_snapshot_hash": self.previous_snapshot_hash,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class RollbackOperation:
    """Record of a rollback operation."""

    rollback_id: str
    target_snapshot_id: str | None
    reason: RollbackReason
    initiated_by: str
    approved_by: list[str] = field(default_factory=list)
    status: RollbackStatus = RollbackStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    executed_at: str | None = None
    changes_rolled_back: list[str] = field(default_factory=list)
    emergency: bool = False
    hash: str | None = None

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        data = {
            "rollback_id": self.rollback_id,
            "target_snapshot_id": self.target_snapshot_id,
            "reason": self.reason.value,
            "initiated_by": self.initiated_by,
            "approved_by": sorted(self.approved_by),
            "status": self.status.value,
            "created_at": self.created_at,
            "emergency": self.emergency,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class BaselineChangeProposal:
    """Proposal for a baseline change requiring tribunal approval."""

    proposal_id: str
    change_type: BaselineChangeType
    pattern_id: str | None
    proposed_by: str
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)
    status: BaselineChangeStatus = BaselineChangeStatus.PROPOSED
    votes: dict[str, VoteDecision] = field(default_factory=dict)
    approvers: list[str] = field(default_factory=list)
    rejectors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    voting_deadline: str | None = None
    executed_at: str | None = None
    previous_change_hash: str | None = None
    proposal_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.proposal_hash:
            self.proposal_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        data = {
            "proposal_id": self.proposal_id,
            "change_type": self.change_type.value,
            "pattern_id": self.pattern_id,
            "proposed_by": self.proposed_by,
            "rationale": self.rationale,
            "created_at": self.created_at,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class BaselineTribunalRuling:
    """Tribunal ruling on a baseline change."""

    ruling_id: str
    proposal_id: str
    ruling_type: str
    reasoning: str
    confidence: float
    quorum_achieved: bool
    vote_summary: dict[str, int]
    issued_by: str = "baseline_tribunal"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    hash: str | None = None

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        data = {
            "ruling_id": self.ruling_id,
            "proposal_id": self.proposal_id,
            "ruling_type": self.ruling_type,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "quorum_achieved": self.quorum_achieved,
            "vote_summary": self.vote_summary,
            "timestamp": self.timestamp,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class DriftReport:
    """Report on baseline drift analysis."""

    drift_detected: bool
    total_patterns: int
    status_distribution: dict[str, int]
    provisional_ratio: float
    proven_ratio: float
    threshold: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# =============================================================================
# BaselineRollbackManager
# =============================================================================


class BaselineRollbackManager:
    """
    Manages baseline snapshots and rollback operations.

    Features:
    - Periodic baseline snapshots
    - Rollback to any previous snapshot
    - Emergency reset with Charlie approval
    - Full audit trail
    """

    def __init__(
        self,
        snapshot_interval: int = 100,
        max_snapshots: int = 50,
        emergency_approval_required: list[str] | None = None,
    ):
        """
        Initialize the rollback manager.

        Args:
            snapshot_interval: Create snapshot every N changes
            max_snapshots: Maximum snapshots to retain
            emergency_approval_required: Agent IDs required for emergency approval
        """
        self._snapshots: dict[str, BaselineSnapshot] = {}
        self._latest_snapshot_id: str | None = None
        self._snapshot_interval = snapshot_interval
        self._max_snapshots = max_snapshots

        self._rollback_operations: dict[str, RollbackOperation] = {}
        self._change_counter: int = 0

        self._emergency_approval_required = emergency_approval_required or ["charlie"]

        logger.info(
            "BaselineRollbackManager initialized",
            snapshot_interval=snapshot_interval,
            max_snapshots=max_snapshots,
        )

    def create_snapshot(
        self,
        baseline_hash: str,
        patterns: dict[str, Any],
        change_history_ids: list[str],
    ) -> BaselineSnapshot:
        """
        Create a point-in-time snapshot of baseline.

        Args:
            baseline_hash: Current baseline hash
            patterns: Current patterns dict
            change_history_ids: IDs of changes included

        Returns:
            Created snapshot
        """
        self._change_counter += 1

        summary: dict[str, int] = {}
        for pattern in patterns.values():
            status = (
                pattern.get("status", "unknown")
                if isinstance(pattern, dict)
                else getattr(pattern, "status", "unknown")
            )
            if hasattr(status, "value"):
                status = status.value
            summary[status] = summary.get(status, 0) + 1

        previous_hash = None
        if self._latest_snapshot_id and self._latest_snapshot_id in self._snapshots:
            previous_hash = self._snapshots[self._latest_snapshot_id].hash

        snapshot = BaselineSnapshot(
            snapshot_id=f"snap-{datetime.now(UTC).timestamp()}",
            timestamp=datetime.now(UTC).isoformat(),
            baseline_hash=baseline_hash,
            pattern_count=len(patterns),
            patterns_summary=summary,
            change_history_ids=change_history_ids,
            previous_snapshot_hash=previous_hash,
        )

        self._snapshots[snapshot.snapshot_id] = snapshot
        self._latest_snapshot_id = snapshot.snapshot_id

        self._prune_snapshots()

        logger.info(
            "Baseline snapshot created",
            snapshot_id=snapshot.snapshot_id,
            pattern_count=len(patterns),
        )

        return snapshot

    def request_rollback(
        self,
        target_snapshot_id: str | None,
        reason: RollbackReason,
        initiated_by: str,
        emergency: bool = False,
    ) -> RollbackOperation:
        """
        Request a rollback operation.

        Args:
            target_snapshot_id: Snapshot to rollback to (None for full reset)
            reason: Reason for rollback
            initiated_by: Agent requesting rollback
            emergency: Whether this is an emergency

        Returns:
            Rollback operation record
        """
        rollback_id = f"rb-{datetime.now(UTC).timestamp()}"

        rollback_op = RollbackOperation(
            rollback_id=rollback_id,
            target_snapshot_id=target_snapshot_id,
            reason=reason,
            initiated_by=initiated_by,
            emergency=emergency,
        )

        self._rollback_operations[rollback_id] = rollback_op

        logger.info(
            "Rollback requested",
            rollback_id=rollback_id,
            reason=reason.value,
            initiated_by=initiated_by,
            emergency=emergency,
        )

        return rollback_op

    def approve_rollback(
        self,
        rollback_id: str,
        approved_by: str,
    ) -> bool:
        """
        Approve a rollback operation.

        Args:
            rollback_id: ID of rollback to approve
            approved_by: Agent approving

        Returns:
            True if rollback can proceed
        """
        rollback_op = self._rollback_operations.get(rollback_id)
        if not rollback_op:
            return False

        if approved_by not in rollback_op.approved_by:
            rollback_op.approved_by.append(approved_by)

        if rollback_op.emergency:
            return "charlie" in rollback_op.approved_by
        return len(rollback_op.approved_by) >= 2

    def execute_rollback(
        self,
        rollback_id: str,
    ) -> bool:
        """
        Execute an approved rollback.

        Args:
            rollback_id: ID of rollback to execute

        Returns:
            True if successful
        """
        rollback_op = self._rollback_operations.get(rollback_id)
        if not rollback_op:
            return False

        if rollback_op.status != RollbackStatus.PENDING:
            return False

        rollback_op.status = RollbackStatus.EXECUTED
        rollback_op.executed_at = datetime.now(UTC).isoformat()

        logger.info(
            "Rollback executed",
            rollback_id=rollback_id,
            target=rollback_op.target_snapshot_id,
        )

        return True

    def _prune_snapshots(self) -> None:
        """Remove old snapshots beyond max limit."""
        if len(self._snapshots) <= self._max_snapshots:
            return

        sorted_snapshots = sorted(
            self._snapshots.values(),
            key=lambda s: s.timestamp,
            reverse=True,
        )

        for snapshot in sorted_snapshots[self._max_snapshots :]:
            del self._snapshots[snapshot.snapshot_id]

    def get_snapshot_history(self, limit: int = 10) -> list[BaselineSnapshot]:
        """Get recent snapshots."""
        return sorted(
            self._snapshots.values(),
            key=lambda s: s.timestamp,
            reverse=True,
        )[:limit]

    def get_rollback_status(self, rollback_id: str) -> RollbackOperation | None:
        """Get status of a rollback operation."""
        return self._rollback_operations.get(rollback_id)

    def should_create_snapshot(self) -> bool:
        """Check if a snapshot should be created based on change interval."""
        return self._change_counter >= self._snapshot_interval


# =============================================================================
# BaselineTribunal
# =============================================================================


class BaselineTribunal:
    """
    Specialized tribunal for baseline change approval.

    Features:
    - CONS-03 quorum approval (3+ agents required)
    - Gradual drift handling via deliberation
    - Emergency reset with Charlie approval
    - Integration with ConsensusAuditTrail
    """

    def __init__(
        self,
        quorum_size: int = 3,
        voting_timeout_seconds: float = 300.0,
        approval_threshold: float = 0.66,
        drift_threshold: float = 0.15,
    ):
        """
        Initialize the baseline tribunal.

        Args:
            quorum_size: Number of agents required for quorum
            voting_timeout_seconds: Time limit for voting
            approval_threshold: Ratio required for approval
            drift_threshold: 15% change triggers drift review
        """
        self._proposals: dict[str, BaselineChangeProposal] = {}
        self._rulings: dict[str, BaselineTribunalRuling] = {}

        self._quorum_size = quorum_size
        self._voting_timeout = voting_timeout_seconds
        self._approval_threshold = approval_threshold
        self._drift_threshold = drift_threshold

        self._eligible_voters: set[str] = {
            "steward",
            "alpha",
            "beta",
            "charlie",
            "sentinel",
            "sentinel_prime",
        }

        self._drift_history: list[dict[str, Any]] = []

        logger.info(
            "BaselineTribunal initialized",
            quorum_size=quorum_size,
            voting_timeout=voting_timeout_seconds,
            drift_threshold=drift_threshold,
        )

    def propose_baseline_change(
        self,
        change_type: BaselineChangeType,
        proposed_by: str,
        rationale: str,
        pattern_id: str | None = None,
        evidence_refs: list[str] | None = None,
    ) -> BaselineChangeProposal:
        """
        Propose a baseline change for tribunal approval.

        Args:
            change_type: Type of change
            proposed_by: Agent proposing the change
            rationale: Reason for the change
            pattern_id: Related pattern ID
            evidence_refs: Evidence document references

        Returns:
            Created proposal
        """
        proposal_id = f"bl_proposal-{datetime.now(UTC).timestamp()}"

        voting_deadline = datetime.now(UTC).timestamp() + self._voting_timeout

        proposal = BaselineChangeProposal(
            proposal_id=proposal_id,
            change_type=change_type,
            pattern_id=pattern_id,
            proposed_by=proposed_by,
            rationale=rationale,
            evidence_refs=evidence_refs or [],
            voting_deadline=datetime.fromtimestamp(voting_deadline, UTC).isoformat(),
        )

        self._proposals[proposal_id] = proposal

        logger.info(
            "Baseline change proposed",
            proposal_id=proposal_id,
            change_type=change_type.value,
            proposed_by=proposed_by,
        )

        return proposal

    def cast_vote(
        self,
        proposal_id: str,
        agent_id: str,
        decision: VoteDecision,
        reasoning: str | None = None,
    ) -> dict[str, Any]:
        """
        Cast a vote on a baseline change proposal.

        Args:
            proposal_id: Proposal to vote on
            agent_id: Agent casting vote
            decision: Vote decision
            reasoning: Optional reasoning

        Returns:
            Vote result with quorum status
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return {"success": False, "error": "Proposal not found"}

        if proposal.status not in (BaselineChangeStatus.PROPOSED, BaselineChangeStatus.VOTING):
            return {"success": False, "error": "Proposal not accepting votes"}

        if agent_id not in self._eligible_voters:
            return {"success": False, "error": "Agent not eligible to vote"}

        proposal.votes[agent_id] = decision

        if decision == VoteDecision.APPROVE:
            if agent_id not in proposal.approvers:
                proposal.approvers.append(agent_id)
        elif decision == VoteDecision.REJECT and agent_id not in proposal.rejectors:
            proposal.rejectors.append(agent_id)

        proposal.status = BaselineChangeStatus.VOTING

        quorum_result = self._check_quorum(proposal)

        logger.info(
            "Vote cast",
            proposal_id=proposal_id,
            agent_id=agent_id,
            decision=decision.value,
            current_approvers=len(proposal.approvers),
            current_rejectors=len(proposal.rejectors),
        )

        return {
            "success": True,
            "proposal_id": proposal_id,
            "vote_recorded": True,
            "quorum_achieved": quorum_result["achieved"],
            "votes_summary": {
                "approve": len(proposal.approvers),
                "reject": len(proposal.rejectors),
                "total": len(proposal.votes),
            },
        }

    def _check_quorum(self, proposal: BaselineChangeProposal) -> dict[str, Any]:
        """Check if quorum has been achieved."""
        total_votes = len(proposal.votes)
        approve_count = len(proposal.approvers)
        reject_count = len(proposal.rejectors)

        if total_votes < self._quorum_size:
            return {
                "achieved": False,
                "reason": f"Insufficient votes: {total_votes}/{self._quorum_size}",
                "approve_count": approve_count,
                "reject_count": reject_count,
            }

        approve_ratio = approve_count / total_votes

        if approve_ratio >= self._approval_threshold:
            proposal.status = BaselineChangeStatus.APPROVED
            return {
                "achieved": True,
                "reason": "Approval threshold reached",
                "approve_count": approve_count,
                "reject_count": reject_count,
            }

        if reject_count >= total_votes - approve_count + 1:
            proposal.status = BaselineChangeStatus.REJECTED
            return {
                "achieved": False,
                "reason": "Majority rejection",
                "approve_count": approve_count,
                "reject_count": reject_count,
            }

        return {
            "achieved": False,
            "reason": "Voting ongoing",
            "approve_count": approve_count,
            "reject_count": reject_count,
        }

    def issue_ruling(
        self,
        proposal_id: str,
        reasoning: str,
        confidence: float = 1.0,
    ) -> BaselineTribunalRuling:
        """
        Issue a ruling on an approved baseline change.

        Args:
            proposal_id: Proposal to rule on
            reasoning: Ruling reasoning
            confidence: Ruling confidence

        Returns:
            Issued ruling
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        ruling_id = f"bl_ruling-{datetime.now(UTC).timestamp()}"

        ruling = BaselineTribunalRuling(
            ruling_id=ruling_id,
            proposal_id=proposal_id,
            ruling_type="UPHOLD",
            reasoning=reasoning,
            confidence=confidence,
            quorum_achieved=proposal.status == BaselineChangeStatus.APPROVED,
            vote_summary={
                "approve": len(proposal.approvers),
                "reject": len(proposal.rejectors),
                "abstain": len(proposal.votes) - len(proposal.approvers) - len(proposal.rejectors),
            },
        )

        self._rulings[ruling_id] = ruling
        proposal.status = BaselineChangeStatus.EXECUTED
        proposal.executed_at = datetime.now(UTC).isoformat()

        logger.info(
            "Baseline tribunal ruling issued",
            ruling_id=ruling_id,
            proposal_id=proposal_id,
            ruling_type="UPHOLD",
        )

        return ruling

    def request_emergency_reset(
        self,
        initiated_by: str,
        reason: str,
        target_snapshot_id: str | None = None,
    ) -> BaselineChangeProposal:
        """
        Request emergency baseline reset.

        Args:
            initiated_by: Agent requesting reset (must be Steward)
            reason: Reason for reset
            target_snapshot_id: Optional specific snapshot to restore

        Returns:
            Emergency reset proposal
        """
        if initiated_by != "steward":
            raise ValueError("Only Steward can initiate emergency reset")

        proposal = self.propose_baseline_change(
            change_type=BaselineChangeType.EMERGENCY_RESET,
            proposed_by=initiated_by,
            rationale=reason,
            pattern_id=target_snapshot_id,
        )

        logger.warning(
            "Emergency reset requested",
            proposal_id=proposal.proposal_id,
            initiated_by=initiated_by,
            reason=reason,
        )

        return proposal

    def approve_emergency_reset(
        self,
        proposal_id: str,
        approved_by: str,
    ) -> dict[str, Any]:
        """
        Approve emergency reset.

        Args:
            proposal_id: Proposal to approve
            approved_by: Agent approving (must be Charlie)

        Returns:
            Approval result
        """
        if approved_by != "charlie":
            return {"success": False, "error": "Charlie approval required for emergency reset"}

        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return {"success": False, "error": "Proposal not found"}

        if proposal.change_type != BaselineChangeType.EMERGENCY_RESET:
            return {"success": False, "error": "Not an emergency reset proposal"}

        result = self.cast_vote(proposal_id, approved_by, VoteDecision.APPROVE)

        if result.get("quorum_achieved"):
            self.issue_ruling(
                proposal_id,
                reasoning="Emergency reset approved by Charlie",
                confidence=1.0,
            )

        return result

    def check_baseline_drift(
        self,
        patterns: dict[str, Any],
    ) -> DriftReport:
        """
        Check for baseline drift (gradual unauthorized changes).

        Args:
            patterns: Current patterns dict

        Returns:
            Drift analysis report
        """
        status_counts: dict[str, int] = defaultdict(int)
        for pattern in patterns.values():
            status = (
                pattern.get("status", "unknown")
                if isinstance(pattern, dict)
                else getattr(pattern, "status", "unknown")
            )
            if hasattr(status, "value"):
                status = status.value
            status_counts[status] += 1

        total = len(patterns)
        provisional_ratio = status_counts.get("provisional", 0) / max(total, 1)
        proven_ratio = status_counts.get("proven", 0) / max(total, 1)

        drift_detected = provisional_ratio > self._drift_threshold

        report = DriftReport(
            drift_detected=drift_detected,
            total_patterns=total,
            status_distribution=dict(status_counts),
            provisional_ratio=provisional_ratio,
            proven_ratio=proven_ratio,
            threshold=self._drift_threshold,
        )

        if drift_detected:
            self._drift_history.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "report": {
                        "drift_detected": drift_detected,
                        "total_patterns": total,
                        "provisional_ratio": provisional_ratio,
                    },
                }
            )
            logger.warning("Baseline drift detected", provisional_ratio=provisional_ratio)

        return report

    def get_proposal_status(self, proposal_id: str) -> BaselineChangeProposal | None:
        """Get current status of a proposal."""
        return self._proposals.get(proposal_id)

    def list_pending_proposals(self) -> list[BaselineChangeProposal]:
        """List all proposals awaiting approval."""
        return [
            p
            for p in self._proposals.values()
            if p.status in (BaselineChangeStatus.PROPOSED, BaselineChangeStatus.VOTING)
        ]

    def get_tribunal_statistics(self) -> dict[str, Any]:
        """Get tribunal statistics."""
        total = len(self._proposals)
        approved = sum(
            1 for p in self._proposals.values() if p.status == BaselineChangeStatus.APPROVED
        )
        rejected = sum(
            1 for p in self._proposals.values() if p.status == BaselineChangeStatus.REJECTED
        )

        return {
            "total_proposals": total,
            "approved": approved,
            "rejected": rejected,
            "pending": total - approved - rejected,
            "approval_rate": approved / max(total, 1),
            "quorum_size": self._quorum_size,
            "eligible_voters": list(self._eligible_voters),
            "drift_events": len(self._drift_history),
        }


# =============================================================================
# BaselineUpdateService
# =============================================================================


class BaselineUpdateService:
    """
    Unified service for baseline updates combining rollback and tribunal.

    This service provides a unified interface for:
    - Baseline change proposals and voting
    - Snapshot management and rollback
    - Drift detection and alerting
    - Emergency reset handling
    """

    def __init__(
        self,
        quorum_size: int = 3,
        voting_timeout_seconds: float = 300.0,
        snapshot_interval: int = 100,
        drift_threshold: float = 0.15,
    ):
        """
        Initialize the baseline update service.

        Args:
            quorum_size: Agents required for quorum
            voting_timeout_seconds: Voting time limit
            snapshot_interval: Changes between snapshots
            drift_threshold: Drift detection threshold
        """
        self._rollback_manager = BaselineRollbackManager(
            snapshot_interval=snapshot_interval,
        )
        self._tribunal = BaselineTribunal(
            quorum_size=quorum_size,
            voting_timeout_seconds=voting_timeout_seconds,
            drift_threshold=drift_threshold,
        )

        logger.info(
            "BaselineUpdateService initialized",
            quorum_size=quorum_size,
            snapshot_interval=snapshot_interval,
        )

    def propose_change(
        self,
        change_type: BaselineChangeType,
        proposed_by: str,
        rationale: str,
        pattern_id: str | None = None,
    ) -> BaselineChangeProposal:
        """Propose a baseline change."""
        return self._tribunal.propose_baseline_change(
            change_type=change_type,
            proposed_by=proposed_by,
            rationale=rationale,
            pattern_id=pattern_id,
        )

    def vote(
        self,
        proposal_id: str,
        agent_id: str,
        decision: VoteDecision,
    ) -> dict[str, Any]:
        """Cast a vote on a proposal."""
        return self._tribunal.cast_vote(proposal_id, agent_id, decision)

    def create_snapshot(
        self,
        baseline_hash: str,
        patterns: dict[str, Any],
        change_history_ids: list[str],
    ) -> BaselineSnapshot:
        """Create a baseline snapshot."""
        return self._rollback_manager.create_snapshot(
            baseline_hash=baseline_hash,
            patterns=patterns,
            change_history_ids=change_history_ids,
        )

    def request_rollback(
        self,
        target_snapshot_id: str | None,
        reason: RollbackReason,
        initiated_by: str,
        emergency: bool = False,
    ) -> RollbackOperation:
        """Request a rollback."""
        return self._rollback_manager.request_rollback(
            target_snapshot_id=target_snapshot_id,
            reason=reason,
            initiated_by=initiated_by,
            emergency=emergency,
        )

    def check_drift(self, patterns: dict[str, Any]) -> DriftReport:
        """Check for baseline drift."""
        return self._tribunal.check_baseline_drift(patterns)

    def get_statistics(self) -> dict[str, Any]:
        """Get combined statistics."""
        return {
            "tribunal": self._tribunal.get_tribunal_statistics(),
            "snapshots": len(self._rollback_manager._snapshots),
            "pending_rollbacks": len(self._rollback_manager._rollback_operations),
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def create_baseline_update_service(
    config: dict[str, Any] | None = None,
) -> BaselineUpdateService:
    """
    Create a configured baseline update service.

    Args:
        config: Optional configuration

    Returns:
        Configured BaselineUpdateService
    """
    if config is None:
        config = {}

    return BaselineUpdateService(
        quorum_size=config.get("quorum_size", 3),
        voting_timeout_seconds=config.get("voting_timeout_seconds", 300.0),
        snapshot_interval=config.get("snapshot_interval", 100),
        drift_threshold=config.get("drift_threshold", 0.15),
    )
