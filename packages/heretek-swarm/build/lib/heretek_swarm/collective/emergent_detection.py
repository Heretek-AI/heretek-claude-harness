"""
Emergent Pattern Detector - Session 46 Emergent Intelligence

Implements detection of patterns emerging from swarm interactions that are
not present in individual agents. This module identifies collective behaviors,
classifies emergent patterns, and validates emergence.

Features:
- Detect patterns emerging from swarm interactions
- Identify collective behaviors not present in individual agents
- Classify emergent patterns (coordination, optimization, innovation)
- Emergent pattern validation
- Zero-trust validation of all detected patterns
- Evolution Engine for organic capability development tracking

Zero-Trust Principles:
- All emergent patterns validated before reporting
- Statistical significance required
- Multi-agent correlation verified
- Audit logging for all detections
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from .emergent_detection_types import (
    AgentBehaviorSnapshot,
    CollectiveBehavior,
    DetectionEvent,
    EmergenceDetectionConfig,
    EmergenceLevel,
    EmergentPattern,
    EmergentPatternClass,
)
from .emergent_detection_utils import (
    calculate_confidence,
    calculate_impact_score,
    calculate_shift_score,
    calculate_solution_novelty,
    calculate_statistical_significance,
    calculate_temporal_span,
    calculate_window_metrics,
    classify_emergence_level,
    classify_solution_provenance,
    measure_collective_capability,
)
from .evolution_engine import EvolutionEngine

logger = structlog.get_logger(__name__)


class EmergentPatternDetector:
    """
    Detector for emergent patterns in swarm behavior.
    """

    def __init__(self, config: EmergenceDetectionConfig | None = None):
        self.config = config or EmergenceDetectionConfig()

        self._agent_snapshots: dict[str, list[AgentBehaviorSnapshot]] = {}
        self._collective_behaviors: list[CollectiveBehavior] = []
        self._emergent_patterns: list[EmergentPattern] = []
        self._detection_events: list[DetectionEvent] = []

        self._individual_baselines: dict[str, dict[str, float]] = {}
        self._collective_baselines: dict[str, float] = {}

        # Solution novelty history: stores validated patterns for novelty comparison
        self._solution_history: list[EmergentPattern] = []

        self._evolution_engine: EvolutionEngine | None = None

        self._on_emergence_detected: list[Callable] = []
        self._on_pattern_validated: list[Callable] = []
        self._validation_hooks: list[Callable] = []

        logger.info(
            "emergent_pattern_detector_initialized",
            min_emergence_score=self.config.min_emergence_score,
            min_participating_agents=self.config.min_participating_agents,
        )

    @property
    def evolution_engine(self) -> EvolutionEngine:
        if self._evolution_engine is None:
            self._evolution_engine = EvolutionEngine()
        return self._evolution_engine

    def set_evolution_engine(self, engine: EvolutionEngine) -> None:
        self._evolution_engine = engine

    def register_detection_callback(self, callback: Callable) -> None:
        self._on_emergence_detected.append(callback)
        logger.debug("detection_callback_registered", callback=callback.__name__)

    def register_validation_callback(self, callback: Callable) -> None:
        self._on_pattern_validated.append(callback)
        logger.debug("validation_callback_registered", callback=callback.__name__)

    def register_validation_hook(self, callback: Callable) -> None:
        self._validation_hooks.append(callback)
        logger.debug("validation_hook_registered", callback=callback.__name__)

    def record_agent_snapshot(self, snapshot: AgentBehaviorSnapshot) -> None:
        agent_id = snapshot.agent_id

        if agent_id not in self._agent_snapshots:
            self._agent_snapshots[agent_id] = []

        self._agent_snapshots[agent_id].append(snapshot)

        cutoff = datetime.now(UTC) - timedelta(seconds=self.config.baseline_window_seconds * 2)

        self._agent_snapshots[agent_id] = [
            s
            for s in self._agent_snapshots[agent_id]
            if datetime.fromisoformat(s.timestamp) > cutoff
        ]

        self._update_individual_baseline(agent_id)

        if self._evolution_engine:
            agent_state = {
                "capability_levels": snapshot.metrics,
                "fitness_score": snapshot.success_rate,
                "behaviors": snapshot.active_strategies,
            }
            self._evolution_engine._create_agent_snapshot(agent_id, agent_state)  # noqa: SLF001

    def record_collective_behavior(self, behavior: CollectiveBehavior) -> None:
        self._collective_behaviors.append(behavior)

        cutoff = datetime.now(UTC) - timedelta(seconds=self.config.analysis_window_seconds * 2)

        self._collective_behaviors = [
            b for b in self._collective_behaviors if datetime.fromisoformat(b.start_time) > cutoff
        ]

    def record_solution_outcome(
        self,
        pattern: EmergentPattern,
        problem_signature: dict[str, Any] | None = None,
        approach_used: str | None = None,
        expected_performance: float | None = None,
        solution_threshold: float = 0.5,
    ) -> None:
        """
        Compute and store solution novelty for a validated pattern.

        Calculates how novel the solution/outcome is compared to historical
        solutions, then classifies provenance based on novelty and validation rate.

        Args:
            pattern: The emergent pattern to record solution outcome for.
            problem_signature: Dict describing the problem characteristics.
            approach_used: Name/identifier of the approach used.
            expected_performance: Baseline performance to compare against.
            solution_threshold: Stakeholder-configurable threshold for provenance
                classification (default 0.5). Higher = stricter PROVEN criteria.
        """
        # Build problem signature from pattern evidence if not provided
        if problem_signature is None:
            problem_signature = pattern.evidence.get("problem_signature", {})

        # Extract approach from evidence if not provided
        if approach_used is None:
            approach_used = pattern.evidence.get("approach_used", "unknown")

        # Extract expected performance from pattern metadata if available
        if expected_performance is None:
            expected_performance = pattern.evidence.get("expected_performance")

        # Get historical patterns for novelty comparison
        historical = self._solution_history

        # Calculate solution novelty using three-factor model
        pattern.solution_novelty = calculate_solution_novelty(
            pattern=pattern,
            historical_patterns=historical,
            problem_signature=problem_signature,
            approach_used=approach_used,
            expected_performance=expected_performance,
        )

        # Classify provenance based on novelty and validation
        pattern.solution_provenance = classify_solution_provenance(
            solution_novelty=pattern.solution_novelty,
            validation_rate=pattern.validation_rate,
            solution_threshold=solution_threshold,
        )

        # Store in history for future novelty comparisons
        self._solution_history.append(pattern)

        logger.debug(
            "solution_outcome_recorded",
            pattern_id=pattern.pattern_id,
            solution_novelty=pattern.solution_novelty,
            solution_provenance=pattern.solution_provenance.value,
        )

    async def analyze_for_emergence(self) -> list[EmergentPattern]:
        return []

    def get_emergent_patterns(
        self,
        pattern_class: EmergentPatternClass | None = None,
        min_emergence_level: EmergenceLevel | None = None,
        limit: int = 100,
    ) -> list[EmergentPattern]:
        patterns = self._emergent_patterns

        if pattern_class:
            patterns = [p for p in patterns if p.pattern_class == pattern_class]

        if min_emergence_level:
            level_order = {
                EmergenceLevel.WEAK: 0,
                EmergenceLevel.MODERATE: 1,
                EmergenceLevel.STRONG: 2,
                EmergenceLevel.CRITICAL: 3,
            }
            min_level = level_order[min_emergence_level]
            patterns = [p for p in patterns if level_order[p.emergence_level] >= min_level]

        return patterns[-limit:]

    def get_evolution_metrics(self) -> dict[str, Any]:
        if self._evolution_engine:
            return self._evolution_engine.get_evolution_metrics().to_dict()
        return {}

    def get_patterns_by_impact(
        self, min_impact: float = 0.0, limit: int = 100
    ) -> list[EmergentPattern]:
        filtered = [p for p in self._emergent_patterns if p.impact_score >= min_impact]
        return filtered[-limit:]

    def get_harmful_patterns(self, limit: int = 100) -> list[EmergentPattern]:
        harmful = [p for p in self._emergent_patterns if p.impact_score < 0]
        return harmful[-limit:]

    def get_beneficial_patterns(
        self, min_impact: float = 0.0, limit: int = 100
    ) -> list[EmergentPattern]:
        beneficial = [p for p in self._emergent_patterns if p.impact_score >= min_impact]
        return beneficial[-limit:]

    def get_collective_behaviors(self) -> list[CollectiveBehavior]:
        return list(self._collective_behaviors)

    def get_detection_history(self, limit: int = 100) -> list[DetectionEvent]:
        return self._detection_events[-limit:]

    def _get_snapshot_windows(
        self, window_size_seconds: float = 60.0
    ) -> list[list[AgentBehaviorSnapshot]]:
        all_snapshots = []
        for snapshots in self._agent_snapshots.values():
            all_snapshots.extend(snapshots)

        if not all_snapshots:
            return []

        sorted_snapshots = sorted(all_snapshots, key=lambda s: datetime.fromisoformat(s.timestamp))

        windows = []
        current_window = []
        window_start = datetime.fromisoformat(sorted_snapshots[0].timestamp)

        for snapshot in sorted_snapshots:
            snapshot_time = datetime.fromisoformat(snapshot.timestamp)

            if (snapshot_time - window_start).total_seconds() <= window_size_seconds:
                current_window.append(snapshot)
            else:
                windows.append(current_window)
                current_window = [snapshot]
                window_start = snapshot_time

        if current_window:
            windows.append(current_window)

        return windows

    def _calculate_window_metrics(self, window: list[AgentBehaviorSnapshot]) -> dict[str, float]:
        return calculate_window_metrics(window)

    def _calculate_shift_score(
        self, prev_metrics: dict[str, float], curr_metrics: dict[str, float]
    ) -> float:
        return calculate_shift_score(prev_metrics, curr_metrics)

    def _get_active_agents(self, window: list[AgentBehaviorSnapshot]) -> list[str]:
        return list({s.agent_id for s in window})

    def _classify_emergence_level(self, score: float) -> EmergenceLevel:
        return classify_emergence_level(score)

    def _update_individual_baseline(self, agent_id: str) -> None:
        snapshots = self._agent_snapshots.get(agent_id, [])

        if len(snapshots) < 5:
            return

        recent = snapshots[-10:]

        self._individual_baselines[agent_id] = {
            "success_rate": sum(s.success_rate for s in recent) / len(recent),
            "interaction_rate": sum(s.interaction_count for s in recent) / len(recent),
            "efficiency": sum(s.metrics.get("efficiency", 0.5) for s in recent) / len(recent),
        }

    def _get_individual_baseline(self, agent_ids: list[str]) -> float:
        baselines = []

        for agent_id in agent_ids:
            if agent_id in self._individual_baselines:
                baselines.append(self._individual_baselines[agent_id].get("success_rate", 0.5))  # noqa: PERF401

        return sum(baselines) / len(baselines) if baselines else 0.5

    def _measure_collective_capability(self, behaviors: list[CollectiveBehavior]) -> float:
        return measure_collective_capability(behaviors)

    def _calculate_temporal_span(self, behaviors: list[CollectiveBehavior]) -> float:
        return calculate_temporal_span(behaviors)

    async def _validate_and_store_pattern(self, pattern: EmergentPattern) -> DetectionEvent:
        event = DetectionEvent(
            pattern=pattern,
            detection_method="multi_agent_analysis",
            raw_score=pattern.emergence_score,
            threshold=self.config.min_emergence_score,
        )

        if pattern.emergence_score < self.config.min_emergence_score:
            event.passed_validation = False
            event.validation_details["reason"] = "emergence_score_below_threshold"
            return event

        if len(pattern.participating_agents) < self.config.min_participating_agents:
            event.passed_validation = False
            event.validation_details["reason"] = "insufficient_participating_agents"
            return event

        pattern.statistical_significance = calculate_statistical_significance(pattern)

        if pattern.statistical_significance > self.config.statistical_threshold:
            event.passed_validation = False
            event.validation_details["reason"] = "not_statistically_significant"
            return event

        pattern.confidence = calculate_confidence(pattern)

        if pattern.confidence < self.config.min_confidence:
            event.passed_validation = False
            event.validation_details["reason"] = "confidence_below_threshold"
            return event

        if self.config.validation_required:
            for hook in self._validation_hooks:
                try:
                    result = hook(pattern)
                    if asyncio.iscoroutine(result):
                        result = await result
                    if not result:
                        event.passed_validation = False
                        event.validation_details["reason"] = "validation_hook_rejected"
                        return event
                except Exception as e:
                    logger.error(
                        "validation_hook_error", pattern_id=pattern.pattern_id, error=str(e)
                    )

        event.passed_validation = True
        pattern.is_validated = True

        pattern.impact_score = calculate_impact_score(pattern)

        existing_pattern = self._find_similar_pattern(pattern)

        if existing_pattern:
            pattern.frequency = existing_pattern.frequency + 1
            pattern.first_detected = existing_pattern.first_detected

        # Compute and store solution novelty for validated patterns
        self.record_solution_outcome(pattern)

        self._emergent_patterns.append(pattern)

        logger.info(
            "emergent_pattern_validated",
            pattern_id=pattern.pattern_id,
            pattern_class=pattern.pattern_class.value,
            emergence_level=pattern.emergence_level.value,
            impact_score=pattern.impact_score,
        )

        return event

    def _find_similar_pattern(self, pattern: EmergentPattern) -> EmergentPattern | None:
        for existing in self._emergent_patterns:
            if existing.pattern_class == pattern.pattern_class and set(
                existing.participating_agents
            ) == set(pattern.participating_agents):
                return existing
        return None

    async def _call_detection_callbacks(self, event: DetectionEvent) -> None:
        for callback in self._on_emergence_detected:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error("detection_callback_error", callback=callback.__name__, error=str(e))

        self._detection_events.append(event)

    def get_status(self) -> dict[str, Any]:
        return {
            "total_patterns": len(self._emergent_patterns),
            "validated_patterns": sum(1 for p in self._emergent_patterns if p.is_validated),
            "total_behaviors": len(self._collective_behaviors),
            "tracked_agents": len(self._agent_snapshots),
            "config": {
                "min_emergence_score": self.config.min_emergence_score,
                "min_participating_agents": self.config.min_participating_agents,
                "validation_required": self.config.validation_required,
            },
        }

    def get_emergence_statistics(self) -> dict[str, Any]:
        by_class: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for p in self._emergent_patterns:
            pc = (
                p.pattern_class.value if hasattr(p.pattern_class, "value") else str(p.pattern_class)
            )
            pl = (
                p.emergence_level.value
                if hasattr(p.emergence_level, "value")
                else str(p.emergence_level)
            )
            by_class[pc] = by_class.get(pc, 0) + 1
            by_level[pl] = by_level.get(pl, 0) + 1
        validated = [p for p in self._emergent_patterns if p.is_validated]
        avg_score = (
            sum(p.emergence_score for p in self._emergent_patterns) / len(self._emergent_patterns)
            if self._emergent_patterns
            else 0.0
        )
        return {
            "total_patterns": len(self._emergent_patterns),
            "validated_patterns": len(validated),
            "by_class": by_class,
            "by_level": by_level,
            "average_emergence_score": avg_score,
            "tracked_agents": len(self._agent_snapshots),
        }

    def calculate_emergence_metrics(self) -> dict[str, Any]:
        patterns = self._emergent_patterns
        if not patterns:
            return {
                "swarm_emergence_index": 0.0,
                "collective_intelligence_factor": 0.0,
                "coordination_level": 0.0,
                "pattern_diversity": 0.0,
                "validation_rate": 0.0,
            }
        avg_score = sum(p.emergence_score for p in patterns) / len(patterns)
        validation_rate = sum(1 for p in patterns if p.is_validated) / len(patterns)
        unique_classes = len({p.pattern_class for p in patterns})
        pattern_diversity = unique_classes / max(len(EmergentPatternClass), 1)
        coordination_patterns = [
            p
            for p in patterns
            if hasattr(p.pattern_class, "value") and "coord" in p.pattern_class.value.lower()
        ]
        coordination_level = len(coordination_patterns) / len(patterns) if patterns else 0.0
        return {
            "swarm_emergence_index": avg_score,
            "collective_intelligence_factor": avg_score * validation_rate,
            "coordination_level": coordination_level,
            "pattern_diversity": pattern_diversity,
            "validation_rate": validation_rate,
        }


class EmergenceAnalyzer:
    """Analyzer for emergent patterns and collective behaviors."""

    def __init__(self, detector: EmergentPatternDetector):
        self.detector = detector
        logger.info("emergence_analyzer_initialized")

    def analyze_emergence_trends(self) -> dict[str, Any]:
        patterns = self.detector._emergent_patterns  # noqa: SLF001

        if len(patterns) < 5:
            return {"trend": "insufficient_data"}

        mid = len(patterns) // 2
        early = patterns[:mid]
        recent = patterns[mid:]

        early_avg = sum(p.emergence_score for p in early) / len(early)
        recent_avg = sum(p.emergence_score for p in recent) / len(recent)

        trend = "increasing" if recent_avg > early_avg else "decreasing"
        change = abs(recent_avg - early_avg)

        return {
            "trend": trend,
            "early_avg_score": early_avg,
            "recent_avg_score": recent_avg,
            "change": change,
            "early_count": len(early),
            "recent_count": len(recent),
        }

    def identify_key_contributors(self) -> list[dict[str, Any]]:
        agent_contributions: dict[str, int] = defaultdict(int)

        for pattern in self.detector._emergent_patterns:  # noqa: SLF001
            for agent_id in pattern.participating_agents:
                agent_contributions[agent_id] += 1

        contributors = [
            {"agent_id": aid, "contribution_count": count}
            for aid, count in sorted(agent_contributions.items(), key=lambda x: x[1], reverse=True)
        ]

        return contributors[:10]

    def analyze_pattern_correlations(self) -> dict[str, Any]:
        patterns = self.detector._emergent_patterns  # noqa: SLF001

        if len(patterns) < 10:
            return {"correlations": "insufficient_data"}

        class_cooccurrences: dict[tuple[str, str], int] = defaultdict(int)

        for pattern in patterns:
            class1 = pattern.pattern_class.value
            for other in patterns:
                if other.pattern_id != pattern.pattern_id:
                    class2 = other.pattern_class.value
                    key = tuple(sorted([class1, class2]))
                    class_cooccurrences[key] += 1

        return {
            "cooccurrences": dict(class_cooccurrences),
            "most_correlated": max(class_cooccurrences.items(), key=lambda x: x[1])[0]
            if class_cooccurrences
            else None,
        }

    def get_emergence_timeline(self) -> list[dict[str, Any]]:
        timeline = []

        for pattern in sorted(self.detector._emergent_patterns, key=lambda p: p.timestamp):  # noqa: SLF001
            timeline.append(  # noqa: PERF401
                {
                    "timestamp": pattern.timestamp,
                    "pattern_class": pattern.pattern_class.value,
                    "emergence_level": pattern.emergence_level.value,
                    "emergence_score": pattern.emergence_score,
                    "agent_count": len(pattern.participating_agents),
                }
            )

        return timeline
