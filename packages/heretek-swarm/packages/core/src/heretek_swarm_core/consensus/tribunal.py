"""
Tribunal - Consensus Decision Appeals & Resolution System.

The Tribunal provides retroactive binding consensus decisions where agents
can appeal past decisions. It maintains a complete evidence chain and
provides binding resolutions for disputed outcomes.

Example:
    ```python
    from heretek_swarm_core.consensus.tribunal import Tribunal, Evidence, TribunalCase

    tribunal = Tribunal()

    # Submit evidence
    evidence = tribunal.submit_evidence(
        agent_id="agent-1",
        case_id="case-001",
        content="Test results show 98% success rate",
        evidence_type="test_result"
    )

    # Create appeal case
    case = tribunal.create_case(
        original_decision_id="decision-001",
        appellant_agent_id="agent-2",
        grounds="New evidence emerged",
        description="Appealing based on new test results"
    )

    # Issue binding decision
    ruling = tribunal.issue_ruling(case.case_id, "uphold", reasoning="Evidence is compelling")
    ```
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("Tribunal")


@dataclass
class TribunalConfig:
    """Configuration for Tribunal deliberation."""

    max_rounds: int = 3
    round_timeout_seconds: float = 15.0
    tiebreaker_role: str = "steward"


class CaseStatus(Enum):
    """Status of a tribunal case."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    EVIDENCE_SUBMITTED = "evidence_submitted"
    CLOSED = "closed"
    DISMISSED = "dismissed"


class RulingType(Enum):
    """Types of tribunal rulings."""

    UPHOLD = "uphold"
    OVERRULE = "overrule"
    MODIFY = "modify"
    DISMISS = "dismiss"
    REMAND = "remand"


class EvidenceType(Enum):
    """Types of tribunal evidence."""

    DOCUMENT = "document"
    TEST_RESULT = "test_result"
    EXPERT_OPINION = "expert_opinion"
    HISTORICAL = "historical"
    LOGICAL = "logical"
    SIMULATION = "simulation"
    WITNESS = "witness"
    ANNOTATION = "annotation"


@dataclass
class TribunalEvidence:
    """Evidence submitted to a tribunal case."""

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = ""
    agent_id: str = ""
    evidence_type: EvidenceType = EvidenceType.DOCUMENT
    content: str = ""
    source: str | None = None
    reliability_score: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    hash: str | None = None

    def __post_init__(self) -> None:
        """Generate hash for integrity."""
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate cryptographic hash of evidence."""
        data = {
            "evidence_id": self.evidence_id,
            "case_id": self.case_id,
            "agent_id": self.agent_id,
            "evidence_type": self.evidence_type.value,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class TribunalCase:
    """A case brought before the tribunal."""

    case_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_decision_id: str = ""
    original_consensus_id: str = ""
    appellant_agent_id: str = ""
    grounds: str = ""
    description: str = ""
    status: CaseStatus = CaseStatus.PENDING
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    closed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    hash: str | None = None

    def __post_init__(self) -> None:
        """Generate hash for integrity."""
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate cryptographic hash of case."""
        data = {
            "case_id": self.case_id,
            "original_decision_id": self.original_decision_id,
            "original_consensus_id": self.original_consensus_id,
            "appellant_agent_id": self.appellant_agent_id,
            "grounds": self.grounds,
            "created_at": self.created_at,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class TribunalRuling:
    """A ruling issued by the tribunal."""

    ruling_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = ""
    ruling_type: RulingType = RulingType.DISMISS
    reasoning: str = ""
    issued_by: str = "tribunal"
    confidence: float = 1.0
    precedent_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    evidence_considered: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    hash: str | None = None

    def __post_init__(self) -> None:
        """Generate hash for integrity."""
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate cryptographic hash of ruling."""
        data = {
            "ruling_id": self.ruling_id,
            "case_id": self.case_id,
            "ruling_type": self.ruling_type.value,
            "reasoning": self.reasoning,
            "issued_by": self.issued_by,
            "confidence": self.confidence,
            "precedent_id": self.precedent_id,
            "timestamp": self.timestamp,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class Tribunal:
    """
    Tribunal for consensus decision appeals and resolution.

    Provides retroactive binding consensus decisions where agents
    can appeal past decisions. Maintains complete evidence chains
    and issues binding resolutions.

    Attributes:
        case_retention_days: Days to retain closed cases
        enable_precedent: Whether to use precedent in rulings
    """

    def __init__(
        self,
        case_retention_days: int = 365,
        enable_precedent: bool = True,
        max_rounds: int = 3,
        round_timeout_seconds: float = 15.0,
        tiebreaker_role: str = "steward",
        event_mesh: Any | None = None,
    ) -> None:
        """
        Initialize the Tribunal.

        Args:
            case_retention_days: Days to retain case records
            enable_precedent: Enable precedent-based reasoning
            max_rounds: Maximum deliberation rounds before tiebreaker (GOV-05-M)
            round_timeout_seconds: Timeout per round for convoy mitigation
            tiebreaker_role: Role to invoke as tiebreaker
            event_mesh: Optional EventMesh for NATS precedent publishing.
                        When provided, binding rulings (UPHOLD/OVERRULE)
                        fire precedent_recorded events via NATS.
        """
        self.case_retention_days = case_retention_days
        self.enable_precedent = enable_precedent
        self.max_rounds = max_rounds
        self.round_timeout_seconds = round_timeout_seconds
        self.tiebreaker_role = tiebreaker_role
        self.current_round: int = 0
        self._event_mesh = event_mesh  # Optional NATS event mesh

        # Storage
        self._cases: dict[str, TribunalCase] = {}
        self._evidence: dict[str, TribunalEvidence] = {}
        self._rulings: dict[str, TribunalRuling] = {}
        self._decision_case_map: dict[str, str] = {}  # decision_id -> case_id
        self._precedents: list[str] = []  # ruling_ids of binding precedents

        # GOV-05-M: Tiebreaker tracking
        self._tiebreaker_invoked: bool = False
        self._tiebreaker_reason: str | None = None

        logger.info(
            "Tribunal initialized",
            retention_days=case_retention_days,
            precedent_enabled=enable_precedent,
            max_rounds=max_rounds,
            tiebreaker_role=tiebreaker_role,
        )

    def submit_evidence(
        self,
        agent_id: str,
        case_id: str,
        content: str,
        evidence_type: EvidenceType = EvidenceType.DOCUMENT,
        source: str | None = None,
        reliability_score: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> TribunalEvidence:
        """
        Submit evidence to a tribunal case.

        Args:
            agent_id: Agent submitting evidence
            case_id: Case to submit evidence to
            content: Evidence content
            evidence_type: Type of evidence
            source: Evidence source
            reliability_score: Reliability score (0.0-1.0)
            metadata: Additional metadata

        Returns:
            Submitted evidence record
        """
        evidence = TribunalEvidence(
            case_id=case_id,
            agent_id=agent_id,
            evidence_type=evidence_type,
            content=content,
            source=source,
            reliability_score=reliability_score,
            metadata=metadata or {},
        )

        self._evidence[evidence.evidence_id] = evidence

        # Update case
        if case_id in self._cases:
            case = self._cases[case_id]
            case.evidence_ids.append(evidence.evidence_id)
            case.updated_at = datetime.now(UTC).isoformat()
            if case.status == CaseStatus.PENDING:
                case.status = CaseStatus.EVIDENCE_SUBMITTED

        logger.info(
            "Evidence submitted to tribunal",
            evidence_id=evidence.evidence_id,
            case_id=case_id,
            agent_id=agent_id,
            evidence_type=evidence_type.value,
        )

        return evidence

    def create_case(
        self,
        original_decision_id: str,
        appellant_agent_id: str,
        grounds: str,
        description: str,
        original_consensus_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TribunalCase:
        """
        Create a new tribunal case (appeal).

        Args:
            original_decision_id: Decision being appealed
            appellant_agent_id: Agent filing appeal
            grounds: Grounds for appeal
            description: Case description
            original_consensus_id: Original consensus ID
            metadata: Additional metadata

        Returns:
            Created tribunal case
        """
        # Check if case already exists for this decision
        if original_decision_id in self._decision_case_map:
            existing_case_id = self._decision_case_map[original_decision_id]
            raise ValueError(
                f"Case already exists for decision {original_decision_id}: {existing_case_id}"
            )

        case = TribunalCase(
            original_decision_id=original_decision_id,
            original_consensus_id=original_consensus_id or "",
            appellant_agent_id=appellant_agent_id,
            grounds=grounds,
            description=description,
            metadata=metadata or {},
        )

        self._cases[case.case_id] = case
        self._decision_case_map[original_decision_id] = case.case_id

        logger.info(
            "Tribunal case created",
            case_id=case.case_id,
            original_decision_id=original_decision_id,
            appellant_agent_id=appellant_agent_id,
            grounds=grounds,
        )

        return case

    def get_case(self, case_id: str) -> TribunalCase | None:
        """
        Get a tribunal case by ID.

        Args:
            case_id: Case ID

        Returns:
            Tribunal case or None if not found
        """
        return self._cases.get(case_id)

    def get_case_by_decision(self, decision_id: str) -> TribunalCase | None:
        """
        Get a tribunal case by original decision ID.

        Args:
            decision_id: Original decision ID

        Returns:
            Tribunal case or None if not found
        """
        case_id = self._decision_case_map.get(decision_id)
        return self._cases.get(case_id) if case_id else None

    def get_evidence(self, evidence_id: str) -> TribunalEvidence | None:
        """
        Get evidence by ID.

        Args:
            evidence_id: Evidence ID

        Returns:
            Evidence or None if not found
        """
        return self._evidence.get(evidence_id)

    def get_case_evidence(self, case_id: str) -> list[TribunalEvidence]:
        """
        Get all evidence for a case.

        Args:
            case_id: Case ID

        Returns:
            List of evidence for the case
        """
        case = self._cases.get(case_id)
        if not case:
            return []
        return [self._evidence[eid] for eid in case.evidence_ids if eid in self._evidence]

    def issue_ruling(
        self,
        case_id: str,
        ruling_type: RulingType,
        reasoning: str,
        issued_by: str = "tribunal",
        confidence: float = 1.0,
        precedent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TribunalRuling:
        """
        Issue a ruling on a tribunal case.

        Args:
            case_id: Case to rule on
            ruling_type: Type of ruling
            reasoning: Ruling reasoning
            issued_by: Entity issuing ruling
            confidence: Ruling confidence
            precedent_id: Precedent ruling ID
            metadata: Additional metadata

        Returns:
            Issued ruling

        Raises:
            ValueError: If case not found or already closed
        """
        case = self._cases.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        if case.status == CaseStatus.CLOSED:
            raise ValueError(f"Case already closed: {case_id}")

        ruling = TribunalRuling(
            case_id=case_id,
            ruling_type=ruling_type,
            reasoning=reasoning,
            issued_by=issued_by,
            confidence=confidence,
            precedent_id=precedent_id,
            evidence_considered=case.evidence_ids.copy(),
            metadata=metadata or {},
        )

        self._rulings[ruling.ruling_id] = ruling

        # Update case status
        case.status = CaseStatus.CLOSED
        case.closed_at = datetime.now(UTC).isoformat()
        case.updated_at = datetime.now(UTC).isoformat()

        # Register as precedent if applicable
        if self.enable_precedent and ruling_type in (
            RulingType.UPHOLD,
            RulingType.OVERRULE,
        ):
            self._precedents.append(ruling.ruling_id)

        # Fire-and-forget NATS publish for binding precedents
        if (
            self._event_mesh is not None
            and ruling_type in (RulingType.UPHOLD, RulingType.OVERRULE)
        ):
            try:
                self._event_mesh.publish_to_nats(
                    event_type="precedent_recorded",
                    source_agent="tribunal",
                    payload={
                        "ruling_id": ruling.ruling_id,
                        "case_id": case_id,
                        "ruling_type": ruling_type.value,
                        "reasoning": reasoning,
                        "confidence": confidence,
                        "anomaly_id": case.original_decision_id,
                        "precedent_id": precedent_id,
                        "timestamp": ruling.timestamp,
                    },
                )
                logger.info(
                    "tribunal_precedent_published",
                    ruling_id=ruling.ruling_id,
                    case_id=case_id,
                    ruling_type=ruling_type.value,
                )
            except Exception as e:
                logger.debug(
                    "nats_publisher_not_available",
                    error=str(e),
                    ruling_id=ruling.ruling_id,
                    case_id=case_id,
                )

        logger.info(
            "Tribunal ruling issued",
            ruling_id=ruling.ruling_id,
            case_id=case_id,
            ruling_type=ruling_type.value,
            confidence=confidence,
        )

        # Structured immune-loop signal: tribunal_ruling_issued
        logger.info(
            "tribunal_ruling_issued",
            ruling_id=ruling.ruling_id,
            case_id=case_id,
            ruling_type=ruling_type.value,
            issued_by=issued_by,
            confidence=confidence,
        )

        return ruling

    def get_ruling(self, ruling_id: str) -> TribunalRuling | None:
        """
        Get a ruling by ID.

        Args:
            ruling_id: Ruling ID

        Returns:
            Ruling or None if not found
        """
        return self._rulings.get(ruling_id)

    def get_case_ruling(self, case_id: str) -> TribunalRuling | None:
        """
        Get the ruling for a case.

        Args:
            case_id: Case ID

        Returns:
            Ruling or None if no ruling exists
        """
        for ruling in self._rulings.values():
            if ruling.case_id == case_id:
                return ruling
        return None

    def get_precedents(
        self,
        limit: int = 10,
        ruling_type: RulingType | None = None,
    ) -> list[TribunalRuling]:
        """
        Get binding precedents.

        Args:
            limit: Maximum precedents to return
            ruling_type: Filter by ruling type

        Returns:
            List of precedent rulings
        """
        precedents = []
        for ruling_id in self._precedents:
            ruling = self._rulings.get(ruling_id)
            if ruling and (ruling_type is None or ruling.ruling_type == ruling_type):
                precedents.append(ruling)

        return sorted(
            precedents,
            key=lambda r: r.timestamp,
            reverse=True,
        )[:limit]

    def find_similar_precedents(
        self,
        grounds: str,
        limit: int = 5,
    ) -> list[TribunalRuling]:
        """
        Find precedents similar to given grounds.

        Args:
            grounds: Grounds description
            limit: Maximum results

        Returns:
            List of similar precedents
        """
        grounds_lower = grounds.lower()
        scored: list[tuple[float, TribunalRuling]] = []

        for ruling_id in self._precedents:
            ruling = self._rulings.get(ruling_id)
            if not ruling:
                continue

            # Simple keyword matching
            ruling_words = set(ruling.reasoning.lower().split())
            grounds_words = set(grounds_lower.split())
            overlap = len(ruling_words & grounds_words)
            score = overlap / max(len(ruling_words), len(grounds_words))

            if score > 0:
                scored.append((score, ruling))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ruling for _, ruling in scored[:limit]]

    def list_cases(
        self,
        status: CaseStatus | None = None,
        limit: int = 100,
    ) -> list[TribunalCase]:
        """
        List tribunal cases.

        Args:
            status: Filter by status
            limit: Maximum cases to return

        Returns:
            List of cases
        """
        cases = list(self._cases.values())

        if status is not None:
            cases = [c for c in cases if c.status == status]

        return sorted(
            cases,
            key=lambda c: c.created_at,
            reverse=True,
        )[:limit]

    def calculate_case_quality(self, case_id: str) -> float:
        """
        Calculate the quality score of a case based on evidence.

        Args:
            case_id: Case ID

        Returns:
            Quality score (0.0-1.0)
        """
        case = self._cases.get(case_id)
        if not case:
            return 0.0

        evidence_list = self.get_case_evidence(case_id)
        if not evidence_list:
            return 0.0

        total_score = 0.0
        for evidence in evidence_list:
            type_modifiers = {
                EvidenceType.TEST_RESULT: 0.95,
                EvidenceType.SIMULATION: 0.85,
                EvidenceType.DOCUMENT: 0.8,
                EvidenceType.HISTORICAL: 0.85,
                EvidenceType.EXPERT_OPINION: 0.75,
                EvidenceType.LOGICAL: 0.9,
                EvidenceType.WITNESS: 0.7,
                EvidenceType.ANNOTATION: 0.6,
            }
            modifier = type_modifiers.get(evidence.evidence_type, 0.7)
            total_score += evidence.reliability_score * modifier

        return min(1.0, total_score / len(evidence_list))

    def export_case_audit(
        self,
        case_id: str,
    ) -> dict[str, Any]:
        """
        Export complete audit record for a case.

        Args:
            case_id: Case ID

        Returns:
            Complete case audit record
        """
        case = self._cases.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        ruling = self.get_case_ruling(case_id)
        evidence_list = self.get_case_evidence(case_id)

        return {
            "case": {
                "case_id": case.case_id,
                "original_decision_id": case.original_decision_id,
                "original_consensus_id": case.original_consensus_id,
                "appellant_agent_id": case.appellant_agent_id,
                "grounds": case.grounds,
                "description": case.description,
                "status": case.status.value,
                "created_at": case.created_at,
                "closed_at": case.closed_at,
                "hash": case.hash,
            },
            "evidence": [
                {
                    "evidence_id": e.evidence_id,
                    "agent_id": e.agent_id,
                    "evidence_type": e.evidence_type.value,
                    "content": e.content,
                    "source": e.source,
                    "reliability_score": e.reliability_score,
                    "timestamp": e.timestamp,
                    "hash": e.hash,
                }
                for e in evidence_list
            ],
            "ruling": (
                {
                    "ruling_id": ruling.ruling_id,
                    "ruling_type": ruling.ruling_type.value,
                    "reasoning": ruling.reasoning,
                    "issued_by": ruling.issued_by,
                    "confidence": ruling.confidence,
                    "precedent_id": ruling.precedent_id,
                    "timestamp": ruling.timestamp,
                    "hash": ruling.hash,
                }
                if ruling
                else None
            ),
            "quality_score": self.calculate_case_quality(case_id),
        }

    def deliberate(
        self,
        topic: str,
        agent_votes: dict[str, str],
    ) -> dict[str, Any]:
        """
        Conduct deliberation with max_rounds enforcement.

        GOV-05-M: Enforces max_rounds (default 3) and invokes tiebreaker
        on round limit without unanimity.

        Args:
            topic: Deliberation topic
            agent_votes: Dict mapping agent_id to their vote/position

        Returns:
            Deliberation decision with metadata
        """
        self.current_round = 0
        self._tiebreaker_invoked = False
        self._tiebreaker_reason = None

        logger.info(
            f"Tribunal deliberation started: topic={topic}, max_rounds={self.max_rounds}, agents={list(agent_votes.keys())}"
        )

        while self.current_round < self.max_rounds:
            self.current_round += 1
            logger.debug(
                f"Tribunal round {self.current_round}/{self.max_rounds} for topic: {topic}"
            )

            if self._check_unanimous(agent_votes):
                decision = self._create_decision(topic, agent_votes, unanimous=True)
                logger.info("Tribunal: Unanimous agreement reached at round {self.current_round}")
                return decision

            if self.current_round >= self.max_rounds:
                break

        logger.warning("Tribunal: max_rounds {self.max_rounds} reached for topic {topic}")
        self._tiebreaker_invoked = True
        self._tiebreaker_reason = f"max_rounds_{self.max_rounds}_reached"
        logger.warning("TIEBREAKER_INVOKED: round={self.current_round} topic={topic}")

        return self._create_decision_with_tiebreaker(topic, agent_votes)

    def _check_unanimous(self, agent_votes: dict[str, str]) -> bool:
        """Check if all agents have the same vote."""
        if len(agent_votes) < 2:
            return True
        votes = list(agent_votes.values())
        return all(v == votes[0] for v in votes)

    def _create_decision(
        self,
        topic: str,
        agent_votes: dict[str, str],
        unanimous: bool = False,
    ) -> dict[str, Any]:
        """Create a decision record from deliberation."""
        vote_counts: dict[str, int] = {}
        for vote in agent_votes.values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        winning_vote = max(vote_counts, key=vote_counts.get)
        confidence = vote_counts[winning_vote] / len(agent_votes) if agent_votes else 0.0

        return {
            "decision": winning_vote,
            "topic": topic,
            "confidence": confidence,
            "unanimous": unanimous,
            "round": self.current_round,
            "tiebreaker_invoked": False,
            "tiebreaker_role": None,
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_votes": dict(agent_votes),
            "vote_distribution": vote_counts,
        }

    def _create_decision_with_tiebreaker(
        self,
        topic: str,
        agent_votes: dict[str, str],
    ) -> dict[str, Any]:
        """
        Create a decision using tiebreaker when max_rounds reached.

        GOV-05-M: Invokes Steward (or Charlie in failover) as tiebreaker.
        """
        vote_counts: dict[str, int] = {}
        for vote in agent_votes.values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        winning_vote = max(vote_counts, key=vote_counts.get)
        tiebreaker_weight = 1.5 if self.tiebreaker_role == "charlie" else 1.0

        adjusted_counts = dict(vote_counts)
        if len(agent_votes) >= 2:
            adjusted_counts[winning_vote] += tiebreaker_weight

        final_decision = max(adjusted_counts, key=adjusted_counts.get)
        total_weight = sum(adjusted_counts.values())
        confidence = adjusted_counts[final_decision] / total_weight if total_weight > 0 else 0.0

        return {
            "decision": final_decision,
            "topic": topic,
            "confidence": confidence,
            "unanimous": False,
            "round": self.current_round,
            "tiebreaker_invoked": True,
            "tiebreaker_role": self.tiebreaker_role,
            "tiebreaker_reason": self._tiebreaker_reason,
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_votes": dict(agent_votes),
            "vote_distribution": adjusted_counts,
            "original_vote_distribution": vote_counts,
        }
