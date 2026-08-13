"""Collective algorithms module.

Contains bio-inspired swarm intelligence algorithms:
- ACO: Ant Colony Optimization
- PSO: Particle Swarm Optimization
- ABC: Artificial Bee Colony
"""

from heretek_swarm.collective.algorithms.abc import ABC, BeeAgent
from heretek_swarm.collective.algorithms.abc import SwarmDecision as ABCSwarmDecision
from heretek_swarm.collective.algorithms.aco import ACO, PheromoneTrail
from heretek_swarm.collective.algorithms.aco import SwarmDecision as ACOSwarmDecision
from heretek_swarm.collective.algorithms.pso import (
    PSO,
    Particle,
    SwarmPattern,
)
from heretek_swarm.collective.algorithms.pso import (
    SwarmDecision as PSOSwarmDecision,
)

__all__ = [
    "ABC",
    "ACO",
    "PSO",
    "ABCSwarmDecision",
    "ACOSwarmDecision",
    "BeeAgent",
    "PSOSwarmDecision",
    "Particle",
    "PheromoneTrail",
    "SwarmPattern",
]
