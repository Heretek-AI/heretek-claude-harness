"""
Governance Protocol Module

Defines governance protocols and context for zero-trust validation.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from heretek_swarm.governance.agent_identity import AgentIdentity


class ValidationStatus(StrEnum):
    """Status of a governance validation."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class GovernanceProtocol:
    """
    Defines a governance protocol for validating agent actions.

    Protocols specify the requirements for validating specific types of
    governance decisions or actions.

    Attributes:
        protocol_id: Unique identifier for the protocol
        name: Human-readable name for the protocol
        description: Detailed description of the protocol's purpose
        required_roles: Set of roles that are allowed to execute this protocol
        zero_trust_required: Whether zero-trust validation is required
        max_deliberation_rounds: Maximum rounds for deliberation (0 = none)
    """

    protocol_id: str
    name: str
    description: str
    required_roles: set[str] = field(default_factory=set)
    zero_trust_required: bool = True
    max_deliberation_rounds: int = 0

    def validate_role_access(self, agent_role: str) -> bool:
        """Check if a role has access to this protocol."""
        if not self.required_roles:
            return True
        return agent_role in self.required_roles

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "protocol_id": self.protocol_id,
            "name": self.name,
            "description": self.description,
            "required_roles": sorted(self.required_roles),
            "zero_trust_required": self.zero_trust_required,
            "max_deliberation_rounds": self.max_deliberation_rounds,
        }


@dataclass
class GovernanceContext:
    """
    Context for a governance validation request.

    This dataclass carries all the information needed to perform
    governance validation including the agent identity, protocol,
    and validation state.

    Attributes:
        agent_identity: The identity of the agent requesting validation
        protocol: The governance protocol to validate against
        request_id: Unique identifier for this request
        timestamp: When the request was created
        validation_result: Result of the validation (if completed)
    """

    agent_identity: AgentIdentity
    protocol: GovernanceProtocol
    request_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    validation_result: ValidationStatus = ValidationStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_identity": self.agent_identity.to_dict(),
            "protocol": self.protocol.to_dict(),
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "validation_result": self.validation_result.value,
        }
