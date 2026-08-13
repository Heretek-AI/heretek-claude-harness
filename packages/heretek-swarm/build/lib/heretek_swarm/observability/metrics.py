"""
Metrics collection and monitoring for Heretek Swarm.

Provides real-time metrics collection, consciousness metrics, and agent performance tracking.

Features:
- Per-agent performance metrics
- Aggregate swarm health metrics
- Consciousness metrics (Phi, FEP)
- Cycle detection metrics from workflow engine
- Phi training metrics from training environment
- Real-time metrics collection
- Prometheus format export
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import time

# Import cycle detector and phi training for metrics integration
try:
    from heretek_swarm.consciousness.phi_training import PhiTrainingEnvironment
    from heretek_swarm.workflow.engine import (
        get_cycle_detector_metrics,
    )

    CYCLE_DETECTOR_AVAILABLE = True
except ImportError:
    CYCLE_DETECTOR_AVAILABLE = False
    PhiTrainingEnvironment = None

# Mapping from PhiCalculator qualitative labels to numeric values
_MAPPING_INTEGRATION = {
    "very_high": 1.0,
    "high": 0.75,
    "moderate": 0.5,
    "low": 0.25,
    "minimal": 0.1,
    "unknown": 0.0,
}
_MAPPING_DIFFERENTIATION = {
    "very_high": 1.0,
    "high": 0.75,
    "moderate": 0.5,
    "low": 0.25,
    "minimal": 0.1,
    "unknown": 0.0,
}


@dataclass
class AgentMetrics:
    """Metrics for an individual agent."""

    agent_id: str
    agent_type: str = "worker"
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_task_duration_ms: float = 0.0
    avg_task_duration_seconds: float = 0.0
    success_rate: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    error_count: int = 0
    health_score: float = 0.0
    last_activity: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "avg_task_duration_ms": self.avg_task_duration_ms,
            "avg_task_duration_seconds": self.avg_task_duration_seconds,
            "success_rate": self.success_rate,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "error_count": self.error_count,
            "health_score": self.health_score,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


@dataclass
class SwarmMetricsData:
    """Aggregate metrics for the entire swarm."""

    total_agents: int = 0
    active_agents: int = 0
    idle_agents: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_messages: int = 0
    avg_message_latency_ms: float = 0.0
    health_score: float = 100.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_agents": self.total_agents,
            "active_agents": self.active_agents,
            "idle_agents": self.idle_agents,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_messages": self.total_messages,
            "avg_message_latency_ms": self.avg_message_latency_ms,
            "health_score": self.health_score,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConsciousnessMetricsData:
    """Consciousness metrics (IIT Phi and FEP)."""

    phi_score: float = 0.0
    phi_avg: float = 0.0
    phi_max: float = 0.0
    phi_min: float = 0.0
    integration_level: float = 0.0
    differentiation_level: float = 0.0
    free_energy_avg: float = 0.0
    free_energy_variance: float = 0.0
    agent_phi_scores: dict[str, float] = field(default_factory=dict)
    agent_fep_scores: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "phi_score": self.phi_score,
            "phi_avg": self.phi_avg,
            "phi_max": self.phi_max,
            "phi_min": self.phi_min,
            "integration_level": self.integration_level,
            "differentiation_level": self.differentiation_level,
            "free_energy_avg": self.free_energy_avg,
            "free_energy_variance": self.free_energy_variance,
            "agent_phi_scores": self.agent_phi_scores,
            "agent_fep_scores": self.agent_fep_scores,
            "timestamp": self.timestamp.isoformat(),
        }


class SwarmMetricsCollector:
    """
    Collects and aggregates metrics from all agents in the swarm.

    Features:
    - Per-agent performance metrics
    - Aggregate swarm health metrics
    - Consciousness metrics (Phi, FEP)
    - Real-time metrics collection
    """

    def __init__(self) -> None:
        self._agent_metrics: dict[str, AgentMetrics] = {}
        self._agent_states: dict[str, str] = {}
        self._message_latencies: list[float] = []
        self._task_durations: list[float] = []
        self._swarm_metrics_history: list[SwarmMetricsData] = []
        self._consciousness_metrics_history: list[ConsciousnessMetricsData] = []
        self._start_time = datetime.now(UTC)
        self._consciousness_callback: callable | None = None
        self._agent_state_callback: callable | None = None

    def record_agent_activity(
        self,
        agent_id: str,
        task_completed: bool = False,
        task_failed: bool = False,
        task_duration_ms: float = 0.0,
        message_sent: bool = False,
        message_received: bool = False,
        error: bool = False,
        agent_type: str = "worker",
    ) -> None:
        """Record activity for an agent."""
        if agent_id not in self._agent_metrics:
            self._agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id, agent_type=agent_type)

        metrics = self._agent_metrics[agent_id]
        metrics.last_activity = datetime.now(UTC)

        if task_completed:
            metrics.tasks_completed += 1
            if task_duration_ms > 0:
                self._task_durations.append(task_duration_ms)
                metrics.avg_task_duration_ms = sum(self._task_durations) / len(self._task_durations)
                metrics.avg_task_duration_seconds = metrics.avg_task_duration_ms / 1000.0

        if task_failed:
            metrics.tasks_failed += 1

        # Update success rate
        total = metrics.tasks_completed + metrics.tasks_failed
        if total > 0:
            metrics.success_rate = metrics.tasks_completed / total

        if message_sent:
            metrics.messages_sent += 1

        if message_received:
            metrics.messages_received += 1

        if error:
            metrics.error_count += 1

        # Update health score
        self._update_health_score(metrics)

    def record_actor_execution(self, agent_id: str, duration_ms: float) -> None:
        """
        Record actor message processing duration.

        Appends duration to the rolling task_durations window, recomputes
        avg_task_duration_ms and avg_task_duration_seconds on the agent's
        AgentMetrics entry.  Unlike record_agent_activity, this does NOT
        increment task counters — it is for passive timing instrumentation.

        Rolling window: capped at 10 000 entries; trimmed to the most recent
        5 000 when the cap is exceeded.

        Args:
            agent_id: The agent identifier.
            duration_ms: Processing duration in milliseconds.
        """
        # Ensure agent metrics entry exists
        if agent_id not in self._agent_metrics:
            self._agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id)

        metrics = self._agent_metrics[agent_id]
        metrics.last_activity = datetime.now(UTC)

        # Append to rolling window
        self._task_durations.append(duration_ms)
        if len(self._task_durations) > 10000:
            self._task_durations = self._task_durations[-5000:]

        # Recompute averages
        if self._task_durations:
            avg_ms = sum(self._task_durations) / len(self._task_durations)
            metrics.avg_task_duration_ms = avg_ms
            metrics.avg_task_duration_seconds = avg_ms / 1000.0

    def update_agent_state(self, agent_id: str, state: str) -> None:
        """Update agent state (alias for backward compatibility)."""
        if agent_id not in self._agent_metrics:
            self._agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id)
        self._agent_metrics[agent_id].last_activity = datetime.now(UTC)
        self._agent_states[agent_id] = state

    def record_agent_task(
        self,
        agent_id: str,
        duration_seconds: float,
        success: bool,
        agent_type: str = "worker",
    ) -> None:
        """Record agent task completion."""
        task_completed = success
        task_failed = not success
        self.record_agent_activity(
            agent_id,
            task_completed=task_completed,
            task_failed=task_failed,
            task_duration_ms=duration_seconds * 1000,
            error=task_failed,  # Task failure counts as an error
            agent_type=agent_type,
        )

    def record_agent_message(self, agent_id: str, sent: bool, latency_seconds: float = 0.0) -> None:
        """Record agent message sent or received."""
        if sent:
            self.record_agent_activity(agent_id, message_sent=True)
        else:
            self.record_agent_activity(agent_id, message_received=True)
        if latency_seconds > 0:
            self.record_message_latency(latency_seconds * 1000)

    def _update_health_score(self, metrics: AgentMetrics) -> None:
        """Calculate agent health score based on various factors."""
        # Base score
        score = 100.0

        # Penalize errors
        score -= min(metrics.error_count * 5, 30)

        # Penalize failures
        total_tasks = metrics.tasks_completed + metrics.tasks_failed
        if total_tasks > 0:
            failure_rate = metrics.tasks_failed / total_tasks
            score -= failure_rate * 20

        # Penalize inactivity (if no activity in last 5 minutes)
        if metrics.last_activity:
            inactive_seconds = (datetime.now(UTC) - metrics.last_activity).total_seconds()
            if inactive_seconds > 300:
                score -= min((inactive_seconds - 300) / 60, 20)

        metrics.health_score = max(0, min(100, score))

    def record_message_latency(self, latency_ms: float) -> None:
        """Record message latency."""
        self._message_latencies.append(latency_ms)
        # Keep only last 1000 measurements
        if len(self._message_latencies) > 1000:
            self._message_latencies = self._message_latencies[-1000:]

    def _update_states_from_callback(self) -> None:
        """Update agent states from registered callback."""
        if self._agent_state_callback:
            states = self._agent_state_callback()
            for agent_id, state in states.items():
                self._agent_states[agent_id] = state

    def _count_active_idle_agents(self) -> tuple[int, int]:
        """Count active and idle agents based on state or activity."""
        active_agents = 0
        idle_agents = 0
        now = datetime.now(UTC)

        for agent_id in self._agent_metrics:
            if agent_id in self._agent_states:
                state = self._agent_states[agent_id]
                if state == "active":
                    active_agents += 1
                elif state == "idle":
                    idle_agents += 1
            else:
                metrics = self._agent_metrics[agent_id]
                inactive_seconds = (
                    (now - metrics.last_activity).total_seconds()
                    if metrics.last_activity
                    else float("inf")
                )
                if inactive_seconds < 60:
                    active_agents += 1
                else:
                    idle_agents += 1

        return active_agents, idle_agents

    def _calculate_task_metrics(self) -> tuple[int, int, int, int]:
        """Calculate task-related metrics."""
        total_tasks = 0
        completed_tasks = 0
        failed_tasks = 0
        total_messages = 0

        for m in self._agent_metrics.values():
            total_tasks += m.tasks_completed + m.tasks_failed
            completed_tasks += m.tasks_completed
            failed_tasks += m.tasks_failed
            total_messages += m.messages_sent + m.messages_received

        return total_tasks, completed_tasks, failed_tasks, total_messages

    def collect_swarm_metrics(self) -> SwarmMetricsData:
        """Collect aggregate swarm metrics."""
        self._update_states_from_callback()

        total_agents = len(self._agent_metrics)
        active_agents, idle_agents = self._count_active_idle_agents()
        total_tasks, completed_tasks, failed_tasks, total_messages = self._calculate_task_metrics()

        avg_latency = (
            sum(self._message_latencies) / len(self._message_latencies)
            if self._message_latencies
            else 0
        )
        health_score = (
            sum(m.health_score for m in self._agent_metrics.values()) / len(self._agent_metrics)
            if self._agent_metrics
            else 100.0
        )

        result = SwarmMetricsData(
            total_agents=total_agents,
            active_agents=active_agents,
            idle_agents=idle_agents,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            total_messages=total_messages,
            avg_message_latency_ms=avg_latency,
            health_score=health_score,
        )
        self._swarm_metrics_history.append(result)
        return result

    def get_agent_metrics_history(self, limit: int = 10) -> list[SwarmMetricsData]:
        """Get history of agent metrics."""
        return self._swarm_metrics_history[-limit:] if self._swarm_metrics_history else []

    def get_consciousness_metrics_history(self, limit: int = 10) -> list[ConsciousnessMetricsData]:
        """Get history of consciousness metrics."""
        return (
            self._consciousness_metrics_history[-limit:]
            if self._consciousness_metrics_history
            else []
        )

    def register_consciousness_callback(self, callback: callable) -> None:
        """Register a consciousness metrics callback."""
        self._consciousness_callback = callback

    def register_agent_state_callback(self, callback: callable) -> None:
        """Register an agent state callback."""
        self._agent_state_callback = callback

    def _calculate_agent_health(self, metrics: AgentMetrics) -> float:
        """Calculate health score for an agent."""
        score = 100.0
        score -= min(metrics.error_count * 5, 30)
        total = metrics.tasks_completed + metrics.tasks_failed
        if total > 0:
            score -= (metrics.tasks_failed / total) * 20
        return max(0, min(100, score))

    def _determine_integration_level(self, phi_scores: dict[str, float]) -> str:
        """Determine integration level from phi scores."""
        values = list(phi_scores.values()) if phi_scores else [0]
        avg = sum(values) / len(values)
        if avg >= 0.9:
            return "very_high"
        if avg >= 0.75:
            return "high"
        if avg >= 0.5:
            return "moderate"
        if avg >= 0.25:
            return "low"
        return "minimal"

    def _determine_differentiation_level(self, phi_scores: dict[str, float]) -> str:
        """Determine differentiation level from phi variance."""
        values = list(phi_scores.values()) if phi_scores else [0]
        if len(values) < 2:
            return "minimal"
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance**0.5
        if std_dev > 0.3:
            return "high"
        if std_dev > 0.2:
            return "moderate"
        if std_dev > 0.1:
            return "low"
        return "minimal"

    def collect_agent_metrics(self, agent_id: str) -> AgentMetrics:
        """Get metrics for a specific agent."""
        return self._agent_metrics.get(agent_id, AgentMetrics(agent_id=agent_id))

    def get_all_agent_metrics(self) -> dict[str, AgentMetrics]:
        """Get metrics for all agents."""
        return self._agent_metrics.copy()

    def get_agent_states(self) -> dict[str, str]:
        """Get current states of all agents."""
        states = {}
        now = datetime.now(UTC)
        for agent_id in self._agent_metrics:
            if agent_id in self._agent_states:
                states[agent_id] = self._agent_states[agent_id]
            else:
                metrics = self._agent_metrics[agent_id]
                if metrics.last_activity:
                    inactive_seconds = (now - metrics.last_activity).total_seconds()
                    if inactive_seconds < 60:
                        states[agent_id] = "active"
                    elif inactive_seconds < 300:
                        states[agent_id] = "idle"
                    else:
                        states[agent_id] = "inactive"
                else:
                    states[agent_id] = "unknown"
        return states

    def calculate_health_score(self) -> float:
        """Calculate overall swarm health score."""
        if not self._agent_metrics:
            return 0.0

        avg_health = sum(m.health_score for m in self._agent_metrics.values()) / len(
            self._agent_metrics
        )

        # Factor in error rates
        total_tasks = sum(m.tasks_completed + m.tasks_failed for m in self._agent_metrics.values())
        total_failures = sum(m.tasks_failed for m in self._agent_metrics.values())
        failure_penalty = (total_failures / total_tasks * 10) if total_tasks > 0 else 0

        return max(0, min(100, avg_health - failure_penalty))

    def collect_consciousness_metrics(self) -> ConsciousnessMetricsData:
        """Collect consciousness metrics computed from IIT Phi and FEP calculators."""
        import structlog
        from heretek_swarm.consciousness.fep_active_inference import FreeEnergyCalculator
        from heretek_swarm.consciousness.iit_phi import PhiCalculator

        _log = structlog.get_logger(__name__)

        callback_result = self._consciousness_callback() if self._consciousness_callback else None
        agent_phi_scores = self._compute_phi_scores(callback_result)
        agent_fep_scores = self._compute_fep_scores(callback_result)

        integration_level, differentiation_level = self._compute_phi_levels(
            agent_phi_scores, PhiCalculator, _log
        )

        free_energy_avg, free_energy_variance = self._compute_free_energy(
            agent_fep_scores, FreeEnergyCalculator, _log
        )

        phi_values = list(agent_phi_scores.values()) if agent_phi_scores else [0]
        result = ConsciousnessMetricsData(
            phi_avg=sum(phi_values) / len(phi_values) if phi_values else 0,
            phi_max=max(phi_values) if phi_values else 0,
            phi_min=min(phi_values) if phi_values else 0,
            integration_level=integration_level,
            differentiation_level=differentiation_level,
            free_energy_avg=free_energy_avg,
            free_energy_variance=free_energy_variance,
            agent_phi_scores=agent_phi_scores,
            agent_fep_scores=agent_fep_scores,
        )
        self._consciousness_metrics_history.append(result)
        return result

    def _compute_phi_scores(self, callback_result: dict | None) -> dict[str, float]:
        """Compute agent phi scores from callback or agent metrics."""
        if callback_result and "phi_scores" in callback_result:
            return callback_result["phi_scores"]
        scores: dict[str, float] = {}
        for agent_id, metrics in self._agent_metrics.items():
            activity_score = min(1.0, (metrics.messages_sent + metrics.messages_received) / 100)
            health_factor = metrics.health_score / 100
            scores[agent_id] = activity_score * health_factor
        return scores

    def _compute_fep_scores(self, callback_result: dict | None) -> dict[str, float]:
        """Compute agent FEP scores from callback or agent metrics."""
        if callback_result and "fep_scores" in callback_result:
            return callback_result["fep_scores"]
        scores: dict[str, float] = {}
        for agent_id, metrics in self._agent_metrics.items():
            error_factor = 1 / (1 + metrics.error_count)
            health_factor = metrics.health_score / 100
            scores[agent_id] = error_factor * health_factor
        return scores

    def _compute_phi_levels(
        self, agent_phi_scores: dict[str, float], PhiCalculator: type, _log: Any
    ) -> tuple[float, float]:
        """Compute integration and differentiation levels via PhiCalculator."""
        if not agent_phi_scores:
            _log.warning("consciousness_metrics_empty_agents", reason="no_agent_phi_scores_available")
            return 0.0, 0.0

        try:
            phi_calc = PhiCalculator(strict_validation=False)
            elements = list(agent_phi_scores.keys())
            connectivity = self._build_connectivity(elements)
            psi_state = agent_phi_scores.get(elements[0], 0.5) if elements else 0.5
            ces = {
                "system_id": "swarm-metrics",
                "elements": elements,
                "connectivity": connectivity,
                "current_state": dict.fromkeys(elements, psi_state),
            }
            phi_result = phi_calc.calculate_phi(ces)
            return (
                _MAPPING_INTEGRATION.get(phi_result.integration_level, 0.5),
                _MAPPING_DIFFERENTIATION.get(phi_result.differentiation_level, 0.5),
            )
        except Exception:
            _log.warning("phi_calculator_failed", exc_info=True)
            return 0.0, 0.0

    def _build_connectivity(self, elements: list[str]) -> dict[str, dict[str, float]]:
        """Build connectivity matrix from agent metrics."""
        connectivity: dict[str, dict[str, float]] = {}
        for aid, metrics in self._agent_metrics.items():
            if aid not in elements:
                continue
            total_interactions = metrics.messages_sent + metrics.messages_received
            if total_interactions > 0:
                connectivity[aid] = {
                    other: min(1.0, total_interactions / 100)
                    for other in elements if other != aid
                }
            else:
                connectivity[aid] = {other: 0.1 for other in elements if other != aid}
        return connectivity

    def _compute_free_energy(
        self, agent_fep_scores: dict[str, float], FreeEnergyCalculator: type, _log: Any
    ) -> tuple[float, float]:
        """Compute free energy avg and variance via FEP calculator."""
        free_energy_values = self._calculate_free_energy_values(FreeEnergyCalculator, _log)

        if free_energy_values:
            avg = sum(free_energy_values) / len(free_energy_values)
            variance = sum((v - avg) ** 2 for v in free_energy_values) / len(free_energy_values)
            return avg, variance

        if agent_fep_scores:
            fe_values = list(agent_fep_scores.values())
            avg = sum(fe_values) / len(fe_values)
            variance = sum((v - avg) ** 2 for v in fe_values) / len(fe_values)
            _log.warning("free_energy_calculator_fallback", reason="using_agent_fep_scores_fallback")
            return avg, variance

        _log.warning("free_energy_calculator_empty", reason="no_agent_fep_scores_or_calculations")
        return 0.0, 0.0

    def _calculate_free_energy_values(
        self, FreeEnergyCalculator: type, _log: Any
    ) -> list[float]:
        """Calculate free energy for each agent."""
        values: list[float] = []
        fep_calc = FreeEnergyCalculator(strict_validation=False)
        for agent_id, metrics in self._agent_metrics.items():
            try:
                observations = {
                    "agent_id": agent_id,
                    "task_success": 1 if metrics.tasks_completed > metrics.tasks_failed else 0,
                    "active": 1 if metrics.messages_sent > 0 else 0,
                }
                generative_model = {
                    "likelihood": {
                        "task_success": {"1": 0.8, "0": 0.2},
                        "active": {"1": 0.7, "0": 0.3},
                    },
                    "prior": {
                        "task_success": {"1": 0.5, "0": 0.5},
                        "active": {"1": 0.5, "0": 0.5},
                    },
                }
                fe = fep_calc.calculate_free_energy(observations, generative_model)
                values.append(fe)
            except Exception:
                _log.warning("fep_calculator_failed", agent_id=agent_id, exc_info=True)
        return values


class RealTimeMetricsStream:
    """
    Real-time metrics streaming for observability.

    Provides:
    - Periodic metrics snapshots
    - WebSocket streaming support
    - Prometheus format export
    """

    def __init__(self, collector: SwarmMetricsCollector):
        self._collector = collector
        self._snapshot_interval = 5  # seconds
        self._last_snapshot: SwarmMetricsData | None = None
        self._running: bool = False
        self._snapshot: MetricsSnapshot | None = None

    def stop_streaming(self) -> None:
        """Stop the metrics streaming."""
        self._running = False

    def get_metrics_snapshot(self) -> "MetricsSnapshot":
        """Get current metrics snapshot."""
        # Return cached snapshot if available
        if self._snapshot is not None:
            return self._snapshot

        swarm = self._collector.collect_swarm_metrics()
        consciousness = self._collector.collect_consciousness_metrics()
        agents = self._collector.get_all_agent_metrics()
        health = self._collector.calculate_health_score()
        self._snapshot = MetricsSnapshot(
            swarm_metrics=swarm,
            consciousness_metrics=consciousness,
            agent_metrics=agents,
            health_score=health,
        )
        return self._snapshot

    async def stream_metrics(self, interval_seconds: float = 1.0) -> dict[str, Any]:
        """
        Stream metrics at regular intervals.

        Args:
            interval_seconds: Interval between metrics snapshots.

        Yields:
            Dictionary containing metrics snapshot data.
        """
        import asyncio

        while self._running:
            snapshot = self.get_metrics_snapshot()
            yield {
                "swarm_metrics": snapshot.swarm_metrics.to_dict(),
                "consciousness_metrics": snapshot.consciousness_metrics.to_dict(),
                "agent_metrics": {aid: am.to_dict() for aid, am in snapshot.agent_metrics.items()},
                "health_score": snapshot.health_score,
            }
            await asyncio.sleep(interval_seconds)

    def _export_swarm_metrics(self, metrics: SwarmMetricsData) -> list[str]:
        """Export swarm metrics as Prometheus format lines."""
        return [
            "# HELP heretek_swarm_total_agents Total number of agents",
            "# TYPE heretek_swarm_total_agents gauge",
            f"heretek_swarm_total_agents {metrics.total_agents}",
            "",
            "# HELP heretek_swarm_active_agents Number of active agents",
            "# TYPE heretek_swarm_active_agents gauge",
            f"heretek_swarm_active_agents {metrics.active_agents}",
            "",
            "# HELP heretek_swarm_health_score Overall swarm health score",
            "# TYPE heretek_swarm_health_score gauge",
            f"heretek_swarm_health_score {metrics.health_score}",
            "",
            "# HELP heretek_swarm_total_tasks Total tasks processed",
            "# TYPE heretek_swarm_total_tasks counter",
            f"heretek_swarm_total_tasks {metrics.total_tasks}",
            "",
        ]

    def _export_consciousness_metrics(self, consciousness: ConsciousnessMetricsData) -> list[str]:
        """Export consciousness metrics as Prometheus format lines."""
        return [
            "# HELP heretek_swarm_consciousness_phi_avg Average consciousness phi score",
            "# TYPE heretek_swarm_consciousness_phi_avg gauge",
            f"heretek_swarm_consciousness_phi_avg {consciousness.phi_avg}",
            "",
            "# HELP heretek_swarm_consciousness_phi_max Maximum consciousness phi score",
            "# TYPE heretek_swarm_consciousness_phi_max gauge",
            f"heretek_swarm_consciousness_phi_max {consciousness.phi_max}",
            "",
            "# HELP heretek_swarm_consciousness_fep_avg Average free energy score",
            "# TYPE heretek_swarm_consciousness_fep_avg gauge",
            f"heretek_swarm_consciousness_fep_avg {consciousness.free_energy_avg}",
            "",
        ]

    def _export_cycle_metrics(self) -> list[str]:
        """Export cycle detection metrics if available."""
        lines = []
        if CYCLE_DETECTOR_AVAILABLE:
            try:
                cycle_metrics = get_cycle_detector_metrics()
                if cycle_metrics:
                    lines.extend(
                        [
                            "# HELP heretek_workflow_cycles_total Total number of workflow cycles detected",  # noqa: E501
                            "# TYPE heretek_workflow_cycles_total counter",
                            f"heretek_workflow_cycles_total {cycle_metrics.get('total_cycles_detected', 0)}",  # noqa: E501
                            "",
                            "# HELP heretek_workflow_cycles_broken_total Total number of workflow cycles broken",  # noqa: E501
                            "# TYPE heretek_workflow_cycles_broken_total counter",
                            f"heretek_workflow_cycles_broken_total {cycle_metrics.get('total_cycles_broken', 0)}",  # noqa: E501
                            "",
                            "# HELP heretek_workflow_avg_iterations_before_cycle Average iterations before cycle detection",  # noqa: E501
                            "# TYPE heretek_workflow_avg_iterations_before_cycle gauge",
                            f"heretek_workflow_avg_iterations_before_cycle {cycle_metrics.get('avg_iterations_before_cycle', 0)}",  # noqa: E501
                            "",
                        ]
                    )
                    for strategy, count in cycle_metrics.get("cycles_by_strategy", {}).items():
                        lines.extend(
                            [
                                "# HELP heretek_workflow_cycles_by_strategy Cycles broken by strategy",  # noqa: E501
                                "# TYPE heretek_workflow_cycles_by_strategy gauge",
                                f'heretek_workflow_cycles_by_strategy{{strategy="{strategy}"}} {count}',  # noqa: E501
                                "",
                            ]
                        )
            except Exception as e:
                lines.append(f"# Cycle detection metrics unavailable: {e}")
                lines.append("")
        return lines

    def _export_phi_training_metrics(self) -> list[str]:
        """Export Phi training metrics if available."""
        lines = []
        if CYCLE_DETECTOR_AVAILABLE and PhiTrainingEnvironment:
            try:
                lines.extend(
                    [
                        "# HELP heretek_phi_training_episodes_total Total Phi training episodes",
                        "# TYPE heretek_phi_training_episodes_total counter",
                        "heretek_phi_training_episodes_total 0",
                        "",
                        "# HELP heretek_phi_training_success_total Successful Phi training episodes",  # noqa: E501
                        "# TYPE heretek_phi_training_success_total counter",
                        "heretek_phi_training_success_total 0",
                        "",
                        "# HELP heretek_phi_training_avg_improvement Average Phi improvement per episode",  # noqa: E501
                        "# TYPE heretek_phi_training_avg_improvement gauge",
                        "heretek_phi_training_avg_improvement 0",
                        "",
                        "# HELP heretek_phi_training_best_phi Best Phi achieved in training",
                        "# TYPE heretek_phi_training_best_phi gauge",
                        "heretek_phi_training_best_phi 0",
                        "",
                    ]
                )
            except Exception as e:
                lines.append(f"# Phi training metrics unavailable: {e}")
        return lines

    def _export_agent_phi_scores(self, consciousness: ConsciousnessMetricsData) -> list[str]:
        """Export per-agent Phi scores."""
        lines = []
        for agent_id, phi_score in consciousness.agent_phi_scores.items():
            lines.extend(
                [
                    "# HELP heretek_agent_phi Agent Phi score",
                    "# TYPE heretek_agent_phi gauge",
                    f'heretek_agent_phi{{agent_id="{agent_id}"}} {phi_score}',
                    "",
                ]
            )
        return lines

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        metrics = self._collector.collect_swarm_metrics()
        consciousness = self._collector.collect_consciousness_metrics()

        lines = (
            self._export_swarm_metrics(metrics)
            + self._export_consciousness_metrics(consciousness)
            + self._export_cycle_metrics()
            + self._export_phi_training_metrics()
            + self._export_agent_phi_scores(consciousness)
        )
        return "\n".join(lines)


_metrics_collector: SwarmMetricsCollector | None = None


def get_metrics_collector() -> SwarmMetricsCollector:
    """Get or create the singleton SwarmMetricsCollector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = SwarmMetricsCollector()
    return _metrics_collector


def record_actor_execution(agent_id: str, duration_ms: float) -> None:
    """
    Convenience function to record actor execution duration via the singleton collector.

    Safe for use from actor hot paths — no per-call Collector allocation.
    Uses the module-level singleton from get_metrics_collector().

    Args:
        agent_id: The agent identifier.
        duration_ms: Processing duration in milliseconds.
    """
    get_metrics_collector().record_actor_execution(agent_id, duration_ms)


@dataclass
class MetricsSnapshot:
    """Snapshot of metrics at a point in time."""

    swarm_metrics: SwarmMetricsData = field(default_factory=lambda: SwarmMetricsData())
    consciousness_metrics: ConsciousnessMetricsData = field(
        default_factory=lambda: ConsciousnessMetricsData()
    )
    agent_metrics: dict[str, AgentMetrics] = field(default_factory=dict)
    health_score: float = 0.0
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "swarm_metrics": self.swarm_metrics.to_dict(),
            "consciousness_metrics": self.consciousness_metrics.to_dict(),
            "agent_metrics": {k: v.to_dict() for k, v in self.agent_metrics.items()},
            "health_score": self.health_score,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


async def record_consensus_round(round_id: str, result: dict[str, Any]) -> None:
    """Record consensus round metrics."""
    from heretek_swarm.infrastructure.otel.logging import get_logger

    logger = get_logger(__name__)
    logger.debug("consensus_round_recorded", round_id=round_id, result=result)


async def record_message_sent(message_id: str, agent_id: str, metadata: dict[str, Any]) -> None:
    """Record message sent metrics."""
    from heretek_swarm.infrastructure.otel.logging import get_logger

    logger = get_logger(__name__)
    logger.debug("message_sent_recorded", message_id=message_id, agent_id=agent_id)


async def record_task_completion(
    task_id: str, agent_id: str, success: bool, metadata: dict[str, Any]
) -> None:
    """Record task completion metrics."""
    from heretek_swarm.infrastructure.otel.logging import get_logger

    logger = get_logger(__name__)
    logger.debug("task_completion_recorded", task_id=task_id, success=success)
