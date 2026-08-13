"""
Artificial Bee Colony implementation.

Uses random module for simulation purposes only.
Not used for security-critical operations (IDs use uuid, not random).
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.collective.swarm_patterns import SwarmPattern

logger = structlog.get_logger("ABC")

# ABC Constants (algorithm thresholds)
ABC_SCOUT_RATIO_DEFAULT = 0.2
ABC_DANCE_THRESHOLD_DEFAULT = 0.7
ABC_SCOUT_MIN_QUALITY = 0.3
ABC_SCOUT_MAX_QUALITY = 1.0
ABC_SPECIALIST_THRESHOLD = 0.7
ABC_SPECIALIST_FRACTION = 0.5
ABC_COVERAGE_WEIGHT = 0.6
ABC_BALANCE_WEIGHT = 0.4
ABC_CONVERGENCE_THRESHOLD = 0.95


@dataclass
class BeeAgent:
    """
    Bee agent in the Bee Algorithm.

    Attributes:
        bee_id: Unique identifier
        role: Bee role (scout, forager, unemployed)
        current_task: Current task being worked on
        task_quality: Quality assessment of current task
        dance_strength: Strength of waggle dance
        agent_id: Associated agent ID
    """

    bee_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "unemployed"
    current_task: str | None = None
    task_quality: float = 0.0
    dance_strength: float = 0.0
    agent_id: str = ""


@dataclass
class SwarmDecision:
    """Result of a swarm intelligence decision process."""

    pattern: SwarmPattern = SwarmPattern.BEE_ALGORITHM
    participants: list[str] = field(default_factory=list)
    convergence_iterations: int = 0
    final_position: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    emergence_indicators: list[str] = field(default_factory=list)
    quality_metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: "")


class ABC:
    """Artificial Bee Colony algorithm for task allocation."""

    def __init__(
        self,
        scout_ratio: float = ABC_SCOUT_RATIO_DEFAULT,
        dance_threshold: float = ABC_DANCE_THRESHOLD_DEFAULT,
        convergence_threshold: float = ABC_CONVERGENCE_THRESHOLD,
    ) -> None:
        """
        Initialize ABC algorithm.

        Args:
            scout_ratio: Ratio of scout bees
            dance_threshold: Threshold for waggle dance
            convergence_threshold: Threshold for convergence
        """
        self.scout_ratio = scout_ratio
        self.dance_threshold = dance_threshold
        self.convergence_threshold = convergence_threshold

        self.bee_colony: list[BeeAgent] = []
        self.task_pool: dict[str, dict[str, Any]] = {}
        self.decision_history: list[SwarmDecision] = []

    def run(
        self,
        tasks: list[str],
        foragers: list[str],
        task_qualities: dict[str, float] | None = None,
        iterations: int = 100,
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
        self._initialize_colony(tasks, foragers, task_qualities or {})

        for task_id, quality in (task_qualities or {}).items():
            if task_id in self.task_pool:
                self.task_pool[task_id]["quality"] = quality

        best_allocation: dict[str, list[str]] = {}
        best_allocation_score = 0.0

        for iteration in range(iterations):  # noqa: B007
            self._scout_phase()
            self._forager_phase()
            self._dance_phase()

            allocation = self._get_allocation()
            score = self._evaluate_allocation(allocation)

            if score > best_allocation_score:
                best_allocation = allocation
                best_allocation_score = score

            if score >= self.convergence_threshold:
                break

        decision = SwarmDecision(
            pattern=SwarmPattern.BEE_ALGORITHM,
            participants=foragers,
            convergence_iterations=iteration + 1,
            final_position={"allocation": best_allocation},
            confidence=best_allocation_score,
            emergence_indicators=self._detect_emergence(best_allocation),
            quality_metrics={
                "tasks_allocated": len(best_allocation),
                "allocation_efficiency": best_allocation_score,
            },
        )

        self.decision_history.append(decision)
        return decision

    def _initialize_colony(
        self,
        tasks: list[str],
        foragers: list[str],
        task_qualities: dict[str, float],
    ) -> None:
        """Initialize bee colony with scouts and foragers."""
        self.bee_colony.clear()
        self.task_pool.clear()

        for task_id in tasks:
            self.task_pool[task_id] = {
                "quality": task_qualities.get(task_id, 0.5),
                "assigned_foragers": [],
                "last_updated": datetime.now(UTC).isoformat(),
            }

        num_scouts = max(1, int(len(foragers) * self.scout_ratio))

        for agent_id in foragers[:num_scouts]:
            bee = BeeAgent(role="scout", agent_id=agent_id)
            self.bee_colony.append(bee)

        for agent_id in foragers[num_scouts:]:
            bee = BeeAgent(role="forager", agent_id=agent_id)
            self.bee_colony.append(bee)

    def _scout_phase(self) -> None:
        """Scout bees search for new tasks."""
        scouts = [b for b in self.bee_colony if b.role == "scout"]

        for _scout in scouts:
            available_tasks = [
                t for t, data in self.task_pool.items() if not data["assigned_foragers"]
            ]

            if available_tasks:
                discovered = random.choice(available_tasks)  # noqa: S311
                self.task_pool[discovered]["quality"] = random.uniform(  # noqa: S311
                    ABC_SCOUT_MIN_QUALITY, ABC_SCOUT_MAX_QUALITY
                )

    def _forager_phase(self) -> None:
        """Forager bees exploit known tasks."""
        foragers = [b for b in self.bee_colony if b.role == "forager"]

        for forager in foragers:
            if forager.current_task:
                quality = self.task_pool.get(forager.current_task, {}).get("quality", 0)
                forager.task_quality = quality
            else:
                task_dances = []
                for task_id in self.task_pool:
                    dance_strength = sum(
                        b.dance_strength for b in self.bee_colony if b.current_task == task_id
                    )
                    if dance_strength > 0:
                        task_dances.append((task_id, dance_strength))

                if task_dances:
                    total = sum(d[1] for d in task_dances)
                    weights = [d[1] / total for d in task_dances]
                    selected = random.choices([d[0] for d in task_dances], weights=weights, k=1)[0]  # noqa: S311
                    forager.current_task = selected
                    forager.task_quality = self.task_pool[selected]["quality"]
                    self.task_pool[selected]["assigned_foragers"].append(forager.agent_id)

    def _should_keep_dance(self, bee: BeeAgent) -> bool:
        """Check if bee should keep dancing based on task quality."""
        return bee.current_task and bee.task_quality >= self.dance_threshold

    def _remove_bee_from_task(self, bee: BeeAgent) -> None:
        """Remove bee from its current task and reset role."""
        if bee.current_task in self.task_pool:
            task = self.task_pool[bee.current_task]
            if bee.agent_id in task["assigned_foragers"]:
                task["assigned_foragers"].remove(bee.agent_id)
        bee.current_task = None
        bee.dance_strength = 0.0
        bee.role = "scout"

    def _dance_phase(self) -> None:
        """Bees perform waggle dance to share task information."""
        for bee in self.bee_colony:
            if bee.current_task:
                if self._should_keep_dance(bee):
                    bee.dance_strength = bee.task_quality
                else:
                    self._remove_bee_from_task(bee)

    def _get_allocation(self) -> dict[str, list[str]]:
        """Get current task allocation."""
        allocation = {}
        for task_id, data in self.task_pool.items():
            allocation[task_id] = data["assigned_foragers"].copy()
        return allocation

    def _evaluate_allocation(self, allocation: dict[str, list[str]]) -> float:
        """Evaluate quality of task allocation."""
        if not allocation:
            return 0.0

        covered = sum(1 for agents in allocation.values() if agents)
        coverage_score = covered / len(allocation) if allocation else 0

        forager_counts = [len(agents) for agents in allocation.values() if agents]
        if forager_counts:
            avg_count = sum(forager_counts) / len(forager_counts)
            variance = sum((c - avg_count) ** 2 for c in forager_counts) / len(forager_counts)
            balance_score = 1.0 / (1.0 + variance)
        else:
            balance_score = 0

        return ABC_COVERAGE_WEIGHT * coverage_score + ABC_BALANCE_WEIGHT * balance_score

    def _detect_emergence(self, allocation: dict[str, list[str]]) -> list[str]:
        """Detect emergence indicators in bee algorithm."""
        indicators = []

        if allocation:
            covered_tasks = sum(1 for agents in allocation.values() if agents)
            if covered_tasks == len(allocation):
                indicators.append("complete_coverage")

        specialist_count = sum(
            1
            for bee in self.bee_colony
            if bee.current_task is not None and bee.dance_strength > ABC_SPECIALIST_THRESHOLD
        )
        if specialist_count > len(self.bee_colony) * ABC_SPECIALIST_FRACTION:
            indicators.append("task_specialization")

        return indicators
