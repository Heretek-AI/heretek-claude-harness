"""
Particle Swarm Optimization implementation.

Uses random module for simulation purposes only.
Not used for security-critical operations (IDs use uuid, not random).
"""

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from heretek_swarm.collective.swarm_patterns import SwarmPattern

logger = structlog.get_logger("PSO")

# PSO Constants (algorithm thresholds)
PSO_INERTIA_DEFAULT = 0.7
PSO_COGNITIVE_DEFAULT = 1.5
PSO_SOCIAL_DEFAULT = 1.5
PSO_INITIAL_POSITION_VARIANCE = 0.1
PSO_INITIAL_VELOCITY_RANGE = 0.01
PSO_VELOCITY_CLAMP_MIN = -0.5
PSO_VELOCITY_CLAMP_MAX = 0.5
PSO_CONVERGENCE_THRESHOLD_DEFAULT = 0.95
PSO_STRONG_CONSENSUS_THRESHOLD = 0.8
PSO_HIGH_CLUSTERING_THRESHOLD = 0.2
PSO_EXPLORATORY_BEHAVIOR_THRESHOLD = 0.8
PSO_MIN_CONVERGENCE_ITERATIONS = 5
PSO_CONVERGENCE_HISTORY_LENGTH = 5


@dataclass
class Particle:
    """
    Particle in PSO algorithm.

    Attributes:
        particle_id: Unique identifier
        position: Current position in search space
        velocity: Current velocity vector
        best_position: Best position found by this particle
        best_value: Best fitness value found
        agent_id: Associated agent ID
    """

    particle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position: dict[str, float] = field(default_factory=dict)
    velocity: dict[str, float] = field(default_factory=dict)
    best_position: dict[str, float] = field(default_factory=dict)
    best_value: float = float("-inf")
    agent_id: str = ""


@dataclass
class SwarmDecision:
    """
    Result of a swarm intelligence decision process.

    Attributes:
        pattern: Swarm pattern used
        participants: Participating agents
        convergence_iterations: Iterations to converge
        final_position: Final decision position
        confidence: Decision confidence
        emergence_indicators: Indicators of emergent behavior
        quality_metrics: Quality metrics for the decision
    """

    pattern: SwarmPattern = SwarmPattern.PSO
    participants: list[str] = field(default_factory=list)
    convergence_iterations: int = 0
    final_position: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    emergence_indicators: list[str] = field(default_factory=list)
    quality_metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: "")
    # Skipping timestamp import for dataclass


class PSO:
    """Particle Swarm Optimization algorithm."""

    def __init__(
        self,
        inertia: float = PSO_INERTIA_DEFAULT,
        cognitive: float = PSO_COGNITIVE_DEFAULT,
        social: float = PSO_SOCIAL_DEFAULT,
        convergence_threshold: float = PSO_CONVERGENCE_THRESHOLD_DEFAULT,
    ) -> None:
        """
        Initialize PSO algorithm.

        Args:
            inertia: Inertia weight
            cognitive: Cognitive coefficient
            social: Social coefficient
            convergence_threshold: Threshold for convergence
        """
        self.inertia = inertia
        self.cognitive = cognitive
        self.social = social
        self.convergence_threshold = convergence_threshold

        self.particles: dict[str, Particle] = {}
        self.global_best_position: dict[str, float] = {}
        self.global_best_value: float = float("-inf")
        self.decision_history: list[SwarmDecision] = []

    def run(
        self,
        participants: list[str],
        decision_space: dict[str, float],
        fitness_function: Callable[[dict[str, float]], float] | None = None,
        iterations: int = 100,
    ) -> SwarmDecision:
        """
        Run Particle Swarm Optimization for decision convergence.

        Args:
            participants: List of participating agent IDs
            decision_space: Initial decision space with options and weights
            fitness_function: Function to evaluate solution quality
            iterations: Number of iterations

        Returns:
            Swarm decision with converged result
        """
        self._initialize_particles(participants, decision_space)

        for iteration in range(iterations):
            for particle in self.particles.values():
                self._update_velocity(particle)
                self._update_position(particle)
                fitness = self._evaluate_fitness(particle.position, fitness_function)

                if fitness > particle.best_value:
                    particle.best_value = fitness
                    particle.best_position = particle.position.copy()

                if fitness > self.global_best_value:
                    self.global_best_value = fitness
                    self.global_best_position = particle.position.copy()

            if self._check_convergence(iteration):
                logger.info("PSO converged at iteration {iteration}")
                break

        decision = SwarmDecision(
            pattern=SwarmPattern.PSO,
            participants=participants,
            convergence_iterations=iteration + 1,
            final_position=self.global_best_position.copy(),
            confidence=self.global_best_value,
            emergence_indicators=self._detect_emergence(),
            quality_metrics={
                "convergence_rate": (iteration + 1) / iterations,
                "final_fitness": self.global_best_value,
                "particle_diversity": self._calculate_diversity(),
            },
        )

        self.decision_history.append(decision)
        return decision

    def _initialize_particles(
        self,
        participants: list[str],
        decision_space: dict[str, float],
    ) -> None:
        """Initialize PSO particles from participants."""
        self.particles.clear()
        self.global_best_position = {}
        self.global_best_value = float("-inf")

        for i, agent_id in enumerate(participants):
            position = {}
            for key, weight in decision_space.items():
                position[key] = weight + random.uniform(
                    -PSO_INITIAL_POSITION_VARIANCE, PSO_INITIAL_POSITION_VARIANCE
                )

            total = sum(position.values())
            if total > 0:
                position = {k: v / total for k, v in position.items()}

            velocity = {
                k: random.uniform(-PSO_INITIAL_VELOCITY_RANGE, PSO_INITIAL_VELOCITY_RANGE)
                for k in position
            }

            particle = Particle(
                particle_id=f"particle-{i}",
                position=position,
                velocity=velocity,
                best_position=position.copy(),
                agent_id=agent_id,
            )
            self.particles[particle.particle_id] = particle

    def _update_velocity(self, particle: Particle) -> None:
        """Update particle velocity using PSO equations."""
        for key in particle.position:
            cognitive = (
                self.cognitive
                * random.random()
                * (particle.best_position.get(key, 0) - particle.position[key])
            )
            social = (
                self.social
                * random.random()
                * (self.global_best_position.get(key, 0) - particle.position[key])
            )

            particle.velocity[key] = (
                self.inertia * particle.velocity.get(key, 0) + cognitive + social
            )
            particle.velocity[key] = max(
                PSO_VELOCITY_CLAMP_MIN, min(PSO_VELOCITY_CLAMP_MAX, particle.velocity[key])
            )

    def _update_position(self, particle: Particle) -> None:
        """Update particle position based on velocity."""
        for key in particle.position:
            particle.position[key] += particle.velocity.get(key, 0)

        total = sum(particle.position.values())
        if total > 0:
            particle.position = {k: v / total for k, v in particle.position.items()}

    def _evaluate_fitness(
        self,
        position: dict[str, float],
        fitness_function: Callable[[dict[str, float]], float] | None = None,
    ) -> float:
        """Evaluate fitness of a position."""
        if fitness_function:
            return fitness_function(position)
        return sum(position.values())

    def _check_convergence(self, iteration: int) -> bool:
        """Check if PSO has converged."""
        if iteration < PSO_MIN_CONVERGENCE_ITERATIONS:
            return False
        return self.global_best_value >= self.convergence_threshold

    def _detect_emergence(self) -> list[str]:
        """Detect emergence indicators in PSO."""
        indicators = []
        if self.global_best_value >= PSO_STRONG_CONSENSUS_THRESHOLD:
            indicators.append("strong_consensus")

        diversity = self._calculate_diversity()
        if diversity < PSO_HIGH_CLUSTERING_THRESHOLD:
            indicators.append("high_clustering")
        elif diversity > PSO_EXPLORATORY_BEHAVIOR_THRESHOLD:
            indicators.append("exploratory_behavior")

        return indicators

    def _calculate_diversity(self) -> float:
        """Calculate diversity of particle positions."""
        if not self.particles:
            return 0.0

        positions = [p.position for p in self.particles.values()]
        if not positions:
            return 0.0

        all_keys = set()
        for pos in positions:
            all_keys.update(pos.keys())

        variance_sum = 0.0
        for key in all_keys:
            values = [pos.get(key, 0) for pos in positions]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            variance_sum += variance

        return variance_sum / len(all_keys) if all_keys else 0.0
