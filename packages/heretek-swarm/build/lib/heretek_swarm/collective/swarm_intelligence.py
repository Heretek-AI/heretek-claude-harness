"""
Swarm Intelligence Patterns for Collective Decision Making.

This module implements bio-inspired swarm intelligence patterns:
- Particle Swarm Optimization (PSO) for decision convergence
- Ant Colony Optimization for pathfinding/routing
- Bee Algorithm for task allocation
- Flocking behavior for agent coordination
- Stigmergy for indirect coordination

These patterns enable emergent collective intelligence through simple
local interactions between agents.

Example:
    ```python
    from heretek_swarm.collective.swarm_intelligence import (
        SwarmIntelligenceEngine,
        SwarmPattern,
        SwarmConfig,
    )

    # Initialize engine
    config = SwarmConfig()
    engine = SwarmIntelligenceEngine(config)

    # Run PSO for decision convergence
    result = await engine.run_pso(
        participants=["agent-1", "agent-2", "agent-3"],
        decision_space={"option_a": 0.3, "option_b": 0.7},
        iterations=10
    )

    # Run bee algorithm for task allocation
    allocation = await engine.run_bee_algorithm(
        tasks=["task-1", "task-2", "task-3"],
        foragers=["agent-1", "agent-2"]
    )
    ```
"""

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.collective.algorithms.abc import ABC
from heretek_swarm.collective.algorithms.aco import ACO
from heretek_swarm.collective.algorithms.pso import PSO
from heretek_swarm.collective.swarm_patterns import SwarmPattern

logger = structlog.get_logger("SwarmIntelligenceEngine")


# Flocking Constants (algorithm thresholds)
FLOCK_SEPARATION_THRESHOLD = 5.0
FLOCK_MAX_SPEED = 2.0
FLOCK_COHESION_DISTANCE_DIVISOR = 10.0
FLOCK_TIGHT_THRESHOLD = 0.8
FLOCK_SYNC_THRESHOLD = 0.9
FLOCK_COLLECTIVE_COHESION = 0.7
FLOCK_COLLECTIVE_ALIGNMENT = 0.8

# Stigmergy Constants (algorithm thresholds)
STIGMERGY_SEARCH_RADIUS = 5
STIGMERGY_TRACE_MIN_THRESHOLD = 0.1
STIGMERGY_TRACE_ACCUMULATION_THRESHOLD = 0.1
STIGMERGY_COLLECTIVE_THRESHOLD = 0.3


@dataclass
class FlockingAgent:
    """Agent exhibiting flocking behavior."""

    agent_id: str = ""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    heading: tuple[float, float, float] = (0.0, 0.0, 1.0)
    neighbors: list[str] = field(default_factory=list)


@dataclass
class StigmergicTrace:
    """Trace left by an agent for stigmergic coordination."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    trace_type: str = "marker"
    content: dict[str, Any] = field(default_factory=dict)
    strength: float = 1.0
    decay_rate: float = 0.05
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class SwarmDecision:
    """Result of a swarm intelligence decision process."""

    pattern: SwarmPattern = SwarmPattern.PSO
    participants: list[str] = field(default_factory=list)
    convergence_iterations: int = 0
    final_position: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    emergence_indicators: list[str] = field(default_factory=list)
    quality_metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class SwarmConfig:
    """Configuration for swarm intelligence algorithms."""

    pso_inertia: float = 0.7
    pso_cognitive: float = 1.5
    pso_social: float = 1.5
    ant_evaporation: float = 0.1
    ant_alpha: float = 1.0
    ant_beta: float = 2.0
    bee_scout_ratio: float = 0.2
    bee_dance_threshold: float = 0.7
    flock_separation_weight: float = 1.5
    flock_alignment_weight: float = 1.0
    flock_cohesion_weight: float = 1.0
    flock_perception_radius: float = 10.0
    stigmergy_decay: float = 0.05
    max_iterations: int = 100
    convergence_threshold: float = 0.95


class SwarmIntelligenceEngine:
    """Engine for swarm intelligence patterns."""

    def __init__(self, config: SwarmConfig | None = None) -> None:
        """Initialize swarm intelligence engine."""
        self.config = config or SwarmConfig()

        # Initialize algorithm instances
        self._pso = PSO(
            inertia=self.config.pso_inertia,
            cognitive=self.config.pso_cognitive,
            social=self.config.pso_social,
            convergence_threshold=self.config.convergence_threshold,
        )

        self._aco = ACO(
            evaporation=self.config.ant_evaporation,
            alpha=self.config.ant_alpha,
            beta=self.config.ant_beta,
            convergence_threshold=self.config.convergence_threshold,
        )

        self._abc = ABC(
            scout_ratio=self.config.bee_scout_ratio,
            dance_threshold=self.config.bee_dance_threshold,
            convergence_threshold=self.config.convergence_threshold,
        )

        # Flocking state
        self.flocking_agents: dict[str, FlockingAgent] = {}

        # Stigmergy state
        self.traces: dict[int, list[StigmergicTrace]] = {}

        # Decision history
        self.decision_history: list[SwarmDecision] = []

        logger.info(
            f"SwarmIntelligenceEngine initialized with max_iterations={self.config.max_iterations}"  # noqa: G004
        )

    # =========================================================================
    # Particle Swarm Optimization
    # =========================================================================

    async def run_pso(
        self,
        participants: list[str],
        decision_space: dict[str, float],
        fitness_function: Any | None = None,
        iterations: int | None = None,
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
        iterations = iterations or self.config.max_iterations

        decision = self._pso.run(
            participants=participants,
            decision_space=decision_space,
            fitness_function=fitness_function,
            iterations=iterations,
        )

        self.decision_history.append(decision)
        logger.info(
            f"PSO completed: {decision.convergence_iterations} iterations, "  # noqa: G004
            f"confidence={decision.confidence:.2f}"
        )

        return decision

    # =========================================================================
    # Ant Colony Optimization
    # =========================================================================

    async def run_ant_colony(
        self,
        nodes: list[str],
        edges: list[tuple[str, str]],
        start_node: str,
        end_node: str,
        num_ants: int = 10,
        iterations: int | None = None,
    ) -> SwarmDecision:
        """
        Run Ant Colony Optimization for pathfinding.

        Args:
            nodes: List of node identifiers
            edges: List of edges (from, to)
            start_node: Starting node
            end_node: Destination node
            num_ants: Number of ants to simulate
            iterations: Number of iterations

        Returns:
            Swarm decision with optimal path
        """
        iterations = iterations or self.config.max_iterations

        decision = self._aco.run(
            nodes=nodes,
            edges=edges,
            start_node=start_node,
            end_node=end_node,
            num_ants=num_ants,
            iterations=iterations,
        )

        self.decision_history.append(decision)
        logger.info("ACO completed: found path with quality {decision.confidence:.2f}")

        return decision

    # =========================================================================
    # Bee Algorithm
    # =========================================================================

    async def run_bee_algorithm(
        self,
        tasks: list[str],
        foragers: list[str],
        task_qualities: dict[str, float] | None = None,
        iterations: int | None = None,
    ) -> SwarmDecision:
        """
        Run Bee Algorithm for task allocation.

        Args:
            tasks: List of task identifiers
            foragers: List of forager agent IDs
            task_qualities: Optional initial task quality assessments
            iterations: Number of iterations

        Returns:
            Swarm decision with task allocation
        """
        iterations = iterations or self.config.max_iterations

        decision = self._abc.run(
            tasks=tasks,
            foragers=foragers,
            task_qualities=task_qualities,
            iterations=iterations,
        )

        self.decision_history.append(decision)
        logger.info("Bee Algorithm completed: {len(decision.final_position)} tasks allocated")

        return decision

    # =========================================================================
    # Flocking Behavior
    # =========================================================================

    async def run_flocking(
        self,
        agents: list[str],
        initial_positions: dict[str, tuple[float, float, float]] | None = None,
        iterations: int = 50,
    ) -> SwarmDecision:
        """Run flocking behavior simulation for agent coordination."""
        self._initialize_flocking_agents(agents, initial_positions or {})

        flock_center = (0.0, 0.0, 0.0)
        avg_heading = (0.0, 0.0, 1.0)

        for _iteration in range(iterations):
            self._update_neighbors()

            for agent in self.flocking_agents.values():
                self._apply_flocking_rules(agent)

            for agent in self.flocking_agents.values():
                self._update_flocking_position(agent)

            flock_center = self._calculate_flock_center()
            avg_heading = self._calculate_average_heading()

        decision = SwarmDecision(
            pattern=SwarmPattern.FLOCKING,
            participants=agents,
            convergence_iterations=iterations,
            final_position={
                "center": flock_center,
                "heading": avg_heading,
            },
            confidence=self._calculate_flocking_cohesion(),
            emergence_indicators=self._detect_emergence_flocking(),
            quality_metrics={
                "cohesion": self._calculate_flocking_cohesion(),
                "alignment": self._calculate_flocking_alignment(),
                "separation": self._calculate_flocking_separation(),
            },
        )

        self.decision_history.append(decision)
        logger.info("Flocking simulation completed: {iterations} iterations")

        return decision

    def _initialize_flocking_agents(
        self,
        agents: list[str],
        initial_positions: dict[str, tuple[float, float, float]],
    ) -> None:
        """Initialize flocking agents."""
        self.flocking_agents.clear()

        for agent_id in agents:
            position = initial_positions.get(
                agent_id,
                (
                    random.uniform(-10, 10),  # noqa: S311
                    random.uniform(-10, 10),  # noqa: S311
                    random.uniform(-10, 10),  # noqa: S311
                ),
            )

            velocity = (
                random.uniform(-1, 1),  # noqa: S311
                random.uniform(-1, 1),  # noqa: S311
                random.uniform(-1, 1),  # noqa: S311
            )

            agent = FlockingAgent(
                agent_id=agent_id,
                position=position,
                velocity=velocity,
                heading=(0.0, 0.0, 1.0),
            )

            self.flocking_agents[agent_id] = agent

    def _update_neighbors(self) -> None:
        """Update neighbor lists for all agents."""
        for agent_id, agent in self.flocking_agents.items():
            neighbors = []
            for other_id, other in self.flocking_agents.items():
                if other_id != agent_id:
                    distance = self._calculate_distance(agent.position, other.position)
                    if distance < self.config.flock_perception_radius:
                        neighbors.append(other_id)
            agent.neighbors = neighbors

    def _apply_flocking_rules(self, agent: FlockingAgent) -> None:
        """Apply flocking rules to update agent velocity."""
        separation = self._calculate_separation(agent)
        alignment = self._calculate_alignment(agent)
        cohesion = self._calculate_cohesion(agent)

        new_velocity = (
            agent.velocity[0]
            + separation[0] * self.config.flock_separation_weight
            + alignment[0] * self.config.flock_alignment_weight
            + cohesion[0] * self.config.flock_cohesion_weight,
            agent.velocity[1]
            + separation[1] * self.config.flock_separation_weight
            + alignment[1] * self.config.flock_alignment_weight
            + cohesion[1] * self.config.flock_cohesion_weight,
            agent.velocity[2]
            + separation[2] * self.config.flock_separation_weight
            + alignment[2] * self.config.flock_alignment_weight
            + cohesion[2] * self.config.flock_cohesion_weight,
        )

        magnitude = math.sqrt(sum(v**2 for v in new_velocity))
        if magnitude > 0:
            scale = min(FLOCK_MAX_SPEED, magnitude) / magnitude
            agent.velocity = tuple(v * scale for v in new_velocity)

        agent.heading = agent.velocity

    def _calculate_separation(self, agent: FlockingAgent) -> tuple[float, float, float]:
        """Calculate separation steering force."""
        separation = [0.0, 0.0, 0.0]
        count = 0

        for neighbor_id in agent.neighbors:
            neighbor = self.flocking_agents[neighbor_id]
            distance = self._calculate_distance(agent.position, neighbor.position)

            if distance > 0 and distance < FLOCK_SEPARATION_THRESHOLD:
                diff = tuple(a - b for a, b in zip(agent.position, neighbor.position, strict=False))
                diff = tuple(d / distance for d in diff)
                separation = tuple(s + d for s, d in zip(separation, diff, strict=False))
                count += 1

        if count > 0:
            separation = tuple(s / count for s in separation)

        return separation

    def _calculate_alignment(self, agent: FlockingAgent) -> tuple[float, float, float]:
        """Calculate alignment steering force."""
        if not agent.neighbors:
            return (0.0, 0.0, 0.0)

        avg_velocity = [0.0, 0.0, 0.0]
        for neighbor_id in agent.neighbors:
            neighbor = self.flocking_agents[neighbor_id]
            avg_velocity = tuple(
                a + b for a, b in zip(avg_velocity, neighbor.velocity, strict=False)
            )

        avg_velocity = tuple(v / len(agent.neighbors) for v in avg_velocity)

        return tuple(a - c for a, c in zip(avg_velocity, agent.velocity, strict=False))

    def _calculate_cohesion(self, agent: FlockingAgent) -> tuple[float, float, float]:
        """Calculate cohesion steering force."""
        if not agent.neighbors:
            return (0.0, 0.0, 0.0)

        center = [0.0, 0.0, 0.0]
        for neighbor_id in agent.neighbors:
            neighbor = self.flocking_agents[neighbor_id]
            center = tuple(c + n for c, n in zip(center, neighbor.position, strict=False))

        center = tuple(c / len(agent.neighbors) for c in center)

        return tuple(c - p for c, p in zip(center, agent.position, strict=False))

    def _update_flocking_position(self, agent: FlockingAgent) -> None:
        """Update agent position based on velocity."""
        agent.position = tuple(p + v for p, v in zip(agent.position, agent.velocity, strict=False))

    def _calculate_distance(
        self,
        pos1: tuple[float, float, float],
        pos2: tuple[float, float, float],
    ) -> float:
        """Calculate Euclidean distance between two positions."""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2, strict=False)))

    def _calculate_flock_center(self) -> tuple[float, float, float]:
        """Calculate center of the flock."""
        if not self.flocking_agents:
            return (0.0, 0.0, 0.0)

        center = [0.0, 0.0, 0.0]
        for agent in self.flocking_agents.values():
            center = tuple(c + a for c, a in zip(center, agent.position, strict=False))

        return tuple(c / len(self.flocking_agents) for c in center)

    def _calculate_average_heading(self) -> tuple[float, float, float]:
        """Calculate average heading of the flock."""
        if not self.flocking_agents:
            return (0.0, 0.0, 1.0)

        avg = [0.0, 0.0, 0.0]
        for agent in self.flocking_agents.values():
            avg = tuple(a + h for a, h in zip(avg, agent.heading, strict=False))

        result = tuple(a / len(self.flocking_agents) for a in avg)

        magnitude = math.sqrt(sum(v**2 for v in result))
        if magnitude > 0:
            result = tuple(v / magnitude for v in result)

        return result

    def _calculate_flocking_cohesion(self) -> float:
        """Calculate overall flock cohesion."""
        if len(self.flocking_agents) < 2:
            return 1.0

        center = self._calculate_flock_center()
        distances = [
            self._calculate_distance(agent.position, center)
            for agent in self.flocking_agents.values()
        ]

        avg_distance = sum(distances) / len(distances)

        return 1.0 / (1.0 + avg_distance / FLOCK_COHESION_DISTANCE_DIVISOR)

    def _calculate_flocking_alignment(self) -> float:
        """Calculate overall flock alignment."""
        if not self.flocking_agents:
            return 0.0

        avg_heading = self._calculate_average_heading()

        alignment_sum = 0.0
        for agent in self.flocking_agents.values():
            dot_product = sum(a * h for a, h in zip(agent.heading, avg_heading, strict=False))
            alignment_sum += dot_product

        return alignment_sum / len(self.flocking_agents)

    def _calculate_flocking_separation(self) -> float:
        """Calculate overall flock separation."""
        if len(self.flocking_agents) < 2:
            return 1.0

        min_distances = []
        for agent_id, agent in self.flocking_agents.items():
            min_dist = float("inf")
            for other_id, other in self.flocking_agents.items():
                if other_id != agent_id:
                    dist = self._calculate_distance(agent.position, other.position)
                    min_dist = min(min_dist, dist)
            if min_dist < float("inf"):
                min_distances.append(min_dist)

        if not min_distances:
            return 0.0

        avg_min_dist = sum(min_distances) / len(min_distances)

        return min(1.0, avg_min_dist / FLOCK_SEPARATION_THRESHOLD)

    def _detect_emergence_flocking(self) -> list[str]:
        """Detect emergence indicators in flocking."""
        indicators = []

        cohesion = self._calculate_flocking_cohesion()
        alignment = self._calculate_flocking_alignment()

        if cohesion > FLOCK_TIGHT_THRESHOLD:
            indicators.append("tight_flock")

        if alignment > FLOCK_SYNC_THRESHOLD:
            indicators.append("synchronized_movement")

        if cohesion > FLOCK_COLLECTIVE_COHESION and alignment > FLOCK_COLLECTIVE_ALIGNMENT:
            indicators.append("collective_behavior")

        return indicators

    # =========================================================================
    # Stigmergy (Indirect Coordination)
    # =========================================================================

    async def run_stigmergy(
        self,
        agents: list[str],
        environment_size: tuple[int, int] = (100, 100),
        iterations: int = 100,
    ) -> SwarmDecision:
        """Run stigmergic coordination simulation."""
        self.traces.clear()
        for x in range(environment_size[0]):
            self.traces[x] = []

        agent_positions = {
            agent_id: (
                random.randint(0, environment_size[0] - 1),  # noqa: S311
                random.randint(0, environment_size[1] - 1),  # noqa: S311
            )
            for agent_id in agents
        }

        trace_density = 0.0
        coordination_score = 0.0

        for _iteration in range(iterations):
            for agent_id in agents:
                x, y = agent_positions[agent_id]

                trace = StigmergicTrace(
                    agent_id=agent_id,
                    trace_type="marker",
                    content={"position": (x, y)},
                    strength=1.0,
                    decay_rate=self.config.stigmergy_decay,
                )

                if x in self.traces:
                    self.traces[x].append(trace)

                new_position = self._stigmergic_movement(agent_id, (x, y), environment_size)
                agent_positions[agent_id] = new_position

            self._decay_traces()

            trace_density = self._calculate_trace_density(environment_size)
            coordination_score = self._calculate_stigmergy_coordination(agent_positions)

        decision = SwarmDecision(
            pattern=SwarmPattern.STIGMERGY,
            participants=agents,
            convergence_iterations=iterations,
            final_position={
                "trace_density": trace_density,
                "coordination_score": coordination_score,
            },
            confidence=coordination_score,
            emergence_indicators=self._detect_emergence_stigmergy(trace_density),
            quality_metrics={
                "trace_density": trace_density,
                "coordination_score": coordination_score,
            },
        )

        self.decision_history.append(decision)
        logger.info("Stigmergy simulation completed: density={trace_density:.2f}")

        return decision

    def _stigmergic_movement(
        self,
        agent_id: str,  # noqa: ARG002
        current_pos: tuple[int, int],
        environment_size: tuple[int, int],
    ) -> tuple[int, int]:
        """Move agent based on stigmergic traces."""
        x, y = current_pos
        nearby_traces = self._find_nearby_traces(x, y, environment_size)

        if nearby_traces:
            return self._move_toward_strongest_trace(x, y, nearby_traces)

        return self._random_move(x, y, environment_size)

    def _find_nearby_traces(
        self, x: int, y: int, environment_size: tuple[int, int]
    ) -> list[Any]:
        """Find traces within search radius of position."""
        nearby: list[Any] = []
        for dx in range(-STIGMERGY_SEARCH_RADIUS, STIGMERGY_SEARCH_RADIUS + 1):
            for dy in range(-STIGMERGY_SEARCH_RADIUS, STIGMERGY_SEARCH_RADIUS + 1):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < environment_size[0] and 0 <= ny < environment_size[1]):
                    continue
                if nx not in self.traces:
                    continue
                for trace in self.traces[nx]:
                    if abs(trace.content.get("position", (0, 0))[1] - ny) <= STIGMERGY_SEARCH_RADIUS:
                        nearby.append(trace)
        return nearby

    @staticmethod
    def _move_toward_strongest_trace(
        x: int, y: int, nearby_traces: list[Any]
    ) -> tuple[int, int]:
        """Move one step toward the strongest nearby trace."""
        strongest = max(nearby_traces, key=lambda t: t.strength)
        target_x, target_y = strongest.content.get("position", (x, y))
        new_x = x + (1 if target_x > x else (-1 if target_x < x else 0))
        new_y = y + (1 if target_y > y else (-1 if target_y < y else 0))
        return (new_x, new_y)

    @staticmethod
    def _random_move(
        x: int, y: int, environment_size: tuple[int, int]
    ) -> tuple[int, int]:
        """Move randomly within environment bounds."""
        new_x = max(0, min(environment_size[0] - 1, x + random.randint(-1, 1)))  # noqa: S311
        new_y = max(0, min(environment_size[1] - 1, y + random.randint(-1, 1)))  # noqa: S311
        return (new_x, new_y)

    def _decay_traces(self) -> None:
        """Decay trace strengths over time."""
        for x in self.traces:
            for trace in self.traces[x]:
                trace.strength *= 1 - trace.decay_rate

        for x in self.traces:
            self.traces[x] = [
                t for t in self.traces[x] if t.strength > STIGMERGY_TRACE_MIN_THRESHOLD
            ]

    def _calculate_trace_density(self, environment_size: tuple[int, int]) -> float:
        """Calculate trace density in environment."""
        total_traces = sum(len(traces) for traces in self.traces.values())
        total_cells = environment_size[0] * environment_size[1]

        return total_traces / total_cells if total_cells > 0 else 0.0

    def _calculate_stigmergy_coordination(
        self,
        agent_positions: dict[str, tuple[int, int]],
    ) -> float:
        """Calculate coordination score from agent positions."""
        if len(agent_positions) < 2:
            return 1.0

        positions = list(agent_positions.values())
        center_x = sum(p[0] for p in positions) / len(positions)
        center_y = sum(p[1] for p in positions) / len(positions)

        avg_distance = sum(
            math.sqrt((p[0] - center_x) ** 2 + (p[1] - center_y) ** 2) for p in positions
        ) / len(positions)

        max_distance = (
            math.sqrt(
                (positions[0][0] - positions[-1][0]) ** 2
                + (positions[0][1] - positions[-1][1]) ** 2
            )
            if len(positions) > 1
            else 1.0
        )

        return 1.0 - (avg_distance / max_distance) if max_distance > 0 else 1.0

    def _detect_emergence_stigmergy(self, trace_density: float) -> list[str]:
        """Detect emergence indicators in stigmergy."""
        indicators = []

        if trace_density > STIGMERGY_TRACE_ACCUMULATION_THRESHOLD:
            indicators.append("trace_accumulation")

        if trace_density > STIGMERGY_COLLECTIVE_THRESHOLD:
            indicators.append("collective_marking")

        return indicators

    # =========================================================================
    # General Methods
    # =========================================================================

    def get_decision_history(self, limit: int = 100) -> list[SwarmDecision]:
        """Get decision history."""
        return self.decision_history[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """Get swarm intelligence statistics."""
        return {
            "total_decisions": len(self.decision_history),
            "patterns_used": list({d.pattern.value for d in self.decision_history}),
            "avg_confidence": (
                sum(d.confidence for d in self.decision_history) / len(self.decision_history)
                if self.decision_history
                else 0.0
            ),
        }

    def clear_state(self) -> None:
        """Clear all swarm state."""
        self.flocking_agents.clear()
        self.traces.clear()
        self.decision_history.clear()

        # Clear internal algorithm state
        self._pso.particles.clear()
        self._pso.global_best_position = {}
        self._pso.global_best_value = float("-inf")
        self._aco.pheromone_trails.clear()
        self._abc.bee_colony.clear()

        logger.info("Swarm intelligence state cleared")
