"""
Governance Integrations Module

Provides governance-wrapped versions of AgentSociety and DeliberationEngine
that enforce zero-trust validation at agent action and collective decision boundaries.

These classes are designed to be drop-in replacements for their base classes
when governance enforcement is required.
"""

from heretek_swarm.governance.integrations.collective_governance import (
    GovernanceAgentSociety,
    GovernanceSecurityError,
)
from heretek_swarm.governance.integrations.consensus_governance import (
    GovernanceDeliberationEngine,
)

__all__ = [
    "GovernanceAgentSociety",
    "GovernanceDeliberationEngine",
    "GovernanceSecurityError",
]
