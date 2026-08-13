"""
Governance Collective Integration

Provides GovernanceAgentSociety — a governance-wrapped subclass of AgentSociety
that enforces zero-trust validation on agent actions before execution.

Key principle: Validation runs BEFORE the action. On validation failure,
a GovernanceSecurityError is raised and the action is not executed.
"""

from typing import Any

import structlog

from heretek_swarm.collective.society import (
    AgentContribution,
    AgentSociety,
    CollectiveResult,
    CollectiveTask,
)
from heretek_swarm.governance.agent_identity import AgentIdentity, AgentRole, TrustLevel
from heretek_swarm.governance.coordinator import GovernanceCoordinator, GovernanceSecurityError
from heretek_swarm.governance.protocol import GovernanceProtocol

logger = structlog.get_logger(__name__)


class GovernanceAgentSociety(AgentSociety):
    """
    Governance-wrapped AgentSociety that enforces zero-trust validation.

    This class is a subclass of AgentSociety that intercepts agent actions
    and validates them through the GovernanceCoordinator before execution.

    On validation failure:
      - The security event is logged
      - A GovernanceSecurityError is raised
      - The action is NOT executed

    Attributes:
        _governance: The GovernanceCoordinator instance for zero-trust validation
    """

    def __init__(
        self,
        governance: GovernanceCoordinator | None = None,
        supervisor=None,
        contribution_cache_ttl: int = 300,
        enable_swarm_intelligence: bool = True,
        exploration_mode: bool = False,
    ) -> None:
        """
        Initialize the governance-wrapped agent society.

        Args:
            governance: Optional GovernanceCoordinator instance.
                      If not provided, creates a default coordinator.
            supervisor: ActorSupervisor for agent management (passed to parent)
            contribution_cache_ttl: TTL for contribution cache (passed to parent)
            enable_swarm_intelligence: Enable swarm intelligence (passed to parent)
            exploration_mode: Enable exploration mode (passed to parent)
        """
        # Initialize parent class WITHOUT governance-specific params
        super().__init__(
            supervisor=supervisor,
            contribution_cache_ttl=contribution_cache_ttl,
            enable_swarm_intelligence=enable_swarm_intelligence,
            exploration_mode=exploration_mode,
        )
        # Attach governance coordinator
        self._governance = governance or GovernanceCoordinator()

    # -------------------------------------------------------------------------
    # Governance-wrapped task coordination
    # -------------------------------------------------------------------------

    async def coordinate_task(
        self,
        task: CollectiveTask,
        agent_identity: AgentIdentity | None = None,
        protocol: GovernanceProtocol | None = None,
    ) -> CollectiveResult:
        """
        Coordinate a collective task with governance validation.

        Validates the task through the GovernanceCoordinator before execution.
        On validation failure, raises GovernanceSecurityError and does NOT
        execute the task.

        Args:
            task: The collective task to coordinate
            agent_identity: The identity of the agent initiating the task
            protocol: The governance protocol to validate against

        Returns:
            CollectiveResult with task outcome

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        # Build agent identity if not provided — use default observer identity
        if agent_identity is None:
            agent_identity = AgentIdentity(
                agent_id="governance:anonymous",
                role=AgentRole.OBSERVER,
                trust_level=TrustLevel.ZERO_TRUST,
            )

        # Build protocol if not provided — use default collective action protocol
        if protocol is None:
            protocol = GovernanceProtocol(
                protocol_id="collective:coordinate_task",
                name="Collective Task Coordination",
                description="Governance protocol for collective task coordination",
                required_roles={},
                zero_trust_required=True,
            )

        # Prepare action data for validation
        action_data = {
            "task_id": task.id,
            "task_type": task.type.value if hasattr(task.type, "value") else str(task.type),
            "task_description": task.description,
            "priority": task.priority,
            "input_data_keys": list(task.input_data.keys()),
        }

        # Validate through zero-trust governance
        logger.info(
            "governance_validation_started",
            event_type="collective_task",
            agent_id=agent_identity.agent_id,
            protocol_id=protocol.protocol_id,
        )

        result = await self._governance.validate_governance_action(
            agent_identity=agent_identity,
            action_data=action_data,
            protocol=protocol,
        )

        if not result.passed:
            # Log security event
            failed_layers = [
                lr.layer
                for lr in [
                    result.layer1,
                    result.layer2,
                    result.layer3,
                    result.layer4,
                ]
                if not lr.passed
            ]
            logger.error(
                "governance_validation_failed",
                event_type="collective_task",
                agent_id=agent_identity.agent_id,
                protocol_id=protocol.protocol_id,
                request_id=result.request_id,
                failed_layers=failed_layers,
            )
            raise GovernanceSecurityError(
                message=(
                    f"Governance validation failed for collective task {task.id}:  {failed_layers}"
                ),
                result=result,
            )

        # Validation passed — execute the task via parent
        logger.debug(
            "governance_validation_passed",
            event_type="collective_task",
            agent_id=agent_identity.agent_id,
            request_id=result.request_id,
        )

        return await super().coordinate_task(task)

    # -------------------------------------------------------------------------
    # Governance-wrapped contribution submission
    # -------------------------------------------------------------------------

    async def submit_contribution(
        self,
        agent_identity: AgentIdentity,
        task: CollectiveTask,
        contribution_data: dict[str, Any],
        protocol: GovernanceProtocol | None = None,
    ) -> AgentContribution:
        """
        Submit a contribution with governance validation.

        Validates the contribution through the GovernanceCoordinator before
        it is recorded. On validation failure, raises GovernanceSecurityError.

        Args:
            agent_identity: The identity of the contributing agent
            task: The collective task this contribution addresses
            contribution_data: The contribution data being submitted
            protocol: The governance protocol to validate against

        Returns:
            AgentContribution with the recorded contribution

        Raises:
            GovernanceSecurityError: If governance validation fails
        """
        # Build default protocol if not provided
        if protocol is None:
            protocol = GovernanceProtocol(
                protocol_id="collective:submit_contribution",
                name="Contribution Submission",
                description="Governance protocol for agent contribution submission",
                required_roles={},
                zero_trust_required=True,
            )

        # Prepare action data for validation
        action_data = {
            "agent_id": agent_identity.agent_id,
            "task_id": task.id,
            "contribution_keys": list(contribution_data.keys()),
        }

        # Validate through zero-trust governance
        result = await self._governance.validate_governance_action(
            agent_identity=agent_identity,
            action_data=action_data,
            protocol=protocol,
        )

        if not result.passed:
            logger.error(
                "governance_validation_failed",
                event_type="contribution_submission",
                agent_id=agent_identity.agent_id,
                request_id=result.request_id,
                failed_layers=[
                    lr.layer
                    for lr in [
                        result.layer1,
                        result.layer2,
                        result.layer3,
                        result.layer4,
                    ]
                    if not lr.passed
                ],
            )
            raise GovernanceSecurityError(
                message=f"Governance validation failed for contribution to task {task.id}",
                result=result,
            )

        # Validation passed — create and cache contribution via parent mechanism
        contribution = AgentContribution(
            agent_id=agent_identity.agent_id,
            task_id=task.id,
            contribution=contribution_data,
            confidence=contribution_data.get("confidence", 0.8),
        )

        # Cache the contribution
        self._contribution_cache.set(agent_identity.agent_id, task.id, contribution)

        logger.debug(
            "governance_contribution_accepted",
            agent_id=agent_identity.agent_id,
            task_id=task.id,
            request_id=result.request_id,
        )

        return contribution

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
