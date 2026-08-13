"""
Ant Colony Optimization implementation.

Uses random module for simulation purposes only.
Not used for security-critical operations (IDs use uuid, not random).
"""

import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.collective.swarm_patterns import SwarmPattern

logger = structlog.get_logger("ACO")

# ACO Constants (algorithm thresholds)
ACO_INITIAL_PHEROMONE = 1.0
ACO_MIN_PHEROMONE = 0.1
ACO_EVAPORATION_RATE_DEFAULT = 0.1
ACO_ALPHA_DEFAULT = 1.0
ACO_BETA_DEFAULT = 2.0
ACO_PHEROMONE_DEPOSIT_FACTOR = 0.1
ACO_HEURISTIC_BASE_DISTANCE = 1.0
ACO_STRONG_PHEROMONE_TRAIL_THRESHOLD = 2.0
ACO_CONVERGENCE_THRESHOLD = 0.95
ACO_LENGTH_FACTOR_WEIGHT = 0.7
ACO_VALIDITY_FACTOR_WEIGHT = 0.3


@dataclass
class PheromoneTrail:
    """
    Pheromone trail for Ant Colony Optimization.

    Attributes:
        trail_id: Unique identifier
        from_node: Starting node
        to_node: Ending node
        pheromone_level: Current pheromone level
        evaporation_rate: Rate of pheromone decay
        quality: Quality of the path
    """

    trail_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_node: str = ""
    to_node: str = ""
    pheromone_level: float = 1.0
    evaporation_rate: float = 0.1
    quality: float = 1.0
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class SwarmDecision:
    """Result of a swarm intelligence decision process."""

    pattern: SwarmPattern = SwarmPattern.ANT_COLONY
    participants: list[str] = field(default_factory=list)
    convergence_iterations: int = 0
    final_position: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    emergence_indicators: list[str] = field(default_factory=list)
    quality_metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: "")


class ACO:
    """Ant Colony Optimization algorithm."""

    def __init__(
        self,
        evaporation: float = ACO_EVAPORATION_RATE_DEFAULT,
        alpha: float = ACO_ALPHA_DEFAULT,
        beta: float = ACO_BETA_DEFAULT,
        convergence_threshold: float = ACO_CONVERGENCE_THRESHOLD,
    ) -> None:
        """
        Initialize ACO algorithm.

        Args:
            evaporation: Pheromone evaporation rate
            alpha: Pheromone importance factor
            beta: Heuristic importance factor
            convergence_threshold: Threshold for convergence
        """
        self.evaporation = evaporation
        self.alpha = alpha
        self.beta = beta
        self.convergence_threshold = convergence_threshold

        self.pheromone_trails: dict[str, dict[str, PheromoneTrail]] = {}
        self.decision_history: list[SwarmDecision] = []

    def run(
        self,
        nodes: list[str],
        edges: list[tuple[str, str]],
        start_node: str,
        end_node: str,
        num_ants: int = 10,
        iterations: int = 100,
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
        self._initialize_pheromone_trails(edges)

        best_path: list[str] = []
        best_path_quality = 0.0

        for iteration in range(iterations):  # noqa: B007
            paths = []
            for _ in range(num_ants):
                path = self._construct_path(nodes, edges, start_node, end_node)
                if path:
                    paths.append(path)

            for path in paths:
                quality = self._evaluate_path(path, edges)
                self._update_pheromones(path, quality)

                if quality > best_path_quality:
                    best_path = path
                    best_path_quality = quality

            self._evaporate_pheromones()

            if best_path_quality >= self.convergence_threshold:
                break

        decision = SwarmDecision(
            pattern=SwarmPattern.ANT_COLONY,
            participants=[f"ant-{i}" for i in range(num_ants)],
            convergence_iterations=iteration + 1,
            final_position={"path": best_path, "quality": best_path_quality},
            confidence=best_path_quality,
            emergence_indicators=self._detect_emergence(best_path),
            quality_metrics={
                "path_length": len(best_path),
                "pheromone_strength": self._get_path_pheromone_strength(best_path),
            },
        )

        self.decision_history.append(decision)
        return decision

    def _initialize_pheromone_trails(self, edges: list[tuple[str, str]]) -> None:
        """Initialize pheromone trails for edges."""
        self.pheromone_trails.clear()

        for from_node, to_node in edges:
            if from_node not in self.pheromone_trails:
                self.pheromone_trails[from_node] = {}

            trail = PheromoneTrail(
                from_node=from_node,
                to_node=to_node,
                pheromone_level=ACO_INITIAL_PHEROMONE,
                evaporation_rate=self.evaporation,
            )
            self.pheromone_trails[from_node][to_node] = trail

    def _construct_path(
        self,
        nodes: list[str],  # noqa: ARG002
        edges: list[tuple[str, str]],
        start_node: str,
        end_node: str,
    ) -> list[str]:
        """Construct a path for an ant using pheromone probabilities."""
        path = [start_node]
        current = start_node
        visited = {start_node}

        adjacency = defaultdict(list)
        for from_node, to_node in edges:
            adjacency[from_node].append(to_node)

        while current != end_node:
            neighbors = [n for n in adjacency[current] if n not in visited]

            if not neighbors:
                if len(path) > 1:
                    path.pop()
                    current = path[-1]
                    continue
                return []

            probabilities = []
            for neighbor in neighbors:
                pheromone = self.pheromone_trails.get(current, {}).get(neighbor, PheromoneTrail())
                tau = pheromone.pheromone_level**self.alpha
                eta = (ACO_HEURISTIC_BASE_DISTANCE / (1 + len(path))) ** self.beta
                probabilities.append(tau * eta)

            total = sum(probabilities)
            if total > 0:
                probabilities = [p / total for p in probabilities]

            selected = random.choices(neighbors, weights=probabilities, k=1)[0]  # noqa: S311
            path.append(selected)
            visited.add(selected)
            current = selected

        return path

    def _evaluate_path(self, path: list[str], edges: list[tuple[str, str]]) -> float:
        """Evaluate quality of a path."""
        if not path:
            return 0.0

        length_factor = 1.0 / len(path)
        edge_set = set(edges)
        valid_edges = 0
        for i in range(len(path) - 1):
            if (path[i], path[i + 1]) in edge_set:
                valid_edges += 1

        validity_factor = valid_edges / (len(path) - 1) if len(path) > 1 else 0

        return (
            ACO_LENGTH_FACTOR_WEIGHT * length_factor + ACO_VALIDITY_FACTOR_WEIGHT * validity_factor
        )

    def _update_pheromones(self, path: list[str], quality: float) -> None:
        """Update pheromones along a path."""
        for i in range(len(path) - 1):
            from_node, to_node = path[i], path[i + 1]
            if from_node in self.pheromone_trails and to_node in self.pheromone_trails[from_node]:
                trail = self.pheromone_trails[from_node][to_node]
                trail.pheromone_level += quality * ACO_PHEROMONE_DEPOSIT_FACTOR
                trail.quality = quality
                trail.last_updated = datetime.now(UTC).isoformat()

    def _evaporate_pheromones(self) -> None:
        """Evaporate pheromones on all trails."""
        for from_node in self.pheromone_trails.values():
            for trail in from_node.values():
                trail.pheromone_level *= 1 - trail.evaporation_rate
                trail.pheromone_level = max(ACO_MIN_PHEROMONE, trail.pheromone_level)

    def _get_path_pheromone_strength(self, path: list[str]) -> float:
        """Get total pheromone strength along a path."""
        total = 0.0
        for i in range(len(path) - 1):
            from_node, to_node = path[i], path[i + 1]
            if from_node in self.pheromone_trails and to_node in self.pheromone_trails[from_node]:
                total += self.pheromone_trails[from_node][to_node].pheromone_level
        return total

    def _detect_emergence(self, best_path: list[str]) -> list[str]:
        """Detect emergence indicators in ACO."""
        indicators = []

        if len(best_path) > 0:
            indicators.append("path_emergence")

        avg_pheromone = 0.0
        trail_count = 0
        for from_node in self.pheromone_trails.values():
            for trail in from_node.values():
                avg_pheromone += trail.pheromone_level
                trail_count += 1

        if trail_count > 0:
            avg_pheromone /= trail_count

        if avg_pheromone > ACO_STRONG_PHEROMONE_TRAIL_THRESHOLD:
            indicators.append("strong_pheromone_trail")

        return indicators
