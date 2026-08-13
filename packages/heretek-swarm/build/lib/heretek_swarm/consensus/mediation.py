"""
Mediation Module for Heretek Swarm Arbiter.

This module provides dispute mediation between agents when deliberation fails:
- MediationSession management for ongoing mediations
- Binding decision arbitration when consensus cannot be reached
- Core Triad override handling for governance conflicts
- Human review escalation for unresolvable disputes

Components:
- MediationSession: Active mediation state
- MediationEngine: Core mediation logic
- CoreTriadOverride: Core Triad governance override records
- HumanReviewEscalation: Human review requests

Reference: Phase 2 Plan Task 4 (SAFE-03)
"""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("mediation")

CORE_TRIAD_AGENTS = frozenset({"steward", "alpha", "beta", "charlie"})


class MediationOutcome(StrEnum):
    """How mediation concluded."""

    RESOLVED_BINDING = "resolved_binding"
    RESOLVED_CONSENSUS = "resolved_consensus"
    ESCALATED_CORE_TRIAD = "escalated_core_triad"
    ESCALATED_HUMAN = "escalated_human"
    FAILED = "failed"


class MediationState(StrEnum):
    """State of a mediation session."""

    ACTIVE = "active"
    STALLED = "stalled"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class PositionType(StrEnum):
    """Agent position in mediation."""

    AGREE = "agree"
    DISAGREE = "disagree"
    COMPROMISE = "compromise"
    ABSTAIN = "abstain"


@dataclass
class AgentPosition:
    """An agent's position in mediation."""

    agent_id: str
    position: PositionType
    argument: str
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class MediationSession:
    """Ongoing mediation session state."""

    session_id: str
    conflict_id: str
    deliberation_id: str
    participants: list[str]
    started_at: str
    rounds: int = 0
    max_rounds: int = 3
    state: MediationState = MediationState.ACTIVE
    positions: dict[str, AgentPosition] = field(default_factory=dict)
    binding_decision: dict[str, Any] | None = None
    outcome: MediationOutcome | None = None


@dataclass
class MediationRequest:
    """Request for mediation."""

    request_id: str
    conflict_id: str
    deliberation_id: str
    reason: str
    participants: list[str]
    initiated_by: str
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class MediationResult:
    """Result of mediation."""

    result_id: str
    session_id: str
    outcome: MediationOutcome
    final_position: dict[str, Any]
    consensus_achieved: bool
    rounds_completed: int
    binding_decision: dict[str, Any] | None = None
    core_triad_override: bool = False
    human_review_requested: bool = False
    completed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class CoreTriadOverride:
    """Record of Core Triad governance override."""

    override_id: str
    session_id: str
    original_decision: dict[str, Any]
    overridden_by: list[str]
    reasoning: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    hash: str | None = None

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        data = {
            "override_id": self.override_id,
            "session_id": self.session_id,
            "original_decision": self.original_decision,
            "overridden_by": sorted(self.overridden_by),
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]


@dataclass
class HumanReviewEscalation:
    """Human review escalation request."""

    escalation_id: str
    session_id: str
    conflict_id: str
    reason: str
    positions_summary: dict[str, str]
    recommended_action: str | None = None
    reviewed: bool = False
    reviewer_id: str | None = None
    review_notes: str | None = None
    disposition: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class MediationEngine:
    """
    Core mediation engine for Arbiter.

    Handles dispute resolution when deliberation fails:
    - Start mediation from failed deliberation
    - Collect and manage agent positions
    - Run mediation rounds
    - Issue binding decisions
    - Handle Core Triad overrides
    - Escalate to human review when needed
    """

    def __init__(
        self,
        max_rounds: int = 3,
        consensus_threshold: float = 0.66,
    ):
        """
        Initialize the mediation engine.

        Args:
            max_rounds: Maximum mediation rounds before escalation
            consensus_threshold: Ratio needed for consensus
        """
        self._max_rounds = max_rounds
        self._consensus_threshold = consensus_threshold

        self._sessions: dict[str, MediationSession] = {}
        self._requests: dict[str, MediationRequest] = {}
        self._overrides: dict[str, CoreTriadOverride] = {}
        self._escalations: dict[str, HumanReviewEscalation] = {}

        self._stats = {
            "total_mediations": 0,
            "resolved_binding": 0,
            "resolved_consensus": 0,
            "escalated_core_triad": 0,
            "escalated_human": 0,
            "failed": 0,
        }

        logger.info(
            "MediationEngine initialized",
            max_rounds=max_rounds,
            consensus_threshold=consensus_threshold,
        )

    async def start_mediation(
        self,
        conflict_id: str,
        deliberation_id: str,
        reason: str,
        participants: list[str],
        initiated_by: str,
    ) -> MediationSession:
        """
        Start mediation after deliberation failure.

        Args:
            conflict_id: ID of the conflict
            deliberation_id: ID of the failed deliberation
            reason: Why mediation is needed
            participants: Agent IDs in the dispute
            initiated_by: Agent requesting mediation

        Returns:
            Created mediation session
        """
        request_id = f"med_req-{datetime.now(UTC).timestamp()}"
        session_id = f"med_session-{datetime.now(UTC).timestamp()}"

        request = MediationRequest(
            request_id=request_id,
            conflict_id=conflict_id,
            deliberation_id=deliberation_id,
            reason=reason,
            participants=participants,
            initiated_by=initiated_by,
        )
        self._requests[request_id] = request

        session = MediationSession(
            session_id=session_id,
            conflict_id=conflict_id,
            deliberation_id=deliberation_id,
            participants=participants,
            started_at=datetime.now(UTC).isoformat(),
            max_rounds=self._max_rounds,
        )
        self._sessions[session_id] = session

        self._stats["total_mediations"] += 1

        logger.info(
            "Mediation started",
            session_id=session_id,
            conflict_id=conflict_id,
            participants=len(participants),
        )

        return session

    async def submit_position(
        self,
        session_id: str,
        agent_id: str,
        position: PositionType,
        argument: str,
        confidence: float = 0.5,
    ) -> bool:
        """
        Submit an agent's position during mediation.

        Args:
            session_id: Mediation session
            agent_id: Agent submitting position
            position: Agent's position
            argument: Supporting argument
            confidence: Confidence level

        Returns:
            True if position was recorded
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("position_submitted_to_unknown_session", session_id=session_id)
            return False

        if session.state != MediationState.ACTIVE:
            logger.info(
                "position_submitted_to_inactive_session", session_id=session_id, state=session.state
            )
            return False

        agent_position = AgentPosition(
            agent_id=agent_id,
            position=position,
            argument=argument,
            confidence=confidence,
        )
        session.positions[agent_id] = agent_position

        logger.info(
            "Position submitted",
            session_id=session_id,
            agent_id=agent_id,
            position=position.value,
        )

        return True

    async def run_mediation_round(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Execute one mediation round.

        Analyzes current positions and determines if consensus
        can be reached or if more rounds are needed.

        Args:
            session_id: Mediation session

        Returns:
            Round analysis results
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        session.rounds += 1

        positions = list(session.positions.values())
        if not positions:
            return {
                "success": True,
                "round": session.rounds,
                "consensus_achieved": False,
                "message": "No positions submitted yet",
            }

        agree_count = sum(1 for p in positions if p.position == PositionType.AGREE)
        disagree_count = sum(1 for p in positions if p.position == PositionType.DISAGREE)
        compromise_count = sum(1 for p in positions if p.position == PositionType.COMPROMISE)

        total = len(positions)
        agree_ratio = agree_count / total

        consensus_achieved = agree_ratio >= self._consensus_threshold

        if consensus_achieved:
            session.state = MediationState.RESOLVED
            session.outcome = MediationOutcome.RESOLVED_CONSENSUS
            self._stats["resolved_consensus"] += 1

            logger.info(
                "Mediation reached consensus",
                session_id=session_id,
                rounds=session.rounds,
                agree_ratio=agree_ratio,
            )

        elif session.rounds >= session.max_rounds:
            session.state = MediationState.STALLED

            logger.info(
                "Mediation stalled - max rounds reached",
                session_id=session_id,
                rounds=session.rounds,
            )

        return {
            "success": True,
            "round": session.rounds,
            "consensus_achieved": consensus_achieved,
            "positions_count": len(positions),
            "agree_count": agree_count,
            "disagree_count": disagree_count,
            "compromise_count": compromise_count,
            "agree_ratio": agree_ratio,
            "state": session.state.value,
        }

    async def finalize_mediation(
        self,
        session_id: str,
        binding_decision: dict[str, Any] | None = None,
    ) -> MediationResult:
        """
        Conclude mediation and emit binding decision.

        Args:
            session_id: Mediation session
            binding_decision: Optional binding decision to apply

        Returns:
            Mediation result
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.state == MediationState.RESOLVED:
            outcome = session.outcome or MediationOutcome.RESOLVED_CONSENSUS
        elif session.state == MediationState.STALLED:
            outcome = MediationOutcome.ESCALATED_HUMAN
        else:
            outcome = MediationOutcome.FAILED

        session.binding_decision = binding_decision
        session.outcome = outcome

        result = MediationResult(
            result_id=f"med_result-{datetime.now(UTC).timestamp()}",
            session_id=session_id,
            outcome=outcome,
            final_position={
                "rounds": session.rounds,
                "positions": {
                    agent_id: pos.position.value for agent_id, pos in session.positions.items()
                },
            },
            consensus_achieved=session.state == MediationState.RESOLVED,
            rounds_completed=session.rounds,
            binding_decision=binding_decision,
            human_review_requested=outcome == MediationOutcome.ESCALATED_HUMAN,
        )

        if outcome == MediationOutcome.RESOLVED_BINDING:
            self._stats["resolved_binding"] += 1
        elif outcome == MediationOutcome.ESCALATED_HUMAN:
            self._stats["escalated_human"] += 1
        elif outcome == MediationOutcome.FAILED:
            self._stats["failed"] += 1

        logger.info(
            "Mediation finalized",
            session_id=session_id,
            outcome=outcome.value,
            rounds=session.rounds,
        )

        return result

    async def check_core_triad_override(
        self,
        session_id: str,
        decision: dict[str, Any],
    ) -> tuple[bool, CoreTriadOverride | None]:
        """
        Check if Core Triad governance overrides a decision.

        Args:
            session_id: Mediation session
            decision: The proposed decision

        Returns:
            Tuple of (override_needed, override_record)
        """
        session = self._sessions.get(session_id)
        if not session:
            return False, None

        rejecting_agents = [
            agent_id
            for agent_id, pos in session.positions.items()
            if agent_id in CORE_TRIAD_AGENTS and pos.position == PositionType.DISAGREE
        ]

        if not rejecting_agents:
            return False, None

        override = CoreTriadOverride(
            override_id=f"override-{datetime.now(UTC).timestamp()}",
            session_id=session_id,
            original_decision=decision,
            overridden_by=rejecting_agents,
            reasoning=f"Core Triad agents {rejecting_agents} rejected the decision",
        )
        self._overrides[override.override_id] = override

        self._stats["escalated_core_triad"] += 1

        logger.warning(
            "Core Triad override triggered",
            session_id=session_id,
            overridden_by=rejecting_agents,
        )

        return True, override

    async def escalate_to_human_review(
        self,
        session_id: str,
        reason: str,
        recommended_action: str | None = None,
    ) -> HumanReviewEscalation:
        """
        Escalate to human review as last resort.

        Args:
            session_id: Mediation session
            reason: Why human review is needed
            recommended_action: Optional recommended resolution

        Returns:
            Human review escalation record
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        positions_summary = {
            agent_id: pos.position.value for agent_id, pos in session.positions.items()
        }

        escalation = HumanReviewEscalation(
            escalation_id=f"escalation-{datetime.now(UTC).timestamp()}",
            session_id=session_id,
            conflict_id=session.conflict_id,
            reason=reason,
            positions_summary=positions_summary,
            recommended_action=recommended_action,
        )
        self._escalations[escalation.escalation_id] = escalation

        session.state = MediationState.ESCALATED

        logger.info(
            "Escalated to human review",
            session_id=session_id,
            escalation_id=escalation.escalation_id,
            reason=reason,
        )

        return escalation

    def get_session(self, session_id: str) -> MediationSession | None:
        """Get a mediation session by ID."""
        return self._sessions.get(session_id)

    def get_pending_escalations(self) -> list[HumanReviewEscalation]:
        """Get all unreviewed human escalations."""
        return [e for e in self._escalations.values() if not e.reviewed]

    def record_human_review(
        self,
        escalation_id: str,
        reviewer_id: str,
        disposition: str,
        notes: str | None = None,
    ) -> bool:
        """
        Record human review of an escalation.

        Args:
            escalation_id: Escalation being reviewed
            reviewer_id: Human reviewer
            disposition: Decision (approve/reject/investigate)
            notes: Optional review notes

        Returns:
            True if review was recorded
        """
        escalation = self._escalations.get(escalation_id)
        if not escalation:
            return False

        escalation.reviewed = True
        escalation.reviewer_id = reviewer_id
        escalation.disposition = disposition
        escalation.review_notes = notes

        logger.info(
            "Human review recorded",
            escalation_id=escalation_id,
            reviewer_id=reviewer_id,
            disposition=disposition,
        )

        return True

    def get_statistics(self) -> dict[str, Any]:
        """Get mediation statistics."""
        return {
            **self._stats,
            "active_sessions": sum(
                1 for s in self._sessions.values() if s.state == MediationState.ACTIVE
            ),
            "pending_escalations": len(self.get_pending_escalations()),
            "core_triad_overrides": len(self._overrides),
        }


def create_mediation_engine(
    config: dict[str, Any] | None = None,
) -> MediationEngine:
    """
    Create a configured mediation engine.

    Args:
        config: Optional configuration

    Returns:
        Configured MediationEngine
    """
    if config is None:
        config = {}

    return MediationEngine(
        max_rounds=config.get("max_rounds", 3),
        consensus_threshold=config.get("consensus_threshold", 0.66),
    )
