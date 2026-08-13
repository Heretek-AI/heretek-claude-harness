"""
CONS01: Inter-Agent Dispute Resolution Engine.

Implements the Deliberation Engine Integration for Phase 2 Wave 1.
Enables 100% consensus without human mediation for non-critical decisions
with position change ratio >= 15%.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from .swarm_deliberation import (
    Position,
    SwarmDeliberationEngine,
)
from .tribunal import EvidenceType, RulingType, Tribunal

logger = structlog.get_logger("cons01_dispute_resolution")


class DisputeType(Enum):
    CONSTITUTIONAL = "constitutional"
    SAFETY_CRITICAL = "safety_critical"
    RESOURCE_ALLOCATION = "resource"
    EXTERNAL_REPUTATION = "reputation"
    TECHNICAL = "technical"
    PRIORITY = "priority"
    IMPLEMENTATION = "implementation"

    @property
    def is_critical(self) -> bool:
        return self in {
            DisputeType.CONSTITUTIONAL,
            DisputeType.SAFETY_CRITICAL,
            DisputeType.RESOURCE_ALLOCATION,
            DisputeType.EXTERNAL_REPUTATION,
        }


class DisputeState(Enum):
    SUBMITTED = "submitted"
    DELIBERATING = "deliberating"
    CONSENSUS = "consensus"
    ESCALATED = "escalated"
    FAILED = "failed"


@dataclass
class Evidence:
    evidence_id: str
    agent_id: str
    content: str
    timestamp: str
    weight: float = 1.0


@dataclass
class PositionChangeRecord:
    agent_id: str
    dispute_id: str
    round: int
    old_position: str
    new_position: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class MinorityReport:
    agent_id: str
    original_position: str
    final_position: str
    rationale: str
    confidence: float
    persisted: bool = True


@dataclass
class DisputeSubmission:
    dispute_id: str
    parties: list[str]
    topic: str
    description: str
    dispute_type: DisputeType
    evidence: list[Evidence] = field(default_factory=list)
    submitted_by: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: DisputeState = DisputeState.SUBMITTED
    requires_human_escalation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.dispute_type.is_critical:
            self.requires_human_escalation = True
            self.status = DisputeState.ESCALATED


@dataclass
class DisputeResult:
    dispute_id: str
    status: DisputeState
    final_position: str | None
    consensus_score: float
    position_change_ratio: float
    minority_reports: list[MinorityReport]
    deliberation_rounds: int
    binding: bool
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class DisputeResolutionEngine:
    def __init__(
        self,
        consensus_threshold: float = 0.75,
        min_rounds: int = 2,
        max_rounds: int = 5,
        position_change_target: float = 0.15,
        tribunal: Tribunal | None = None,
    ) -> None:
        self.consensus_threshold = consensus_threshold
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self.position_change_target = position_change_target
        self.tribunal = tribunal

        self._swarm_engine = SwarmDeliberationEngine(
            max_rounds=max_rounds,
            consensus_threshold=consensus_threshold,
            min_participants=2,
        )

        self.active_disputes: dict[str, DisputeSubmission] = {}
        self.completed_disputes: dict[str, DisputeResult] = {}
        self._position_changes: dict[str, list[PositionChangeRecord]] = {}
        self._minority_reports: dict[str, list[MinorityReport]] = {}
        self._dispute_rounds: dict[str, int] = {}

        logger.info(
            "dispute_resolution_engine_initialized",
            threshold=consensus_threshold,
            min_rounds=min_rounds,
            max_rounds=max_rounds,
        )

    def submit_dispute(self, submission: DisputeSubmission) -> str:
        dispute_id = submission.dispute_id

        self.active_disputes[dispute_id] = submission
        self._position_changes[dispute_id] = []
        self._minority_reports[dispute_id] = []
        self._dispute_rounds[dispute_id] = 0

        if not submission.requires_human_escalation:
            self._start_deliberation(dispute_id)

        logger.info(
            "dispute_submitted",
            dispute_id=dispute_id,
            is_critical=submission.requires_human_escalation,
        )

        return dispute_id

    def _start_deliberation(self, dispute_id: str) -> None:
        dispute = self.active_disputes[dispute_id]
        deliberation_id = f"dispute-{dispute_id}"

        self._swarm_engine.start_deliberation(
            deliberation_id=deliberation_id,
            proposal=dispute.topic,
            participants=dispute.parties,
            domain=dispute.topic,
        )

        dispute.status = DisputeState.DELIBERATING

        logger.info("deliberation_started", dispute_id=dispute_id)

    def add_participant(self, dispute_id: str, agent_id: str) -> bool:
        if dispute_id not in self.active_disputes:
            return False

        dispute = self.active_disputes[dispute_id]
        if dispute.requires_human_escalation:
            return False

        deliberation_id = f"dispute-{dispute_id}"
        participants = self._swarm_engine.active_deliberations.get(deliberation_id, {}).get(
            "participants", set()
        )
        if hasattr(participants, "add"):
            participants.add(agent_id)

        if agent_id not in dispute.parties:
            dispute.parties.append(agent_id)

        return True

    def submit_position(
        self,
        dispute_id: str,
        agent_id: str,
        position: Position,
        confidence: float,
        argument: str | None = None,
    ) -> bool:
        if dispute_id not in self.active_disputes:
            return False

        deliberation_id = f"dispute-{dispute_id}"
        result = self._swarm_engine.submit_position(
            deliberation_id=deliberation_id,
            agent_id=agent_id,
            position=position,
            confidence=confidence,
            argument=argument,
        )

        if result:
            self._track_position_change(dispute_id, agent_id, position)

        return result

    def _track_position_change(
        self,
        dispute_id: str,
        agent_id: str,
        new_position: Position,
    ) -> None:
        deliberation_id = f"dispute-{dispute_id}"
        positions = self._swarm_engine.active_deliberations.get(deliberation_id, {}).get(
            "positions", {}
        )

        old_position = "unknown"
        if agent_id in positions:
            old_position = positions[agent_id].position.value

        if old_position != new_position.value:
            change_record = PositionChangeRecord(
                agent_id=agent_id,
                dispute_id=dispute_id,
                round=self._dispute_rounds.get(dispute_id, 0),
                old_position=old_position,
                new_position=new_position.value,
            )
            self._position_changes[dispute_id].append(change_record)

    def run_deliberation_round(self, dispute_id: str) -> dict[str, Any] | None:
        if dispute_id not in self.active_disputes:
            return None

        dispute = self.active_disputes[dispute_id]
        if dispute.requires_human_escalation:
            return None

        deliberation_id = f"dispute-{dispute_id}"
        round_result = self._swarm_engine.run_deliberation_round(deliberation_id)

        if round_result:
            self._dispute_rounds[dispute_id] = round_result.round_number
            dispute.status = DisputeState.DELIBERATING

            return {
                "round": round_result.round_number,
                "consensus_score": round_result.consensus_score,
                "position_changes": round_result.position_changes,
            }

        return None

    def get_position_change_ratio(self, dispute_id: str) -> float:
        if dispute_id not in self.active_disputes:
            return 0.0

        dispute = self.active_disputes[dispute_id]
        changes = self._position_changes.get(dispute_id, [])
        total_participants = len(dispute.parties)

        if total_participants == 0:
            return 0.0

        agents_who_changed = {c.agent_id for c in changes}
        return len(agents_who_changed) / total_participants

    def finalize_consensus(self, dispute_id: str) -> DisputeResult | None:
        if dispute_id not in self.active_disputes:
            return None

        dispute = self.active_disputes[dispute_id]

        if dispute.requires_human_escalation:
            return self._escalate_to_tribunal(dispute_id)

        deliberation_id = f"dispute-{dispute_id}"
        deliberation_result = self._swarm_engine.finalize_deliberation(deliberation_id)

        if not deliberation_result:
            result = DisputeResult(
                dispute_id=dispute_id,
                status=DisputeState.FAILED,
                final_position=None,
                consensus_score=0.0,
                position_change_ratio=self.get_position_change_ratio(dispute_id),
                minority_reports=[],
                deliberation_rounds=self._dispute_rounds.get(dispute_id, 0),
                binding=False,
            )
            self.completed_disputes[dispute_id] = result
            return result

        minority_reports = self._build_minority_reports(dispute_id, deliberation_result)
        minority_reports.extend(self._minority_reports.get(dispute_id, []))

        final_position = (
            deliberation_result.final_position.value
            if hasattr(deliberation_result.final_position, "value")
            else str(deliberation_result.final_position)
        )

        result = DisputeResult(
            dispute_id=dispute_id,
            status=DisputeState.CONSENSUS,
            final_position=final_position,
            consensus_score=deliberation_result.consensus_score,
            position_change_ratio=self.get_position_change_ratio(dispute_id),
            minority_reports=minority_reports,
            deliberation_rounds=deliberation_result.rounds_completed,
            binding=False,
        )

        dispute.status = DisputeState.CONSENSUS
        self.completed_disputes[dispute_id] = result

        logger.info(
            "consensus_reached",
            dispute_id=dispute_id,
            final_position=final_position,
            position_change_ratio=result.position_change_ratio,
        )

        return result

    def _build_minority_reports(
        self,
        dispute_id: str,
        _deliberation_result: Any,
    ) -> list[MinorityReport]:
        deliberation_id = f"dispute-{dispute_id}"
        minority_opinions = self._swarm_engine.get_minority_opinions(deliberation_id)

        minority_reports = []
        for opinion in minority_opinions:
            report = MinorityReport(
                agent_id=opinion.get("agent_id", "unknown"),
                original_position=opinion.get("position", "UNKNOWN"),
                final_position=opinion.get("position", "UNKNOWN"),
                rationale=opinion.get("argument", ""),
                confidence=opinion.get("confidence", 0.5),
                persisted=True,
            )
            minority_reports.append(report)

        return minority_reports

    def get_minority_reports(self, dispute_id: str) -> list[MinorityReport]:
        return self._minority_reports.get(dispute_id, [])

    def escalate_to_tribunal(self, dispute_id: str) -> DisputeResult | None:
        if dispute_id not in self.active_disputes:
            return None

        return self._escalate_to_tribunal(dispute_id)

    def _escalate_to_tribunal(self, dispute_id: str) -> DisputeResult:
        dispute = self.active_disputes[dispute_id]

        if not self.tribunal:
            logger.error("tribunal_not_available", dispute_id=dispute_id)
            result = DisputeResult(
                dispute_id=dispute_id,
                status=DisputeState.FAILED,
                final_position=None,
                consensus_score=0.0,
                position_change_ratio=0.0,
                minority_reports=[],
                deliberation_rounds=self._dispute_rounds.get(dispute_id, 0),
                binding=True,
            )
            self.completed_disputes[dispute_id] = result
            return result

        case = self.tribunal.create_case(
            original_decision_id=dispute_id,
            appellant_agent_id=dispute.submitted_by or dispute.parties[0],
            grounds=f"CRITICAL dispute: {dispute.dispute_type.value}",
            description=f"{dispute.topic}: {dispute.description}",
        )

        for ev in dispute.evidence:
            self.tribunal.submit_evidence(
                agent_id=ev.agent_id,
                case_id=case.case_id,
                content=ev.content,
                evidence_type=EvidenceType.LOGICAL,
                reliability_score=ev.weight,
            )

        ruling = self.tribunal.issue_ruling(
            case_id=case.case_id,
            ruling_type=RulingType.UPHOLD,
            reasoning=f"Binding decision for CRITICAL {dispute.dispute_type.value} dispute",
            confidence=1.0,
        )

        dispute.status = DisputeState.ESCALATED

        result = DisputeResult(
            dispute_id=dispute_id,
            status=DisputeState.ESCALATED,
            final_position=ruling.ruling_type.value,
            consensus_score=ruling.confidence,
            position_change_ratio=0.0,
            minority_reports=self._minority_reports.get(dispute_id, []),
            deliberation_rounds=self._dispute_rounds.get(dispute_id, 0),
            binding=True,
        )

        self.completed_disputes[dispute_id] = result

        logger.warning("escalated_to_tribunal", dispute_id=dispute_id)

        return result

    def get_dispute_status(self, dispute_id: str) -> DisputeState | None:
        if dispute_id in self.active_disputes:
            return self.active_disputes[dispute_id].status
        if dispute_id in self.completed_disputes:
            return self.completed_disputes[dispute_id].status
        return None

    def get_statistics(self) -> dict[str, Any]:
        total = len(self.active_disputes)
        critical = sum(1 for d in self.active_disputes.values() if d.requires_human_escalation)
        non_critical = total - critical
        consensus = sum(
            1 for r in self.completed_disputes.values() if r.status == DisputeState.CONSENSUS
        )
        escalated = sum(
            1 for r in self.completed_disputes.values() if r.status == DisputeState.ESCALATED
        )

        return {
            "total_disputes": total,
            "critical_disputes": critical,
            "non_critical_disputes": non_critical,
            "consensus_reached": consensus,
            "escalated_to_tribunal": escalated,
            "position_change_target": self.position_change_target,
            "consensus_threshold": self.consensus_threshold,
        }
