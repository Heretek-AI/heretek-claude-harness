"""
Telemetry middleware for OpenTelemetry HTTP tracing.

Extracted from ``observability/tracing.py`` (Phase 2.9 of PLAN.md,
§1.6 "Two tracing systems" — pick one and delete the other). The
canonical tracing primitives live in
:mod:`heretek_swarm.infrastructure.otel.tracing`; this module
holds the FastAPI / Starlette middleware that wraps each request
in a span and propagates trace context.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from heretek_swarm.infrastructure.otel.tracing import (
    SpanAttributes,
    get_tracer,
    init_tracing,
)

logger = structlog.get_logger("infrastructure.otel.middleware")


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware for automatic HTTP request tracing.

    Features:
    - Automatic span creation for each request
    - HTTP method, URL, and status code attributes
    - Request/response timing
    - Trace context propagation
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tracing."""
        from opentelemetry.propagate import extract

        tracer = get_tracer()

        # Extract trace context from incoming headers
        ctx = extract(carrier=dict(request.headers))

        # Get client IP for attribute
        client_ip = request.client.host if request.client else "unknown"

        # Create span for this request
        span_name = f"{request.method} {request.url.path}"

        with tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=trace.SpanKind.SERVER,
            attributes={
                SpanAttributes.HTTP_METHOD: request.method,
                SpanAttributes.HTTP_URL: str(request.url),
                "http.client_ip": client_ip,
                "http.user_agent": request.headers.get("user-agent", "unknown"),
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname or "unknown",
                "http.target": request.url.path,
            },
        ) as span:
            start_time = time.perf_counter()
            # Always set trace_id on request state for correlation (even if
            # span is not recording, e.g. when OTLP exporter is disabled).
            trace_id_value = format(span.get_span_context().trace_id, "032x")
            request.state.trace_id = trace_id_value

            try:
                response = await call_next(request)

                # Add response attributes
                duration_ms = (time.perf_counter() - start_time) * 1000

                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
                span.set_attribute(SpanAttributes.DURATION_MS, duration_ms)

                if response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))
                else:
                    span.set_status(Status(StatusCode.OK))

                # Add trace ID to response headers
                response.headers["X-Trace-ID"] = request.state.trace_id

                return response

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                span.set_attribute(SpanAttributes.DURATION_MS, duration_ms)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


def setup_telemetry_middleware(app) -> None:
    """
    Add telemetry middleware to FastAPI/Starlette application.

    Args:
        app: FastAPI or Starlette application instance
    """
    # Initialize tracing first
    init_tracing()

    # Add middleware
    app.add_middleware(TelemetryMiddleware)

    logger.info("Telemetry middleware configured")


__all__ = ["TelemetryMiddleware", "setup_telemetry_middleware"]
