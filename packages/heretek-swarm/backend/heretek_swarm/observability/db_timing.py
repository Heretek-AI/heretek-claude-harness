"""
Database timing utilities — OTel-backed SQLAlchemy instrumentation.

Phase 2A.3 cutover (commit 1 of 10): the previous hand-rolled
``before_cursor_execute`` / ``after_cursor_execute`` listener is
replaced by the official ``opentelemetry-instrumentation-sqlalchemy``
package, which is the canonical observability surface for SQLAlchemy.

Why this exists
---------------
``opentelemetry-instrumentation-sqlalchemy`` (Apache-2.0) provides
the same functionality as the previous hand-rolled code:

- Auto-instruments every SQLAlchemy engine to emit OTel spans.
- Hooks the same ``before_cursor_execute`` / ``after_cursor_execute``
  events the in-house code used.
- The OTel span carries the SQL statement, parameters, and duration
  as span attributes — compatible with any OTel backend (Jaeger,
  Tempo, etc.).

The in-house code added three things on top that the canonical
package does not provide natively, all of which are preserved here
as thin wrappers:

1. **Slow-query log warnings** (the
   ``db_slow_query`` WARNING-level event) — re-implemented as an
   OTel span processor that scans spans for the
   ``db.statement`` attribute + the span duration and emits the
   WARNING log when ``slow_query_threshold_ms`` is exceeded.

2. **Prometheus Histogram observation** (the
   ``DB_QUERY_DURATION`` histogram) — preserved as a parallel
   observation at the end of every span (the OTel span is
   emitted AND the Prometheus Histogram is observed, so existing
   Grafana dashboards keep working).

3. **A single ``attach_db_timing`` function with the same
   signature** as before — callers don't change.

This module is a thin wrapper that:
- Calls ``SQLAlchemyInstrumentor().instrument(engine=engine)``.
- Installs a custom OTel span processor that emits the slow-query
  log + observes the Prometheus Histogram.
- Preserves the ``attach_db_timing(engine, ..., slow_query_threshold_ms,
  histogram, histogram_labels)`` signature so the 2 callers
  (``config/service.py``, ``api/observability/external_calls.py``)
  don't need to change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

if TYPE_CHECKING:
    from prometheus_client import Histogram
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine

DB_TIMING_ENGINE_ATTR = "_db_timing_attached"
"""Attribute name on the engine that marks it as already instrumented.

Prevents double-instrumentation (idempotency guard).
"""


class DBSlowQuerySpanProcessor:
    """OTel SpanProcessor that emits a slow-query WARNING log and
    observes a Prometheus Histogram for every SQL span.
    """

    def __init__(
        self,
        *,
        slow_query_threshold_ms: float,
        histogram: Histogram | None = None,
        histogram_labels: dict[str, str] | None = None,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> None:
        self._threshold_ms = slow_query_threshold_ms
        self._histogram = histogram
        self._histogram_labels = histogram_labels or {}
        self._logger = logger or structlog.get_logger("db_timing")

    def on_start(self, span, parent_context=None):
        """OTel SpanProcessor hook (no-op for our purposes)."""
        return None

    def on_end(self, span) -> None:
        """OTel SpanProcessor hook: emit slow-query log + observe histogram."""
        # Only act on SQLAlchemy spans.
        name = getattr(span, "name", "") or ""
        if not name.startswith("sqlalchemy"):
            return

        # The OTel SQLAlchemy instrumentor stores the SQL statement on
        # the span as an attribute. We use it to log the slow query.
        attrs = getattr(span, "attributes", None) or {}
        statement = attrs.get("db.statement") or attrs.get("db.query") or ""
        truncated = statement[:200] if isinstance(statement, str) else ""

        # Span duration in milliseconds (the start_time / end_time are
        # nanoseconds since the epoch per the OTel spec).
        try:
            start_ns = span.start_time
            end_ns = span.end_time
            if start_ns is None or end_ns is None:
                return
            duration_ms = (end_ns - start_ns) / 1_000_000.0
        except Exception:
            return

        if duration_ms >= self._threshold_ms:
            self._logger.warning(
                "db_slow_query",
                statement=truncated,
                duration_ms=duration_ms,
            )
        # Always observe the histogram (if provided) on every span,
        # regardless of threshold — the histogram captures the full
        # distribution for percentiles.
        if self._histogram is not None:
            import contextlib
            with contextlib.suppress(Exception):
                # Never let metrics collection break the request.
                self._histogram.labels(**self._histogram_labels).observe(
                    duration_ms / 1000.0
                )


def attach_db_timing(
    engine_or_async_engine: Engine | AsyncEngine,
    logger_name: str = "db_timing",
    slow_query_threshold_ms: float = 500.0,
    histogram: Histogram | None = None,
    histogram_labels: dict[str, str] | None = None,
) -> None:
    """Attach OTel-based DB query timing to a SQLAlchemy engine.

    Phase 2A.3 cutover: the previous hand-rolled
    ``before_cursor_execute`` / ``after_cursor_execute`` listener is
    replaced by the official ``SQLAlchemyInstrumentor``. This
    function is the migration target's stable public surface —
    same signature as before, so callers do not need to change.

    For async engines, attaches to the underlying ``engine.sync_engine``
    because SQLAlchemy's event system operates on the sync engine
    regardless of whether the outer API is async.

    The function is **idempotent** — calling it on the same engine
    twice is a no-op (guards against double-instrumentation).

    Structured log events emitted (via the custom span processor):
    - ``db_slow_query`` (WARNING): emitted when span duration >=
      ``slow_query_threshold_ms``.

    When a Prometheus Histogram is provided, the
    :class:`DBSlowQuerySpanProcessor` observes the query duration
    on the histogram for every span (the histogram captures the
    full distribution, not just slow queries).

    Args:
        engine_or_async_engine: A sync :class:`~sqlalchemy.engine.Engine`
            or async :class:`~sqlalchemy.ext.asyncio.AsyncEngine`.
        logger_name: Name for the structlog logger
            (default ``"db_timing"``).
        slow_query_threshold_ms: Queries taking longer than this emit
            a WARNING-level ``db_slow_query`` event.
        histogram: Optional Prometheus Histogram to observe query
            durations. When provided, ``histogram.labels(
            **histogram_labels or {}).observe()`` is called for
            every span.
        histogram_labels: Labels dictionary for the histogram (e.g.
            ``{'db_name': 'config'}``). Ignored when histogram is None.

    Security:
        Statement text is truncated to 200 characters before logging.
        The OTel SQLAlchemy instrumentor also redacts bind parameters
        by default (configurable).
    """
    # Resolve the sync engine (async engines have a sync_engine attr).
    if hasattr(engine_or_async_engine, "sync_engine"):
        sync_engine: Engine = engine_or_async_engine.sync_engine  # type: ignore[attr-defined]
    else:
        sync_engine = engine_or_async_engine  # type: ignore[assignment]

    # Idempotency guard.
    if getattr(sync_engine, DB_TIMING_ENGINE_ATTR, False):
        return

    # Instrument with the official OTel package. This is the canonical
    # observability surface for SQLAlchemy and replaces the previous
    # hand-rolled before/after-cursor-execute listeners.
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)

    # Install the custom span processor that adds the slow-query log
    # + Prometheus Histogram observation on top of the OTel spans.
    # We do this at the global TracerProvider level so the processor
    # applies to every span (not just the ones instrumented above).
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        # If the project hasn't initialized the OTel SDK yet, the
        # global provider is a no-op ProxyTracerProvider. Initialize
        # a minimal in-process one so the span processor can be
        # attached. This matches the OTel pattern.
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

    # Avoid adding the processor twice.
    existing = getattr(provider, "_db_timing_processors", None)
    if not existing:
        processor = DBSlowQuerySpanProcessor(
            slow_query_threshold_ms=slow_query_threshold_ms,
            histogram=histogram,
            histogram_labels=histogram_labels,
            logger=structlog.get_logger(logger_name),
        )
        provider.add_span_processor(processor)
        # Stash a reference list on the provider so we can dedupe.
        provider._db_timing_processors = [processor]  # type: ignore[attr-defined]

    setattr(sync_engine, DB_TIMING_ENGINE_ATTR, True)
    structlog.get_logger(logger_name).debug(
        "db_timing_attached",
        slow_query_threshold_ms=slow_query_threshold_ms,
    )
