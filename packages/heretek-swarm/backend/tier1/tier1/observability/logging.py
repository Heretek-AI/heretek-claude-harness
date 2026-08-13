"""Structlog processor that injects trace context into log events."""

from __future__ import annotations

from opentelemetry import trace


def add_trace_context(logger, method_name, event_dict):
    """Add trace_id and span_id to every structured log line."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
