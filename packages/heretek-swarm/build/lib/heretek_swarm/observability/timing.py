"""
Timing utilities for performance profiling.

Provides a reusable timing primitive for profiling operations across the Heretek Swarm
system. Used by API latency sampling, actor execution instrumentation, and DB query
duration tracking.

Usage:
    from heretek_swarm.observability.timing import (
        TimedContext, timed, format_duration_ms,
    )
    from prometheus_client import Histogram

    # Context manager
    with TimedContext(
        label="db_query_executed",
        histogram=histogram,
        histogram_labels={"db": "postgres"},
    ) as ctx:
        result = db.execute(query)
        # ctx.elapsed_ms is available after the block

    # Decorator
    params = {"actor_type": "executor"}
    @timed("actor_message_processed", histogram=my_histogram, histogram_labels=params)
    async def process_message(msg: bytes) -> str:
        ...

    # Format helper
    print(format_duration_ms(1234.567))  # "1234.57ms"
"""

from __future__ import annotations

import inspect
import time
from typing import TYPE_CHECKING, Any, Self

import structlog

if TYPE_CHECKING:
    from prometheus_client import Histogram

_logger = structlog.get_logger("observability.timing")


class TimedContext:
    """
    Context manager for measuring elapsed time with structured logging and optional
    Prometheus histogram recording.

    Zero-allocation on the happy path — only calls time.perf_counter() on enter/exit.
    Structlog logger is resolved once at module level. Prometheus observe is optional.

    Attributes:
        label: Short identifier for the operation being timed (used as structlog label).
        histogram: Optional Prometheus Histogram for recording duration distribution.
        histogram_labels: Optional dict of labels for the histogram
            (e.g. {"actor_type": "executor"}).
        extra_fields: Additional key-value pairs to include in the structlog event.
        elapsed_ms: Duration in milliseconds, populated after context exit.
    """

    def __init__(
        self,
        label: str,
        histogram: Histogram | None = None,
        histogram_labels: dict[str, str] | None = None,
        **extra_fields: Any,
    ) -> None:
        self.label = label
        self._histogram = histogram
        self._histogram_labels = histogram_labels or {}
        self._extra_fields = extra_fields
        self._start: float | None = None
        self.elapsed_ms: float | None = None

    def __enter__(self) -> Self:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        # Compute elapsed with microsecond precision
        assert self._start is not None  # guaranteed by __enter__
        elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        self.elapsed_ms = elapsed_ms

        # Record to Prometheus histogram if configured
        if self._histogram is not None:
            duration_seconds = elapsed_ms / 1000.0
            self._histogram.labels(**self._histogram_labels).observe(duration_seconds)

        if exc_type is not None:
            _logger.error(
                "Timed operation failed",
                duration_ms=elapsed_ms,
                label=self.label,
                error=str(exc_val),
                **self._extra_fields,
            )
        else:
            _logger.info(
                "Timed operation completed",
                duration_ms=elapsed_ms,
                label=self.label,
                **self._extra_fields,
            )


def timed(
    label: str,
    histogram: Histogram | None = None,
    histogram_labels: dict[str, str] | None = None,
) -> Any:
    """
    Decorator that times async or sync function execution.

    Uses `inspect.iscoroutinefunction` to choose the appropriate wrapper. On entry,
    creates a `TimedContext` which records start time; on exit, logs duration and
    optionally observes the Prometheus histogram.

    Args:
        label: Operation label for structlog events (e.g. "actor_message_processed").
        histogram: Optional Prometheus Histogram for duration distribution.
        histogram_labels: Labels for the histogram (e.g. {"actor_type": "executor"}).

    Returns:
        Decorated function that wraps the original with timing instrumentation.

    Example:
        params = {"actor_type": "executor"}
        @timed("actor_message_processed", histogram=my_histogram, histogram_labels=params)
        async def process_message(msg: bytes) -> str:
            ...
    """

    def decorator(func: Any) -> Any:
        if inspect.iscoroutinefunction(func):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with TimedContext(
                    label=label,
                    histogram=histogram,
                    histogram_labels=histogram_labels,
                ):
                    return await func(*args, **kwargs)

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with TimedContext(
                label=label,
                histogram=histogram,
                histogram_labels=histogram_labels,
            ):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator


def format_duration_ms(duration_ms: float) -> str:
    """
    Format a duration in milliseconds to a human-readable string.

    Args:
        duration_ms: Duration in milliseconds (float for sub-millisecond precision).

    Returns:
        Formatted string like "1234.57ms".

    Example:
        >>> format_duration_ms(1234.567)
        '1234.57ms'
    """
    return f"{duration_ms:.2f}ms"
