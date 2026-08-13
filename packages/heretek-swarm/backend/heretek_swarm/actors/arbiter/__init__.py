"""
Arbiter subpackage - Split module for arbiter agent.

Modules:
- agent: Core arbitration logic, conflict detection, enums, dataclasses
- handlers: Event handlers and responses
- strategies: Resolution strategies
- constants: Constants for the arbiter
"""

from .agent import (
    ArbiterAgent,
    ArbitrationReport,
    Conflict,
    ConflictSeverity,
    ConflictType,
    Relationship,
    ResolutionStatus,
    ResolutionStrategy,
)

# Alias for backwards compatibility
ArbitrationStrategy = ResolutionStrategy

__all__ = [
    "ArbiterAgent",
    "ArbitrationReport",
    "ArbitrationStrategy",
    "Conflict",
    "ConflictSeverity",
    "ConflictType",
    "Relationship",
    "ResolutionStatus",
    "ResolutionStrategy",
]
