"""
Coordinator Strategies - Dependency Resolution and Coordination Strategies

Contains strategy-related classes and handlers extracted from coordinator.py.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.actors.coordinator.types import CoordinatedTask

import structlog

logger = structlog.get_logger(__name__)


class DependencyResolutionStrategy:
    """Strategy for resolving task dependencies and determining execution order."""

    def __init__(self, tasks: dict[str, CoordinatedTask], dependency_graph: dict[str, set[str]]):
        self._tasks = tasks
        self._dependency_graph = dependency_graph

    def topological_sort(self, graph: dict[str, set[str]]) -> list[str]:
        """Perform topological sort on dependency graph."""
        in_degree = {node: len(deps) for node, deps in graph.items()}
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort by priority for deterministic ordering
            queue.sort(
                key=lambda x: (
                    -self._tasks.get(x, self._tasks.values().__iter__().__next__()).priority
                )
            )
            node = queue.pop(0)
            result.append(node)

            for dependent in self._dependency_graph.get(node, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result

    def identify_parallel_groups(
        self, sorted_tasks: list[str], graph: dict[str, set[str]]
    ) -> list[list[str]]:
        """Identify groups of tasks that can run in parallel."""
        if not sorted_tasks:
            return []

        groups = []
        current_group = []
        completed = set()

        for task_id in sorted_tasks:
            deps = graph.get(task_id, set())

            # If all dependencies are in completed, can add to current group
            if all(d in completed for d in deps):
                current_group.append(task_id)
            else:
                if current_group:
                    groups.append(current_group)
                    completed.update(current_group)
                current_group = [task_id]

        if current_group:
            groups.append(current_group)

        return groups

    def find_critical_path(self, sorted_tasks: list[str], graph: dict[str, set[str]]) -> list[str]:
        """Find the critical path (longest dependency chain)."""
        if not sorted_tasks:
            return []

        # Calculate longest path to each node
        longest_path: dict[str, list[str]] = {task: [task] for task in sorted_tasks}

        for task_id in sorted_tasks:
            deps = graph.get(task_id, set())
            for dep in deps:
                if dep in longest_path:
                    candidate_path = longest_path[dep] + [task_id]
                    if len(candidate_path) > len(longest_path[task_id]):
                        longest_path[task_id] = candidate_path

        # Find the longest path overall
        if longest_path:
            return max(longest_path.values(), key=len)
        return []


class ParallelExecutionStrategy:
    """Strategy for managing parallel task execution groups."""

    def __init__(self):
        self._executed_tasks: set[str] = set()
        self._active_groups: list[list[str]] = []

    def group_by_dependencies(
        self, tasks: list[str], reverse_deps: dict[str, set[str]]
    ) -> list[list[str]]:
        """Group tasks by their dependency readiness for parallel execution."""
        if not tasks:
            return []

        groups = []
        remaining = set(tasks)

        while remaining:
            # Find tasks with all dependencies satisfied
            current_batch = []
            for task_id in list(remaining):
                deps = reverse_deps.get(task_id, set())
                if not deps or all(d in self._executed_tasks for d in deps):
                    current_batch.append(task_id)

            if not current_batch:
                # Circular dependency or error - take one anyway
                if remaining:
                    current_batch = [next(iter(remaining))]
                else:
                    break

            groups.append(current_batch)
            self._executed_tasks.update(current_batch)
            remaining -= set(current_batch)

        return groups

    def reset(self) -> None:
        """Reset execution state for reuse."""
        self._executed_tasks.clear()
        self._active_groups.clear()


class ResourceAllocationStrategy:
    """Strategy for managing resource contention between tasks."""

    def __init__(self):
        self._resources: dict[str, int] = {}
        self._resource_locks: dict[str, set[str]] = {}

    def register_resource(self, resource_name: str, count: int) -> None:
        """Register a resource pool."""
        self._resources[resource_name] = count

    def allocate(self, resource_name: str, task_id: str, count: int = 1) -> tuple[bool, int]:
        """Attempt to allocate resources for a task.

        Returns (success, remaining_count).
        """
        if resource_name not in self._resources:
            return False, 0

        available = self._get_available_count(resource_name)
        if available >= count:
            if resource_name not in self._resource_locks:
                self._resource_locks[resource_name] = set()
            self._resource_locks[resource_name].add(task_id)
            return True, available - count
        return False, available

    def release(self, resource_name: str, task_id: str) -> None:
        """Release resources held by a task."""
        if resource_name in self._resource_locks:
            self._resource_locks[resource_name].discard(task_id)

    def _get_available_count(self, resource_name: str) -> int:
        """Get count of available (unlocked) resources."""
        locked = len(self._resource_locks.get(resource_name, set()))
        total = self._resources.get(resource_name, 0)
        return max(0, total - locked)

    def get_resource_status(self) -> dict[str, dict[str, int | set[str]]]:
        """Get status of all resources."""
        return {
            name: {
                "total": count,
                "available": self._get_available_count(name),
                "locked_by": list(self._resource_locks.get(name, set())),
            }
            for name, count in self._resources.items()
        }
