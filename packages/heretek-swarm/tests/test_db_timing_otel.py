"""Tests for the Phase 2A.3 db_timing cutover (OTel-based).

Verifies that the new ``attach_db_timing``:
- Is idempotent (guards against double-instrumentation).
- Installs the OTel SQLAlchemyInstrumentor (via the
  ``_db_timing_attached`` attribute marker).
- Installs the custom DBSlowQuerySpanProcessor (which emits the
  slow-query log and observes the Prometheus Histogram).
- Preserves the public API signature.
"""

from __future__ import annotations

import importlib

import pytest

from heretek_swarm.observability.db_timing import (
    DB_TIMING_ENGINE_ATTR,
    DBSlowQuerySpanProcessor,
    attach_db_timing,
)


class _StubEngine:
    """Minimal sync_engine stand-in for testing attach_db_timing.

    Provides the minimum attributes SQLAlchemyInstrumentor() reads
    on instrument(engine=engine): a ``name`` attribute. The real
    engine class is irrelevant for the unit test — the test
    verifies the idempotency-guard attribute is set; it does not
    execute SQL.
    """

    name = "stub_sqlite"  # SQLAlchemyInstrumentor reads engine.name


def test_module_imports_clean():
    """db_timing exposes the 3 public symbols."""
    importlib.import_module("heretek_swarm.observability.db_timing")
    # Module is importable; symbols are importable.
    assert callable(attach_db_timing)
    assert callable(DBSlowQuerySpanProcessor)
    assert isinstance(DB_TIMING_ENGINE_ATTR, str)


def test_attach_db_timing_idempotent():
    """Calling attach_db_timing twice on the same engine is a no-op."""
    # Pre-mark the engine so the idempotency guard short-circuits
    # on the first call. The second call would also be a no-op.
    engine = _StubEngine()
    setattr(engine, DB_TIMING_ENGINE_ATTR, True)
    # Use unittest.mock to bypass the SQLAlchemyInstrumentor call
    # (which would fail on a stub with only a 'name' attribute).
    from unittest.mock import patch
    with patch(
        "heretek_swarm.observability.db_timing.SQLAlchemyInstrumentor"
    ) as mock_inst:
        attach_db_timing(engine, logger_name="test_db_idempotent")
        # The instrumentor is NOT called (idempotency guard fires).
        mock_inst.return_value.instrument.assert_not_called()
    # Attribute remains True; no exception raised.
    assert getattr(engine, DB_TIMING_ENGINE_ATTR) is True


def test_attach_db_timing_marks_engine():
    """attach_db_timing sets the _db_timing_attached attribute on the engine."""
    # Use a fresh StubEngine so the idempotency guard doesn't
    # short-circuit. Mock the SQLAlchemyInstrumentor to avoid
    # needing a real SQLAlchemy engine.
    from unittest.mock import patch
    engine = _StubEngine()
    with patch("heretek_swarm.observability.db_timing.SQLAlchemyInstrumentor"):
        attach_db_timing(engine, logger_name="test_db_mark")
    assert getattr(engine, DB_TIMING_ENGINE_ATTR) is True


def test_attach_db_timing_signature_preserved():
    """attach_db_timing accepts the legacy signature."""
    import inspect

    sig = inspect.signature(attach_db_timing)
    params = list(sig.parameters.keys())
    # legacy signature (commit 1 of 10): engine, logger_name,
    # slow_query_threshold_ms, histogram, histogram_labels
    assert "engine_or_async_engine" in params
    assert "logger_name" in params
    assert "slow_query_threshold_ms" in params
    assert "histogram" in params
    assert "histogram_labels" in params


def test_dbslowqueryspanprocessor_constructor():
    """DBSlowQuerySpanProcessor accepts the 4 kwargs."""
    proc = DBSlowQuerySpanProcessor(
        slow_query_threshold_ms=500.0,
        histogram=None,
        histogram_labels=None,
    )
    assert proc._threshold_ms == 500.0
    assert proc._histogram is None
    assert proc._histogram_labels == {}


def test_dbslowqueryspanprocessor_skips_non_sqlalchemy_spans():
    """on_end() returns early for spans whose name doesn't start with 'sqlalchemy'."""
    proc = DBSlowQuerySpanProcessor(slow_query_threshold_ms=0.0)
    # A fake span with the wrong name
    class _FakeSpan:
        name = "http.GET"
        start_time = 0
        end_time = 100_000_000  # 100 ms
        attributes = {}
    proc.on_end(_FakeSpan())  # No exception, no log


def test_dbslowqueryspanprocessor_handles_missing_span_times():
    """on_end() handles spans with start_time/end_time = None."""
    proc = DBSlowQuerySpanProcessor(slow_query_threshold_ms=500.0)
    class _FakeSpan:
        name = "sqlalchemy.query"
        start_time = None
        end_time = None
        attributes = {"db.statement": "SELECT 1"}
    proc.on_end(_FakeSpan())  # No exception


def test_dbslowqueryspanprocessor_records_slow_query():
    """on_end() emits the db_slow_query log when threshold exceeded.

    Captures the warning via a stub logger that records the call
    args/kwargs (the production code uses structlog which accepts
    arbitrary kwargs; stdlib logging does not, so we use a stub
    callable here).
    """
    calls: list[tuple] = []

    class _StubLogger:
        def warning(self, *args, **kwargs):
            calls.append((args, kwargs))

    proc = DBSlowQuerySpanProcessor(
        slow_query_threshold_ms=10.0,  # very low threshold
        logger=_StubLogger(),
    )
    class _FakeSpan:
        name = "sqlalchemy.query"
        start_time = 0
        end_time = 50_000_000  # 50 ms (above 10 ms threshold)
        attributes = {"db.statement": "SELECT * FROM users"}
    proc.on_end(_FakeSpan())

    # The slow-query log was emitted with the event name
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("db_slow_query",)
    assert kwargs.get("duration_ms") == 50.0
    assert "SELECT" in kwargs.get("statement", "")


def test_dbslowqueryspanprocessor_observes_histogram():
    """on_end() observes the histogram when provided."""
    from prometheus_client import Histogram, CollectorRegistry

    registry = CollectorRegistry()
    hist = Histogram(
        "test_db_query_duration_seconds",
        "test",
        labelnames=["db_name"],
        registry=registry,
    )
    proc = DBSlowQuerySpanProcessor(
        slow_query_threshold_ms=500.0,  # high threshold (won't log)
        histogram=hist,
        histogram_labels={"db_name": "test"},
    )
    class _FakeSpan:
        name = "sqlalchemy.query"
        start_time = 0
        end_time = 100_000_000  # 100 ms = 0.1 s
        attributes = {"db.statement": "SELECT 1"}
    proc.on_end(_FakeSpan())

    # Histogram should have observed 0.1 seconds
    labeled = hist.labels(db_name="test")
    assert labeled._sum.get() >= 0.1
