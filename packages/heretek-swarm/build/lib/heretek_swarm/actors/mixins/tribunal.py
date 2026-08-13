"""
TribunalMixin - Tribunal integration for agents.

Provides methods for agents to interact with the Tribunal system,
including submitting appeals, evidence, and querying rulings.
"""

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from heretek_swarm.consensus.tribunal import (
        EvidenceType,
        RulingType,
        Tribunal,
        TribunalCase,
        TribunalEvidence,
        TribunalRuling,
    )

logger = structlog.get_logger("TribunalMixin")


class TribunalMixin:
    """
    Mixin providing Tribunal integration for agents.

    Enables agents to:
        - Submit appeal cases to the Tribunal
        - Submit evidence to Tribunal cases
        - Query case status and rulings
        - Issue rulings (for authorized agents)

    Requires the host actor to have:
        - tribunal: Tribunal | None
        - agent_id: str

    Methods:
        _submit_tribunal_case: Submit an appeal case to the Tribunal
        _submit_tribunal_evidence: Submit evidence to a case
        _get_tribunal_case: Get case status and details
        _issue_tribunal_ruling: Issue a ruling (arbitrator agents only)
        _get_tribunal_precedents: Query binding precedents
        _find_similar_precedents: Find relevant past rulings
    """

    tribunal: "Tribunal | None" = None

    async def _submit_tribunal_case(
        self,
        original_decision_id: str,
        grounds: str,
        description: str,
        original_consensus_id: str = "",
    ) -> "TribunalCase":
        """Submit an appeal case to the Tribunal."""
        if not self.tribunal:
            raise TypeError("_submit_tribunal_case requires tribunal")

        try:
            case = self.tribunal.create_case(
                original_decision_id=original_decision_id,
                appellant_agent_id=self.agent_id,
                grounds=grounds,
                description=description,
                original_consensus_id=original_consensus_id,
            )
            logger.info(
                "tribunal_case_submitted",
                case_id=case.case_id,
                agent_id=self.agent_id,
            )
            return case
        except Exception as e:
            logger.error(
                "tribunal_case_submission_failed",
                agent_id=self.agent_id,
                error=str(e),
            )
            return None

    async def _submit_tribunal_evidence(
        self,
        case_id: str,
        content: str,
        evidence_type: "EvidenceType | None" = None,
        source: str | None = None,
        reliability_score: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> "TribunalEvidence":
        """Submit evidence to a Tribunal case."""
        from heretek_swarm.consensus.tribunal import EvidenceType

        if not self.tribunal:
            raise TypeError("_submit_tribunal_evidence requires tribunal")

        # Default to DOCUMENT if not specified
        if evidence_type is None:
            evidence_type = EvidenceType.DOCUMENT

        try:
            evidence = self.tribunal.submit_evidence(
                agent_id=self.agent_id,
                case_id=case_id,
                content=content,
                evidence_type=evidence_type,
                source=source,
                reliability_score=reliability_score,
                metadata=metadata,
            )
            logger.info(
                "tribunal_evidence_submitted",
                evidence_id=evidence.evidence_id,
                case_id=case_id,
            )
            return evidence
        except Exception as e:
            logger.error(
                "tribunal_evidence_submission_failed",
                agent_id=self.agent_id,
                case_id=case_id,
                error=str(e),
            )
            return None

    async def _get_tribunal_case(self, case_id: str) -> "TribunalCase":
        """Get a Tribunal case by ID."""
        if not self.tribunal:
            raise TypeError("_get_tribunal_case requires tribunal")
        return self.tribunal.get_case(case_id)

    async def _issue_tribunal_ruling(
        self,
        case_id: str,
        ruling_type: "RulingType",
        reasoning: str,
        confidence: float = 1.0,
    ) -> "TribunalRuling":
        """Issue a ruling on a Tribunal case."""
        if not self.tribunal:
            raise TypeError("_issue_tribunal_ruling requires tribunal")

        try:
            ruling = self.tribunal.issue_ruling(
                case_id=case_id,
                ruling_type=ruling_type.value,
                reasoning=reasoning,
                issued_by=self.agent_id,
                confidence=confidence,
            )
            logger.info(
                "tribunal_ruling_issued",
                ruling_id=ruling.ruling_id,
                case_id=case_id,
            )
            return ruling
        except Exception as e:
            logger.error("tribunal_ruling_failed", agent_id=self.agent_id, error=str(e))
            return None

    async def _get_tribunal_precedents(self, limit: int = 10) -> list["TribunalRuling"]:
        """Get binding precedent rulings."""
        if not self.tribunal:
            raise TypeError("_get_tribunal_precedents requires tribunal")
        return self.tribunal.get_precedents(limit=limit)

    async def _find_similar_precedents(
        self, case_id: str, limit: int = 5
    ) -> list["TribunalRuling"]:
        """Find precedents similar to a case."""
        if not self.tribunal:
            raise TypeError("_find_similar_precedents requires tribunal")
        return self.tribunal.find_similar_precedents(case_id, limit=limit)
