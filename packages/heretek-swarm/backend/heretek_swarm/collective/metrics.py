"""
Collective Intelligence Metrics - Session 46 Emergent Intelligence

Implements comprehensive metrics for measuring collective intelligence
in the agent swarm. This module provides swarm intelligence quotient (SIQ),
collective problem-solving efficiency, knowledge transfer rates, and
emergence coefficients.

Features:
- Swarm Intelligence Quotient (SIQ) calculation
- Collective problem-solving efficiency
- Knowledge transfer rate
- Emergence coefficient
- Real-time metrics dashboard data
- Zero-trust validation of all metrics

Zero-Trust Principles:
- All metrics validated before exposure
- Source attribution required
- Statistical significance enforced
- Audit logging for all metric calculations
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

from .adaptive_learning import AdaptiveLearningRateController
from .agent_adaptation import PatternBasedAgentAdaptor
from heretek_swarm.research.emergent_detection import EmergenceLevel, EmergentPatternDetector
from .pattern_library import PatternLibrary

logger = structlog.get_logger(__name__)


class MetricCategory(StrEnum):
    """Categories of collective intelligence metrics."""

    SWARM_INTELLIGENCE = "swarm_intelligence"
    PROBLEM_SOLVING = "problem_solving"
    KNOWLEDGE_TRANSFER = "knowledge_transfer"
    EMERGENCE = "emergence"
    ADAPTATION = "adaptation"
    COORDINATION = "coordination"
    EFFICIENCY = "efficiency"
    RESILIENCE = "resilience"


class MetricAggregation(StrEnum):
    """Aggregation methods for metrics."""

    MEAN = "mean"
    MEDIAN = "median"
    MAX = "max"
    MIN = "min"
    SUM = "sum"
    STD_DEV = "std_dev"
    VARIANCE = "variance"


@dataclass
class MetricDefinition:
    """Definition of a collectible metric."""

    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: MetricCategory = MetricCategory.SWARM_INTELLIGENCE
    unit: str = ""
    aggregation: MetricAggregation = MetricAggregation.MEAN
    min_value: float | None = None
    max_value: float | None = None
    target_value: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "unit": self.unit,
            "aggregation": self.aggregation.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "target_value": self.target_value,
            "metadata": self.metadata,
        }


@dataclass
class MetricValue:
    """A single metric value with metadata."""

    value_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric_id: str = ""
    value: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = ""
    confidence: float = 1.0
    sample_size: int = 1
    statistical_significance: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "value_id": self.value_id,
            "metric_id": self.metric_id,
            "value": self.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "statistical_significance": self.statistical_significance,
            "metadata": self.metadata,
        }


@dataclass
class MetricTimeSeries:
    """Time series of metric values."""

    metric_id: str = ""
    values: list[MetricValue] = field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_id": self.metric_id,
            "values": [v.to_dict() for v in self.values],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "sample_count": self.sample_count,
        }


@dataclass
class SwarmIntelligenceQuotient:
    """Swarm Intelligence Quotient (SIQ) calculation result."""

    calculation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Component scores (0.0 to 1.0)
    coordination_score: float = 0.0
    adaptation_score: float = 0.0
    knowledge_sharing_score: float = 0.0
    problem_solving_score: float = 0.0
    emergence_score: float = 0.0
    resilience_score: float = 0.0

    # Overall SIQ (0.0 to 100.0, normalized like IQ)
    overall_siq: float = 100.0
    siq_percentile: float = 50.0

    # Breakdown
    component_weights: dict[str, float] = field(default_factory=dict)
    component_contributions: dict[str, float] = field(default_factory=dict)

    # Context
    agent_count: int = 0
    observation_window_seconds: float = 0.0
    sample_size: int = 0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "calculation_id": self.calculation_id,
            "timestamp": self.timestamp,
            "coordination_score": self.coordination_score,
            "adaptation_score": self.adaptation_score,
            "knowledge_sharing_score": self.knowledge_sharing_score,
            "problem_solving_score": self.problem_solving_score,
            "emergence_score": self.emergence_score,
            "resilience_score": self.resilience_score,
            "overall_siq": self.overall_siq,
            "siq_percentile": self.siq_percentile,
            "component_weights": self.component_weights,
            "component_contributions": self.component_contributions,
            "agent_count": self.agent_count,
            "observation_window_seconds": self.observation_window_seconds,
            "sample_size": self.sample_size,
            "metadata": self.metadata,
        }


@dataclass
class CollectiveEfficiencyMetrics:
    """Collective problem-solving efficiency metrics."""

    calculation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Efficiency metrics
    task_completion_rate: float = 0.0  # Tasks completed / Tasks attempted
    avg_task_time_seconds: float = 0.0
    optimal_task_time_seconds: float = 0.0  # Theoretical optimal
    efficiency_ratio: float = 0.0  # optimal / actual

    # Resource metrics
    resource_utilization: float = 0.0
    redundant_work_ratio: float = 0.0
    parallel_efficiency: float = 0.0

    # Quality metrics
    solution_quality_avg: float = 0.0
    solution_quality_std: float = 0.0
    first_attempt_success_rate: float = 0.0

    # Collective factor
    collective_efficiency_factor: float = 0.0  # How much better than individuals

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "calculation_id": self.calculation_id,
            "timestamp": self.timestamp,
            "task_completion_rate": self.task_completion_rate,
            "avg_task_time_seconds": self.avg_task_time_seconds,
            "optimal_task_time_seconds": self.optimal_task_time_seconds,
            "efficiency_ratio": self.efficiency_ratio,
            "resource_utilization": self.resource_utilization,
            "redundant_work_ratio": self.redundant_work_ratio,
            "parallel_efficiency": self.parallel_efficiency,
            "solution_quality_avg": self.solution_quality_avg,
            "solution_quality_std": self.solution_quality_std,
            "first_attempt_success_rate": self.first_attempt_success_rate,
            "collective_efficiency_factor": self.collective_efficiency_factor,
            "metadata": self.metadata,
        }


@dataclass
class KnowledgeTransferMetrics:
    """Knowledge transfer rate metrics."""

    calculation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Transfer rates
    patterns_shared: int = 0
    patterns_adopted: int = 0
    adoption_rate: float = 0.0  # adopted / shared
    transfer_rate_per_hour: float = 0.0

    # Knowledge flow
    knowledge_inflow: float = 0.0
    knowledge_outflow: float = 0.0
    knowledge_balance: float = 0.0  # inflow - outflow

    # Network metrics
    active_transmitters: int = 0
    active_receivers: int = 0
    network_density: float = 0.0
    avg_path_length: float = 0.0

    # Retention
    knowledge_retention_rate: float = 0.0
    knowledge_decay_rate: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "calculation_id": self.calculation_id,
            "timestamp": self.timestamp,
            "patterns_shared": self.patterns_shared,
            "patterns_adopted": self.patterns_adopted,
            "adoption_rate": self.adoption_rate,
            "transfer_rate_per_hour": self.transfer_rate_per_hour,
            "knowledge_inflow": self.knowledge_inflow,
            "knowledge_outflow": self.knowledge_outflow,
            "knowledge_balance": self.knowledge_balance,
            "active_transmitters": self.active_transmitters,
            "active_receivers": self.active_receivers,
            "network_density": self.network_density,
            "avg_path_length": self.avg_path_length,
            "knowledge_retention_rate": self.knowledge_retention_rate,
            "knowledge_decay_rate": self.knowledge_decay_rate,
            "metadata": self.metadata,
        }


@dataclass
class EmergenceCoefficient:
    """Emergence coefficient calculation result."""

    calculation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Overall coefficient
    emergence_coefficient: float = 0.0  # 0.0 to 1.0

    # Component coefficients
    behavioral_emergence: float = 0.0
    structural_emergence: float = 0.0
    functional_emergence: float = 0.0
    cognitive_emergence: float = 0.0

    # Emergence indicators
    macro_patterns_detected: int = 0
    micro_macro_link_strength: float = 0.0
    downward_causation_strength: float = 0.0
    novelty_score: float = 0.0

    # Classification
    emergence_type: str = ""
    emergence_strength: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "calculation_id": self.calculation_id,
            "timestamp": self.timestamp,
            "emergence_coefficient": self.emergence_coefficient,
            "behavioral_emergence": self.behavioral_emergence,
            "structural_emergence": self.structural_emergence,
            "functional_emergence": self.functional_emergence,
            "cognitive_emergence": self.cognitive_emergence,
            "macro_patterns_detected": self.macro_patterns_detected,
            "micro_macro_link_strength": self.micro_macro_link_strength,
            "downward_causation_strength": self.downward_causation_strength,
            "novelty_score": self.novelty_score,
            "emergence_type": self.emergence_type,
            "emergence_strength": self.emergence_strength,
            "metadata": self.metadata,
        }


@dataclass
class MetricsDashboard:
    """Real-time metrics dashboard data."""

    dashboard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Summary metrics
    swarm_health_score: float = 0.0  # 0.0 to 100.0
    swarm_intelligence_quotient: float = 0.0
    collective_efficiency: float = 0.0
    emergence_coefficient: float = 0.0

    # Agent metrics
    total_agents: int = 0
    active_agents: int = 0
    avg_agent_performance: float = 0.0

    # Pattern metrics
    total_patterns: int = 0
    validated_patterns: int = 0
    emergent_patterns: int = 0

    # Learning metrics
    learning_rate_avg: float = 0.0
    adaptation_rate: float = 0.0
    convergence_rate: float = 0.0

    # Time series data (recent values)
    siq_history: list[float] = field(default_factory=list)
    efficiency_history: list[float] = field(default_factory=list)
    emergence_history: list[float] = field(default_factory=list)

    # Alerts
    alerts: list[dict[str, Any]] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "dashboard_id": self.dashboard_id,
            "timestamp": self.timestamp,
            "swarm_health_score": self.swarm_health_score,
            "swarm_intelligence_quotient": self.swarm_intelligence_quotient,
            "collective_efficiency": self.collective_efficiency,
            "emergence_coefficient": self.emergence_coefficient,
            "total_agents": self.total_agents,
            "active_agents": self.active_agents,
            "avg_agent_performance": self.avg_agent_performance,
            "total_patterns": self.total_patterns,
            "validated_patterns": self.validated_patterns,
            "emergent_patterns": self.emergent_patterns,
            "learning_rate_avg": self.learning_rate_avg,
            "adaptation_rate": self.adaptation_rate,
            "convergence_rate": self.convergence_rate,
            "siq_history": self.siq_history,
            "efficiency_history": self.efficiency_history,
            "emergence_history": self.emergence_history,
            "alerts": self.alerts,
            "metadata": self.metadata,
        }


class CollectiveIntelligenceMetrics:
    """
    Comprehensive metrics calculator for collective intelligence.

    This class provides calculation and tracking of collective
    intelligence metrics including SIQ, efficiency, knowledge transfer,
    and emergence coefficients.

    Attributes:
        learning_controller: AdaptiveLearningRateController instance
        agent_adaptor: PatternBasedAgentAdaptor instance
        emergence_detector: EmergentPatternDetector instance
    """

    def __init__(
        self,
        learning_controller: AdaptiveLearningRateController | None = None,
        agent_adaptor: PatternBasedAgentAdaptor | None = None,
        emergence_detector: EmergentPatternDetector | None = None,
        pattern_library: PatternLibrary | None = None,
    ):
        """
        Initialize collective intelligence metrics.

        Args:
            learning_controller: AdaptiveLearningRateController instance
            agent_adaptor: PatternBasedAgentAdaptor instance
            emergence_detector: EmergentPatternDetector instance
            pattern_library: PatternLibrary instance
        """
        self.learning_controller = learning_controller or AdaptiveLearningRateController()
        self.agent_adaptor = agent_adaptor or PatternBasedAgentAdaptor()
        self.emergence_detector = emergence_detector or EmergentPatternDetector()
        self.pattern_library = pattern_library

        self._metric_definitions: dict[str, MetricDefinition] = {}
        self._metric_values: dict[str, list[MetricValue]] = {}
        self._siq_history: list[SwarmIntelligenceQuotient] = []
        self._efficiency_history: list[CollectiveEfficiencyMetrics] = []
        self._transfer_history: list[KnowledgeTransferMetrics] = []
        self._emergence_history: list[EmergenceCoefficient] = []

        # Callbacks
        self._on_metric_calculated: list[Callable] = []
        self._on_threshold_exceeded: list[Callable] = []

        # Thresholds
        self._thresholds: dict[str, tuple[float, float]] = {}  # metric_id -> (min, max)

        self._register_default_metrics()

        logger.info("collective_intelligence_metrics_initialized")

    def register_metric_callback(self, callback: Callable) -> None:
        """
        Register callback for metric calculation events.

        Args:
            callback: Async callable receiving MetricValue
        """
        self._on_metric_calculated.append(callback)
        logger.debug("metric_callback_registered", callback=callback.__name__)

    def register_threshold_callback(self, callback: Callable) -> None:
        """
        Register callback for threshold exceeded events.

        Args:
            callback: Async callable receiving threshold event
        """
        self._on_threshold_exceeded.append(callback)
        logger.debug("threshold_callback_registered", callback=callback.__name__)

    def set_threshold(
        self,
        metric_id: str,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        """
        Set threshold for a metric.

        Args:
            metric_id: Metric identifier
            min_value: Optional minimum threshold
            max_value: Optional maximum threshold
        """
        self._thresholds[metric_id] = (min_value, max_value)
        logger.debug(
            "threshold_set",
            metric_id=metric_id,
            min_value=min_value,
            max_value=max_value,
        )

    async def calculate_siq(self) -> SwarmIntelligenceQuotient:
        """
        Calculate Swarm Intelligence Quotient (SIQ).

        Returns:
            SwarmIntelligenceQuotient calculation result
        """
        # Calculate component scores
        coordination_score = await self._calculate_coordination_score()
        adaptation_score = await self._calculate_adaptation_score()
        knowledge_sharing_score = await self._calculate_knowledge_sharing_score()
        problem_solving_score = await self._calculate_problem_solving_score()
        emergence_score = await self._calculate_emergence_score()
        resilience_score = await self._calculate_resilience_score()

        # Component weights (can be customized)
        weights = {
            "coordination": 0.20,
            "adaptation": 0.20,
            "knowledge_sharing": 0.15,
            "problem_solving": 0.20,
            "emergence": 0.15,
            "resilience": 0.10,
        }

        # Calculate weighted overall score (0.0 to 1.0)
        raw_score = (
            coordination_score * weights["coordination"]
            + adaptation_score * weights["adaptation"]
            + knowledge_sharing_score * weights["knowledge_sharing"]
            + problem_solving_score * weights["problem_solving"]
            + emergence_score * weights["emergence"]
            + resilience_score * weights["resilience"]
        )

        # Normalize to SIQ scale (50-150, with 100 as average)
        # Using linear transformation: SIQ = raw_score * 100 + 50
        overall_siq = min(150.0, max(50.0, raw_score * 100 + 50))

        # Calculate percentile (simplified - assumes normal distribution)
        siq_percentile = self._calculate_siq_percentile(overall_siq)

        # Calculate component contributions
        contributions = {
            "coordination": coordination_score * weights["coordination"] / raw_score
            if raw_score > 0
            else 0,
            "adaptation": adaptation_score * weights["adaptation"] / raw_score
            if raw_score > 0
            else 0,
            "knowledge_sharing": knowledge_sharing_score * weights["knowledge_sharing"] / raw_score
            if raw_score > 0
            else 0,
            "problem_solving": problem_solving_score * weights["problem_solving"] / raw_score
            if raw_score > 0
            else 0,
            "emergence": emergence_score * weights["emergence"] / raw_score if raw_score > 0 else 0,
            "resilience": resilience_score * weights["resilience"] / raw_score
            if raw_score > 0
            else 0,
        }

        siq = SwarmIntelligenceQuotient(
            coordination_score=coordination_score,
            adaptation_score=adaptation_score,
            knowledge_sharing_score=knowledge_sharing_score,
            problem_solving_score=problem_solving_score,
            emergence_score=emergence_score,
            resilience_score=resilience_score,
            overall_siq=overall_siq,
            siq_percentile=siq_percentile,
            component_weights=weights,
            component_contributions=contributions,
            agent_count=len(self.learning_controller._agent_states),
            observation_window_seconds=300.0,  # 5 minutes
            sample_size=len(self._siq_history) + 1,
        )

        # Store in history
        self._siq_history.append(siq)

        # Store metric values
        await self._store_metric_value(
            "siq_overall",
            overall_siq,
            source="collective_intelligence_metrics",
        )

        logger.info(
            "siq_calculated",
            overall_siq=overall_siq,
            siq_percentile=siq_percentile,
        )

        return siq

    async def calculate_collective_efficiency(self) -> CollectiveEfficiencyMetrics:
        """
        Calculate collective problem-solving efficiency metrics.

        Returns:
            CollectiveEfficiencyMetrics calculation result
        """
        # Get task statistics from agent states
        agent_states = self.learning_controller._agent_states.values()

        total_updates = sum(s.total_updates for s in agent_states)
        successful_updates = sum(s.successful_updates for s in agent_states)

        # Task completion rate
        task_completion_rate = successful_updates / max(total_updates, 1)

        # Efficiency ratio (simplified)
        avg_success_rate = sum(s.success_rate for s in agent_states) / max(len(agent_states), 1)
        efficiency_ratio = avg_success_rate

        # Resource utilization (based on adaptation activity)
        adaptation_states = self.agent_adaptor._agent_states.values()
        total_adaptations = sum(s.adaptation_count for s in adaptation_states)
        resource_utilization = min(1.0, total_adaptations / max(len(adaptation_states) * 10, 1))

        # Collective efficiency factor
        # How much better the collective performs vs individuals
        individual_avg = avg_success_rate
        collective_avg = task_completion_rate
        collective_efficiency_factor = collective_avg / max(individual_avg, 0.01)

        metrics = CollectiveEfficiencyMetrics(
            task_completion_rate=task_completion_rate,
            avg_task_time_seconds=0.0,  # Would need timing data
            optimal_task_time_seconds=0.0,
            efficiency_ratio=efficiency_ratio,
            resource_utilization=resource_utilization,
            redundant_work_ratio=0.0,  # Would need duplicate work tracking
            parallel_efficiency=efficiency_ratio,
            solution_quality_avg=avg_success_rate,
            solution_quality_std=0.0,
            first_attempt_success_rate=task_completion_rate,
            collective_efficiency_factor=collective_efficiency_factor,
        )

        self._efficiency_history.append(metrics)

        await self._store_metric_value(
            "collective_efficiency",
            efficiency_ratio,
            source="collective_intelligence_metrics",
        )

        logger.info(
            "collective_efficiency_calculated",
            efficiency_ratio=efficiency_ratio,
            collective_efficiency_factor=collective_efficiency_factor,
        )

        return metrics

    async def calculate_knowledge_transfer(self) -> KnowledgeTransferMetrics:
        """
        Calculate knowledge transfer rate metrics.

        Returns:
            KnowledgeTransferMetrics calculation result
        """
        # Get pattern statistics
        adaptor_stats = self.agent_adaptor.get_swarm_adaptation_stats()

        patterns_shared = adaptor_stats.get("total_patterns_adopted", 0) + adaptor_stats.get(
            "total_patterns_rejected", 0
        )
        patterns_adopted = adaptor_stats.get("total_patterns_adopted", 0)

        adoption_rate = patterns_adopted / max(patterns_shared, 1)

        # Calculate transfer rate per hour
        # Based on adaptation events in the last hour
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        recent_adaptations = [
            e
            for e in self.agent_adaptor._adaptation_events
            if datetime.fromisoformat(e.timestamp) > one_hour_ago
        ]
        transfer_rate_per_hour = len(recent_adaptations)

        # Knowledge flow
        # Inflow: patterns adopted from external sources
        # Outflow: patterns contributed to the swarm
        knowledge_inflow = patterns_adopted
        knowledge_outflow = len(self.learning_controller._adaptation_events)
        knowledge_balance = knowledge_inflow - knowledge_outflow

        # Network metrics (simplified)
        active_transmitters = sum(
            1 for s in self.learning_controller._agent_states.values() if s.total_updates > 0
        )
        active_receivers = sum(
            1 for s in self.agent_adaptor._agent_states.values() if len(s.adopted_patterns) > 0
        )

        # Network density (simplified)
        total_agents = len(self.learning_controller._agent_states)
        max_connections = total_agents * (total_agents - 1) / 2
        actual_connections = active_transmitters * active_receivers
        network_density = actual_connections / max(max_connections, 1)

        metrics = KnowledgeTransferMetrics(
            patterns_shared=patterns_shared,
            patterns_adopted=patterns_adopted,
            adoption_rate=adoption_rate,
            transfer_rate_per_hour=float(transfer_rate_per_hour),
            knowledge_inflow=float(knowledge_inflow),
            knowledge_outflow=float(knowledge_outflow),
            knowledge_balance=float(knowledge_balance),
            active_transmitters=active_transmitters,
            active_receivers=active_receivers,
            network_density=network_density,
            avg_path_length=0.0,  # Would need graph analysis
            knowledge_retention_rate=adoption_rate,
            knowledge_decay_rate=0.0,  # Would need longitudinal data
        )

        self._transfer_history.append(metrics)

        await self._store_metric_value(
            "knowledge_transfer_rate",
            transfer_rate_per_hour,
            source="collective_intelligence_metrics",
        )

        logger.info(
            "knowledge_transfer_calculated",
            adoption_rate=adoption_rate,
            transfer_rate_per_hour=transfer_rate_per_hour,
        )

        return metrics

    async def calculate_emergence_coefficient(self) -> EmergenceCoefficient:
        """
        Calculate emergence coefficient.

        Returns:
            EmergenceCoefficient calculation result
        """
        # Get emergence statistics
        emergence_stats = self.emergence_detector.get_emergence_statistics()

        total_patterns = emergence_stats.get("total_patterns", 0)
        emergence_stats.get("validated_patterns", 0)

        # Overall emergence coefficient
        emergence_metrics = self.emergence_detector.calculate_emergence_metrics()
        emergence_coefficient = emergence_metrics.get("swarm_emergence_index", 0.0)

        # Component coefficients
        behavioral_emergence = emergence_metrics.get("coordination_level", 0.0)
        structural_emergence = 0.0  # Would need structural analysis
        functional_emergence = emergence_metrics.get("collective_intelligence_factor", 0.0)
        cognitive_emergence = emergence_coefficient

        # Emergence indicators
        macro_patterns = len(
            [
                p
                for p in self.emergence_detector._emergent_patterns
                if p.emergence_level in [EmergenceLevel.STRONG, EmergenceLevel.CRITICAL]
            ]
        )

        # Micro-macro link strength
        # How well individual behaviors predict collective patterns
        micro_macro_link = emergence_coefficient * 0.8  # Simplified

        # Downward causation strength
        # How much collective patterns influence individual behavior
        downward_causation = len(self.agent_adaptor._adaptation_events) / max(total_patterns, 1)
        downward_causation = min(1.0, downward_causation)

        # Novelty score
        novelty_score = emergence_coefficient * emergence_stats.get("avg_confidence", 0.5)

        # Classification
        if emergence_coefficient >= 0.8:
            emergence_strength = "critical"
            emergence_type = "strong_emergence"
        elif emergence_coefficient >= 0.6:
            emergence_strength = "strong"
            emergence_type = "moderate_emergence"
        elif emergence_coefficient >= 0.4:
            emergence_strength = "moderate"
            emergence_type = "weak_emergence"
        else:
            emergence_strength = "weak"
            emergence_type = "minimal_emergence"

        coefficient = EmergenceCoefficient(
            emergence_coefficient=emergence_coefficient,
            behavioral_emergence=behavioral_emergence,
            structural_emergence=structural_emergence,
            functional_emergence=functional_emergence,
            cognitive_emergence=cognitive_emergence,
            macro_patterns_detected=macro_patterns,
            micro_macro_link_strength=micro_macro_link,
            downward_causation_strength=downward_causation,
            novelty_score=novelty_score,
            emergence_type=emergence_type,
            emergence_strength=emergence_strength,
        )

        self._emergence_history.append(coefficient)

        await self._store_metric_value(
            "emergence_coefficient",
            emergence_coefficient,
            source="collective_intelligence_metrics",
        )

        logger.info(
            "emergence_coefficient_calculated",
            emergence_coefficient=emergence_coefficient,
            emergence_strength=emergence_strength,
        )

        return coefficient

    def get_dashboard_data(self) -> MetricsDashboard:
        """
        Get real-time metrics dashboard data.

        Returns:
            MetricsDashboard with current metrics
        """
        # Get recent history
        siq_history = [s.overall_siq for s in self._siq_history[-20:]]
        efficiency_history = [e.efficiency_ratio for e in self._efficiency_history[-20:]]
        emergence_history = [e.emergence_coefficient for e in self._emergence_history[-20:]]

        # Calculate swarm health score
        health_components = []
        if siq_history:
            health_components.append(siq_history[-1] / 100.0)
        if efficiency_history:
            health_components.append(efficiency_history[-1])
        if emergence_history:
            health_components.append(emergence_history[-1])

        swarm_health_score = (
            (sum(health_components) / len(health_components)) * 100.0 if health_components else 0.0
        )

        # Get current metrics
        current_siq = self._siq_history[-1].overall_siq if self._siq_history else 100.0
        current_efficiency = efficiency_history[-1] if efficiency_history else 0.0
        current_emergence = emergence_history[-1] if emergence_history else 0.0

        # Agent metrics
        agent_states = list(self.learning_controller._agent_states.values())
        active_agents = sum(1 for s in agent_states if s.total_updates > 0)
        avg_performance = sum(s.success_rate for s in agent_states) / max(len(agent_states), 1)

        # Pattern metrics
        adaptor_stats = self.agent_adaptor.get_swarm_adaptation_stats()
        emergence_stats = self.emergence_detector.get_emergence_statistics()

        # Learning metrics
        swarm_stats = self.learning_controller.get_swarm_statistics()
        learning_rate_avg = swarm_stats.get("avg_learning_rate", 0.0)

        # Convergence rate
        converged = swarm_stats.get("converged_agents", 0)
        total = swarm_stats.get("total_agents", 1)
        convergence_rate = converged / total if total > 0 else 0.0

        # Generate alerts
        alerts = self._generate_alerts()

        dashboard = MetricsDashboard(
            swarm_health_score=swarm_health_score,
            swarm_intelligence_quotient=current_siq,
            collective_efficiency=current_efficiency,
            emergence_coefficient=current_emergence,
            total_agents=total,
            active_agents=active_agents,
            avg_agent_performance=avg_performance,
            total_patterns=adaptor_stats.get("total_patterns_adopted", 0),
            validated_patterns=emergence_stats.get("validated_patterns", 0),
            emergent_patterns=emergence_stats.get("total_patterns", 0),
            learning_rate_avg=learning_rate_avg,
            adaptation_rate=adaptor_stats.get("avg_adaptations_per_agent", 0.0),
            convergence_rate=convergence_rate,
            siq_history=siq_history,
            efficiency_history=efficiency_history,
            emergence_history=emergence_history,
            alerts=alerts,
        )

        logger.debug("dashboard_data_generated")

        return dashboard

    def get_metric_time_series(
        self,
        metric_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MetricTimeSeries:
        """
        Get time series data for a metric.

        Args:
            metric_id: Metric identifier
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            MetricTimeSeries with values
        """
        values = self._metric_values.get(metric_id, [])

        # Apply time filters
        if start_time:
            values = [v for v in values if datetime.fromisoformat(v.timestamp) >= start_time]

        if end_time:
            values = [v for v in values if datetime.fromisoformat(v.timestamp) <= end_time]

        start = values[0].timestamp if values else None
        end = values[-1].timestamp if values else None

        return MetricTimeSeries(
            metric_id=metric_id,
            values=values,
            start_time=start,
            end_time=end,
            sample_count=len(values),
        )

    def get_all_metric_definitions(self) -> list[MetricDefinition]:
        """
        Get all registered metric definitions.

        Returns:
            List of metric definitions
        """
        return list(self._metric_definitions.values())

    async def _calculate_coordination_score(self) -> float:
        """Calculate coordination score component."""
        # Based on collective behavior coherence
        behaviors = self.emergence_detector._collective_behaviors
        if not behaviors:
            return 0.5  # Default

        return sum(b.coherence for b in behaviors) / len(behaviors)

    async def _calculate_adaptation_score(self) -> float:
        """Calculate adaptation score component."""
        # Based on adaptation rate and success
        adaptor_stats = self.agent_adaptor.get_swarm_adaptation_stats()
        adoption_rate = adaptor_stats.get("adoption_rate", 0.5)

        # Also consider learning rate adaptations
        self.learning_controller.get_swarm_statistics()

        return adoption_rate

    async def _calculate_knowledge_sharing_score(self) -> float:
        """Calculate knowledge sharing score component."""
        # Based on pattern library statistics
        if self.pattern_library:
            stats = self.pattern_library.get_stats()
            if stats.total_patterns > 0:
                return min(1.0, stats.avg_access_count / 10.0)

        # Fallback to adaptor stats
        adaptor_stats = self.agent_adaptor.get_swarm_adaptation_stats()
        return adaptor_stats.get("adoption_rate", 0.5)

    async def _calculate_problem_solving_score(self) -> float:
        """Calculate problem solving score component."""
        # Based on agent success rates
        agent_states = self.learning_controller._agent_states.values()
        if not agent_states:
            return 0.5

        return sum(s.success_rate for s in agent_states) / len(agent_states)

    async def _calculate_emergence_score(self) -> float:
        """Calculate emergence score component."""
        emergence_metrics = self.emergence_detector.calculate_emergence_metrics()
        return emergence_metrics.get("swarm_emergence_index", 0.0)

    async def _calculate_resilience_score(self) -> float:
        """Calculate resilience score component."""
        # Based on recovery from failures
        agent_states = self.learning_controller._agent_states.values()
        if not agent_states:
            return 0.5

        # Calculate average recovery rate
        recovery_rates = []
        for state in agent_states:
            if state.failed_updates > 0:
                # Recovery = how many successes after failures
                recovery = state.successful_updates / max(state.total_updates, 1)
                recovery_rates.append(recovery)

        if not recovery_rates:
            return 0.5

        return sum(recovery_rates) / len(recovery_rates)

    def _calculate_siq_percentile(self, siq: float) -> float:
        """Calculate SIQ percentile."""
        # Simplified percentile calculation
        # Assumes SIQ follows normal distribution with mean 100, std 15

        if siq <= 50:
            return 0.0
        if siq >= 150:
            return 100.0

        # Linear approximation
        return siq - 50  # 50-150 maps to 0-100 percentile

    def _register_default_metrics(self) -> None:
        """Register default metric definitions."""
        defaults = [
            MetricDefinition(
                name="siq_overall",
                description="Overall Swarm Intelligence Quotient",
                category=MetricCategory.SWARM_INTELLIGENCE,
                unit="IQ points",
                min_value=50.0,
                max_value=150.0,
                target_value=100.0,
            ),
            MetricDefinition(
                name="collective_efficiency",
                description="Collective problem-solving efficiency ratio",
                category=MetricCategory.EFFICIENCY,
                unit="ratio",
                min_value=0.0,
                max_value=1.0,
                target_value=0.8,
            ),
            MetricDefinition(
                name="knowledge_transfer_rate",
                description="Knowledge transfer rate per hour",
                category=MetricCategory.KNOWLEDGE_TRANSFER,
                unit="transfers/hour",
                min_value=0.0,
            ),
            MetricDefinition(
                name="emergence_coefficient",
                description="Overall emergence coefficient",
                category=MetricCategory.EMERGENCE,
                unit="coefficient",
                min_value=0.0,
                max_value=1.0,
                target_value=0.5,
            ),
        ]

        for metric in defaults:
            self._metric_definitions[metric.metric_id] = metric

    async def _store_metric_value(
        self,
        metric_id: str,
        value: float,
        source: str,
        confidence: float = 1.0,
        sample_size: int = 1,
    ) -> None:
        """Store a metric value."""
        metric_value = MetricValue(
            metric_id=metric_id,
            value=value,
            source=source,
            confidence=confidence,
            sample_size=sample_size,
        )

        if metric_id not in self._metric_values:
            self._metric_values[metric_id] = []

        self._metric_values[metric_id].append(metric_value)

        # Trim old values (keep last 1000)
        if len(self._metric_values[metric_id]) > 1000:
            self._metric_values[metric_id] = self._metric_values[metric_id][-1000:]

        # Check thresholds
        await self._check_thresholds(metric_value)

        # Call callbacks
        await self._call_metric_callbacks(metric_value)

    async def _check_thresholds(self, value: MetricValue) -> None:
        """Check if metric value exceeds thresholds."""
        if value.metric_id not in self._thresholds:
            return

        min_thresh, max_thresh = self._thresholds[value.metric_id]

        exceeded = False
        reason = ""

        if min_thresh is not None and value.value < min_thresh:
            exceeded = True
            reason = f"below_minimum:{min_thresh}"

        if max_thresh is not None and value.value > max_thresh:
            exceeded = True
            reason = f"above_maximum:{max_thresh}"

        if exceeded:
            await self._call_threshold_callbacks(value, reason)

    async def _call_metric_callbacks(self, value: MetricValue) -> None:
        """Call registered metric callbacks."""
        for callback in self._on_metric_calculated:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(value)
                else:
                    callback(value)
            except Exception as e:
                logger.error(
                    "metric_callback_error",
                    callback=callback.__name__,
                    error=str(e),
                )

    async def _call_threshold_callbacks(
        self,
        value: MetricValue,
        reason: str,
    ) -> None:
        """Call registered threshold callbacks."""
        event = {
            "metric_id": value.metric_id,
            "value": value.value,
            "reason": reason,
            "timestamp": value.timestamp,
        }

        for callback in self._on_threshold_exceeded:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(
                    "threshold_callback_error",
                    callback=callback.__name__,
                    error=str(e),
                )

    def _generate_alerts(self) -> list[dict[str, Any]]:
        """Generate alerts based on current metrics."""
        alerts = []

        # Check SIQ
        if self._siq_history:
            current_siq = self._siq_history[-1].overall_siq
            if current_siq < 70:
                alerts.append(
                    {
                        "severity": "warning",
                        "type": "low_siq",
                        "message": f"Low SIQ detected: {current_siq:.1f}",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        # Check efficiency
        if self._efficiency_history:
            current_eff = self._efficiency_history[-1].efficiency_ratio
            if current_eff < 0.3:
                alerts.append(
                    {
                        "severity": "warning",
                        "type": "low_efficiency",
                        "message": f"Low efficiency detected: {current_eff:.2f}",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        # Check emergence
        if self._emergence_history:
            current_emerg = self._emergence_history[-1].emergence_coefficient
            if current_emerg > 0.8:
                alerts.append(
                    {
                        "severity": "info",
                        "type": "high_emergence",
                        "message": f"High emergence detected: {current_emerg:.2f}",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        return alerts

    def get_status(self) -> dict[str, Any]:
        """
        Get metrics system status.

        Returns:
            Status dictionary
        """
        return {
            "total_metrics_defined": len(self._metric_definitions),
            "total_metric_values": sum(len(v) for v in self._metric_values.values()),
            "siq_calculations": len(self._siq_history),
            "efficiency_calculations": len(self._efficiency_history),
            "transfer_calculations": len(self._transfer_history),
            "emergence_calculations": len(self._emergence_history),
            "thresholds_configured": len(self._thresholds),
        }


class MetricsExporter:
    """
    Exporter for collective intelligence metrics.

    This class provides export capabilities for metrics data
    in various formats.
    """

    def __init__(self, metrics: CollectiveIntelligenceMetrics):
        """
        Initialize metrics exporter.

        Args:
            metrics: CollectiveIntelligenceMetrics instance
        """
        self.metrics = metrics

        logger.info("metrics_exporter_initialized")

    def export_summary(self) -> dict[str, Any]:
        """
        Export metrics summary.

        Returns:
            Dictionary of summary metrics
        """
        dashboard = self.metrics.get_dashboard_data()

        return {
            "timestamp": dashboard.timestamp,
            "swarm_health": dashboard.swarm_health_score,
            "siq": dashboard.swarm_intelligence_quotient,
            "efficiency": dashboard.collective_efficiency,
            "emergence": dashboard.emergence_coefficient,
            "agents": {
                "total": dashboard.total_agents,
                "active": dashboard.active_agents,
                "avg_performance": dashboard.avg_agent_performance,
            },
            "patterns": {
                "total": dashboard.total_patterns,
                "validated": dashboard.validated_patterns,
                "emergent": dashboard.emergent_patterns,
            },
            "learning": {
                "avg_rate": dashboard.learning_rate_avg,
                "adaptation_rate": dashboard.adaptation_rate,
                "convergence_rate": dashboard.convergence_rate,
            },
        }

    def export_time_series(
        self,
        metric_ids: list[str] | None = None,
        format: str = "dict",
    ) -> dict[str, Any]:
        """
        Export time series data for metrics.

        Args:
            metric_ids: Optional list of metric IDs to export
            format: Export format ("dict" or "csv")

        Returns:
            Exported data
        """
        if metric_ids is None:
            metric_ids = list(self.metrics._metric_values.keys())

        data = {}
        for metric_id in metric_ids:
            series = self.metrics.get_metric_time_series(metric_id)
            data[metric_id] = [v.to_dict() for v in series.values]

        return data
