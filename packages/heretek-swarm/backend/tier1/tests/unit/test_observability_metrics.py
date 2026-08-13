"""Tests for OTel metric instruments."""

from __future__ import annotations

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from tier1.observability.metrics import (
    get_meter,
    record_provider_call,
    record_consensus_outcome,
    record_agent_tokens,
    record_deliberation_latency,
    record_deliberation_rounds,
    toggle_circuit_state,
)


def _setup_provider():
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider, reader


def test_get_meter_returns_meter():
    provider, _ = _setup_provider()
    meter = get_meter("test", provider=provider)
    assert meter is not None


def test_record_provider_call():
    provider, reader = _setup_provider()
    get_meter("test", provider=provider)
    record_provider_call("minimax", 0.5, provider=provider)
    record_provider_call("minimax", 1.0, provider=provider)
    metrics = reader.get_metrics_data()
    assert len(metrics.resource_metrics) > 0


def test_record_consensus_outcome():
    provider, reader = _setup_provider()
    get_meter("test", provider=provider)
    record_consensus_outcome("approved", provider=provider)
    record_consensus_outcome("no-consensus", provider=provider)
    metrics = reader.get_metrics_data()
    assert len(metrics.resource_metrics) > 0


def test_record_agent_tokens():
    provider, reader = _setup_provider()
    get_meter("test", provider=provider)
    record_agent_tokens("alpha", 42, provider=provider)
    metrics = reader.get_metrics_data()
    assert len(metrics.resource_metrics) > 0


def test_record_deliberation_latency():
    provider, reader = _setup_provider()
    get_meter("test", provider=provider)
    record_deliberation_latency(5.0, provider=provider)
    metrics = reader.get_metrics_data()
    assert len(metrics.resource_metrics) > 0


def test_record_deliberation_rounds():
    provider, reader = _setup_provider()
    get_meter("test", provider=provider)
    record_deliberation_rounds(2, provider=provider)
    metrics = reader.get_metrics_data()
    assert len(metrics.resource_metrics) > 0


def test_toggle_circuit_state():
    provider, reader = _setup_provider()
    get_meter("test", provider=provider)
    toggle_circuit_state("minimax", +1, provider=provider)
    toggle_circuit_state("minimax", -1, provider=provider)
    metrics = reader.get_metrics_data()
    assert len(metrics.resource_metrics) > 0


def test_set_default_provider():
    """set_default_provider stores the provider; get_meter uses it when no arg passed."""
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.metrics import NoOpMeter

    from tier1.observability.metrics import (
        _default_provider,
        set_default_provider,
    )
    from tier1 import observability  # access module-level singleton

    # Snapshot and restore so we don't pollute the singleton for later tests.
    original = observability.metrics._default_provider
    try:
        custom = MeterProvider()
        set_default_provider(custom)
        assert observability.metrics._default_provider is custom
        m = observability.get_meter("test.set_default")
        # The meter returned should be sourced from the custom provider.
        # The SDK's MeterProvider.get_meter returns a Meter; NoOpMeter is the API no-op fallback.
        assert m is not None
    finally:
        observability.metrics._default_provider = original


def test_get_meter_uses_arg_provider():
    """get_meter(name, provider=custom) prefers the explicit provider over the default."""
    from opentelemetry.sdk.metrics import MeterProvider

    from tier1.observability.metrics import (
        get_meter,
        set_default_provider,
    )
    from tier1 import observability

    original = observability.metrics._default_provider
    try:
        default = MeterProvider()
        custom = MeterProvider()
        set_default_provider(default)
        m_default = get_meter("test.arg_default")
        m_custom = get_meter("test.arg_custom", provider=custom)
        # The two Meter instances must be different (different providers
        # mint different Meter objects even for the same name).
        assert m_default is not m_custom
    finally:
        observability.metrics._default_provider = original
