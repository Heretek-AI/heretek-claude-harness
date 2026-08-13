"""
Database timing utilities for performance profiling.

Provides SQLAlchemy async engine query timing via event listeners.
Attaches ``before_cursor_execute`` / ``after_cursor_execute`` listeners
that record structured log events for every SQL query.

Security: params summary is type+count only — actual values are never logged.
Query text is truncated to 200 characters.

Usage:
    from heretek_swarm.observability.db_timing import attach_db_timing

    attach_db_timing(engine, logger_name="db_timing", slow_query_threshold_ms=500)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from prometheus_client import Histogram
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine

DB_TIMING_ENGINE_ATTR = "_db_timing_attached"


def attach_db_timing(
    engine_or_async_engine: Engine | AsyncEngine,
    logger_name: str = "db_timing",
    slow_query_threshold_ms: float = 500.0,
    histogram: Histogram | None = None,
    histogram_labels: dict[str, str] | None = None,
) -> None:
    """
    Attach ``before_cursor_execute`` / ``after_cursor_execute`` event
    listeners to a sync or async SQLAlchemy engine for query timing.

    For async engines, attaches to the underlying ``engine.sync_engine``
    — this works because SQLAlchemy's event system operates on the sync
    engine regardless of whether the outer API is async.

    Structured log events emitted:
    - ``db_query_executed`` (DEBUG): truncated statement, params_summary, duration_ms
    - ``db_slow_query`` (WARNING): emitted when duration >= slow_query_threshold_ms

    When a Prometheus Histogram is provided, the ``after_cursor_execute``
    listener also observes the query duration on the histogram.

    Args:
        engine_or_async_engine: A sync :class:`~sqlalchemy.engine.Engine` or
            async :class:`~sqlalchemy.ext.asyncio.AsyncEngine`.
        logger_name: Name for the structlog logger (default ``"db_timing"``).
        slow_query_threshold_ms: Queries taking longer than this emit a
            WARNING-level ``db_slow_query`` event instead of the DEBUG-level
            ``db_query_executed``.
        histogram: Optional Prometheus Histogram to observe query durations.
            When provided, ``histogram.labels(**histogram_labels or {}).observe()``
            is called in ``after_cursor_execute``.
        histogram_labels: Labels dictionary for the histogram (e.g.
            ``{'db_name': 'config'}``). Ignored when histogram is None.

    Security:
        Params summary records type and count only (e.g. ``"3 keys"``, ``"5 rows"``,
        ``"none"``) — actual parameter values are never stored or logged.
        Statement text is truncated to 200 characters.
    """
    from sqlalchemy import event

    # Resolve the sync engine
    if hasattr(engine_or_async_engine, "sync_engine"):
        sync_engine: Engine = engine_or_async_engine.sync_engine
    else:
        sync_engine = engine_or_async_engine

    # Guard against double-attachment
    if getattr(sync_engine, DB_TIMING_ENGINE_ATTR, False):
        return

    logger = structlog.get_logger(logger_name)

    # Per-connection timing state: dict keyed by id(connection) so each
    # connection tracks its own cursor execution independently.
    _timers: dict[int, tuple[float, str, str]] = {}

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        # Summarize params: type + count only, never values (security)
        if parameters:
            if isinstance(parameters, list):
                params_summary = f"{len(parameters)} rows"
            elif isinstance(parameters, dict):
                params_summary = f"{len(parameters)} keys"
            elif isinstance(parameters, tuple):
                params_summary = f"{len(parameters)} positional"
            else:
                params_summary = "present"
        else:
            params_summary = "none"

        # Truncate statement to 200 chars
        truncated = statement[:200] if len(statement) > 200 else statement

        _timers[id(conn)] = (time.perf_counter(), truncated, params_summary)

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        timer_data = _timers.pop(id(conn), None)
        if timer_data is None:
            return

        start_time, truncated_stmt, params_summary = timer_data
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if duration_ms >= slow_query_threshold_ms:
            logger.warning(
                "db_slow_query",
                statement=truncated_stmt,
                params_summary=params_summary,
                duration_ms=duration_ms,
            )
        else:
            logger.debug(
                "db_query_executed",
                statement=truncated_stmt,
                params_summary=params_summary,
                duration_ms=duration_ms,
            )

        # Observe histogram if provided
        if histogram is not None:
            duration_seconds = duration_ms / 1000.0
            labels = histogram_labels if histogram_labels is not None else {}
            histogram.labels(**labels).observe(duration_seconds)

    setattr(sync_engine, DB_TIMING_ENGINE_ATTR, True)
    logger.debug(
        "db_timing_attached",
        slow_query_threshold_ms=slow_query_threshold_ms,
    )
