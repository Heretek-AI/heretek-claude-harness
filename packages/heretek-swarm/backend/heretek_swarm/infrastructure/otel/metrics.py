"""
OpenTelemetry Metrics for Heretek Swarm.

Provides metrics collection based on OpenTelemetry standards.
Supports counters, gauges, histograms, and summaries.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MetricType(Enum):
    """Metric types supported."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    UNKNOWN = "unknown"


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""

    service_name: str = "heretek-swarm"
    exporter: str = "console"  # console, prometheus, otlp
    endpoint: str | None = None
    export_interval_seconds: int = 60
    collect_default_metrics: bool = True


@dataclass
class MetricPoint:
    """A single measurement point."""

    value: float | int  # No default - must be provided
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = field(default_factory=dict)
    count: int = 1  # For aggregated metrics


@dataclass
class Metric:
    """A metric definition and its current value."""

    name: str
    metric_type: MetricType
    description: str = ""
    unit: str = ""
    value: float | int = 0
    points: list[MetricPoint] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a measurement."""
        self.value = value
        point = MetricPoint(
            value=value,
            labels=labels or {},
        )
        self.points.append(point)

        # Keep last 1000 points
        if len(self.points) > 1000:
            self.points = self.points[-1000:]

    def increment(self, amount: float = 1, labels: dict[str, str] | None = None) -> None:
        """Increment a counter."""
        if self.metric_type != MetricType.COUNTER:
            logger.warning("increment_on_non_counter", metric_name=self.name)
        self.record(self.value + amount, labels)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "description": self.description,
            "unit": self.unit,
            "value": self.value,
            "labels": self.labels,
            "point_count": len(self.points),
        }


# =============================================================================
# Global Metrics State
# =============================================================================

_metrics_config: MetricsConfig | None = None
_metrics: dict[str, Metric] = {}
_meter_instance: "Meter | None" = None


def init_metrics(config: MetricsConfig | None = None) -> MetricsConfig:
    """Initialize metrics collection."""
    global _metrics_config, _meter_instance
    _metrics_config = config or MetricsConfig()
    _meter_instance = Meter(_metrics_config)

    logger.info(
        "metrics_initialized",
        service_name=_metrics_config.service_name,
        exporter=_metrics_config.exporter,
    )

    return _metrics_config


def get_meter(service_name: str | None = None) -> "Meter":
    """Get the meter instance."""
    global _metrics_config, _meter_instance

    if _meter_instance is None:
        config = _metrics_config or MetricsConfig()
        if service_name:
            config.service_name = service_name
        _meter_instance = Meter(config)

    return _meter_instance


def record_metric(
    name: str,
    value: float,
    metric_type: MetricType = MetricType.GAUGE,
    labels: dict[str, str] | None = None,
) -> None:
    """Record a metric value globally."""
    meter = get_meter()
    meter.record(name, value, metric_type, labels)


# =============================================================================
# Meter Implementation
# =============================================================================


class Meter:
    """
    OpenTelemetry-compatible meter.

    Creates and manages metrics instruments.
    """

    def __init__(self, config: MetricsConfig):
        self.config = config
        self._instruments: dict[str, Metric] = {}

    def create_counter(
        self,
        name: str,
        description: str = "",
        unit: str = "",
    ) -> "_Counter":
        """Create a counter metric."""
        metric = Metric(
            name=name,
            metric_type=MetricType.COUNTER,
            description=description,
            unit=unit,
        )
        self._instruments[name] = metric
        return _Counter(metric)

    def create_gauge(
        self,
        name: str,
        description: str = "",
        unit: str = "",
    ) -> "_Gauge":
        """Create a gauge metric."""
        metric = Metric(
            name=name,
            metric_type=MetricType.GAUGE,
            description=description,
            unit=unit,
        )
        self._instruments[name] = metric
        return _Gauge(metric)

    def create_histogram(
        self,
        name: str,
        description: str = "",
        unit: str = "",
    ) -> "_Histogram":
        """Create a histogram metric."""
        metric = Metric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            description=description,
            unit=unit,
        )
        self._instruments[name] = metric
        return _Histogram(metric)

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a value for a named metric."""
        if name not in self._instruments:
            self._instruments[name] = Metric(
                name=name,
                metric_type=metric_type,
            )

        self._instruments[name].record(value, labels)
        logger.debug("metric_recorded", name=name, value=value)

    def get_metric(self, name: str) -> Metric | None:
        """Get a metric by name."""
        return self._instruments.get(name)

    def list_metrics(self) -> list[dict[str, Any]]:
        """List all metrics."""
        return [m.to_dict() for m in self._instruments.values()]

    def export(self) -> dict[str, Any]:
        """Export all metrics."""
        return {
            "service_name": self.config.service_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": self.list_metrics(),
        }


class _Counter:
    """A counter metric instrument."""

    def __init__(self, metric: Metric):
        self._metric = metric

    @property
    def name(self) -> str:
        return self._metric.name

    @property
    def value(self) -> float | int:
        return self._metric.value

    def add(self, amount: float = 1, labels: dict[str, str] | None = None) -> None:
        """Add to the counter."""
        self._metric.record(self._metric.value + amount, labels)

    def get(self) -> float | int:
        """Get current value."""
        return self._metric.value


class _Gauge:
    """A gauge metric instrument."""

    def __init__(self, metric: Metric):
        self._metric = metric

    @property
    def name(self) -> str:
        return self._metric.name

    @property
    def value(self) -> float | int:
        return self._metric.value

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge value."""
        self._metric.record(value, labels)

    def get(self) -> float | int:
        """Get current value."""
        return self._metric.value


class _Histogram:
    """A histogram metric instrument."""

    def __init__(self, metric: Metric):
        self._metric = metric
        self._values: list[float] = []

    @property
    def name(self) -> str:
        return self._metric.name

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a value in the histogram."""
        self._values.append(value)
        self._metric.record(value, labels)

        # Keep last 10000 values
        if len(self._values) > 10000:
            self._values = self._values[-10000:]

    def count(self) -> int:
        """Get count of recorded values."""
        return len(self._values)

    def mean(self) -> float:
        """Get mean of recorded values."""
        if not self._values:
            return 0.0
        return sum(self._values) / len(self._values)

    def percentile(self, p: float) -> float:
        """Get percentile of recorded values."""
        if not self._values:
            return 0.0
        sorted_values = sorted(self._values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


class MetricsCollector:
    """
    Collects and aggregates metrics.

    Provides pre-built collectors for common metrics like:
    - Agent metrics (active_count, completed_tasks, etc.)
    - System metrics (cpu, memory, etc.)
    - Business metrics (deliberations, consensus, etc.)
    """

    def __init__(self, meter: Meter):
        self.meter = meter
        self._collectors: dict[str, Any] = {}
        self._setup_default_collectors()

    def _setup_default_collectors(self) -> None:
        """Set up default metric collectors."""
        # Agent metrics
        self.meter.create_gauge(
            "swarm.agents.active",
            "Number of active agents",
        )
        self.meter.create_counter(
            "swarm.agents.total",
            "Total agents created",
        )
        self.meter.create_counter(
            "swarm.tasks.completed",
            "Total tasks completed",
        )
        self.meter.create_counter(
            "swarm.tasks.failed",
            "Total tasks failed",
        )

        # Consensus metrics
        self.meter.create_counter(
            "swarm.consensus.proposals",
            "Total consensus proposals",
        )
        self.meter.create_counter(
            "swarm.consensus.decisions",
            "Total consensus decisions",
        )

        # Consciousness metrics
        self.meter.create_histogram(
            "swarm.consciousness.iit",
            "IIT consciousness scores",
        )
        self.meter.create_histogram(
            "swarm.consciousness.ast",
            "AST consciousness scores",
        )

    def record_agent_active(self, agent_id: str) -> None:
        """Record an agent becoming active."""
        self.meter.record("swarm.agents.active", 1, MetricType.GAUGE, {"agent_id": agent_id})

    def record_task_completed(self, agent_id: str, task_type: str | None = None) -> None:
        """Record a completed task."""
        labels = {"agent_id": agent_id}
        if task_type:
            labels["task_type"] = task_type
        self.meter.record("swarm.tasks.completed", 1, MetricType.COUNTER, labels)

    def record_consensus_decision(
        self,
        topic: str,
        outcome: str,
        participants: int,
    ) -> None:
        """Record a consensus decision."""
        self.meter.record(
            "swarm.consensus.decisions",
            1,
            MetricType.COUNTER,
            {"topic": topic, "outcome": outcome, "participants": str(participants)},
        )

    def record_iit_score(
        self,
        agent_id: str,
        score: float,
        phi_components: dict[str, float] | None = None,
    ) -> None:
        """Record IIT consciousness score."""
        labels = {"agent_id": agent_id}
        if phi_components:
            for key, value in phi_components.items():
                labels[f"phi_{key}"] = str(value)

        self.meter.record("swarm.consciousness.iit", score, MetricType.HISTOGRAM, labels)

    def record_ast_score(
        self,
        agent_id: str,
        score: float,
        dimensions: dict[str, float] | None = None,
    ) -> None:
        """Record AST consciousness score."""
        labels = {"agent_id": agent_id}
        if dimensions:
            for key, value in dimensions.items():
                labels[f"ast_{key}"] = str(value)

        self.meter.record("swarm.consciousness.ast", score, MetricType.HISTOGRAM, labels)


__all__ = [
    "Meter",
    "Metric",
    "MetricPoint",
    "MetricType",
    "MetricsCollector",
    "MetricsConfig",
    "get_meter",
    "init_metrics",
    "record_metric",
]
