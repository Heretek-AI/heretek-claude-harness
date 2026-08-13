"""
Coordinator Agent - Multi-Agent Coordination Specialist

Tier 5 Coordination Agent responsible for:
- Task synchronization across multiple agents
- Dependency resolution and sequencing
- Parallel execution orchestration
- Resource contention management
- Collective task progress tracking

Author: Heretek Swarm Collective
Date: 2026-04-06
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.coordinator.strategies import (
    DependencyResolutionStrategy,
    ParallelExecutionStrategy,
    ResourceAllocationStrategy,
)
from heretek_swarm.actors.coordinator.types import (
    AgentState,
    CoordinatedTask,
    DependencyType,
    TaskStatus,
)
from heretek_swarm.actors.mixins.deliberation import DeliberationMixin
from heretek_swarm.actors.mixins.learning import LearningMixin
from heretek_swarm.actors.mixins.memory import MemoryMixin
from heretek_swarm.actors.mixins.pattern import PatternMixin
from heretek_swarm.actors.mixins.validation import ValidationMixin
from heretek_swarm.actors.validation import validate_message
from heretek_swarm.coordination.sync import (
    TaskSynchronizer,
)
from heretek_swarm.coordination.task_graph import (
    TaskGraph,
)

# Error message constants
_TASKGRAPH_NOT_INIT = "TaskGraph not initialized"
_TASKSYNC_NOT_INIT = "TaskSynchronizer not initialized"

logger = structlog.get_logger(__name__)


class CoordinatorAgent(
    ValidationMixin, AgentActor, PatternMixin, DeliberationMixin, MemoryMixin, LearningMixin
):
    """
    Multi-Agent Coordination Specialist.

    Responsibilities:
    - Manage task dependencies and execution order
    - Synchronize parallel agent activities
    - Resolve resource contention
    - Track collective progress
    - Optimize task assignment based on agent load

    Message Handlers:
    - create_task: Create a new coordinated task
    - update_task: Update task status or metadata
    - get_task_status: Get status of a specific task
    - get_workflow_status: Get status of all tasks in a workflow
    - assign_agent: Assign an agent to the coordination system
    - update_agent_state: Update an agent's state
    - resolve_dependencies: Resolve task dependencies
    - start_workflow: Start execution of a coordinated workflow
    - cancel_workflow: Cancel a running workflow
    - get_coordination_report: Generate coordination status report
    """

    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(
            agent_id=agent_id or f"coordinator_{uuid.uuid4().hex[:8]}",
            config=config or {},
        )

        self._config: dict[str, Any] = {}

        # Task tracking
        self._tasks: dict[str, CoordinatedTask] = {}
        self._task_queues: dict[str, list[str]] = {}  # workflow_id -> task_ids
        self._max_tasks: int = self._config.get("max_tasks", 1000)

        # Agent tracking
        self._agents: dict[str, AgentState] = {}
        self._max_agents: int = self._config.get("max_agents", 100)

        # Dependency resolution
        self._dependency_graph: dict[str, set[str]] = {}  # task_id -> dependent task_ids
        self._reverse_deps: dict[str, set[str]] = {}  # task_id -> dependency task_ids

        # INTG-01: Task graph and synchronizer
        self._task_graph: TaskGraph | None = None
        self._synchronizer: TaskSynchronizer | None = None
        self._cycle_notification_enabled: bool = True
        self._deadlock_escalation_enabled: bool = True
        self._coordination_ratio_history: list[float] = []
        self._max_coordination_ratio: float = 0.35

        # Strategy instances for dependency resolution
        self._dependency_strategy = DependencyResolutionStrategy(
            self._tasks, self._dependency_graph
        )
        self._parallel_strategy = ParallelExecutionStrategy()
        self._resource_strategy = ResourceAllocationStrategy()

        logger.info(
            "coordinator_initialized",
            agent_id=self.agent_id,
            max_tasks=self._max_tasks,
            max_agents=self._max_agents,
        )

    async def initialize(self) -> None:
        """Initialize the Coordinator agent with TaskGraph and TaskSynchronizer."""
        await super().initialize()
        self._task_graph = TaskGraph(max_nodes=self._max_tasks)
        self._synchronizer = TaskSynchronizer(
            deadlock_timeout=timedelta(seconds=30),
            max_retries=3,
            coordination_budget=self._max_coordination_ratio,
        )
        self._register_handlers()
        logger.info(
            "coordinator_intg01_initialized",
            task_graph_max_nodes=self._max_tasks,
            coordination_budget=self._max_coordination_ratio,
        )

    def _register_handlers(self) -> None:
        """Register INTG-01 coordination message handlers."""
        self._message_handlers = {
            "health_check": self._handle_health_check,
            "create_task": self._handle_create_task,
            "update_task": self._handle_update_task,
            "get_task_status": self._handle_get_task_status,
            "get_workflow_status": self._handle_get_workflow_status,
            "assign_agent": self._handle_assign_agent,
            "update_agent_state": self._handle_update_agent_state,
            "resolve_dependencies": self._handle_resolve_dependencies,
            "start_workflow": self._handle_start_workflow,
            "cancel_workflow": self._handle_cancel_workflow,
            "get_coordination_report": self._handle_get_coordination_report,
            "graph_detect_cycles": self._handle_graph_detect_cycles,
            "graph_get_metrics": self._handle_graph_get_metrics,
            "graph_get_topological_order": self._handle_graph_get_topological_order,
            "sync_register_dependency": self._handle_sync_register_dependency,
            "sync_release_dependency": self._handle_sync_release_dependency,
            "sync_detect_deadlock": self._handle_sync_detect_deadlock,
            "get_coordination_ratio": self._handle_get_coordination_ratio,
            "get_sync_health": self._handle_get_sync_health,
        }

    async def _validate_message(self, message: ActorMessage) -> dict[str, Any]:
        """Validate incoming message content."""
        try:
            validated = validate_message(message.message_type, message.content)
            if hasattr(validated, "dict"):
                return validated.dict()
            return validated
        except Exception as e:
            logger.debug("coordinator_message_parse_failed", error=str(e))
            return message.content

    async def _handle_create_task(self, message: ActorMessage) -> None:
        """Create a new coordinated task."""
        try:
            content = await self._validate_message(message)
            request = CoordinatedTask(
                task_id=content.get("task_id"),
                name=content.get("name", "unnamed"),
                description=content.get("description", ""),
                assigned_agents=content.get("assigned_agents", []),
            )
            if len(self._tasks) >= self._max_tasks:
                await self._send_error(message.sender_id, "Task limit reached", message.message_type)
                return
            task_id = request.task_id or f"task_{uuid.uuid4().hex[:12]}"
            if task_id in self._tasks:
                await self._send_error(message.sender_id, f"Task {task_id} already exists", message.message_type)
                return
            task = self._build_coordinated_task(task_id, request)
            if not await self._validate_task_dependencies(task, message):
                return
            self._tasks[task_id] = task
            self._update_dependency_graph(task_id, task.dependencies)
            task.status = TaskStatus.BLOCKED if task.dependencies else TaskStatus.READY
            logger.info("task_created", task_id=task_id, name=request.name,
                         dependencies=len(task.dependencies), status=task.status.value)
            await self.send(message.sender_id, ActorMessage(
                message_type="task_created",
                content={"task_id": task_id, "status": task.status.value},
                sender_id=self.agent_id,
            ))
        except Exception as e:
            logger.error("create_task_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to create task: {e!s}", message.message_type)

    def _build_coordinated_task(self, task_id: str, request: CoordinatedTask) -> CoordinatedTask:
        dep_type = DependencyType(request.dependency_type or "sequential")
        return CoordinatedTask(
            task_id=task_id, name=request.name, description=request.description,
            assigned_agents=request.assigned_agents or [],
            dependencies=request.dependencies or [], dependency_type=dep_type,
            priority=request.priority or 5, metadata=request.metadata or {},
        )

    async def _validate_task_dependencies(self, task: CoordinatedTask, message: ActorMessage) -> bool:
        for dep_id in task.dependencies:
            if dep_id not in self._tasks:
                await self._send_error(message.sender_id, f"Dependency {dep_id} does not exist", message.message_type)
                return False
        return True

    def _update_dependency_graph(self, task_id: str, dependencies: list[str]) -> None:
        self._dependency_graph[task_id] = set()
        self._reverse_deps[task_id] = set(dependencies)
        for dep_id in dependencies:
            if dep_id in self._dependency_graph:
                self._dependency_graph[dep_id].add(task_id)

    async def _handle_update_task(self, message: ActorMessage) -> None:
        """Update task status or metadata."""
        try:
            content = await self._validate_message(message)
            task_id = content.get("task_id")

            if not task_id or task_id not in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} not found",
                    message.message_type,
                )
                return

            task = self._tasks[task_id]
            updates = self._apply_task_updates(task, content)

            logger.info("task_updated", task_id=task_id, updates=updates)
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_updated",
                    content={"task_id": task_id, "updates": updates},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("update_task_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to update task: {e!s}",
                message.message_type,
            )

    def _apply_task_updates(self, task: CoordinatedTask, content: dict[str, Any]) -> list[str]:
        """Apply updates from content dict to task, returning list of change descriptions."""
        updates: list[str] = []
        if "status" in content:
            updates.extend(self._apply_status_update(task, content["status"]))
        if "progress" in content:
            progress = float(content["progress"])
            if 0.0 <= progress <= 1.0:
                task.progress = progress
                updates.append(f"progress: {task.progress}")
        if "metadata" in content:
            task.metadata.update(content["metadata"])
            updates.append("metadata updated")
        if "error_message" in content:
            task.error_message = content["error_message"]
            updates.append("error_message set")
        return updates

    def _apply_status_update(self, task: CoordinatedTask, status_str: str) -> list[str]:
        """Apply status change and track timestamps."""
        old_status = task.status
        task.status = TaskStatus(status_str)
        updates = [f"status: {old_status.value} -> {task.status.value}"]
        if task.status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.now(UTC)
        elif task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.now(UTC)
        return updates

    async def _handle_get_task_status(self, message: ActorMessage) -> None:
        """
        Get status of a specific task.

        Content:
        - task_id: str - Task to query
        """
        try:
            content = await self._validate_message(message)
            task_id = content.get("task_id")

            if not task_id or task_id not in self._tasks:
                await self._send_error(
                    message.sender_id,
                    f"Task {task_id} not found",
                    message.message_type,
                )
                return

            task = self._tasks[task_id]
            dependents = list(self._dependency_graph.get(task_id, []))

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="task_status",
                    content={
                        "task": task.to_dict(),
                        "dependents": dependents,
                        "dependency_count": len(task.dependencies),
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_task_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get task status: {e!s}",
                message.message_type,
            )

    async def _handle_get_workflow_status(self, message: ActorMessage) -> None:
        """
        Get status of all tasks in a workflow.

        Content:
        - workflow_id: str - Workflow to query (optional, returns all if not provided)
        """
        try:
            content = await self._validate_message(message)
            workflow_id = content.get("workflow_id")

            if workflow_id:
                task_ids = self._task_queues.get(workflow_id, [])
                tasks = [self._tasks[tid].to_dict() for tid in task_ids if tid in self._tasks]
            else:
                tasks = [task.to_dict() for task in self._tasks.values()]

            # Calculate summary
            status_counts = {}
            total_progress = 0.0
            for task in tasks:
                status = task["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
                total_progress += task.get("progress", 0.0)

            avg_progress = total_progress / len(tasks) if tasks else 0.0

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="workflow_status",
                    content={
                        "workflow_id": workflow_id or "all",
                        "task_count": len(tasks),
                        "status_counts": status_counts,
                        "average_progress": avg_progress,
                        "tasks": tasks,
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_workflow_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get workflow status: {e!s}",
                message.message_type,
            )

    async def _handle_assign_agent(self, message: ActorMessage) -> None:
        """
        Assign an agent to the coordination system.

        Content:
        - agent_id: str - Agent to assign
        - metadata: Optional[Dict] - Additional agent metadata
        """
        try:
            content = await self._validate_message(message)
            agent_id = content.get("agent_id")

            if not agent_id:
                await self._send_error(
                    message.sender_id,
                    "agent_id is required",
                    message.message_type,
                )
                return

            if len(self._agents) >= self._max_agents:
                await self._send_error(
                    message.sender_id,
                    f"Agent limit reached ({self._max_agents})",
                    message.message_type,
                )
                return

            if agent_id in self._agents:
                await self._send_error(
                    message.sender_id,
                    f"Agent {agent_id} already assigned",
                    message.message_type,
                )
                return

            self._agents[agent_id] = AgentState(
                agent_id=agent_id,
            )

            logger.info(
                "agent_assigned",
                agent_id=agent_id,
                total_agents=len(self._agents),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="agent_assigned",
                    content={"agent_id": agent_id, "status": "assigned"},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("assign_agent_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to assign agent: {e!s}",
                message.message_type,
            )

    async def _handle_update_agent_state(self, message: ActorMessage) -> None:
        """
        Update an agent's state.

        Content:
        - agent_id: str - Agent to update
        - status: Optional[str] - idle|busy|offline
        - current_task: Optional[str] - Current task ID
        - load: Optional[float] - Load 0.0-1.0
        """
        try:
            content = await self._validate_message(message)
            agent_id = content.get("agent_id")

            if not agent_id or agent_id not in self._agents:
                await self._send_error(
                    message.sender_id,
                    f"Agent {agent_id} not found",
                    message.message_type,
                )
                return

            agent = self._agents[agent_id]
            agent.last_heartbeat = datetime.now(UTC)

            if "status" in content:
                agent.status = content["status"]
            if "current_task" in content:
                agent.current_task = content["current_task"]
            if "load" in content:
                agent.load = float(content["load"])

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="agent_state_updated",
                    content={"agent_id": agent_id, "state": agent.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("update_agent_state_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to update agent state: {e!s}",
                message.message_type,
            )

    async def _handle_resolve_dependencies(self, message: ActorMessage) -> None:
        """
        Resolve task dependencies and return execution order.

        Content:
        - task_ids: Optional[List[str]] - Tasks to analyze (all if not provided)
        """
        try:
            content = await self._validate_message(message)
            task_ids = content.get("task_ids", list(self._tasks.keys()))

            # Build subgraph
            subgraph = {
                tid: self._reverse_deps.get(tid, set()) for tid in task_ids if tid in self._tasks
            }

            # Topological sort
            sorted_tasks = self._topological_sort(subgraph)

            # Identify parallel groups
            parallel_groups = self._identify_parallel_groups(sorted_tasks, subgraph)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="dependency_resolution",
                    content={
                        "execution_order": sorted_tasks,
                        "parallel_groups": parallel_groups,
                        "critical_path": self._find_critical_path(sorted_tasks, subgraph),
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("resolve_dependencies_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to resolve dependencies: {e!s}",
                message.message_type,
            )

    async def _handle_start_workflow(self, message: ActorMessage) -> None:
        """
        Start execution of a coordinated workflow.

        Content:
        - workflow_id: str - Workflow to start
        - task_ids: List[str] - Tasks in the workflow
        """
        try:
            content = await self._validate_message(message)
            workflow_id = content.get("workflow_id")
            task_ids = content.get("task_ids", [])

            if not workflow_id:
                await self._send_error(
                    message.sender_id,
                    "workflow_id is required",
                    message.message_type,
                )
                return

            # Register workflow
            self._task_queues[workflow_id] = task_ids

            # Update task statuses
            ready_tasks = []
            for task_id in task_ids:
                if task_id in self._tasks:
                    task = self._tasks[task_id]
                    if not task.dependencies:
                        task.status = TaskStatus.READY
                        ready_tasks.append(task_id)

            logger.info(
                "workflow_started",
                workflow_id=workflow_id,
                task_count=len(task_ids),
                ready_count=len(ready_tasks),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="workflow_started",
                    content={
                        "workflow_id": workflow_id,
                        "ready_tasks": ready_tasks,
                        "blocked_tasks": len(task_ids) - len(ready_tasks),
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("start_workflow_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to start workflow: {e!s}",
                message.message_type,
            )

    async def _handle_cancel_workflow(self, message: ActorMessage) -> None:
        """
        Cancel a running workflow.

        Content:
        - workflow_id: str - Workflow to cancel
        """
        try:
            content = await self._validate_message(message)
            workflow_id = content.get("workflow_id")

            if not workflow_id or workflow_id not in self._task_queues:
                await self._send_error(
                    message.sender_id,
                    f"Workflow {workflow_id} not found",
                    message.message_type,
                )
                return

            task_ids = self._task_queues[workflow_id]
            cancelled = []

            for task_id in task_ids:
                if task_id in self._tasks:
                    task = self._tasks[task_id]
                    if task.status not in (
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    ):
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.now(UTC)
                        cancelled.append(task_id)

            # Remove workflow
            del self._task_queues[workflow_id]

            logger.info(
                "workflow_cancelled",
                workflow_id=workflow_id,
                cancelled_count=len(cancelled),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="workflow_cancelled",
                    content={
                        "workflow_id": workflow_id,
                        "cancelled_tasks": cancelled,
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("cancel_workflow_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to cancel workflow: {e!s}",
                message.message_type,
            )

    async def _handle_get_coordination_report(self, message: ActorMessage) -> None:
        """
        Generate coordination status report.

        Content: (none required)
        """
        try:
            # Task statistics
            task_stats = {
                "total": len(self._tasks),
                "by_status": {},
                "by_priority": {},
            }

            for task in self._tasks.values():
                status = task.status.value
                task_stats["by_status"][status] = task_stats["by_status"].get(status, 0) + 1

                priority = task.priority
                task_stats["by_priority"][priority] = task_stats["by_priority"].get(priority, 0) + 1

            # Agent statistics
            agent_stats = {
                "total": len(self._agents),
                "idle": sum(1 for a in self._agents.values() if a.status == "idle"),
                "busy": sum(1 for a in self._agents.values() if a.status == "busy"),
                "offline": sum(1 for a in self._agents.values() if a.status == "offline"),
            }

            # Workflow statistics
            workflow_stats = {
                "total": len(self._task_queues),
                "workflows": {wid: len(tids) for wid, tids in self._task_queues.items()},
            }

            report = {
                "timestamp": datetime.now(UTC).isoformat(),
                "task_statistics": task_stats,
                "agent_statistics": agent_stats,
                "workflow_statistics": workflow_stats,
                "resource_pools": self._resource_strategy.get_resource_status(),
            }

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="coordination_report",
                    content=report,
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_coordination_report_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to generate report: {e!s}",
                message.message_type,
            )

    async def _unblock_dependents(self, completed_task_id: str) -> None:
        """Unblock tasks that were waiting on the completed task."""
        dependents = self._dependency_graph.get(completed_task_id, set())

        for dep_id in dependents:
            if dep_id in self._tasks:
                task = self._tasks[dep_id]
                if task.status == TaskStatus.BLOCKED:
                    # Check if all dependencies are satisfied
                    remaining_deps = [
                        d
                        for d in task.dependencies
                        if d in self._tasks and self._tasks[d].status != TaskStatus.COMPLETED
                    ]

                    if not remaining_deps:
                        task.status = TaskStatus.READY
                        logger.info(
                            "task_unblocked",
                            task_id=dep_id,
                        )

    def _topological_sort(self, graph: dict[str, set[str]]) -> list[str]:
        """Perform topological sort on dependency graph."""
        in_degree = {node: len(deps) for node, deps in graph.items()}
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort by priority for deterministic ordering
            queue.sort(key=lambda x: -self._tasks.get(x, CoordinatedTask(x, "", "", [])).priority)
            node = queue.pop(0)
            result.append(node)

            for dependent in self._dependency_graph.get(node, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result

    def _identify_parallel_groups(
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

    def _find_critical_path(self, sorted_tasks: list[str], graph: dict[str, set[str]]) -> list[str]:
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

    async def _send_error(
        self,
        recipient: str,
        error_message: str,
        original_type: str,
    ) -> None:
        """Send error response."""
        await self.send(
            recipient,
            ActorMessage(
                message_type="error",
                content={"error": error_message, "original_type": original_type},
                sender_id=self.agent_id,
            ),
        )

    async def _handle_graph_detect_cycles(self, message: ActorMessage) -> None:
        """Detect cycles in task dependency graph."""
        if not self._task_graph:
            await self._send_error(message.sender_id, _TASKGRAPH_NOT_INIT, message.message_type)
            return
        try:
            result = self._task_graph.detect_cycles()
            if result["has_cycles"] and self._cycle_notification_enabled:
                for cycle in result["cycles"]:
                    await self._notify_steward_of_cycle(cycle)
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="cycle_detection_result",
                    content={
                        "has_cycles": result["has_cycles"],
                        "cycle_count": result["cycle_count"],
                        "cycles": result["cycles"],
                    },
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("graph_detect_cycles_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to detect cycles: {e!s}", message.message_type
            )

    async def _handle_graph_get_metrics(self, message: ActorMessage) -> None:
        """Get task graph metrics."""
        if not self._task_graph:
            await self._send_error(message.sender_id, _TASKGRAPH_NOT_INIT, message.message_type)
            return
        try:
            content = message.content or {}
            task_ids = content.get("task_ids")
            if task_ids:
                {
                    tid: self._task_graph._reverse_adjacency.get(tid, set())  # noqa: SLF001
                    for tid in task_ids
                    if tid in self._task_graph._nodes  # noqa: SLF001
                }
                temp_graph = TaskGraph()
                for tid in task_ids:
                    if tid in self._task_graph._nodes:  # noqa: SLF001
                        temp_graph.add_node(tid)
                for tid in task_ids:
                    for dep in self._task_graph._reverse_adjacency.get(tid, []):  # noqa: SLF001
                        if dep in task_ids:
                            temp_graph.add_edge(dep, tid)
                metrics = temp_graph.get_graph_metrics()
            else:
                metrics = self._task_graph.get_graph_metrics()
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="graph_metrics", content=metrics, sender_id=self.agent_id
                ),
            )
        except Exception as e:
            logger.error("graph_get_metrics_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get metrics: {e!s}", message.message_type
            )

    async def _handle_graph_get_topological_order(self, message: ActorMessage) -> None:
        """Get topological order of tasks."""
        if not self._task_graph:
            await self._send_error(message.sender_id, _TASKGRAPH_NOT_INIT, message.message_type)
            return
        try:
            order = self._task_graph.get_topological_order()
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="topological_order",
                    content={"order": order},
                    sender_id=self.agent_id,
                ),
            )
        except ValueError as e:
            await self._send_error(
                message.sender_id, f"Cannot get topological order: {e}", message.message_type
            )
        except Exception as e:
            logger.error("graph_topological_order_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get order: {e!s}", message.message_type
            )

    async def _handle_sync_register_dependency(self, message: ActorMessage) -> None:
        """Register an agent dependency for tracking."""
        if not self._synchronizer:
            await self._send_error(message.sender_id, _TASKSYNC_NOT_INIT, message.message_type)
            return
        try:
            content = message.content or {}
            dependency_id = await self._synchronizer.register_dependency(
                waiting_agent=content.get("waiting_agent", ""),
                holding_agent=content.get("holding_agent", ""),
                resource_id=content.get("resource_id", ""),
            )
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="dependency_registered",
                    content={"dependency_id": dependency_id},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("sync_register_dependency_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to register dependency: {e!s}", message.message_type
            )

    async def _handle_sync_release_dependency(self, message: ActorMessage) -> None:
        """Release an agent dependency."""
        if not self._synchronizer:
            await self._send_error(message.sender_id, _TASKSYNC_NOT_INIT, message.message_type)
            return
        try:
            content = message.content or {}
            released = await self._synchronizer.release_dependency(content.get("dependency_id", ""))
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="dependency_released",
                    content={"released": released},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("sync_release_dependency_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to release dependency: {e!s}", message.message_type
            )

    async def _handle_sync_detect_deadlock(self, message: ActorMessage) -> None:
        """Detect deadlocks in agent dependencies."""
        if not self._synchronizer:
            await self._send_error(message.sender_id, _TASKSYNC_NOT_INIT, message.message_type)
            return
        try:
            content = message.content or {}
            result = await self._synchronizer.detect_deadlock(content.get("agent_id"))
            if result["has_deadlock"] and self._deadlock_escalation_enabled:
                await self._escalate_deadlock_to_arbiter(result["deadlock_chain"] or [])
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="deadlock_detection_result",
                    content=result,
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("sync_detect_deadlock_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to detect deadlock: {e!s}", message.message_type
            )

    async def _handle_get_coordination_ratio(self, message: ActorMessage) -> None:
        """Get current coordination ratio."""
        if not self._synchronizer:
            await self._send_error(message.sender_id, _TASKSYNC_NOT_INIT, message.message_type)
            return
        try:
            ratio = await self._synchronizer.get_coordination_ratio()
            metrics = self._synchronizer.get_metrics()
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="coordination_ratio",
                    content={
                        "coordination_ratio": ratio,
                        "total_capacity": metrics.total_capacity,
                        "coordination_used": metrics.coordination_used,
                        "is_healthy": ratio <= self._max_coordination_ratio,
                    },
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("get_coordination_ratio_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get ratio: {e!s}", message.message_type
            )

    async def _handle_get_sync_health(self, message: ActorMessage) -> None:
        """Get synchronization health report."""
        if not self._synchronizer:
            await self._send_error(message.sender_id, _TASKSYNC_NOT_INIT, message.message_type)
            return
        try:
            report = await self._synchronizer.emit_health_report()
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="sync_health_report", content=report, sender_id=self.agent_id
                ),
            )
        except Exception as e:
            logger.error("get_sync_health_failed", error=str(e))
            await self._send_error(
                message.sender_id, f"Failed to get health: {e!s}", message.message_type
            )

    async def _notify_steward_of_cycle(self, cycle: list[str]) -> None:
        """Notify Steward when task dependency cycle is detected."""
        logger.info("cycle_detected_notifying_steward", cycle=cycle, coordinator_id=self.agent_id)
        await self.send(
            "steward",
            ActorMessage(
                message_type="cycle_detected",
                content={
                    "cycle_node_ids": cycle,
                    "coordinator_id": self.agent_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "resolution_strategy": "awaiting_steward_guidance",
                },
                sender_id=self.agent_id,
            ),
        )

    async def _escalate_deadlock_to_arbiter(self, deadlock_chain: list[str]) -> None:
        """Escalate deadlock to Arbiter when resolution fails."""
        logger.info(
            "deadlock_escalating_to_arbiter", chain=deadlock_chain, coordinator_id=self.agent_id
        )
        await self.send(
            "arbiter",
            ActorMessage(
                message_type="deadlock_escalation",
                content={
                    "deadlock_chain": deadlock_chain,
                    "coordinator_id": self.agent_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "context": {"attempts_resolved": 0},
                },
                sender_id=self.agent_id,
            ),
        )

    async def _update_coordination_ratio(self) -> float:
        """Update and return current coordination ratio."""
        if not self._synchronizer:
            return 0.0
        metrics = self._synchronizer.get_metrics()
        sync_cost = metrics.active_sync_operations * 0.01
        deadlock_cost = metrics.deadlocks_detected * 0.05
        cycle_cost = metrics.cycles_detected * 0.03
        ratio = min(1.0, sync_cost + deadlock_cost + cycle_cost)
        self._coordination_ratio_history.append(ratio)
        if len(self._coordination_ratio_history) > 100:
            self._coordination_ratio_history.pop(0)
        return ratio

    def _is_coordination_healthy(self, ratio: float) -> bool:
        """Check if coordination ratio is within healthy bounds."""
        return ratio <= self._max_coordination_ratio

    def get_capabilities(self) -> list[str]:
        """Return list of capabilities this agent provides."""
        return [
            "task_coordination",
            "dependency_resolution",
            "workflow_management",
            "agent_synchronization",
            "resource_contention_management",
            "parallel_execution",
            "progress_tracking",
        ]
