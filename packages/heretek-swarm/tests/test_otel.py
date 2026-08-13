"""Tests for OTel auto-enable wiring in AutonomousSwarm.

Verifies that init_tracing() is called during startup when
OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from heretek_swarm.infrastructure.otel.tracing import SpanAttributes, get_tracer, span_context


@pytest.fixture(autouse=True)
def _reset_otel_globals():
    """Reset OTel global state between tests to avoid cross-contamination."""
    import heretek_swarm.infrastructure.otel.tracing as tracing_mod

    old_config = tracing_mod._tracer_config
    old_instance = tracing_mod._tracer_instance
    tracing_mod._tracer_config = None
    tracing_mod._tracer_instance = None

    # Also reset the OTel global tracer provider so set_tracer_provider() can
    # be called again in the next test.
    old_provider = trace.get_tracer_provider()
    trace._TRACER_PROVIDER_SET_ONCE._done = False

    yield

    tracing_mod._tracer_config = old_config
    tracing_mod._tracer_instance = old_instance
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(old_provider)


class TestOtelAutoEnable:
    """Verify OTel tracing is auto-enabled when the env var is present."""

    @patch("heretek_swarm.infrastructure.otel.tracing.init_tracing")
    def test_auto_enable_when_endpoint_set(self, mock_init_tracing):
        """init_tracing should be called with exporter='otlp' when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
        from heretek_swarm.runtime.main_loop import AutonomousSwarm

        swarm = AutonomousSwarm(no_infra=True)

        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}):
            import asyncio

            asyncio.run(swarm.initialize())

        mock_init_tracing.assert_called_once()
        call_args = mock_init_tracing.call_args
        config = call_args[0][0] if call_args[0] else call_args[1].get("config")
        assert config is not None
        assert config.exporter == "otlp"

    @patch("heretek_swarm.infrastructure.otel.tracing.init_tracing")
    def test_no_auto_enable_when_endpoint_unset(self, mock_init_tracing):
        """init_tracing should NOT be called when OTEL_EXPORTER_OTLP_ENDPOINT is absent."""
        from heretek_swarm.runtime.main_loop import AutonomousSwarm

        swarm = AutonomousSwarm(no_infra=True)

        # Ensure env var is not set
        env = {k: v for k, v in os.environ.items() if k != "OTEL_EXPORTER_OTLP_ENDPOINT"}
        with patch.dict(os.environ, env, clear=True):
            import asyncio

            asyncio.run(swarm.initialize())

        mock_init_tracing.assert_not_called()

    @patch("heretek_swarm.infrastructure.otel.tracing.init_tracing", side_effect=RuntimeError("boom"))
    def test_auto_enable_failure_is_swallowed(self, mock_init_tracing):
        """A failure in init_tracing should not crash the swarm init."""
        from heretek_swarm.runtime.main_loop import AutonomousSwarm

        swarm = AutonomousSwarm(no_infra=True)

        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}):
            import asyncio

            # Should not raise — the warning is logged and init continues
            asyncio.run(swarm.initialize())

        mock_init_tracing.assert_called_once()


class TestOtelMockCollector:
    """Verify spans flow through the tracing pipeline to an in-memory exporter.

    Uses a real TracerProvider backed by InMemorySpanExporter via
    SimpleSpanProcessor to prove the full span lifecycle works end-to-end.
    """

    @pytest.fixture()
    def _mock_exporter(self):
        """Set up a TracerProvider with InMemorySpanExporter and wire it into
        both the OTel global provider and the heretek_swarm tracing module.

        Yields the exporter so tests can inspect collected spans.
        """
        import heretek_swarm.infrastructure.otel.tracing as tracing_mod

        exporter = InMemorySpanExporter()
        resource = Resource.create({SERVICE_NAME: "heretek-swarm-test"})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        # Wire into OTel global and our module-level globals so get_tracer()
        # and span_context() use the test provider.
        trace._TRACER_PROVIDER_SET_ONCE._done = False
        trace.set_tracer_provider(provider)
        tracing_mod._tracer_config = tracing_mod.TracingConfig()
        tracing_mod._tracer_instance = trace.get_tracer(
            "heretek-swarm-test", "0.0.0"
        )

        yield exporter

        # Cleanup
        provider.shutdown()

    def test_spans_appear_in_mock_exporter(self, _mock_exporter):
        """Create spans via get_tracer() and span_context(); verify they
        appear in the exporter with correct names."""
        exporter = _mock_exporter

        # Create a span using the module-level get_tracer()
        tracer = get_tracer()
        with tracer.start_as_current_span("test-span-direct") as span:
            span.set_attribute("test.key", "direct")

        # Create a span using the span_context() context manager
        with span_context("test-span-context", {"test.key": "context"}):
            pass

        # Force flush SimpleSpanProcessor to push spans to exporter
        exporter.export(exporter.get_finished_spans())

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]
        assert "test-span-direct" in span_names
        assert "test-span-context" in span_names

        # Verify attributes on the direct span
        direct_span = next(s for s in spans if s.name == "test-span-direct")
        assert direct_span.attributes["test.key"] == "direct"

    def test_span_with_attributes_recorded(self, _mock_exporter):
        """Verify Heretek Swarm SpanAttributes are correctly recorded."""
        exporter = _mock_exporter
        tracer = get_tracer()

        with tracer.start_as_current_span("attribute-test") as span:
            span.set_attribute(SpanAttributes.AGENT_ID, "agent-42")
            span.set_attribute(SpanAttributes.WORKFLOW_ID, "wf-99")
            span.set_attribute(SpanAttributes.AGENT_TYPE, "catalyst")
            span.set_attribute(SpanAttributes.TOKENS_USED, 1234)

        spans = exporter.get_finished_spans()
        assert len(spans) >= 1
        recorded = next(s for s in spans if s.name == "attribute-test")

        assert recorded.attributes[SpanAttributes.AGENT_ID] == "agent-42"
        assert recorded.attributes[SpanAttributes.WORKFLOW_ID] == "wf-99"
        assert recorded.attributes[SpanAttributes.AGENT_TYPE] == "catalyst"
        assert recorded.attributes[SpanAttributes.TOKENS_USED] == 1234

    def test_nested_spans_collected(self, _mock_exporter):
        """Create parent and child spans; verify both appear with correct
        parent-child relationship via parent span context."""
        exporter = _mock_exporter
        tracer = get_tracer()

        with tracer.start_as_current_span("parent-span") as parent:
            parent_ctx = parent.get_span_context()
            with tracer.start_as_current_span("child-span") as child:
                child_ctx = child.get_span_context()

        spans = exporter.get_finished_spans()
        parent_recorded = next(s for s in spans if s.name == "parent-span")
        child_recorded = next(s for s in spans if s.name == "child-span")

        # Both spans collected
        assert parent_recorded is not None
        assert child_recorded is not None

        parent_sc = parent_recorded.get_span_context()
        child_sc = child_recorded.get_span_context()

        # Child's parent ID matches parent's span ID
        assert child_recorded.parent.span_id == parent_sc.span_id

        # Both share the same trace ID
        assert parent_sc.trace_id == child_sc.trace_id
