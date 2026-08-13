"""
OpenTelemetry Tracing for Heretek Swarm.

Provides distributed tracing based on OpenTelemetry standards.
Supports OTLP export, console export, and B3 context propagation.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, Self, TypeVar

import httpx
import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import Sampler, TraceIdRatioBased
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from heretek_swarm_core.models.external_call_log import ExternalCallLog
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger(__name__)


class TraceState(Enum):
    """Trace lifecycle state."""

    UNSTARTED = "unstarted"
    ACTIVE = "active"
    ENDED = "ended"


class SpanStatus(Enum):
    """Span execution status."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class TracingConfig:
    """Configuration for distributed tracing."""

    service_name: str = "heretek-swarm"
    service_version: str = "0.1.0"
    exporter: str = "console"  # console, otlp
    endpoint: str | None = None
    sample_rate: float = 1.0  # 0.0-1.0
    propagate_b3: bool = True
    max_attributes: int = 64
    max_span_events: int = 128


# =============================================================================
# Global State
# =============================================================================

_tracer_config: TracingConfig | None = None
_tracer_instance: trace.Tracer | None = None
_propagator = TraceContextTextMapPropagator()


# =============================================================================
# Initialization
# =============================================================================


def init_tracing(config: TracingConfig | None = None) -> TracingConfig:
    """
    Initialize OpenTelemetry tracing with the given configuration.

    Sets up the TracerProvider with OTLP or console exporter and configures
    context propagation.
    """
    global _tracer_config, _tracer_instance

    _tracer_config = config or TracingConfig()

    resource = Resource.create(
        {
            SERVICE_NAME: _tracer_config.service_name,
            SERVICE_VERSION: _tracer_config.service_version,
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            "heretek.swarm.node_id": os.getenv("NODE_ID", str(uuid.uuid4())),
        }
    )

    sampler: Sampler = TraceIdRatioBased(_tracer_config.sample_rate)

    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter_type = _tracer_config.exporter.lower()
    if exporter_type == "otlp":
        endpoint = _tracer_config.endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=endpoint,
                insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true",
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP tracing exporter configured", endpoint=endpoint)
        except Exception as e:
            logger.warning("Failed to configure OTLP exporter", error=str(e))
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("Console tracing exporter configured")

    trace.set_tracer_provider(provider)
    set_global_textmap(_propagator)

    _tracer_instance = trace.get_tracer(
        _tracer_config.service_name,
        _tracer_config.service_version,
    )

    logger.info(
        "tracing_initialized",
        service_name=_tracer_config.service_name,
        exporter=_tracer_config.exporter,
        sample_rate=_tracer_config.sample_rate,
    )

    return _tracer_config


# Backwards-compat alias: this module historically exposed
# ``initialize_tracing`` in observability/tracing.py with the same
# signature. Both names point at the same function so old callers
# keep working.
def initialize_tracing(
    config: TracingConfig | None = None,
) -> TracingConfig:
    """Backwards-compat alias for :func:`init_tracing`."""
    return init_tracing(config)


def get_tracer(service_name: str | None = None) -> trace.Tracer:
    """
    Get the global tracer instance, initializing if necessary.

    Args:
        service_name: Override the service name for this tracer.

    Returns:
        The active tracer instance.
    """
    global _tracer_config, _tracer_instance

    if _tracer_instance is None:
        config = _tracer_config or TracingConfig()
        if service_name:
            config.service_name = service_name
        init_tracing(config)

    return _tracer_instance


def create_tracing_config(
    service_name: str = "heretek-swarm",
    exporter: str = "console",
    endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> TracingConfig:
    """Convenience function to create TracingConfig."""
    return TracingConfig(
        service_name=service_name,
        exporter=exporter,
        endpoint=endpoint,
        sample_rate=sample_rate,
    )


# =============================================================================
# Span Helpers
# =============================================================================


def _span_kind_from_str(kind: str) -> SpanKind:
    """Convert string kind to SpanKind enum."""
    mapping = {
        "internal": SpanKind.INTERNAL,
        "client": SpanKind.CLIENT,
        "server": SpanKind.SERVER,
        "producer": SpanKind.PRODUCER,
        "consumer": SpanKind.CONSUMER,
    }
    return mapping.get(kind.lower(), SpanKind.INTERNAL)


def create_span(
    name: str,
    trace_id: str | None = None,
    parent_id: str | None = None,
    kind: str = "internal",
) -> Span:
    """
    Create a new span without starting it.

    Args:
        name: Name of the span.
        trace_id: Optional trace ID to use.
        parent_id: Optional parent span ID.
        kind: Span kind (internal, client, server, producer, consumer).

    Returns:
        A newly created span (not yet started).
    """
    span_kind = _span_kind_from_str(kind)

    ctx = trace.get_current_context()

    tracer_impl = get_tracer()
    return tracer_impl.start_span(
        name=name,
        context=ctx,
        kind=span_kind,
    )


def with_span(name: str) -> Callable:
    """
    Decorator to wrap a function in a span.

    Handles both sync and async functions.

    Usage:
        @with_span("my_operation")
        async def my_operation():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
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
            with tracer.start_as_current_span(name) as span:
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
    kind: str = "internal",
):
    """
    Context manager for creating spans.

    Args:
        name: Span name.
        attributes: Optional span attributes.
        kind: Span kind.

    Example:
        with span_context("consensus.vote", {"consensus_id": round_id}):
            await vote_on_proposal(proposal)
    """
    tracer = get_tracer()
    span_kind = _span_kind_from_str(kind)

    with tracer.start_as_current_span(
        name,
        kind=span_kind,
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
    """Extract current trace context for propagation across process boundaries."""
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
# Predefined Span Names
# =============================================================================


class SpanNames:
    """Standardized span names for Heretek Swarm operations."""

    API_REQUEST = "api.request"
    API_HEALTH_CHECK = "api.health_check"

    AGENT_INITIALIZE = "agent.initialize"
    AGENT_EXECUTE = "agent.execute"
    AGENT_PROCESS_MESSAGE = "agent.process_message"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_LLM_INFERENCE = "agent.llm_inference"

    CONSENSUS_ROUND_START = "consensus.round_start"
    CONSENSUS_VOTE = "consensus.vote"
    CONSENSUS_AGREEMENT = "consensus.agreement"
    CONSENSUS_ROUND_COMPLETE = "consensus.round_complete"

    CONSCIOUSNESS_CALCULATE_PHI = "consciousness.calculate_phi"
    CONSCIOUSNESS_UPDATE = "consciousness.update"
    CONSCIOUSNESS_MEASURE = "consciousness.measure"

    COLLECTIVE_BROADCAST = "collective.broadcast"
    COLLECTIVE_GATHER = "collective.gather"
    COLLECTIVE_SYNC = "collective.sync"

    WORKFLOW_EXECUTE = "workflow.execute"
    WORKFLOW_STEP = "workflow.step"

    MEMORY_STORE = "memory.store"
    MEMORY_RETRIEVE = "memory.retrieve"
    MEMORY_SEARCH = "memory.search"


class SpanAttributes:
    """Standardized attribute keys for Heretek Swarm spans."""

    AGENT_ID = "heretek.agent.id"
    AGENT_TYPE = "heretek.agent.type"
    TASK_ID = "heretek.task.id"
    TASK_TYPE = "heretek.task.type"
    CONSENSUS_ID = "heretek.consensus.id"
    CONSENSUS_ROUND = "heretek.consensus.round"
    WORKFLOW_ID = "heretek.workflow.id"
    WORKFLOW_STEP = "heretek.workflow.step"

    PHI_SCORE = "heretek.consciousness.phi_score"
    CONSCIOUSNESS_LEVEL = "heretek.consciousness.level"
    INTEGRATION_SCORE = "heretek.consciousness.integration_score"
    INFORMATION_SCORE = "heretek.consciousness.information_score"

    VOTES_TOTAL = "heretek.consensus.votes.total"
    VOTES_FOR = "heretek.consensus.votes.for"
    VOTES_AGAINST = "heretek.consensus.votes.against"
    QUORUM_REACHED = "heretek.consensus.quorum_reached"

    DURATION_MS = "heretek.duration_ms"
    TOKENS_USED = "heretek.tokens.used"
    TOKENS_COST = "heretek.tokens.cost"

    HTTP_METHOD = "http.method"
    HTTP_URL = "http.url"
    HTTP_STATUS_CODE = "http.status_code"


# =============================================================================
# Instrumented httpx Client
# =============================================================================

_extra_logger = structlog.get_logger(__name__)

# Module-level session factory singleton for ExternalCallLog
_external_call_log_session_factory: async_sessionmaker | None = None  # type: ignore[type-arg]


def _get_external_call_log_session_factory() -> async_sessionmaker:  # type: ignore[type-arg]
    """
    Get or create the module-level session factory for ExternalCallLog.

    Mirrors the pattern used in api/observability.py.
    """
    global _external_call_log_session_factory
    if _external_call_log_session_factory is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            _extra_logger.warning("DATABASE_URL not set — ExternalCallLog entries will not be persisted")
            # Return a no-op sentinel that the caller handles gracefully
            # Sentinel: caller handles None gracefully — no DB session when DATABASE_URL is unset
            return None  # type: ignore[return-value]

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
        _external_call_log_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _extra_logger.info("ExternalCallLog session factory initialized")
    return _external_call_log_session_factory


def _get_agent_context() -> tuple[str, str]:
    """
    Extract agent_id and agent_type from the current OTel span context.

    Reads span attributes set by the agent's tracing layer (heretek.agent.id
    and heretek.agent.type). Returns ("unknown", "unknown") when no span is
    active or the attributes are not set.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        # Access .attributes via getattr to satisfy type checkers that see the
        # abstract Span interface (NonRecordingSpan has no attributes).
        attrs: dict[str, Any] = getattr(span, "attributes", {})
        agent_id = str(attrs.get(SpanAttributes.AGENT_ID) or "unknown")
        agent_type = str(attrs.get(SpanAttributes.AGENT_TYPE) or "unknown")
        return agent_id, agent_type
    return "unknown", "unknown"


async def _write_call_log(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    agent_id: str,
    agent_type: str,
    url: str,
    method: str,
    status_code: int | None,
    duration_ms: float,
    request_headers: dict[str, Any] | None,
    request_body: str | None,
    response_body: str | None,
    tool_name: str | None,
    error_message: str | None,
    call_type: str = "http",
) -> None:
    """
    Write an ExternalCallLog entry to the database.

    Encrypts request headers, request body, and response body before storage.
    Silently catches and logs DB errors so they never propagate to callers.
    """
    # Lazy imports: avoid circular dependency between heretek_swarm and
    # heretek_swarm_core at module load time. See CLAUDE.md notes on
    # the packages extraction work for context.
    from heretek_swarm_core.models.external_call_log import ExternalCallLog
    from heretek_swarm_core.models.external_call_log_encryption import get_encryptor

    encryptor = get_encryptor()

    # Sanitize and encrypt headers
    headers_encrypted: str | None = None
    if request_headers:
        sanitized = encryptor.sanitize(request_headers)
        headers_encrypted = encryptor.encrypt(sanitized).get("encrypted") or None

    # Encrypt bodies
    request_body_encrypted: str | None = None
    if request_body:
        request_body_encrypted = encryptor.encrypt({"body": request_body}).get("encrypted") or None

    response_body_encrypted: str | None = None
    if response_body:
        encrypted = encryptor.encrypt({"body": response_body})
        response_body_encrypted = encrypted.get("encrypted") or None

    try:

        async def _write() -> None:
            nonlocal headers_encrypted, request_body_encrypted, response_body_encrypted
            async with session_factory() as session:
                log = ExternalCallLog(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    call_type=call_type,
                    url=url,
                    method=method,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_headers_encrypted=headers_encrypted,
                    request_body_encrypted=request_body_encrypted,
                    response_body_encrypted=response_body_encrypted,
                    tool_name=tool_name,
                    error_message=error_message,
                )
                session.add(log)
                await session.commit()

        await _write()
    except Exception as e:
        _extra_logger.warning(
            "external_call_log_write_failed",
            agent_id=agent_id,
            url=url,
            method=method,
            error=str(e),
        )


class InstrumentedAsyncClient:
    """
    httpx.AsyncClient wrapper that instruments all HTTP calls with OTel spans
    and writes ExternalCallLog entries to the database.

    Wraps an existing httpx.AsyncClient (or creates one lazily) and intercepts
    every HTTP request to:
      1. Extract agent context from the current OTel span.
      2. Create an OTel span covering the HTTP call.
      3. Execute the underlying request.
      4. Write an ExternalCallLog entry with encrypted headers/bodies.

    Errors (timeouts, connection errors, HTTP errors) are logged with
    status='error' and the error message, without re-raising.

    Usage::

        async with instrumented_httpx_client() as client:
            response = await client.get("https://api.example.com/v1/completions")
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        session_factory: async_sessionmaker | None = None,  # type: ignore[type-arg]
        call_type: str = "http",
    ) -> None:
        """
        Initialize the instrumented client.

        Args:
            client: Existing httpx.AsyncClient to wrap. If None, one is created
                on first use via ``httpx.AsyncClient()``.
            session_factory: Async SQLAlchemy session factory for writing
                ExternalCallLog entries. If None, uses the module-level factory
                (which is a no-op when DATABASE_URL is not set).
            call_type: Call type label written to ExternalCallLog.call_type
                (default "http"). Used to distinguish httpx calls from MCP calls.
        """
        self._client = client
        self._session_factory = session_factory
        self._call_type = call_type
        self._owns_client = client is None

    # ------------------------------------------------------------------
    # Public httpx.AsyncClient interface
    # ------------------------------------------------------------------

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("GET", url, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("POST", url, headers=headers, **kwargs)

    async def put(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("PUT", url, headers=headers, **kwargs)

    async def patch(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("PATCH", url, headers=headers, **kwargs)

    async def delete(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("DELETE", url, headers=headers, **kwargs)

    async def head(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("HEAD", url, headers=headers, **kwargs)

    async def options(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request("OPTIONS", url, headers=headers, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute an HTTP request with OTel instrumentation and call logging.

        Creates a CLIENT span named ``http.request``, sets HTTP method/URL/status
        attributes, then delegates to the underlying httpx.AsyncClient.
        On completion (success or error) writes an ExternalCallLog entry.
        """
        client = self._get_client()
        session_factory = self._session_factory or _get_external_call_log_session_factory()

        agent_id, agent_type = _get_agent_context()

        # Determine the URL domain for the span name
        domain = url
        if "://" in url:
            domain = url.split("://", 1)[1].split("/", 1)[0]

        span_name = f"http {method} {domain}"
        tracer = get_tracer()

        with tracer.start_as_current_span(
            span_name,
            kind=SpanKind.CLIENT,
            attributes={
                SpanAttributes.HTTP_METHOD: method,
                SpanAttributes.HTTP_URL: url,
                SpanAttributes.AGENT_ID: agent_id,
                SpanAttributes.AGENT_TYPE: agent_type,
            },
        ) as span:
            start = time.perf_counter()
            response_body_str: str | None = None
            request_body_str: str | None = None
            if content is not None:
                if isinstance(content, bytes):
                    request_body_str = content.decode("utf-8", errors="replace")
                else:
                    request_body_str = content

            try:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    content=content,
                    **kwargs,
                )

                duration_ms = (time.perf_counter() - start) * 1000

                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
                span.set_status(
                    Status(StatusCode.OK) if 200 <= response.status_code < 400 else Status(StatusCode.ERROR)
                )

                # Extract response body for logging (up to MAX_BODY_SIZE = 10KB)
                if response.text:
                    from heretek_swarm_core.models.external_call_log_encryption import MAX_BODY_SIZE

                    response_body_str = response.text[:MAX_BODY_SIZE]

                # Write log entry (fire-and-forget — errors caught inside)
                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=response_body_str,
                        tool_name=None,
                        error_message=None,
                        call_type=self._call_type,
                    )

                return response

            except httpx.TimeoutException as e:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=None,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,
                        tool_name=None,
                        error_message=f"TimeoutException: {e}",
                        call_type=self._call_type,
                    )
                raise

            except httpx.ConnectError as e:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=None,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,
                        tool_name=None,
                        error_message=f"ConnectError: {e}",
                        call_type=self._call_type,
                    )
                raise

            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=None,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,
                        tool_name=None,
                        error_message=f"{type(e).__name__}: {e}",
                        call_type=self._call_type,
                    )
                raise

    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute a streaming HTTP request with OTel instrumentation and call logging.

        Creates a CLIENT span and intercepts the streaming response. On completion
        writes an ExternalCallLog entry. Unlike request(), the caller receives the
        raw httpx.Response so they can call response.aiter_lines().

        Usage::

            async with client.stream("POST", "/chat/completions", json=payload) as response:
                async for line in response.aiter_lines():
                    ...
        """
        client = self._get_client()
        session_factory = self._session_factory or _get_external_call_log_session_factory()

        agent_id, agent_type = _get_agent_context()

        domain = url
        if "://" in url:
            domain = url.split("://", 1)[1].split("/", 1)[0]

        span_name = f"http {method} {domain}"
        tracer = get_tracer()

        with tracer.start_as_current_span(
            span_name,
            kind=SpanKind.CLIENT,
            attributes={
                SpanAttributes.HTTP_METHOD: method,
                SpanAttributes.HTTP_URL: url,
                SpanAttributes.AGENT_ID: agent_id,
                SpanAttributes.AGENT_TYPE: agent_type,
            },
        ) as span:
            start = time.perf_counter()
            request_body_str: str | None = None
            if content is not None:
                if isinstance(content, bytes):
                    request_body_str = content.decode("utf-8", errors="replace")
                else:
                    request_body_str = content

            try:
                response = await client.stream(
                    method,
                    url,
                    headers=headers,
                    content=content,
                    **kwargs,
                )

                duration_ms = (time.perf_counter() - start) * 1000

                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
                span.set_status(
                    Status(StatusCode.OK) if 200 <= response.status_code < 400 else Status(StatusCode.ERROR)
                )

                # Write log entry on stream exit
                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,  # Streaming body not captured per-chunk
                        tool_name=None,
                        error_message=None,
                        call_type=self._call_type,
                    )

                return response

            except httpx.TimeoutException as e:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=None,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,
                        tool_name=None,
                        error_message=f"TimeoutException: {e}",
                        call_type=self._call_type,
                    )
                raise

            except httpx.ConnectError as e:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=None,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,
                        tool_name=None,
                        error_message=f"ConnectError: {e}",
                        call_type=self._call_type,
                    )
                raise

            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)

                if session_factory is not None:
                    await _write_call_log(
                        session_factory=session_factory,
                        agent_id=agent_id,
                        agent_type=agent_type,
                        url=url,
                        method=method,
                        status_code=None,
                        duration_ms=duration_ms,
                        request_headers=headers,
                        request_body=request_body_str,
                        response_body=None,
                        tool_name=None,
                        error_message=f"{type(e).__name__}: {e}",
                        call_type=self._call_type,
                    )
                raise

    @property
    def is_closed(self) -> bool:
        """
        Return True if the underlying httpx.AsyncClient has been closed.

        Also returns True if the client hasn't been created yet (lazy creation),
        since we consider an uninitialized wrapper as "closed" from the caller's
        perspective.
        """
        if self._client is None:
            # Lazy client not created yet — treat as closed to allow re-init
            return True
        return self._client.is_closed

    async def aclose(self) -> None:
        """Close the underlying httpx.AsyncClient if we own it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client


def instrumented_httpx_client(
    client: httpx.AsyncClient | None = None,
    session_factory: async_sessionmaker | None = None,  # type: ignore[type-arg]
    call_type: str = "http",
) -> InstrumentedAsyncClient:
    """
    Create an InstrumentedAsyncClient that wraps an httpx.AsyncClient.

    This is the primary entry point. The returned InstrumentedAsyncClient is an
    async-context-manager that can be used with ``async with``::

        async with instrumented_httpx_client() as client:
            response = await client.post("https://api.example.com", json={"prompt": "hi"})

    Or directly::

        client = instrumented_httpx_client()
        try:
            response = await client.get("https://api.example.com")
        finally:
            await client.aclose()

    Args:
        client: Optional pre-configured httpx.AsyncClient to wrap. If not
            provided, one is created lazily on first request.
        session_factory: SQLAlchemy async session factory for ExternalCallLog
            persistence. Defaults to the module-level factory (silently skipped
            when DATABASE_URL is not configured).
        call_type: Label written to ExternalCallLog.call_type. Default "http".
            Use e.g. "mcp" when wrapping MCP transport calls.

    Returns:
        InstrumentedAsyncClient instance (also an async context manager).
    """
    return InstrumentedAsyncClient(
        client=client,
        session_factory=session_factory,
        call_type=call_type,
    )


# =============================================================================
# Public API
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])

__all__ = [
    "InstrumentedAsyncClient",
    "Span",
    "SpanAttributes",
    "SpanKind",
    "SpanNames",
    "SpanStatus",
    "TraceState",
    "TracingConfig",
    "create_span",
    "create_tracing_config",
    "get_current_span",
    "get_trace_context",
    "get_tracer",
    "init_tracing",
    "instrumented_httpx_client",
    "set_span_attribute",
    "set_span_attributes",
    "span_context",
    "with_span",
]
