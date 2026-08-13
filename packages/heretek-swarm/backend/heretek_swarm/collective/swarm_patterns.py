"""
Shared enum types for swarm intelligence patterns.

This module defines shared enums used across swarm intelligence
algorithm implementations to ensure consistent type comparisons.
"""

from enum import Enum


class SwarmPattern(Enum):
    """Swarm intelligence pattern types."""

    PSO = "particle_swarm_optimization"
    ANT_COLONY = "ant_colony_optimization"
    BEE_ALGORITHM = "bee_algorithm"
    FLOCKING = "flocking_behavior"
    STIGMERGY = "stigmergy_indirect_coordination"


class FlockingRule(Enum):
    """Flocking behavior rules."""

    SEPARATION = "separation"
    ALIGNMENT = "alignment"
    COHESION = "cohesion"
