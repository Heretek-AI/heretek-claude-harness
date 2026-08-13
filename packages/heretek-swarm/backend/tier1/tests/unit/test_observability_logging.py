"""Tests for the add_trace_context structlog processor."""

from __future__ import annotations

from unittest.mock import MagicMock

from tier1.observability.logging import add_trace_context


def _fake_span(trace_id: int = 0xDEADBEEF, span_id: int = 0xCAFEBABE, valid: bool = True):
    ctx = MagicMock()
    ctx.trace_id = trace_id
    ctx.span_id = span_id
    ctx.is_valid = valid
    span = MagicMock()
    span.get_span_context.return_value = ctx
    return span


def test_injects_trace_id_and_span_id():
    span = _fake_span()
    import tier1.observability.logging as mod

    original = mod.trace.get_current_span
    mod.trace.get_current_span = lambda: span
    try:
        event_dict = {"event": "test"}
        result = add_trace_context(None, None, event_dict)
        assert "trace_id" in result
        assert "span_id" in result
        assert result["trace_id"] == format(0xDEADBEEF, "032x")
        assert result["span_id"] == format(0xCAFEBABE, "016x")
    finally:
        mod.trace.get_current_span = original


def test_no_inject_when_span_invalid():
    span = _fake_span(valid=False)
    import tier1.observability.logging as mod

    original = mod.trace.get_current_span
    mod.trace.get_current_span = lambda: span
    try:
        event_dict = {"event": "test"}
        result = add_trace_context(None, None, event_dict)
        assert "trace_id" not in result
        assert "span_id" not in result
    finally:
        mod.trace.get_current_span = original
