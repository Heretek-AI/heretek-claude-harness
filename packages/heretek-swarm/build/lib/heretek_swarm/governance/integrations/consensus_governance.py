"""
Governance Consensus Integration

Provides GovernanceDeliberationEngine — a governance-wrapped subclass of DeliberationEngine
that enforces zero-trust validation on deliberation inputs before they are processed.

Key principle: Validation runs BEFORE the input is accepted. On validation failure,
a GovernanceSecurityError is raised and the input is NOT recorded.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog

from heretek_swarm.consensus.deliberation import (
    ArgumentType,
    DeliberationEngine,
    DeliberationResult,
    DeliberationRound,
    EvidenceType,
    Position,
)
from heretek_swarm.governance.agent_identity import AgentIdentity, AgentRole, TrustLevel
from heretek_swarm.governance.coordinator import GovernanceCoordinator
from heretek_swarm.security.zero_trust import ZeroTrustResult

logger = structlog.get_logger("GovernanceDeliberationEngine")


class GovernanceSecurityError(Exception):
    """
    Exception raised when governance validation fails.

    Carries the ZeroTrustResult with per-layer pass/fail details
    and failure reasons for debugging and audit purposes.
    """

    def __init__(self, message: str, result: ZeroTrustResult):
        super().__init__(message)
        self.result = result

    def get_failed_layers(self) -> list[str]:
        """Get list of layers that failed validation."""
        failed = []
        for layer in [
            self.result.layer1,
            self.result.layer2,
            self.result.layer3,
            self.result.layer4,
        ]:
            if not layer.passed:
                failed.append(layer.layer)  # noqa: PERF401
        return failed

    def get_failure_reasons(self) -> list[str]:
        """Get reasons for each failed layer."""
        reasons = []
        for layer in [
            self.result.layer1,
            self.result.layer2,
            self.result.layer3,
            self.result.layer4,
        ]:
            if not layer.passed and layer.reason:
                reasons.append(f"{layer.layer}: {layer.reason}")  # noqa: PERF401
        return reasons


class GovernanceDeliberationEngine(DeliberationEngine):
    """
    Governance-wrapped DeliberationEngine that enforces zero-trust validation.

    This class is a subclass of DeliberationEngine that intercepts deliberation
    inputs and validates them through the GovernanceCoordinator before they are
    recorded or processed.

    On validation failure:
      - The security event is logged
      - A GovernanceSecurityError is raised
      - The input is NOT recorded

    Attributes:
        _governance: The GovernanceCoordinator instance for zero-trust validation
    """

    def __init__(
        self,
        governance: GovernanceCoordinator | None = None,
        config=None,  # DeliberationConfig | None — deliberately untyped to avoid circular import
        expertise_profiler=None,
    ) -> None:
        """
        Initialize the governance-wrapped deliberation engine.

        Args:
            governance: Optional GovernanceCoordinator instance.
                      If not provided, creates a default coordinator.
            config: Deliberation configuration (passed to parent)
            expertise_profiler: Optional expertise profiler (passed to parent)
        """
        # Initialize parent class
        super().__init__(config=config, expertise_profiler=expertise_profiler)
        # Attach governance coordinator
        self._governance = governance or GovernanceCoordinator()

    def _run_async(self, coro) -> Any:
        """
        Run an async coroutine from a synchronous method.

        Detects whether we are already inside an async context and uses the
        appropriate runner to avoid 'asyncio.run() cannot be called from a
        running event loop' errors.

        Args:
            coro: An awaitable coroutine

        Returns:
            The result of the coroutine
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — create a new one
            return asyncio.run(coro)
        else:
            if loop.is_running():
                # Loop is already running — execute in a separate thread with its own loop
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            else:
                # Loop exists but is not running — safe to use run_until_complete
                return loop.run_until_complete(coro)

    # -------------------------------------------------------------------------
    # Governance-wrapped deliberation inputs
    # -------------------------------------------------------------------------

    def submit_argument(
        self,
        deliberation_id: str,
        agent_id: str,
        position: Position,
        reasoning: str,
        evidence_refs: list[str] | None = None,
        confidence: float = 0.5,
        argument_type: ArgumentType = ArgumentType.PRIMARY,
        supports: list[str] | None = None,
        rebuttals: list[str] | None = None,
        agent_identity: AgentIdentity | None = None,
    ) -> str | None:
        """
        Submit an argument to deliberation with governance validation.

        Validates the argument through the GovernanceCoordinator before it is
        recorded. On validation failure, raises GovernanceSecurityError.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent submitting argument
            position: Position (for/against/neutral)
            reasoning: Argument reasoning
            evidence_refs: References to supporting evidence
            confidence: Confidence in argument
            argument_type: Type of argument
            supports: IDs of arguments this supports
            rebuttals: IDs of arguments this rebuts
            agent_identity: Optional AgentIdentity for governance validation.
                          If not provided, a default observer identity is created.

        Returns:
            Argument ID if accepted and validated, None if deliberation not found

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        # Build agent identity if not provided
        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id=agent_id,
                role=AgentRole.OBSERVER,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        # Prepare input data for governance validation
        input_data = {
            "deliberation_id": deliberation_id,
            "agent_id": agent_id,
            "position": position.value,
            "reasoning_length": len(reasoning),
            "evidence_ref_count": len(evidence_refs) if evidence_refs else 0,
            "confidence": confidence,
            "argument_type": argument_type.value,
        }

        # Validate through zero-trust governance
        logger.info(
            "governance_validation_started",
            event_type="submit_argument",
            agent_id=agent_id,
            deliberation_id=deliberation_id,
        )

        result = self._run_async(
            self._governance.validate_deliberation_input(
                input_data=input_data,
                agent_identity=agent_identity,
            )
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="submit_argument",
                agent_id=agent_id,
                deliberation_id=deliberation_id,
                request_id=result.request_id,
                failed_layers=[
                    lr.layer
                    for lr in [result.layer1, result.layer2, result.layer3, result.layer4]
                    if not lr.passed
                ],
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for argument by {agent_id} "
                f"in deliberation {deliberation_id}",
                result=result,
            )

        logger.debug(
            "governance_validation_passed",
            event_type="submit_argument",
            agent_id=agent_id,
            deliberation_id=deliberation_id,
            request_id=result.request_id,
        )

        # Validation passed — delegate to parent
        return super().submit_argument(
            deliberation_id=deliberation_id,
            agent_id=agent_id,
            position=position,
            reasoning=reasoning,
            evidence_refs=evidence_refs,
            confidence=confidence,
            argument_type=argument_type,
            supports=supports,
            rebuttals=rebuttals,
        )

    def submit_counter_argument(
        self,
        deliberation_id: str,
        agent_id: str,
        original_argument_id: str,
        counter_reasoning: str,
        evidence_refs: list[str] | None = None,
        confidence: float = 0.5,
        agent_identity: AgentIdentity | None = None,
    ) -> str | None:
        """
        Submit a counter-argument with governance validation.

        Validates the counter-argument through GovernanceCoordinator before it
        is recorded. On validation failure, raises GovernanceSecurityError.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent submitting counter-argument
            original_argument_id: ID of argument being countered
            counter_reasoning: Counter-argument reasoning
            evidence_refs: References to supporting evidence
            confidence: Confidence in counter-argument
            agent_identity: Optional AgentIdentity for governance validation.

        Returns:
            Counter-argument ID if accepted and validated, None if not found

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id=agent_id,
                role=AgentRole.OBSERVER,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        input_data = {
            "deliberation_id": deliberation_id,
            "agent_id": agent_id,
            "original_argument_id": original_argument_id,
            "counter_reasoning_length": len(counter_reasoning),
            "evidence_ref_count": len(evidence_refs) if evidence_refs else 0,
            "confidence": confidence,
        }

        result = self._run_async(
            self._governance.validate_deliberation_input(
                input_data=input_data,
                agent_identity=agent_identity,
            )
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="submit_counter_argument",
                agent_id=agent_id,
                deliberation_id=deliberation_id,
                request_id=result.request_id,
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for counter-argument by {agent_id}",
                result=result,
            )

        return super().submit_counter_argument(
            deliberation_id=deliberation_id,
            agent_id=agent_id,
            original_argument_id=original_argument_id,
            counter_reasoning=counter_reasoning,
            evidence_refs=evidence_refs,
            confidence=confidence,
        )

    def submit_evidence(
        self,
        deliberation_id: str,
        evidence_type: EvidenceType,
        content: str,
        source: str | None = None,
        reliability_score: float = 0.5,
        submitted_by: str = "",
        agent_identity: AgentIdentity | None = None,
    ) -> str | None:
        """
        Submit evidence to deliberation with governance validation.

        Args:
            deliberation_id: Deliberation identifier
            evidence_type: Type of evidence
            content: Evidence content
            source: Evidence source
            reliability_score: Reliability rating
            submitted_by: Agent submitting evidence
            agent_identity: Optional AgentIdentity for governance validation.

        Returns:
            Evidence ID if accepted and validated, None if deliberation not found

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id=submitted_by or "anonymous",
                role=AgentRole.OBSERVER,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        input_data = {
            "deliberation_id": deliberation_id,
            "submitted_by": submitted_by,
            "evidence_type": evidence_type.value,
            "content_length": len(content),
            "has_source": source is not None,
            "reliability_score": reliability_score,
        }

        result = self._run_async(
            self._governance.validate_deliberation_input(
                input_data=input_data,
                agent_identity=agent_identity,
            )
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="submit_evidence",
                submitted_by=submitted_by,
                deliberation_id=deliberation_id,
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for evidence submitted by {submitted_by}",
                result=result,
            )

        return super().submit_evidence(
            deliberation_id=deliberation_id,
            evidence_type=evidence_type,
            content=content,
            source=source,
            reliability_score=reliability_score,
            submitted_by=submitted_by,
        )

    # -------------------------------------------------------------------------
    # Governance-wrapped deliberation execution
    # -------------------------------------------------------------------------

    def run_deliberation(
        self,
        deliberation_id: str,
        agent_identity: AgentIdentity | None = None,
    ) -> DeliberationResult | None:
        """
        Run the full deliberation process with governance validation.

        Validates that deliberation execution is authorized before proceeding.

        Args:
            deliberation_id: Deliberation identifier
            agent_identity: Optional AgentIdentity of the agent triggering execution.

        Returns:
            Deliberation result or None if deliberation not found

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        if deliberation_id not in self.active_deliberations:
            return None

        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id="governance:deliberation_runner",
                role=AgentRole.GOVERNANCE,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        data = self.active_deliberations[deliberation_id]
        input_data = {
            "deliberation_id": deliberation_id,
            "topic": data["topic"],
            "participant_count": len(data["participants"]),
            "current_round": self.current_rounds.get(deliberation_id, 0),
            "action": "run_deliberation",
        }

        result = self._run_async(
            self._governance.validate_deliberation_input(
                input_data=input_data,
                agent_identity=agent_identity,
            )
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="run_deliberation",
                deliberation_id=deliberation_id,
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for deliberation execution {deliberation_id}",  # noqa: E501
                result=result,
            )

        # Run deliberation rounds until complete
        max_rounds = self.config.max_rounds if self.config else 5
        for _ in range(max_rounds):
            state = self.deliberation_states.get(deliberation_id, "")
            if state == "completed":
                break
            round_result = self.run_deliberation_round(deliberation_id)
            if round_result is None:
                break
            if round_result.outcome.value in ("consensus", "majority", "deadlock"):
                break

        return self.finalize_deliberation(deliberation_id)

    def run_deliberation_round(
        self,
        deliberation_id: str,
        agent_identity: AgentIdentity | None = None,
    ) -> DeliberationRound | None:
        """
        Run a single deliberation round with governance validation.

        Args:
            deliberation_id: Deliberation identifier
            agent_identity: Optional AgentIdentity of the agent triggering the round.

        Returns:
            Round result or None if deliberation not found

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        if deliberation_id not in self.active_deliberations:
            return None

        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id="governance:round_runner",
                role=AgentRole.GOVERNANCE,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        input_data = {
            "deliberation_id": deliberation_id,
            "current_round": self.current_rounds.get(deliberation_id, 0),
            "action": "run_deliberation_round",
        }

        result = self._run_async(
            self._governance.validate_deliberation_input(
                input_data=input_data,
                agent_identity=agent_identity,
            )
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="run_deliberation_round",
                deliberation_id=deliberation_id,
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for round execution in {deliberation_id}",
                result=result,
            )

        return super().run_deliberation_round(deliberation_id)

    def finalize_deliberation(
        self,
        deliberation_id: str,
        agent_identity: AgentIdentity | None = None,
    ) -> DeliberationResult | None:
        """
        Finalize deliberation with governance validation.

        Args:
            deliberation_id: Deliberation identifier
            agent_identity: Optional AgentIdentity of the agent triggering finalization.

        Returns:
            Final deliberation result or None

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        if deliberation_id not in self.active_deliberations:
            return None

        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id="governance:finalizer",
                role=AgentRole.GOVERNANCE,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        input_data = {
            "deliberation_id": deliberation_id,
            "action": "finalize_deliberation",
        }

        result = self._run_async(
            self._governance.validate_deliberation_input(
                input_data=input_data,
                agent_identity=agent_identity,
            )
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="finalize_deliberation",
                deliberation_id=deliberation_id,
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for finalization of {deliberation_id}",
                result=result,
            )

        return super().finalize_deliberation(deliberation_id)

    # -------------------------------------------------------------------------
    # Governance status inspection
    # -------------------------------------------------------------------------

    def get_governance_status(self) -> dict[str, Any]:
        """
        Get governance validation status and metrics.

        Returns:
            Dictionary with validation_count, failed_validations, event_counts,
            high_severity_events, and validator_metrics.
        """
        return self._governance.get_governance_status()
