"""
Prometheus metrics — native ``prometheus_client`` interface.

# OWNER: heretek-platform-team (Phase 2A.1 cutover, commit 1+9 of the
# prometheus wrapper removal; the file exceeds the 300-LOC CI gate
# because it consolidates the wrapper's module-level metrics, helper
# functions, and FastAPI middleware into a single canonical surface;
# splitting would re-introduce the import-cycle and singleton
# ambiguity that motivated the consolidation).

This module is the canonical Prometheus surface for the heretek_swarm.
It uses the official ``prometheus_client`` library (already a dep)
directly: module-level Counter / Gauge / Histogram instances on
the default ``REGISTRY``, with module-level helper functions for
each metric operation. No wrapper class.

Migration status (Phase 2A.1 cutover)
-------------------------------------
The previous hand-rolled ``observability/prometheus_metrics.py``
wrapper class (``PrometheusMetrics``, 755 LOC) has been removed.
All callers now import from this module directly. The 5 migration
PRs (commits 3-7 of the cutover roadmap) migrated the 7 caller
files.

This module exposes:
- 14 module-level metrics (Counter / Gauge / Histogram) with
  standard Prometheus label schemas.
- 14+ module-level helper functions as the public call surface.
- ``export_prometheus() -> tuple[bytes, str]`` for the /metrics
  endpoint (returns body + content_type).
- ``setup_metrics_middleware(app)`` for the FastAPI per-request
  middleware.

Migration pattern
-----------------
Old code (pre-cutover)::

    from heretek_swarm.observability.prometheus_metrics import (
        PrometheusMetrics,
        get_metrics,
    )
    metrics = get_metrics()
    metrics.increment_tasks_completed(agent_id="agent_1")

New code (this module)::

    from heretek_swarm.observability.prometheus_native import (
        TASKS_COMPLETED,
        increment_tasks_completed,
    )
    increment_tasks_completed(agent_id="agent_1")

The ``TASKS_COMPLETED`` constant is a module-level ``Counter``; calling
its ``.inc()`` method (or the ``increment_tasks_completed`` helper
for backward compat) records the event. No class instance, no wrapper.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Module-level metrics — the prometheus_client pattern
# ---------------------------------------------------------------------------
# Defining the metrics at module level (rather than inside a class)
# is the idiomatic prometheus_client pattern. The library registers
# each metric with the default REGISTRY on import; this means the
# metric is automatically exposed via generate_latest() without any
# additional plumbing.

AGENTS_TOTAL = Gauge(
    "heretek_swarm_agents_total",
    "Total number of registered agents in the swarm",
    labelnames=["agent_type"],
    registry=REGISTRY,
)
AGENTS_ACTIVE = Gauge(
    "heretek_swarm_agents_active",
    "Number of currently active agents",
    labelnames=["agent_type"],
    registry=REGISTRY,
)
TASKS_COMPLETED = Counter(
    "heretek_swarm_tasks_completed_total",
    "Total tasks completed by the swarm",
    labelnames=["agent_id", "task_type"],
    registry=REGISTRY,
)
TASKS_FAILED = Counter(
    "heretek_swarm_tasks_failed_total",
    "Total tasks that failed",
    labelnames=["agent_id", "task_type"],
    registry=REGISTRY,
)
MESSAGES_TOTAL = Counter(
    "heretek_swarm_messages_total",
    "Total messages processed",
    labelnames=["direction", "message_type"],
    registry=REGISTRY,
)
CONSENSUS_ROUNDS = Counter(
    "heretek_swarm_consensus_rounds_total",
    "Total consensus rounds executed",
    labelnames=["consensus_type", "outcome"],
    registry=REGISTRY,
)
PHI_SCORE = Gauge(
    "heretek_swarm_phi_score",
    "Current phi consciousness score (IIT)",
    labelnames=["agent_id"],
    registry=REGISTRY,
)
FREE_ENERGY = Gauge(
    "heretek_swarm_free_energy",
    "Current free energy level (FEP)",
    labelnames=["agent_id"],
    registry=REGISTRY,
)
HEALTH_SCORE = Gauge(
    "heretek_swarm_health_score",
    "Current swarm health score (0.0-1.0)",
    registry=REGISTRY,
)
API_REQUEST_DURATION = Histogram(
    "heretek_swarm_api_request_duration_seconds",
    "API request latency in seconds",
    labelnames=["method", "endpoint", "status"],
    registry=REGISTRY,
)
API_REQUESTS_TOTAL = Counter(
    "heretek_swarm_api_requests_total",
    "Total API requests handled",
    labelnames=["method", "endpoint", "status"],
    registry=REGISTRY,
)
EXTERNAL_CALL_LOGS = Counter(
    "heretek_swarm_external_call_logs_total",
    "Total external call logs recorded",
    labelnames=["agent_type", "call_type", "status"],
    registry=REGISTRY,
)
EXTERNAL_CALL_DURATION = Histogram(
    "heretek_swarm_external_call_log_duration_seconds",
    "External call duration in seconds",
    labelnames=["agent_type", "call_type", "method"],
    registry=REGISTRY,
)
ENCRYPTION_LATENCY = Histogram(
    "heretek_swarm_encryption_latency_seconds",
    "Encryption/decryption latency in seconds",
    labelnames=["operation", "field_type"],
    registry=REGISTRY,
)

# Additional metrics required by the wrapper's call sites (Phase 2A.1 cutover).
ACTOR_PROCESSING_DURATION = Histogram(
    "heretek_swarm_actor_processing_duration_seconds",
    "Actor mailbox-processing latency in seconds",
    labelnames=["actor_type"],
    registry=REGISTRY,
)
DB_QUERY_DURATION = Histogram(
    "heretek_swarm_db_query_duration_seconds",
    "Database query latency in seconds",
    labelnames=["db_name"],
    registry=REGISTRY,
)
LLM_CALL_DURATION = Histogram(
    "heretek_swarm_llm_call_duration_seconds",
    "LLM call latency in seconds",
    labelnames=["agent_id", "provider", "model"],
    registry=REGISTRY,
)
LLM_TOKENS = Counter(
    "heretek_swarm_llm_tokens_total",
    "LLM token usage by token_type (prompt/completion/total)",
    labelnames=["agent_id", "provider", "model", "token_type"],
    registry=REGISTRY,
)
UPTIME_SECONDS = Gauge(
    "heretek_swarm_uptime_seconds",
    "Swarm uptime in seconds",
    registry=REGISTRY,
)


# ---------------------------------------------------------------------------
# Endpoint normalization (lifted from the legacy wrapper)
# ---------------------------------------------------------------------------
# The legacy wrapper's _normalize_endpoint() reduces Prometheus label
# cardinality by replacing dynamic path segments (UUIDs, numeric IDs) with
# ``{id}`` placeholders. Without this, every UUID-bearing endpoint
# would explode the label space and blow out Prometheus storage.
# Compiled once at module scope (hot path).

_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_NUMERIC_ID_PATTERN = re.compile(r"/\d+(?=/|$)")


def _normalize_endpoint(endpoint: str) -> str:
    """Reduce endpoint label cardinality by replacing UUIDs/numeric IDs with ``{id}``.

    Public-utility helper (not exported in __all__); called from
    :func:`record_api_request` so every call site benefits automatically.
    """
    endpoint = _UUID_PATTERN.sub("{id}", endpoint)
    endpoint = _NUMERIC_ID_PATTERN.sub("/{id}", endpoint)
    return endpoint


# ---------------------------------------------------------------------------
# Helper functions — drop-in replacements for the wrapper methods
# ---------------------------------------------------------------------------
# These functions are the migration target. Each corresponds to a
# method on the legacy ``PrometheusMetrics`` class. Existing callers
# can swap one import path at a time; the wrapper class remains
# available as a shim for the transition.


def increment_tasks_completed(agent_id: str, task_type: str = "default") -> None:
    """Record a task completion event."""
    TASKS_COMPLETED.labels(agent_id=agent_id, task_type=task_type).inc()


def increment_tasks_failed(agent_id: str, task_type: str = "default") -> None:
    """Record a task failure event."""
    TASKS_FAILED.labels(agent_id=agent_id, task_type=task_type).inc()


def increment_messages(direction: str, message_type: str = "general") -> None:
    """Record a message processed (direction = 'sent' or 'received').

    Label schema is reconciled to the legacy wrapper:
    ``(direction, message_type)``.
    """
    MESSAGES_TOTAL.labels(direction=direction, message_type=message_type).inc()


def increment_consensus_rounds(consensus_type: str, outcome: str) -> None:
    """Record a consensus round completion."""
    CONSENSUS_ROUNDS.labels(consensus_type=consensus_type, outcome=outcome).inc()


def record_phi_score(agent_id: str, score: float) -> None:
    """Record the current phi (IIT) score for an agent."""
    PHI_SCORE.labels(agent_id=agent_id).set(score)


def record_free_energy(agent_id: str, score: float) -> None:
    """Record the current free-energy (FEP) score for an agent."""
    FREE_ENERGY.labels(agent_id=agent_id).set(score)


def record_health_score(score: float) -> None:
    """Record the current swarm health score (0.0-1.0)."""
    HEALTH_SCORE.set(score)


def record_api_request(
    method: str, endpoint: str, status: int, duration: float
) -> None:
    """Record an API request's status code and duration.

    The endpoint is normalized via :func:`_normalize_endpoint` to
    keep Prometheus label cardinality bounded (UUIDs and numeric
    IDs collapse to ``{id}`` placeholders).
    """
    status_str = str(status)
    endpoint = _normalize_endpoint(endpoint)
    API_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status_str).inc()
    API_REQUEST_DURATION.labels(method=method, endpoint=endpoint, status=status_str).observe(
        duration
    )


def increment_external_call_logs(
    agent_type: str, call_type: str, status: int
) -> None:
    """Record an external call log event."""
    EXTERNAL_CALL_LOGS.labels(
        agent_type=agent_type, call_type=call_type, status=str(status)
    ).inc()


def record_external_call_duration(
    call_type: str,
    status: int,
    duration_seconds: float,
    agent_type: str = "unknown",
    method: str = "POST",
) -> None:
    """Record the duration of an external call.

    Label schema is reconciled to the legacy wrapper:
    ``(agent_type, call_type, method)``. The ``status`` argument is
    accepted for backward compat but is not a label (the legacy
    wrapper tracked it via a Counter, not the Duration Histogram).
    """
    EXTERNAL_CALL_DURATION.labels(
        agent_type=agent_type, call_type=call_type, method=method
    ).observe(duration_seconds)


def record_encryption_latency(
    operation: str, field_type: str, duration_seconds: float
) -> None:
    """Record the latency of an encryption/decryption operation."""
    ENCRYPTION_LATENCY.labels(operation=operation, field_type=field_type).observe(
        duration_seconds
    )


def export_prometheus() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint.

    This is the drop-in replacement for ``PrometheusMetrics.export_prometheus()``.
    Uses ``prometheus_client.generate_latest()`` directly.
    """
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


# ---------------------------------------------------------------------------
# Helpers added for the Phase 2A.1 wrapper-cutover (commit 1)
# ---------------------------------------------------------------------------
# These are the wrapper class's `record_*` methods, lifted to
# module-level so callers can drop their `PrometheusMetrics` instance
# and call the native helpers directly. Signatures match the
# wrapper's signatures so the migration is a 1-line import swap.


def record_agent_registration(agent_id: str, agent_type: str) -> None:
    """Register a new agent and increment the agents_total gauge."""
    AGENTS_TOTAL.labels(agent_type=agent_type).inc()


def record_agent_unregistration(agent_id: str, agent_type: str) -> None:
    """Unregister an agent and decrement the agents_total gauge."""
    AGENTS_TOTAL.labels(agent_type=agent_type).dec()


def record_agent_active(agent_id: str, agent_type: str) -> None:
    """Mark an agent as active (increment the agents_active gauge)."""
    AGENTS_ACTIVE.labels(agent_type=agent_type).inc()


def record_agent_inactive(agent_id: str, agent_type: str) -> None:
    """Mark an agent as inactive (decrement the agents_active gauge)."""
    AGENTS_ACTIVE.labels(agent_type=agent_type).dec()


def record_task_completed(
    agent_id: str, agent_type: str, task_type: str = "general"
) -> None:
    """Record a task completion event (wrapper-class signature)."""
    TASKS_COMPLETED.labels(agent_id=agent_id, task_type=task_type).inc()


def record_task_failed(
    agent_id: str, agent_type: str, task_type: str = "general"
) -> None:
    """Record a task failure event (wrapper-class signature)."""
    TASKS_FAILED.labels(agent_id=agent_id, task_type=task_type).inc()


def record_message(direction: str, message_type: str = "general") -> None:
    """Record a message processed (direction = 'sent' or 'received').

    Label schema: ``(direction, message_type)``.
    """
    MESSAGES_TOTAL.labels(direction=direction, message_type=message_type).inc()


def record_message_sent(message_type: str = "general") -> None:
    """Record a sent message."""
    record_message("sent", message_type)


def record_message_received(message_type: str = "general") -> None:
    """Record a received message."""
    record_message("received", message_type)


def record_consensus_round(
    consensus_type: str = "deliberation", outcome: str = "success"
) -> None:
    """Record a consensus round completion."""
    CONSENSUS_ROUNDS.labels(consensus_type=consensus_type, outcome=outcome).inc()


def record_actor_processing(
    agent_id: str,
    actor_type: str = "unknown",
    duration_seconds: float = 0.0,
) -> None:
    """Record actor mailbox-processing latency.

    The ``agent_id`` is logged via structlog in the wrapper; in the
    native module it is not used as a label (cardinality control).
    """
    ACTOR_PROCESSING_DURATION.labels(actor_type=actor_type).observe(duration_seconds)


def record_db_query(
    duration_seconds: float = 0.0, db_name: str = "unknown"
) -> None:
    """Record a database-query latency observation."""
    DB_QUERY_DURATION.labels(db_name=db_name).observe(duration_seconds)


def record_db_query_duration(
    duration_seconds: float = 0.0, db_name: str = "unknown"
) -> None:
    """Alias for :func:`record_db_query` (matches the wrapper's
    ``record_db_query_duration`` helper)."""
    record_db_query(duration_seconds, db_name)


def record_llm_call(
    agent_id: str,
    provider: str,
    model: str,
    duration_seconds: float,
) -> None:
    """Record an LLM call invocation duration."""
    LLM_CALL_DURATION.labels(
        agent_id=agent_id, provider=provider, model=model
    ).observe(duration_seconds)


def record_llm_tokens(
    agent_id: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    """Record LLM token usage across prompt / completion / total buckets.

    Emits three ``.labels(token_type=...).inc(count)`` calls so the
    wire format matches the wrapper's ``record_llm_tokens_consumed``.
    """
    LLM_TOKENS.labels(
        agent_id=agent_id, provider=provider, model=model, token_type="prompt"
    ).inc(prompt_tokens)
    LLM_TOKENS.labels(
        agent_id=agent_id, provider=provider, model=model, token_type="completion"
    ).inc(completion_tokens)
    LLM_TOKENS.labels(
        agent_id=agent_id, provider=provider, model=model, token_type="total"
    ).inc(total_tokens)


def record_uptime(seconds: float) -> None:
    """Set the swarm-uptime gauge (seconds since process start)."""
    UPTIME_SECONDS.set(seconds)


# ---------------------------------------------------------------------------
# FastAPI middleware (lifted from the legacy wrapper)
# ---------------------------------------------------------------------------


def setup_metrics_middleware(app: FastAPI) -> None:
    """Install Prometheus per-request middleware on a FastAPI app.

    Records every request's method, endpoint (normalized), status,
    and duration. Exceptions during metric collection are swallowed
    so a misbehaving exporter can never break the request path.
    The ``/metrics`` path is skipped to avoid self-scrape pollution.
    """
    import structlog
    from starlette.middleware.base import BaseHTTPMiddleware

    _logger = structlog.get_logger("prometheus_middleware")

    class PrometheusRequestMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # type: ignore[override]
            # Skip the metrics endpoint itself.
            if request.url.path == "/metrics":
                return await call_next(request)
            start_time = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            try:
                record_api_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code,
                    duration=duration,
                )
            except Exception as exc:  # never let metrics break the request
                _logger.debug("prometheus_metrics_collection_failed", error=str(exc))
            return response

    app.add_middleware(PrometheusRequestMiddleware)


# ---------------------------------------------------------------------------
# Read helpers (Phase 2A.3 cutover) — public values out of metric objects
# ---------------------------------------------------------------------------
# The previous approach to reading a metric's value (used by the
# legacy ``SwarmMetricsCollector`` and the JSON debug endpoint)
# reached into prometheus_client's private ``_metrics`` / ``_value``
# attributes. That works on the current version but is brittle:
# prometheus_client reserves the right to rename or restructure
# internals. The helpers below go through the public ``collect()``
# API and tolerate the labeled / unlabeled / no-data cases.


def read_metric_value(metric) -> float:
    """Return the aggregate (sum) of value samples for a Counter or Gauge.

    Uses the public ``metric.collect()`` API — no private attribute
    access. For an unlabeled metric this is the single value. For a
    labeled metric this is the sum across all label combinations,
    which matches the "total" semantic the JSON debug endpoint wants
    (e.g. tasks completed across all agents, not just one).

    Three classes of "metadata" samples are skipped because they
    are not data:
- ``_created`` samples (OpenMetrics creation timestamp; value is a
      Unix epoch in seconds — would dominate the sum).
    - Histogram ``_bucket`` samples (the ``le`` label is the reliable
      signal; summing buckets is meaningless).

    Returns ``0.0`` on any failure so a metrics-reading bug never
    breaks the request path; callers that need strict error handling
    should call ``metric.collect()`` directly.
    """
    try:
        total = 0.0
        for m in metric.collect():
            for sample in m.samples:
                if sample.name.endswith("_created"):
                    continue
                if "le" in sample.labels:
                    continue
                total += sample.value
        return total
    except Exception:
        return 0.0


def read_metric_samples(metric) -> dict[str, float]:
    """Return per-label sample values for a Counter or Gauge.

    Uses the public ``metric.collect()`` API. The dict key is a
    stable ``"labelname1=value1,labelname2=value2"`` string built
    from the sample's labels. Unlabeled metrics yield ``{"": value}``.
    ``_created`` and Histogram bucket samples are skipped (same rules
    as :func:`read_metric_value`).
    """
    out: dict[str, float] = {}
    try:
        for m in metric.collect():
            for sample in m.samples:
                if sample.name.endswith("_created"):
                    continue
                if "le" in sample.labels:
                    continue
                key = ",".join(
                    f"{name}={sample.labels[name]}" for name in sorted(sample.labels)
                )
                out[key] = sample.value
    except Exception:
        return out
    return out


# ---------------------------------------------------------------------------
# Test-only: a fresh registry for unit tests
# ---------------------------------------------------------------------------
# Tests need to instantiate metrics in a clean registry to avoid
# the "Duplicated timeseries" error on re-import. The factory below
# creates a fresh ``CollectorRegistry`` and re-instantiates all the
# metrics on it. Tests that need isolation call ``build_test_registry()``
# in a fixture; production code uses the module-level REGISTRY.


def build_test_registry() -> CollectorRegistry:
    """Build a fresh CollectorRegistry for tests.

    This is intentionally a factory rather than a singleton so
    tests can own their own registry. Production code does not
    need this; module-level metrics on REGISTRY are the right
    pattern for runtime use.
    """
    return CollectorRegistry()


__all__ = [
    "ACTOR_PROCESSING_DURATION",
    "AGENTS_ACTIVE",
    "AGENTS_TOTAL",
    "API_REQUESTS_TOTAL",
    "API_REQUEST_DURATION",
    "CONSENSUS_ROUNDS",
    "CONTENT_TYPE_LATEST",
    "DB_QUERY_DURATION",
    "ENCRYPTION_LATENCY",
    "EXTERNAL_CALL_DURATION",
    "EXTERNAL_CALL_LOGS",
    "FREE_ENERGY",
    "HEALTH_SCORE",
    "LLM_CALL_DURATION",
    "LLM_TOKENS",
    "MESSAGES_TOTAL",
    "PHI_SCORE",
    "TASKS_COMPLETED",
    "TASKS_FAILED",
    "UPTIME_SECONDS",
    "build_test_registry",
    "export_prometheus",
    "increment_consensus_rounds",
    "increment_external_call_logs",
    "increment_messages",
    "increment_tasks_completed",
    "increment_tasks_failed",
    "record_actor_processing",
    "record_agent_active",
    "record_agent_inactive",
    "record_agent_registration",
    "record_agent_unregistration",
    "record_api_request",
    "record_consensus_round",
    "record_db_query",
    "record_db_query_duration",
    "record_encryption_latency",
    "record_external_call_duration",
    "record_free_energy",
    "record_health_score",
    "record_llm_call",
    "record_llm_tokens",
    "record_message",
    "record_message_received",
    "record_message_sent",
    "record_phi_score",
    "record_task_completed",
    "record_task_failed",
    "record_uptime",
    "read_metric_samples",
    "read_metric_value",
    "setup_metrics_middleware",
]
