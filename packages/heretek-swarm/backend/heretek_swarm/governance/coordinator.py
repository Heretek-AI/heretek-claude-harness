"""
Governance Coordinator Module

Provides the main governance coordinator that enforces zero-trust validation
at agent action and collective decision boundaries.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.governance.agent_identity import AgentIdentity
from heretek_swarm.governance.protocol import (
    GovernanceProtocol,
)
from heretek_swarm_core.security.zero_trust import (
    Severity,
    ZeroTrustResult,
    ZeroTrustValidator,
)

logger = structlog.get_logger(__name__)


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
                failed.append(layer.layer)
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
                reasons.append(f"{layer.layer}: {layer.reason}")
        return reasons


class GovernanceCoordinator:
    """
    Coordinates governance validation for agent actions and collective decisions.

    The coordinator integrates with ZeroTrustValidator to enforce zero-trust
    principles at key decision boundaries:
    - Agent action validation
    - Collective decision validation
    - Deliberation input validation

    Attributes:
        validator: The underlying ZeroTrustValidator for layer validation
        _validation_count: Total number of validations performed
        _failed_validations: Number of failed validations
        _event_counts: Counts of events by type
        _high_severity_events: List of high severity events
    """

    def __init__(
        self,
        validator: ZeroTrustValidator | None = None,
    ):
        """
        Initialize the GovernanceCoordinator.

        Args:
            validator: Optional ZeroTrustValidator instance.
                      If not provided, creates a default validator.
        """
        self.validator = validator or ZeroTrustValidator()
        self._validation_count = 0
        self._failed_validations = 0
        self._event_counts: dict[str, int] = defaultdict(int)
        self._high_severity_events: list[dict[str, Any]] = []

    def _create_request_id(self) -> str:
        """Generate a new UUID v4 request ID."""
        return str(uuid.uuid4())

    def _log_validation(
        self,
        event_type: str,
        result: ZeroTrustResult,
        additional_context: dict[str, Any] | None = None,
    ) -> None:
        """Log a validation event with structured logging."""
        context = additional_context or {}

        # Determine severity
        severity = Severity.INFO
        if not result.passed:
            severity = Severity.WARNING
            if result.layer1.severity in (Severity.HIGH, Severity.CRITICAL):
                severity = result.layer1.severity
            elif result.layer2.severity in (Severity.HIGH, Severity.CRITICAL):
                severity = result.layer2.severity

        # Track event counts
        self._event_counts[event_type] += 1
        self._event_counts[f"{event_type}:{severity.value}"] += 1

        # Store high severity events
        if severity in (Severity.HIGH, Severity.CRITICAL):
            self._high_severity_events.append(
                {
                    "event_type": event_type,
                    "request_id": result.request_id,
                    "agent_id": result.agent_id,
                    "passed": result.passed,
                    "severity": severity.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                    **context,
                }
            )
            # Keep only last 1000 events
            if len(self._high_severity_events) > 1000:
                self._high_severity_events = self._high_severity_events[-1000:]

        # Structured log
        log_method = {
            Severity.INFO: logger.info,
            Severity.WARNING: logger.warning,
            Severity.HIGH: logger.error,
            Severity.CRITICAL: logger.critical,
        }.get(severity, logger.info)

        log_method(
            f"governance_validation_{event_type}",
            event_type=event_type,
            request_id=result.request_id,
            agent_id=result.agent_id,
            passed=result.passed,
            total_latency_ms=result.total_latency_ms,
            severity=severity.value,
            **context,
        )

    async def validate_governance_action(
        self,
        agent_identity: AgentIdentity,
        action_data: dict[str, Any],
        protocol: GovernanceProtocol,
    ) -> ZeroTrustResult:
        """
        Validate an agent's governance action.

        This method validates that an agent is authorized to perform a specific
        action under a given governance protocol.

        Args:
            agent_identity: The identity of the agent attempting the action
            action_data: The data describing the action being performed
            protocol: The governance protocol to validate against

        Returns:
            ZeroTrustResult with validation results

        Raises:
            GovernanceSecurityError: If validation fails and raise_on_failure is True
        """
        request_id = self._create_request_id()

        # Create governance context
        context = {
            "agent_identity": agent_identity.to_dict(),
            "protocol": protocol.to_dict(),
            "action_type": "governance_action",
        }

        # Perform validation through zero-trust validator
        result = await self.validator.validate_request(
            data=action_data,
            context=context,
            agent_id=agent_identity.agent_id,
            request_id=request_id,
        )

        # Update metrics
        self._validation_count += 1
        if not result.passed:
            self._failed_validations += 1

        # Log the event
        self._log_validation(
            event_type="governance_action",
            result=result,
            additional_context={
                "agent_role": agent_identity.role.value,
                "protocol_id": protocol.protocol_id,
            },
        )

        return result

    async def validate_collective_decision(
        self,
        decision_data: dict[str, Any],
        participants: list[AgentIdentity],
        protocol: GovernanceProtocol,
    ) -> ZeroTrustResult:
        """
        Validate a collective decision made by multiple agents.

        This method validates that a collective decision meets governance
        requirements including participant authorization and decision integrity.

        Args:
            decision_data: The data describing the decision being made
            participants: List of agent identities participating in the decision
            protocol: The governance protocol to validate against

        Returns:
            ZeroTrustResult with validation results
        """
        request_id = self._create_request_id()

        # Build participant context
        participant_context = {
            "participant_ids": [p.agent_id for p in participants],
            "participant_roles": [p.role.value for p in participants],
            "participant_count": len(participants),
            "action_type": "collective_decision",
        }

        # Enrich decision data with participant information
        enriched_data = {
            **decision_data,
            "_governance": participant_context,
        }

        # Perform validation
        result = await self.validator.validate_request(
            data=enriched_data,
            context={
                "protocol": protocol.to_dict(),
                **participant_context,
            },
            agent_id=None,  # Collective decisions don't have single agent
            request_id=request_id,
        )

        # Update metrics
        self._validation_count += 1
        if not result.passed:
            self._failed_validations += 1

        # Log the event
        self._log_validation(
            event_type="collective_decision",
            result=result,
            additional_context={
                "protocol_id": protocol.protocol_id,
                "participant_count": len(participants),
            },
        )

        return result

    async def validate_deliberation_input(
        self,
        input_data: dict[str, Any],
        agent_identity: AgentIdentity,
    ) -> ZeroTrustResult:
        """
        Validate input to a deliberation process.

        This method validates that input to a deliberation session meets
        governance requirements for the participating agents.

        Args:
            input_data: The input data being provided to deliberation
            agent_identity: The identity of the agent providing the input

        Returns:
            ZeroTrustResult with validation results
        """
        request_id = self._create_request_id()

        # Create context for deliberation
        context = {
            "agent_identity": agent_identity.to_dict(),
            "agent_role": agent_identity.role.value,
            "agent_trust_level": agent_identity.trust_level.value,
            "action_type": "deliberation_input",
        }

        # Perform validation
        result = await self.validator.validate_request(
            data=input_data,
            context=context,
            agent_id=agent_identity.agent_id,
            request_id=request_id,
        )

        # Update metrics
        self._validation_count += 1
        if not result.passed:
            self._failed_validations += 1

        # Log the event
        self._log_validation(
            event_type="deliberation_input",
            result=result,
            additional_context={
                "agent_role": agent_identity.role.value,
            },
        )

        return result

    def get_governance_status(self) -> dict[str, Any]:
        """
        Get the current governance status and metrics.

        Returns:
            Dictionary containing validation counts, event counts,
            and high severity events.
        """
        return {
            "validation_count": self._validation_count,
            "failed_validations": self._failed_validations,
            "event_counts": dict(self._event_counts),
            "high_severity_events": self._high_severity_events[-100:],
            "validator_metrics": self.validator.get_metrics(),
        }
