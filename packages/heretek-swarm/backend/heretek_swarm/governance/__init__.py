"""
Governance Module for Heretek Swarm

Provides zero-trust governance validation at agent action and collective
decision boundaries. The governance layer ensures that all agent actions
and collective decisions are validated according to defined protocols.

Key Components:
- AgentIdentity: Represents agent identity with role and trust level
- GovernanceProtocol: Defines validation requirements for specific actions
- GovernanceCoordinator: Coordinates governance validation using zero-trust
- GovernanceSecurityError: Exception for failed validations

Reference: EXPANSION_ROADMAP.md SH-1 Enhanced Zero-Trust Governance
"""

import structlog

from heretek_swarm.governance.agent_identity import (
    AgentIdentity,
    AgentRole,
    TrustLevel,
)
from heretek_swarm.governance.coordinator import (
    GovernanceCoordinator,
    GovernanceSecurityError,
)
from heretek_swarm.governance.protocol import (
    GovernanceContext,
    GovernanceProtocol,
    ValidationStatus,
)
from heretek_swarm_core.security.zero_trust import (
    ZeroTrustValidator,
    create_default_validator,
)

logger = structlog.get_logger(__name__)

__all__ = [
    # Agent Identity
    "AgentIdentity",
    "AgentRole",
    # Protocol
    "GovernanceContext",
    # Coordinator
    "GovernanceCoordinator",
    "GovernanceProtocol",
    "GovernanceSecurityError",
    "TrustLevel",
    "ValidationStatus",
    # Zero-trust integration
    "ZeroTrustValidator",
    "create_default_validator",
]


def create_coordinator(
    validator: ZeroTrustValidator | None = None,
) -> GovernanceCoordinator:
    """
    Factory function to create a GovernanceCoordinator.

    Args:
        validator: Optional ZeroTrustValidator instance.
                  If not provided, creates a default validator.

    Returns:
        Configured GovernanceCoordinator instance.
    """
    return GovernanceCoordinator(validator=validator)


# ---------------------------------------------------------------------------
# Governance-wrapped integrations (lazy imports to avoid circular dependencies)
# ---------------------------------------------------------------------------


def GovernanceAgentSociety(*args, **kwargs) -> "GovernanceAgentSociety":  # type: ignore[name-defined]
    """
    Governance-wrapped AgentSociety that enforces zero-trust validation.

    Import from heretek_swarm.governance.integrations for direct usage.

    Returns:
        GovernanceAgentSociety subclass instance with governance enforcement.
    """
    from heretek_swarm.governance.integrations.collective_governance import (
        GovernanceAgentSociety as GCS,
    )

    return GCS(*args, **kwargs)


def GovernanceDeliberationEngine(*args, **kwargs) -> "GovernanceDeliberationEngine":  # type: ignore[name-defined]
    """
    Governance-wrapped DeliberationEngine that enforces zero-trust validation.

    Import from heretek_swarm.governance.integrations for direct usage.

    Returns:
        GovernanceDeliberationEngine subclass instance with governance enforcement.
    """
    from heretek_swarm.governance.integrations.consensus_governance import (
        GovernanceDeliberationEngine as GDE,
    )

    return GDE(*args, **kwargs)
