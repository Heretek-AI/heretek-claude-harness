"""
OpenTelemetry Distributed Tracing for Heretek Swarm.

Provides distributed tracing across:
- API requests
- Agent operations
- Consensus rounds
- Consciousness calculations

Span attributes:
- agent_id: Unique agent identifier
- task_id: Current task being executed
- consensus_id: Consensus round identifier
- phi_score: Consciousness measurement value
"""

import os
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("observability.tracing")

# Global tracer instance
_tracer: trace.Tracer | None = None
_propagator = TraceContextTextMapPropagator()


def initialize_tracing(
    service_name: str = "heretek-swarm",
    service_version: str = "0.1.0",
    otlp_endpoint: str | None = None,
    enable_console_export: bool = False,
) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing with OTLP exporter.

    Args:
        service_name: Name of the service for tracing
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint (defaults to OTEL_EXPORTER_OTLP_ENDPOINT env)
        enable_console_export: Enable console export for debugging

    Returns:
        Configured tracer instance
    """
    global _tracer

    # Create resource with service information
    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            "heretek.swarm.node_id": os.getenv("NODE_ID", str(uuid.uuid4())),
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter only when an endpoint is explicitly set OR
    # auto-detection is requested. Without this gate, the default
    # http://localhost:4317 endpoint is used even when no collector is
    # deployed, producing noisy StatusCode.UNAVAILABLE warnings on every
    # batch export.
    if otlp_endpoint is None:
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    otlp_enabled = (
        otlp_endpoint is not None
        and not enable_console_export
        and os.getenv("OTEL_SDK_DISABLED", "false").lower() != "true"
    )

    if otlp_enabled:
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true",
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP tracing configured", endpoint=otlp_endpoint)
        except Exception as e:
            logger.warning("Failed to configure OTLP exporter", error=str(e))
    else:
        logger.info(
            "OTLP tracing disabled (no OTEL_EXPORTER_OTLP_ENDPOINT set); "
            "spans will not be exported"
        )

    # Add console exporter for debugging
    if enable_console_export or os.getenv("OTEL_DEBUG", "false").lower() == "true":
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console tracing export enabled")

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Configure trace context propagation
    set_global_textmap(_propagator)

    # Get tracer instance
    _tracer = trace.get_tracer(service_name, service_version)

    logger.info(
        "OpenTelemetry tracing initialized",
        service=service_name,
        version=service_version,
        otlp_endpoint=otlp_endpoint,
    )

    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance, initializing if necessary."""
    global _tracer
    if _tracer is None:
        _tracer = initialize_tracing()
    return _tracer


def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Callable:
    """
    Decorator to create a span around a function.

    Args:
        name: Span name
        attributes: Optional span attributes
        kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)

    Example:
        @create_span("agent.execute_task", {"agent_id": "agent-1"})
        async def execute_task(task: Task):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                name,
                kind=kind,
                attributes=attributes or {},
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                name,
                kind=kind,
                attributes=attributes or {},
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def span_context(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """
    Context manager for creating spans.

    Args:
        name: Span name
        attributes: Optional span attributes
        kind: Span kind

    Example:
        with span_context("consensus.vote", {"consensus_id": round_id}):
            await vote_on_proposal(proposal)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes or {},
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def get_current_span() -> Span | None:
    """Get the current active span."""
    return trace.get_current_span()


def get_trace_context() -> dict[str, str]:
    """Extract current trace context for propagation."""
    carrier: dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier


def set_span_attribute(key: str, value: Any) -> None:
    """Set an attribute on the current span."""
    span = get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, value)


def set_span_attributes(attributes: dict[str, Any]) -> None:
    """Set multiple attributes on the current span."""
    span = get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


# =============================================================================
# Predefined Span Names for Heretek Swarm
# =============================================================================


class SpanNames:
    """Standardized span names for Heretek Swarm operations."""

    # API spans
    API_REQUEST = "api.request"
    API_HEALTH_CHECK = "api.health_check"

    # Agent spans
    AGENT_INITIALIZE = "agent.initialize"
    AGENT_EXECUTE = "agent.execute"
    AGENT_PROCESS_MESSAGE = "agent.process_message"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_LLM_INFERENCE = "agent.llm_inference"

    # Consensus spans
    CONSENSUS_ROUND_START = "consensus.round_start"
    CONSENSUS_VOTE = "consensus.vote"
    CONSENSUS_AGREEMENT = "consensus.agreement"
    CONSENSUS_ROUND_COMPLETE = "consensus.round_complete"

    # Consciousness spans
    CONSCIOUSNESS_CALCULATE_PHI = "consciousness.calculate_phi"
    CONSCIOUSNESS_UPDATE = "consciousness.update"
    CONSCIOUSNESS_MEASURE = "consciousness.measure"

    # Collective spans
    COLLECTIVE_BROADCAST = "collective.broadcast"
    COLLECTIVE_GATHER = "collective.gather"
    COLLECTIVE_SYNC = "collective.sync"

    # Workflow spans
    WORKFLOW_EXECUTE = "workflow.execute"
    WORKFLOW_STEP = "workflow.step"

    # Memory spans
    MEMORY_STORE = "memory.store"
    MEMORY_RETRIEVE = "memory.retrieve"
    MEMORY_SEARCH = "memory.search"


# =============================================================================
# Span Attribute Keys
# =============================================================================


class SpanAttributes:
    """Standardized attribute keys for Heretek Swarm spans."""

    # Entity identifiers
    AGENT_ID = "heretek.agent.id"
    AGENT_TYPE = "heretek.agent.type"
    TASK_ID = "heretek.task.id"
    TASK_TYPE = "heretek.task.type"
    CONSENSUS_ID = "heretek.consensus.id"
    CONSENSUS_ROUND = "heretek.consensus.round"
    WORKFLOW_ID = "heretek.workflow.id"
    WORKFLOW_STEP = "heretek.workflow.step"

    # Consciousness metrics
    PHI_SCORE = "heretek.consciousness.phi_score"
    CONSCIOUSNESS_LEVEL = "heretek.consciousness.level"
    INTEGRATION_SCORE = "heretek.consciousness.integration_score"
    INFORMATION_SCORE = "heretek.consciousness.information_score"

    # Consensus metrics
    VOTES_TOTAL = "heretek.consensus.votes.total"
    VOTES_FOR = "heretek.consensus.votes.for"
    VOTES_AGAINST = "heretek.consensus.votes.against"
    QUORUM_REACHED = "heretek.consensus.quorum_reached"

    # Performance metrics
    DURATION_MS = "heretek.duration_ms"
    TOKENS_USED = "heretek.tokens.used"
    TOKENS_COST = "heretek.tokens.cost"

    # HTTP metrics
    HTTP_METHOD = "http.method"
    HTTP_URL = "http.url"
    HTTP_STATUS_CODE = "http.status_code"


# =============================================================================
# Starlette Middleware for HTTP Tracing
# =============================================================================


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
        tracer = get_tracer()

        # Extract trace context from incoming headers
        ctx = _propagator.extract(carrier=dict(request.headers))

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
            # Always set trace_id on request state for correlation (even if span
            # is not recording, e.g. when OTLP exporter is disabled).
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


def setup_telemetry_middleware(app):
    """
    Add telemetry middleware to FastAPI/Starlette application.

    Args:
        app: FastAPI or Starlette application instance
    """
    # Initialize tracing first
    initialize_tracing()

    # Add middleware
    app.add_middleware(TelemetryMiddleware)

    logger.info("Telemetry middleware configured")


# =============================================================================
# Context Propagation Helpers
# =============================================================================


async def propagate_trace_context(coro):
    """
    Execute coroutine with trace context propagation.

    Ensures child spans are linked to the current trace.
    """
    tracer = get_tracer()
    ctx = trace.get_current_context()

    with tracer.start_as_current_span(
        "propagated.task",
        context=ctx,
        kind=trace.SpanKind.INTERNAL,
    ):
        return await coro


# =============================================================================
# Shutdown
# =============================================================================


async def shutdown_tracing():
    """Shutdown tracing provider and flush spans."""
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        await provider.shutdown()
    logger.info("Tracing shutdown complete")
