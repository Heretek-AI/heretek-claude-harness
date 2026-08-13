"""
OpenTelemetry (OTel) Infrastructure.

Provides distributed tracing, metrics collection, and structured logging
for the Heretek Swarm based on OpenTelemetry standards.
"""

from heretek_swarm.infrastructure.otel.logging import (
    LoggingConfig,
    get_log_config,
    init_logging,
)
from heretek_swarm.infrastructure.otel.metrics import (
    MetricsCollector,
    MetricsConfig,
    get_meter,
    init_metrics,
    record_metric,
)
from heretek_swarm.observability.tracing import (  # noqa: F401
    initialize_tracing,
    setup_telemetry_middleware,
)
from heretek_swarm.infrastructure.otel.tracing import (
    InstrumentedAsyncClient,
    SpanAttributes,
    SpanKind,
    SpanNames,
    SpanStatus,
    TraceState,
    TracingConfig,
    create_span,
    create_tracing_config,
    get_current_span,
    get_trace_context,
    get_tracer,
    init_tracing,
    instrumented_httpx_client,
    set_span_attribute,
    set_span_attributes,
    span_context,
    with_span,
)

__all__ = [
    "InstrumentedAsyncClient",
    "LoggingConfig",
    "MetricsCollector",
    "MetricsConfig",
    "SpanAttributes",
    "SpanKind",
    "SpanNames",
    "SpanStatus",
    "TraceState",
    "TracingConfig",
    "create_span",
    "create_tracing_config",
    "get_current_span",
    "get_log_config",
    "get_meter",
    "get_trace_context",
    "get_tracer",
    "init_logging",
    "init_metrics",
    "init_tracing",
    "instrumented_httpx_client",
    "record_metric",
    "set_span_attribute",
    "set_span_attributes",
    "span_context",
    "with_span",
    "initialize_tracing",
    "setup_telemetry_middleware",
]
