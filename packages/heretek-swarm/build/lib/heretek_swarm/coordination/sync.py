"""Synchronization mechanisms with deadlock detection and coordination ratio tracking."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class DeadlockState(Enum):
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    RESOLVING = "resolving"
    RESOLVED = "resolved"

class EscalationLevel(Enum):
    NONE = "none"
    COORDINATOR = "coordinator"
    STEWARD = "steward"
    ARBITER = "arbiter"
    HUMAN = "human"

@dataclass
class AgentDependency:
    dependency_id: str
    waiting_agent_id: str
    holding_agent_id: str
    resource_id: str
    wait_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    state: DeadlockState = DeadlockState.NONE
    cycle_detected: bool = False

    @property
    def wait_duration(self) -> timedelta:
        return datetime.now(UTC) - self.wait_start

    @property
    def is_expired(self) -> bool:
        return self.wait_duration > self.timeout

@dataclass
class CoordinationMetrics:
    total_capacity: float = 1.0
    coordination_used: float = 0.0
    coordination_ratio: float = 0.0
    active_sync_operations: int = 0
    pending_dependencies: int = 0
    deadlocks_detected: int = 0
    cycles_detected: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_capacity": self.total_capacity,
            "coordination_used": self.coordination_used,
            "coordination_ratio": self.coordination_ratio,
            "active_sync_operations": self.active_sync_operations,
            "pending_dependencies": self.pending_dependencies,
            "deadlocks_detected": self.deadlocks_detected,
            "cycles_detected": self.cycles_detected,
            "last_updated": self.last_updated.isoformat(),
        }

class TaskSynchronizer:
    def __init__(
        self,
        deadlock_timeout: timedelta = timedelta(seconds=30),
        max_retries: int = 3,
        coordination_budget: float = 0.35,
    ):
        self._dependencies: dict[str, AgentDependency] = {}
        self._agent_locks: dict[str, set[str]] = {}
        self._wait_for_graph: dict[str, set[str]] = {}
        self._deadlock_timeout = deadlock_timeout
        self._max_retries = max_retries
        self._coordination_budget = coordination_budget
        self._metrics = CoordinationMetrics()
        self._steward_client: Any = None
        self._arbiter_client: Any = None
        self._on_cycle_detected: Any = None
        self._on_deadlock_detected: Any = None

    async def register_dependency(
        self,
        waiting_agent: str,
        holding_agent: str,
        resource_id: str,
    ) -> str:
        dependency_id = str(uuid.uuid4())
        dep = AgentDependency(
            dependency_id=dependency_id,
            waiting_agent_id=waiting_agent,
            holding_agent_id=holding_agent,
            resource_id=resource_id,
        )
        self._dependencies[dependency_id] = dep
        if holding_agent not in self._agent_locks:
            self._agent_locks[holding_agent] = set()
        self._agent_locks[holding_agent].add(resource_id)
        if waiting_agent not in self._wait_for_graph:
            self._wait_for_graph[waiting_agent] = set()
        self._wait_for_graph[waiting_agent].add(holding_agent)
        self._metrics.pending_dependencies = len(self._dependencies)
        self._metrics.active_sync_operations += 1
        await self.record_coordination_usage("register_dependency", 0.01)
        return dependency_id

    async def release_dependency(self, dependency_id: str) -> bool:
        if dependency_id not in self._dependencies:
            return False
        dep = self._dependencies[dependency_id]
        if dep.holding_agent_id in self._agent_locks:
            self._agent_locks[dep.holding_agent_id].discard(dep.resource_id)
        if dep.waiting_agent_id in self._wait_for_graph:
            self._wait_for_graph[dep.waiting_agent_id].discard(dep.holding_agent_id)
        del self._dependencies[dependency_id]
        self._metrics.pending_dependencies = len(self._dependencies)
        self._metrics.active_sync_operations = max(0, self._metrics.active_sync_operations - 1)
        await self.record_coordination_usage("release_dependency", 0.005)
        return True

    async def get_blocking_agents(self, agent_id: str) -> list[str]:
        return list(self._wait_for_graph.get(agent_id, set()))

    async def detect_deadlock(self, agent_id: str | None = None) -> dict[str, Any]:
        cycle = self._detect_wait_for_cycle()
        has_deadlock = cycle is not None
        if has_deadlock:
            self._metrics.deadlocks_detected += 1
            await self.record_coordination_usage("deadlock_detection", 0.05)
        suspected = list(self._wait_for_graph.keys()) if agent_id is None else [agent_id]
        return {
            "has_deadlock": has_deadlock,
            "deadlock_chain": cycle,
            "suspected_agents": suspected,
            "detection_time": datetime.now(UTC),
        }

    async def check_deadlock_timeout(self) -> list[AgentDependency]:
        expired = [dep for dep in self._dependencies.values() if dep.is_expired]
        for dep in expired:
            dep.state = DeadlockState.SUSPECTED
        return expired

    async def resolve_deadlock(
        self,
        deadlock_chain: list[str],
        strategy: str = "escalate",
    ) -> dict[str, Any]:
        agents_notified: list[str] = []
        escalation_level = EscalationLevel.NONE
        resolved = False
        if strategy == "timeout":
            resolved, agents_notified = await self._resolve_by_timeout()
            escalation_level = EscalationLevel.COORDINATOR
        elif strategy == "negotiate":
            resolved, agents_notified = await self._resolve_by_negotiation(deadlock_chain)
            escalation_level = EscalationLevel.STEWARD
        elif strategy == "escalate":
            await self.escalate_to_arbiter(deadlock_chain, {})
            escalation_level = EscalationLevel.ARBITER
            resolved = True
        self._mark_deadlock_resolved(deadlock_chain)
        await self.record_coordination_usage("deadlock_resolution", 0.02)
        return {
            "resolved": resolved,
            "action": strategy,
            "agents_notified": agents_notified,
            "escalation_level": escalation_level,
        }

    async def _resolve_by_timeout(self) -> tuple[bool, list[str]]:
        agents_notified: list[str] = []
        resolved = False
        for dep in self._dependencies.values():
            if dep.is_expired:
                dep.state = DeadlockState.RESOLVING
                await self.release_dependency(dep.dependency_id)
                resolved = True
                agents_notified.append(dep.waiting_agent_id)
        return resolved, agents_notified

    async def _resolve_by_negotiation(self, deadlock_chain: list[str]) -> tuple[bool, list[str]]:
        agents_notified: list[str] = []
        resolved = False
        for agent_id in deadlock_chain:
            if agent_id in self._agent_locks:
                self._agent_locks[agent_id].clear()
                resolved = True
                agents_notified.append(agent_id)
        return resolved, agents_notified

    def _mark_deadlock_resolved(self, deadlock_chain: list[str]) -> None:
        for dep in self._dependencies.values():
            if dep.waiting_agent_id in deadlock_chain:
                dep.state = DeadlockState.RESOLVED

    async def escalate_to_arbiter(
        self,
        deadlock_chain: list[str],  # noqa: ARG002
        context: dict[str, Any],  # noqa: ARG002
    ) -> str:
        escalation_id = str(uuid.uuid4())
        await self.record_coordination_usage("arbiter_escalation", 0.05)
        return escalation_id

    async def notify_cycle_detected(
        self,
        cycle: list[str],
        graph_snapshot: dict[str, Any],
    ) -> None:
        self._metrics.cycles_detected += 1
        await self.record_coordination_usage("cycle_notification", 0.02)
        if self._on_cycle_detected:
            await self._on_cycle_detected(cycle, graph_snapshot)

    async def record_coordination_usage(self, _operation_type: str, cost: float) -> None:
        self._metrics.coordination_used += cost
        self._metrics.coordination_ratio = (
            self._metrics.coordination_used / self._metrics.total_capacity
        )
        self._metrics.last_updated = datetime.now(UTC)

    async def get_coordination_ratio(self) -> float:
        return min(1.0, self._metrics.coordination_ratio)

    async def pause_coordination_if_needed(self) -> bool:
        ratio = await self.get_coordination_ratio()
        if ratio > self._coordination_budget:
            await self.record_coordination_usage("coordination_paused", 0.0)
            return True
        return False

    def get_metrics(self) -> CoordinationMetrics:
        return self._metrics

    async def emit_health_report(self) -> dict[str, Any]:
        return {
            "coordination_ratio": self._metrics.coordination_ratio,
            "active_sync_operations": self._metrics.active_sync_operations,
            "pending_dependencies": self._metrics.pending_dependencies,
            "deadlocks_detected": self._metrics.deadlocks_detected,
            "cycles_detected": self._metrics.cycles_detected,
            "is_healthy": self._metrics.coordination_ratio <= self._coordination_budget,
        }

    def _detect_wait_for_cycle(self) -> list[str] | None:
        WHITE = 0
        GRAY = 1
        BLACK = 2
        color: dict[str, int] = dict.fromkeys(self._wait_for_graph, WHITE)
        parent: dict[str, str | None] = dict.fromkeys(self._wait_for_graph)
        cycle_path: list[str] | None = None

        def dfs(agent: str) -> bool:
            nonlocal cycle_path
            color[agent] = GRAY
            for neighbor in self._wait_for_graph.get(agent, set()):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    path = [agent, neighbor]
                    current = agent
                    while current != neighbor and parent[current] is not None:
                        current = parent[current]
                        path.append(current)
                    if cycle_path is None or len(path) < len(cycle_path):
                        cycle_path = path
                    return True
                if color[neighbor] == WHITE:
                    parent[neighbor] = agent
                    if dfs(neighbor):
                        return True
            color[agent] = BLACK
            return False

        for agent in self._wait_for_graph:
            if color[agent] == WHITE and dfs(agent):
                return cycle_path
        return None
