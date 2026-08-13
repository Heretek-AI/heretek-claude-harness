"""OTel metric instruments for Tier 1.

All instruments are lazily created via a module-level provider.
Pass `provider=InMemoryMetricReader()` in tests; omit in production
(defaults to the global MeterProvider set by init_telemetry).
"""

from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.metrics import MeterProvider

# Module-level default provider (set by init_telemetry in production)
_default_provider: MeterProvider | None = None


def set_default_provider(provider: MeterProvider) -> None:
    global _default_provider
    _default_provider = provider


def get_meter(name: str, provider: MeterProvider | None = None) -> metrics.Meter:
    """Get or create a named meter. Uses the default provider if none given."""
    prov = provider or _default_provider or metrics.get_meter_provider()
    return prov.get_meter(name)


# --- Instruments (created on first use, cached on the meter) ---

_meters: dict[str, metrics.Meter] = {}


def _m(name: str) -> metrics.Meter:
    if name not in _meters:
        _meters[name] = get_meter("tier1")
    return _meters[name]


def record_provider_call(provider_name: str, duration_s: float, *, provider=None) -> None:
    """Record the duration of a single provider call."""
    m = _m("provider") if provider is None else get_meter("tier1", provider)
    m.create_histogram(
        "tier1.provider.call.duration",
        unit="s",
        description="Seconds per LLM provider call",
    ).record(duration_s, {"provider": provider_name})


def toggle_circuit_state(provider_name: str, delta: int, *, provider=None) -> None:
    """Record a circuit state change: +1 opens, -1 closes."""
    m = _m("circuit") if provider is None else get_meter("tier1", provider)
    m.create_up_down_counter(
        "tier1.provider.circuit.open",
        description="Number of providers with open circuits",
    ).add(delta, {"provider": provider_name})


def record_consensus_outcome(outcome: str, *, provider=None) -> None:
    """Record a consensus outcome (approved, rejected, no-consensus, timeout)."""
    m = _m("consensus") if provider is None else get_meter("tier1", provider)
    m.create_counter(
        "tier1.deliberation.consensus",
        description="Consensus outcomes",
    ).add(1, {"outcome": outcome})


def record_deliberation_latency(duration_s: float, *, provider=None) -> None:
    """Record total deliberation wall-clock time."""
    m = _m("deliberation") if provider is None else get_meter("tier1", provider)
    m.create_histogram(
        "tier1.deliberation.latency",
        unit="s",
        description="Total deliberation wall-clock seconds",
    ).record(duration_s)


def record_deliberation_rounds(rounds: int, *, provider=None) -> None:
    """Record the number of rounds before verdict."""
    m = _m("deliberation") if provider is None else get_meter("tier1", provider)
    m.create_histogram(
        "tier1.deliberation.rounds",
        description="Number of rounds before verdict",
    ).record(rounds)


def record_agent_tokens(agent: str, count: int, *, provider=None) -> None:
    """Record the number of tokens yielded by an agent."""
    m = _m("agent") if provider is None else get_meter("tier1", provider)
    m.create_counter(
        "tier1.agent.tokens",
        description="Tokens yielded per agent",
    ).add(count, {"agent": agent})
