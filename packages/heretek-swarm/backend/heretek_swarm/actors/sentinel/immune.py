"""
Sentinel Immune Response Manager - Immune response building (CONS-02).

This module provides the ImmuneResponseManager class that encapsulates all
CONS-02 immune response building state and methods previously inline in
SentinelAgent. It acts as a delegate, wrapping ImmuneResponseBuilding and
adding Sentinel-specific state management.

Key capabilities:
- Learning from anomaly responses (like an immune system learning from infection)
- Pattern addition to baseline with quorum approval
- Novel attack pattern preservation for human review
- False positive rate tracking (< 1% target)
- Immune memory snapshot and statistics
- Behavioral baseline status and vote submission

Reference: Phase 2 Plan Task 2 (CONS-02)

Note: This module is distinct from consensus/immune.py which provides the
      ImmuneResponseBuilding and ImmuneResponseEngine infrastructure classes.
      This module provides the Sentinel-specific orchestration manager.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm_core.security.immune import (
    ImmuneResponseBuilding,
    PatternClassification,
    ResponseOutcome,
)
from heretek_swarm_core.security.behavioral_baseline import (
    BaselineChangeType,
    BehavioralBaseline,
)

logger = structlog.get_logger("ImmuneResponseManager")


class ImmuneResponseManager:
    """
    Immune response building manager for CONS-02.

    Encapsulates all immune system state: the ImmuneResponseBuilding instance,
    behavioral baseline reference, novel pattern queue, outcome tracking,
    and learning configuration.

    Designed to be instantiated by SentinelAgent.__init__ and used as a
    delegate for all immune-related methods.
    """

    def __init__(
        self,
        immune_system: ImmuneResponseBuilding,
        behavioral_baseline: BehavioralBaseline,
        agent_id: str | None = None,
        auto_learn_enabled: bool = True,
        preserve_novel_patterns: bool = True,
    ):
        """
        Initialize the immune response manager.

        Args:
            immune_system: Core immune response building system.
            behavioral_baseline: Baseline store for pattern management.
            agent_id: ID of the owning SentinelAgent.
            auto_learn_enabled: Whether automatic learning is active.
            preserve_novel_patterns: Whether to preserve novel patterns for review.
        """
        self._immune_system = immune_system
        self._behavioral_baseline = behavioral_baseline
        self._agent_id = agent_id

        self.auto_learn_enabled = auto_learn_enabled
        self.preserve_novel_patterns = preserve_novel_patterns

        # Novel pattern preservation queue
        self._novel_pattern_queue: list[str] = []
        self._max_novel_pattern_queue = 100

        logger.info(
            "ImmuneResponseManager_initialized",
            agent_id=agent_id,
            auto_learn=auto_learn_enabled,
            preserve_novel=preserve_novel_patterns,
        )

    # ---- Public API --------------------------------------------------------

    async def record_anomaly_response_outcome(
        self,
        anomaly_id: str,
        _response_id: str,
        outcome: ResponseOutcome,
        pattern_content: dict[str, Any],
        pattern_type: str,
        severity: str,
        response_time_ms: float,
    ) -> None:
        """
        Record the outcome of an anomaly response for immune learning.

        This is the core method for CONS-02 immune response building.
        When an anomaly is detected and responded to, this method records
        the outcome so the system can learn from it.

        Args:
            anomaly_id: ID of the anomaly.
            response_id: ID of the response.
            outcome: Result of the response.
            pattern_content: Content of the detected pattern.
            pattern_type: Type of anomaly.
            severity: Severity level.
            response_time_ms: Time taken to respond.
        """
        # Record the response in the immune system
        immune_response = self._immune_system.record_response(
            pattern_content=pattern_content,
            anomaly_id=anomaly_id,
            agent_id=self._agent_id or "sentinel",
            outcome=outcome,
            response_time_ms=response_time_ms,
        )

        # Learn from the response
        immunity_acquired = self._immune_system.learn_from_response(
            response=immune_response,
            pattern_content=pattern_content,
            pattern_type=pattern_type,
            severity=severity,
        )

        # If immunity acquired, check if we should request baseline update
        if immunity_acquired and self.auto_learn_enabled:
            # Check if this is a novel pattern
            classification, immune_pattern = self._immune_system.check_pattern_immunity(
                pattern_content
            )

            if immune_pattern:
                # Request baseline update with quorum
                await self._request_baseline_update(
                    pattern_id=immune_pattern.pattern_id,
                    pattern_type=pattern_type,
                    pattern_content=pattern_content,
                    confidence=immune_pattern.confidence,
                )

        # If novel pattern and preservation is enabled, preserve it
        if outcome == ResponseOutcome.SUCCESS and self.preserve_novel_patterns:
            classification, _ = self._immune_system.check_pattern_immunity(pattern_content)
            if classification == PatternClassification.NOVEL_MALICIOUS:
                preservation_id = self._immune_system.preserve_novel_pattern(
                    pattern_content=pattern_content,
                    pattern_type=pattern_type,
                    context={
                        "anomaly_id": anomaly_id,
                        "severity": severity,
                        "first_occurrence": datetime.now(UTC).isoformat(),
                    },
                )
                self._novel_pattern_queue.append(preservation_id)

                # Prune queue if too large
                if len(self._novel_pattern_queue) > self._max_novel_pattern_queue:
                    self._novel_pattern_queue = self._novel_pattern_queue[
                        -self._max_novel_pattern_queue:
                    ]

                logger.info(
                    "novel_pattern_preserved_for_review",
                    preservation_id=preservation_id,
                    anomaly_id=anomaly_id,
                )

        logger.info(
            "anomaly_response_outcome_recorded",
            anomaly_id=anomaly_id,
            outcome=outcome.value,
            immunity_acquired=immunity_acquired,
        )

    async def report_response_outcome(
        self,
        anomaly_id: str,
        outcome: ResponseOutcome,
        pending_tracking: dict[str, dict[str, Any]],
    ) -> bool:
        """
        Report the outcome of a previous anomaly response.

        This should be called after the immediate response to an anomaly,
        once the outcome is known (success, failure, false positive, etc.).

        Args:
            anomaly_id: ID of the anomaly.
            outcome: Outcome of the response.
            pending_tracking: Dict of pending outcome tracking from AnomalyMonitor.

        Returns:
            True if outcome was recorded.
        """
        if anomaly_id not in pending_tracking:
            logger.warning("outcome_reported_for_unknown_anomaly", anomaly_id=anomaly_id)
            return False

        tracking = pending_tracking[anomaly_id]

        await self.record_anomaly_response_outcome(
            anomaly_id=anomaly_id,
            response_id=tracking["response_id"],
            outcome=outcome,
            pattern_content=tracking["pattern_content"],
            pattern_type=tracking["pattern_type"],
            severity=tracking["severity"],
            response_time_ms=tracking["response_time_ms"],
        )

        logger.info(
            "response_outcome_reported",
            anomaly_id=anomaly_id,
            outcome=outcome.value,
        )

        return True

    def check_pattern_immunity(
        self,
        pattern_content: dict[str, Any],
    ) -> tuple[PatternClassification, float]:
        """
        Check if a pattern is recognized by the immune system.

        Args:
            pattern_content: Content of the pattern to check.

        Returns:
            Tuple of (classification, confidence).
        """
        classification, immune_pattern = self._immune_system.check_pattern_immunity(
            pattern_content
        )
        confidence = immune_pattern.confidence if immune_pattern else 0.0
        return (classification, confidence)

    def get_novel_patterns_for_review(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get novel patterns awaiting human review.

        Args:
            limit: Maximum patterns to return.

        Returns:
            List of novel pattern preservation records as dicts.
        """
        patterns = self._immune_system.get_novel_patterns_for_review(limit=limit)
        return [
            {
                "preservation_id": p.preservation_id,
                "pattern_type": p.pattern_type,
                "first_observed": p.first_observed.isoformat(),
                "last_observed": p.last_observed.isoformat(),
                "occurrence_count": p.occurrence_count,
                "reviewed": p.reviewed,
                "disposition": p.disposition,
                "context": p.context,
            }
            for p in patterns
        ]

    async def submit_human_review(
        self,
        preservation_id: str,
        reviewer_id: str,
        disposition: str,
        notes: str | None = None,
    ) -> bool:
        """
        Submit human review of a novel pattern.

        Args:
            preservation_id: ID of the preservation record.
            reviewer_id: ID of the human reviewer.
            disposition: Decision (approve/reject/investigate).
            notes: Optional review notes.

        Returns:
            True if review was recorded.
        """
        result = self._immune_system.record_human_review(
            preservation_id=preservation_id,
            reviewer_id=reviewer_id,
            disposition=disposition,
            notes=notes,
        )

        if result and disposition == "approve":
            # If approved, request baseline update
            patterns = self._immune_system.get_novel_patterns_for_review(limit=1000)
            for p in patterns:
                if p.preservation_id == preservation_id:
                    await self._request_baseline_update(
                        pattern_id=p.pattern_hash,  # Use hash as pattern_id for novel patterns
                        pattern_type=p.pattern_type,
                        pattern_content=p.pattern_content,
                        confidence=0.9,  # Human approved
                    )
                    break

        return result

    def get_immune_system_statistics(self) -> dict[str, Any]:
        """
        Get immune response building statistics.

        Returns:
            Statistics dictionary.
        """
        return self._immune_system.get_statistics()

    def get_immune_memory_snapshot(self) -> dict[str, dict[str, Any]]:
        """
        Get snapshot of immune memory.

        Returns:
            Dictionary of learned patterns.
        """
        return self._immune_system.get_immune_memory_snapshot()

    def get_behavioral_baseline_status(self) -> dict[str, Any]:
        """
        Get behavioral baseline status.

        Returns:
            Status information.
        """
        return {
            "integrity": self._behavioral_baseline.verify_baseline_integrity(),
            "statistics": self._behavioral_baseline.get_statistics(),
            "approved_patterns": self._behavioral_baseline.get_baseline_patterns(
                approved_only=True
            ),
        }

    def submit_baseline_vote(
        self,
        request_id: str,
        agent_id: str,
        approve: bool,
    ) -> bool:
        """
        Submit a vote for a baseline change request.

        Args:
            request_id: ID of the change request.
            agent_id: ID of voting agent.
            approve: True to approve, False to reject.

        Returns:
            True if vote was recorded.
        """
        return self._behavioral_baseline.submit_change_vote(request_id, agent_id, approve)

    # ---- Internal ----------------------------------------------------------

    async def _request_baseline_update(
        self,
        pattern_id: str,
        pattern_type: str,
        pattern_content: dict[str, Any],
        confidence: float,
    ) -> str | None:
        """
        Request quorum approval for adding a pattern to the baseline.

        Args:
            pattern_id: ID of the pattern.
            pattern_type: Type of pattern.
            pattern_content: Pattern content.
            confidence: Confidence level.

        Returns:
            Request ID if created.
        """
        # Add pattern to behavioral baseline
        baseline_pattern_id = self._behavioral_baseline.add_baseline_pattern(
            pattern_type=pattern_type,
            description="Immune-learned pattern from anomaly response",
            content=pattern_content,
            confidence=confidence,
            requester_id=self._agent_id,
        )

        # Request baseline change with quorum
        request_id = self._behavioral_baseline.request_baseline_change(
            change_type=BaselineChangeType.PATTERN_ADDED,
            pattern_id=baseline_pattern_id,
            proposed_value={"pattern_content": pattern_content, "confidence": confidence},
            reasoning=(
                f"Pattern learned from "
                f"{self._immune_system.min_occurrences_for_immunity}+ "
                f"successful anomaly responses"
            ),
            requester_id=self._agent_id or "sentinel",
        )

        logger.info(
            "baseline_update_requested",
            pattern_id=pattern_id,
            baseline_pattern_id=baseline_pattern_id,
            request_id=request_id,
        )

        return request_id
