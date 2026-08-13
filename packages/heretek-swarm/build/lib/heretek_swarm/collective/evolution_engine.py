"""
Evolution Engine - Organic Capability Development Tracking

Extracted from emergent_detection.py as part of Phase 3 refactor.
Tracks and manages organic capability development in the swarm.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from .emergent_detection_types import (
    AgentCapabilitySnapshot,
    CapabilityRecord,
    EvolutionMetrics,
    EvolutionPhase,
)

logger = structlog.get_logger(__name__)


class EvolutionEngine:
    """
    Evolution Engine for tracking and managing organic capability development.

    Key Metrics:
        - evolution_rate: Speed of capability development (capabilities/hour)
        - fitness_landscape: Current environment-agent fit (0-1)
        - adaptability_index: How quickly swarm adapts to changes (0-1)
    """

    def __init__(
        self,
        capability_window_hours: float = 24.0,
        stabilization_threshold: float = 0.8,
        min_fitness_samples: int = 10,
    ):
        self._capability_records: dict[str, CapabilityRecord] = {}
        self._agent_snapshots: dict[str, list[AgentCapabilitySnapshot]] = {}
        self._capability_history: list[CapabilityRecord] = []

        self._evolution_start: str = datetime.now(UTC).isoformat()
        self._last_evolution_check: str = datetime.now(UTC).isoformat()
        self._generation_counter: int = 0

        self._capability_window_hours = capability_window_hours
        self._stabilization_threshold = stabilization_threshold
        self._min_fitness_samples = min_fitness_samples

        self._metrics = EvolutionMetrics()

        self._on_capability_emerged: list[Callable] = []
        self._on_capability_stabilized: list[Callable] = []
        self._on_evolution_phase_changed: list[Callable] = []

        logger.info(
            "evolution_engine_initialized",
            capability_window_hours=capability_window_hours,
            stabilization_threshold=stabilization_threshold,
        )

    def register_capability_emerged_callback(self, callback: Callable) -> None:
        self._on_capability_emerged.append(callback)

    def register_capability_stabilized_callback(self, callback: Callable) -> None:
        self._on_capability_stabilized.append(callback)

    def register_phase_changed_callback(self, callback: Callable) -> None:
        self._on_evolution_phase_changed.append(callback)

    def record_capability_gain(
        self,
        agent_id: str,
        capability_type: str,
        capability_name: str,
        fitness_contribution: float = 0.0,
        description: str = "",
        contributing_agents: list[str] | None = None,
    ) -> CapabilityRecord:
        existing_key = f"{capability_type}:{capability_name}"
        if existing_key in self._capability_records:
            record = self._capability_records[existing_key]
            record.last_reinforced = datetime.now(UTC).isoformat()
            if agent_id not in record.contributing_agents:
                record.contributing_agents.append(agent_id)
            return record

        start_time = datetime.fromisoformat(self._evolution_start)
        development_time = (datetime.now(UTC) - start_time).total_seconds()

        total_capabilities = len(self._capability_history)
        hours_elapsed = max(development_time / 3600, 0.001)
        evolution_rate = (total_capabilities + 1) / hours_elapsed

        record = CapabilityRecord(
            capability_type=capability_type,
            capability_name=capability_name,
            description=description,
            origin_agent_id=agent_id,
            contributing_agents=contributing_agents or [agent_id],
            development_time_seconds=development_time,
            evolution_rate=evolution_rate,
            fitness_contribution=fitness_contribution,
        )

        self._capability_records[existing_key] = record
        self._capability_history.append(record)

        self._update_agent_capabilities(agent_id, capability_type, capability_name)
        self._update_evolution_metrics()

        asyncio.create_task(self._call_capability_emerged_callbacks(record))  # noqa: RUF006

        logger.info(
            "capability_recorded",
            capability_type=capability_type,
            capability_name=capability_name,
            agent_id=agent_id,
            evolution_rate=evolution_rate,
        )

        return record

    def detect_evolution(
        self,
        agent_states: dict[str, dict[str, Any]],
    ) -> list[CapabilityRecord]:
        new_capabilities = []

        for agent_id, state in agent_states.items():
            prev_snapshot = self._get_latest_snapshot(agent_id)

            current_caps = state.get("capability_levels", {})
            state.get("fitness_score", 0.0)
            state.get("behaviors", [])

            if prev_snapshot:
                for cap_type, level in current_caps.items():
                    prev_level = prev_snapshot.capability_levels.get(cap_type, 0.0)

                    if level > prev_level + 0.2 and level > 0.5:
                        record = self.record_capability_gain(
                            agent_id=agent_id,
                            capability_type=cap_type,
                            capability_name=f"{cap_type}_level_{int(level * 100)}",
                            fitness_contribution=level - prev_level,
                            description=f"Advanced {cap_type} capability",
                        )
                        new_capabilities.append(record)

            self._create_agent_snapshot(agent_id, state)

        self._update_evolution_metrics()

        return new_capabilities

    def assess_fitness(
        self,
        agent_id: str,  # noqa: ARG002
        performance_history: list[float],
        capability_levels: dict[str, float],
        environment_demand: dict[str, float] | None = None,
    ) -> float:
        if not performance_history:
            return 0.0

        recent_perf = (
            performance_history[-10:] if len(performance_history) >= 10 else performance_history
        )
        base_fitness = sum(recent_perf) / len(recent_perf)

        if capability_levels:
            capability_fitness = sum(capability_levels.values()) / len(capability_levels)
        else:
            capability_fitness = 0.5

        if len(performance_history) >= 10:
            early_avg = sum(performance_history[:5]) / 5
            late_avg = sum(performance_history[-5:]) / 5
            trend = (late_avg - early_avg) / max(early_avg, 0.01)
            trend_fitness = max(0, min(1, 0.5 + trend))
        else:
            trend_fitness = 0.5

        if environment_demand:
            alignment_scores = []
            for cap_type, demand_level in environment_demand.items():
                current_level = capability_levels.get(cap_type, 0.0)
                alignment = 1.0 - abs(current_level - demand_level)
                alignment_scores.append(max(0, alignment))

            environment_fitness = (
                sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0.5
            )
        else:
            environment_fitness = 0.5

        fitness = (
            base_fitness * 0.4
            + capability_fitness * 0.3
            + trend_fitness * 0.15
            + environment_fitness * 0.15
        )

        return max(0.0, min(1.0, fitness))

    def get_evolution_metrics(self) -> EvolutionMetrics:
        self._update_evolution_metrics()
        return self._metrics

    def get_capability_records(
        self,
        capability_type: str | None = None,
        min_fitness: float | None = None,
        stabilized_only: bool = False,
    ) -> list[CapabilityRecord]:
        records = list(self._capability_records.values())

        if capability_type:
            records = [r for r in records if r.capability_type == capability_type]

        if min_fitness is not None:
            records = [r for r in records if r.fitness_contribution >= min_fitness]

        if stabilized_only:
            records = [r for r in records if r.is_stabilized]

        return records

    def get_agent_capability_history(self, agent_id: str) -> list[AgentCapabilitySnapshot]:
        return self._agent_snapshots.get(agent_id, [])

    def _update_agent_capabilities(
        self,
        agent_id: str,
        capability_type: str,  # noqa: ARG002
        capability_name: str,  # noqa: ARG002
    ) -> None:
        if agent_id not in self._agent_snapshots:
            self._agent_snapshots[agent_id] = []

    def _get_latest_snapshot(self, agent_id: str) -> AgentCapabilitySnapshot | None:
        snapshots = self._agent_snapshots.get(agent_id, [])
        return snapshots[-1] if snapshots else None

    def _create_agent_snapshot(
        self,
        agent_id: str,
        state: dict[str, Any],
    ) -> AgentCapabilitySnapshot:
        prev_snapshot = self._get_latest_snapshot(agent_id)

        newly_acquired = []
        current_caps = state.get("capability_levels", {})

        if prev_snapshot:
            for cap_type in current_caps:
                if cap_type not in prev_snapshot.capability_levels:
                    newly_acquired.append(cap_type)  # noqa: PERF401

        snapshot = AgentCapabilitySnapshot(
            agent_id=agent_id,
            capability_levels=current_caps.copy(),
            fitness_score=state.get("fitness_score", 0.0),
            fitness_history=state.get("fitness_history", []),
            behavior_diversity=state.get("behavior_diversity", 0.0),
            behavior_innovation=state.get("behavior_innovation", 0.0),
            success_rate=state.get("success_rate", 0.0),
            adaptation_count=state.get("adaptation_count", 0),
            active_capabilities=list(current_caps.keys()),
            newly_acquired=newly_acquired,
        )

        if agent_id not in self._agent_snapshots:
            self._agent_snapshots[agent_id] = []

        self._agent_snapshots[agent_id].append(snapshot)

        if len(self._agent_snapshots[agent_id]) > 100:
            self._agent_snapshots[agent_id] = self._agent_snapshots[agent_id][-100:]

        return snapshot

    def _update_evolution_metrics(self) -> None:
        metrics = self._metrics

        metrics.total_capabilities = len(self._capability_records)

        metrics.stabilized_capabilities = sum(
            1 for r in self._capability_records.values() if r.is_stabilized
        )

        metrics.inherited_capabilities = sum(
            r.inheritance_count for r in self._capability_records.values()
        )

        cutoff = datetime.now(UTC) - timedelta(hours=self._capability_window_hours)
        metrics.active_capabilities = sum(
            1
            for r in self._capability_records.values()
            if datetime.fromisoformat(r.last_reinforced) > cutoff
        )

        start_time = datetime.fromisoformat(self._evolution_start)
        hours_elapsed = max((datetime.now(UTC) - start_time).total_seconds() / 3600, 0.001)
        metrics.evolution_rate = metrics.total_capabilities / hours_elapsed

        if self._capability_records:
            types = {r.capability_type for r in self._capability_records.values()}
            metrics.capability_diversity = len(types) / max(metrics.total_capabilities, 1)
        else:
            metrics.capability_diversity = 0.0

        all_fitness = []
        for snapshots in self._agent_snapshots.values():
            if snapshots:
                all_fitness.append(snapshots[-1].fitness_score)  # noqa: PERF401

        if all_fitness:
            metrics.avg_fitness = sum(all_fitness) / len(all_fitness)
            metrics.max_fitness = max(all_fitness)
            metrics.min_fitness = min(all_fitness)
            metrics.fitness_variance = self._calculate_variance(all_fitness)

            if len(all_fitness) >= 2:
                metrics.fitness_trend = all_fitness[-1] - all_fitness[0]
        else:
            metrics.avg_fitness = 0.0
            metrics.max_fitness = 0.0
            metrics.min_fitness = 0.0
            metrics.fitness_variance = 0.0
            metrics.fitness_trend = 0.0

        metrics.fitness_landscape = metrics.avg_fitness
        metrics.adaptability_index = self._calculate_adaptability_index()

        new_phase = self._determine_evolution_phase()
        if new_phase != metrics.current_phase:
            old_phase = metrics.current_phase
            metrics.current_phase = new_phase
            asyncio.create_task(self._call_phase_changed_callbacks(old_phase, new_phase))  # noqa: RUF006

        metrics.generations = self._generation_counter
        metrics.selection_fidelity = self._calculate_selection_fidelity()

    def _calculate_variance(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

    def _calculate_adaptability_index(self) -> float:
        if not self._capability_history:
            return 0.5

        recent_window = timedelta(hours=self._capability_window_hours)
        cutoff = datetime.now(UTC) - recent_window

        recent_caps = [
            r for r in self._capability_history if datetime.fromisoformat(r.first_observed) > cutoff
        ]

        if not recent_caps:
            return 0.5

        recent_rate = len(recent_caps) / self._capability_window_hours
        avg_dev_time = sum(r.development_time_seconds for r in recent_caps) / len(recent_caps)

        rate_component = min(recent_rate / 10.0, 1.0)
        time_component = max(0, 1.0 - (avg_dev_time / 3600))

        adaptability = (rate_component + time_component) / 2

        return max(0.0, min(1.0, adaptability))

    def _determine_evolution_phase(self) -> EvolutionPhase:
        total_capabilities = len(self._capability_records)
        stabilized_count = self._metrics.stabilized_capabilities

        if total_capabilities > 0:
            stabilization_ratio = stabilized_count / total_capabilities
        else:
            stabilization_ratio = 0.0

        if total_capabilities == 0:
            return EvolutionPhase.INITIALIZATION

        if stabilization_ratio > 0.7 and self._metrics.avg_fitness > 0.7:
            return EvolutionPhase.EQUILIBRIUM

        if stabilization_ratio > 0.5:
            return EvolutionPhase.MATURATION

        if self._metrics.capability_diversity > 0.5:
            return EvolutionPhase.EMERGENCE

        if total_capabilities > 5:
            return EvolutionPhase.SELECTION

        return EvolutionPhase.EXPLORATION

    def _calculate_selection_fidelity(self) -> float:
        if not self._capability_records:
            return 0.5

        recent_capabilities = list(self._capability_records.values())[-20:]

        if not recent_capabilities:
            return 0.5

        high_fitness = sum(1 for r in recent_capabilities if r.fitness_contribution > 0.5)
        selection_fidelity = high_fitness / len(recent_capabilities)

        return max(0.0, min(1.0, selection_fidelity))

    async def _call_capability_emerged_callbacks(self, record: CapabilityRecord) -> None:
        for callback in self._on_capability_emerged:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(record)
                else:
                    callback(record)
            except Exception as e:
                logger.error("capability_emerged_callback_error", error=str(e))

    async def _call_capability_stabilized_callbacks(self, record: CapabilityRecord) -> None:
        for callback in self._on_capability_stabilized:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(record)
                else:
                    callback(record)
            except Exception as e:
                logger.error("capability_stabilized_callback_error", error=str(e))

    async def _call_phase_changed_callbacks(
        self,
        old_phase: EvolutionPhase,
        new_phase: EvolutionPhase,
    ) -> None:
        for callback in self._on_evolution_phase_changed:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(old_phase, new_phase)
                else:
                    callback(old_phase, new_phase)
            except Exception as e:
                logger.error("phase_changed_callback_error", error=str(e))

    def get_status(self) -> dict[str, Any]:
        return {
            "total_capabilities": len(self._capability_records),
            "tracked_agents": len(self._agent_snapshots),
            "current_phase": self._metrics.current_phase.value,
            "evolution_rate": self._metrics.evolution_rate,
            "fitness_landscape": self._metrics.fitness_landscape,
            "adaptability_index": self._metrics.adaptability_index,
        }
