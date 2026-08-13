"""
Agent Identity Module for Governance

Provides agent identity models and role-based access control for the governance layer.
"""

from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)


class AgentRole(StrEnum):
    """
    Enumeration of agent roles within the governance system.

    Roles define the hierarchy of trust and capability within the swarm governance:
    - STEWARD: Highest privilege role for critical governance decisions
    - GOVERNANCE: Role for governance-level decision making
    - OPERATOR: Standard operational role with moderate trust
    - OBSERVER: Read-only role with no decision-making authority
    """

    STEWARD = "steward"
    GOVERNANCE = "governance"
    OPERATOR = "operator"
    OBSERVER = "observer"


class TrustLevel(StrEnum):
    """
    Enumeration of trust levels for agents.

    Trust levels determine the validation requirements for agent actions:
    - ZERO_TRUST: No inherent trust, requires full validation
    - LOW: Minimal trust, basic validation required
    - MEDIUM: Moderate trust, standard validation
    - HIGH: High trust, minimal validation required
    - FULLY_TRUSTED: Complete trust, validation bypassed
    """

    ZERO_TRUST = "zero_trust"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FULLY_TRUSTED = "fully_trusted"


class AgentIdentity(BaseModel):
    """
    Represents an agent's identity within the governance system.

    This model captures the essential identity attributes needed for
    governance decisions and zero-trust validation.

    Attributes:
        agent_id: Unique identifier for the agent (UUID v4)
        role: The agent's governance role
        trust_level: The agent's current trust level
        capabilities: Set of capabilities this agent possesses
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    agent_id: str = Field(
        ...,
        description="Unique agent identifier (UUID v4)",
        min_length=1,
    )
    role: AgentRole = Field(
        default=AgentRole.OBSERVER,
        description="Agent's governance role",
    )
    trust_level: TrustLevel = Field(
        default=TrustLevel.ZERO_TRUST,
        description="Agent's current trust level",
    )
    capabilities: set[str] = Field(
        default_factory=set,
        description="Set of capability identifiers this agent possesses",
    )

    def has_capability(self, capability: str) -> bool:
        """Check if the agent has a specific capability."""
        return capability in self.capabilities

    def has_any_capability(self, capabilities: list[str]) -> bool:
        """Check if the agent has any of the specified capabilities."""
        return bool(set(capabilities) & self.capabilities)

    def has_all_capabilities(self, capabilities: list[str]) -> bool:
        """Check if the agent has all of the specified capabilities."""
        return set(capabilities).issubset(self.capabilities)

    def can_assume_role(self, required_role: AgentRole) -> bool:
        """Check if the agent can assume a role based on their current role hierarchy."""
        role_hierarchy = {
            AgentRole.STEWARD: 4,
            AgentRole.GOVERNANCE: 3,
            AgentRole.OPERATOR: 2,
            AgentRole.OBSERVER: 1,
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 0)

    def requires_validation(self) -> bool:
        """Check if the agent requires zero-trust validation based on trust level."""
        return self.trust_level in (TrustLevel.ZERO_TRUST, TrustLevel.LOW, TrustLevel.MEDIUM)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "trust_level": self.trust_level.value,
            "capabilities": sorted(self.capabilities),
        }
