"""
OpenTelemetry tracing — backwards-compat re-export.

.. deprecated::
    The canonical tracing implementation now lives in
    :mod:`heretek_swarm.infrastructure.otel.tracing` (which
    contains ``TracingConfig``, ``init_tracing``,
    ``InstrumentedAsyncClient``, ``instrumented_httpx_client``,
    and the full configuration surface).

    This module is a thin re-export shim so existing imports
    (``from heretek_swarm.observability.tracing import ...``)
    keep working. New code should import from
    :mod:`heretek_swarm.infrastructure.otel.tracing` directly.

    Implements Phase 2.9 of PLAN.md (§1.6 "Two tracing systems" —
    pick one and delete the other). The infrastructure/otel/tracing.py
    is the survivor because it carries the
    ``InstrumentedAsyncClient`` that the LLM and embedding providers
    depend on.
"""

from __future__ import annotations

# All canonical tracing primitives come from the infrastructure
# package. Re-export them so ``from heretek_swarm.observability.tracing
# import X`` keeps working for every X below.
from heretek_swarm.infrastructure.otel.tracing import (  # noqa: F401
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


# Compatibility alias: this module historically exposed
# ``initialize_tracing`` while infrastructure/otel/tracing uses
# ``init_tracing``. Both names point at the same function so old
# callers keep working.
def initialize_tracing(*args: object, **kwargs: object) -> TracingConfig:
    """Backwards-compat alias for :func:`init_tracing`."""
    return init_tracing(*args, **kwargs)


# Middleware: the TelemetryMiddleware that lives in
# observability/tracing.py historically is infrastructure code; it
# has moved to infrastructure/otel/middleware.py.
from heretek_swarm.infrastructure.otel.middleware import (  # noqa: E402, F401
    TelemetryMiddleware,
    setup_telemetry_middleware,
)


__all__ = [
    "InstrumentedAsyncClient",
    "SpanAttributes",
    "SpanKind",
    "SpanNames",
    "SpanStatus",
    "TelemetryMiddleware",
    "TraceState",
    "TracingConfig",
    "create_span",
    "create_tracing_config",
    "get_current_span",
    "get_trace_context",
    "get_tracer",
    "init_tracing",
    "initialize_tracing",
    "instrumented_httpx_client",
    "set_span_attribute",
    "set_span_attributes",
    "setup_telemetry_middleware",
    "span_context",
    "with_span",
]
