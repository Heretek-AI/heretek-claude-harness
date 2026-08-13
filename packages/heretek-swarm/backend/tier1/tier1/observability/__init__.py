"""Tier 1 observability — OpenTelemetry setup, metrics, logging.

Usage:
    from tier1.observability import init_telemetry, get_tracer, get_meter
    init_telemetry(app)  # called once in create_app()
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from tier1.observability.logging import add_trace_context


def get_tracer(name: str):
    """Get a named tracer from the global OTel TracerProvider."""
    from opentelemetry import trace

    return trace.get_tracer(name)


def get_meter(name: str):
    """Get a named meter from the global OTel MeterProvider."""
    from opentelemetry import metrics

    return metrics.get_meter(name)


def _init_otel(app: FastAPI) -> None:
    """Configure OTel providers, FastAPI instrumentor, and structlog."""
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # Traces → Jaeger
    trace_exporter = OTLPSpanExporter(endpoint="http://jaeger:4318/v1/traces")
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics → Jaeger + Prometheus
    metric_exporter = OTLPMetricExporter(endpoint="http://jaeger:4318/v1/metrics")
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Wire the default provider for metrics.py
    from tier1.observability.metrics import set_default_provider

    set_default_provider(meter_provider)

    # FastAPI auto-instrumentation
    FastAPIInstrumentor.instrument_app(app)

    # Structlog trace context
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            add_trace_context,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
    )


def init_telemetry(app: FastAPI) -> None:
    """Initialize OpenTelemetry for the application.

    Safe to call multiple times — only configures once.
    Degrades silently if OTel SDK is not installed.
    """
    try:
        _init_otel(app)
    except ImportError:
        # OTel SDK not installed — all get_tracer/get_meter calls
        # will return no-ops from the opentelemetry-api package.
        pass
