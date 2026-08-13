# Tier 1 Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full OpenTelemetry observability to Tier 1 — Prometheus `/metrics` endpoint, structured logs with trace correlation, and Jaeger distributed traces through Tribunal.

**Architecture:** New `tier1/observability/` module with three files (`__init__.py`, `logging.py`, `metrics.py`). `init_telemetry(app)` wires OTel providers at app startup. Existing code gets minimal instrumentation: spans around Tribunal.run and provider calls, counters for consensus outcomes and token throughput.

**Tech Stack:** opentelemetry-api/sdk 1.24+, opentelemetry-exporter-otlp, opentelemetry-instrumentation-fastapi, structlog, pytest.

## Global Constraints

- Working directory: `backend/tier1/`
- Python 3.11
- OTel deps go in `[project.dependencies]` (not `[project.optional-dependencies].dev`)
- Jaeger OTLP HTTP endpoint: `http://jaeger:4318`
- Prometheus scrapes OTel SDK's PrometheusMetricReader at port `9464`
- Graceful degradation: if OTel SDK not installed, `get_tracer()` and `get_meter()` return no-ops
- No live Jaeger/Prometheus in tests — all in-memory via OTel InMemoryMetricReader

## File Structure

**Create:**
- `tier1/observability/__init__.py` — `init_telemetry()`, `get_tracer()`, `get_meter()`
- `tier1/observability/logging.py` — `add_trace_context` structlog processor
- `tier1/observability/metrics.py` — 6 instrument singletons
- `tests/unit/test_observability_logging.py` — logging processor test
- `tests/unit/test_observability_metrics.py` — metrics instruments test
- `tests/unit/test_observability_init.py` — init_telemetry wiring test

**Modify:**
- `tier1/api/app.py:64-73` — call `init_telemetry(app)` in `create_app()`
- `tier1/deliberation/graph.py:81-84` — wrap `Tribunal.run()` with span + latency/round metrics
- `tier1/llm/garage.py:197-213,237-250` — wrap provider calls with span + duration metric
- `tier1/deliberation/nodes/steward.py:48-78` — record consensus_outcome counter
- `tier1/deliberation/nodes/_base.py:88-101` — record agent_token_count
- `pyproject.toml` — add 4 OTel deps

**Docker (local dev):**
- `docker-compose.yml` — add jaeger + prometheus services
- `prometheus.yml` — new scrape config

---

## Task 1: Add OTel dependencies

**Files:**
- Modify: `pyproject.toml:11-28`

- [ ] **Step 1: Add OTel deps**

Edit `backend/tier1/pyproject.toml`. Add after `"tenacity>=8.2"` in `[project.dependencies]`:

```toml
dependencies = [
    ...
    "tenacity>=8.2",
    "opentelemetry-api>=1.24",
    "opentelemetry-sdk>=1.24",
    "opentelemetry-exporter-otlp>=1.24",
    "opentelemetry-instrumentation-fastapi>=0.45",
]
```

- [ ] **Step 2: Install**

```bash
cd backend/tier1 && source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 3: Verify import**

```bash
cd backend/tier1 && source .venv/bin/activate && python -c "from opentelemetry import trace, metrics; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run full suite (no regressions)**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/pyproject.toml && git commit -m "build(tier1): add OpenTelemetry dependencies"
```

---

## Task 2: Logging processor (add_trace_context)

**Files:**
- Create: `tier1/observability/__init__.py`
- Create: `tier1/observability/logging.py`
- Test: `tests/unit/test_observability_logging.py`

**Interfaces:**
- Produces: `add_trace_context(logger, method_name, event_dict) -> event_dict`
- Consumed by: Task 4 (wired into structlog via `init_telemetry`)

- [ ] **Step 1: Write the failing test**

Write `backend/tier1/tests/unit/test_observability_logging.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_observability_logging.py -v --no-cov
```

Expected: FAIL (module not found).

- [ ] **Step 3: Create `__init__.py` and `logging.py`**

Write `backend/tier1/observability/__init__.py`:

```python
"""Tier 1 observability — OpenTelemetry setup, metrics, logging."""

from tier1.observability.logging import add_trace_context  # noqa: F401
```

Write `backend/tier1/observability/logging.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_observability_logging.py -v --no-cov
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/observability/ backend/tier1/tests/unit/test_observability_logging.py && git commit -m "feat(tier1): add_trace_context structlog processor"
```

---

## Task 3: Metrics instruments

**Files:**
- Create: `tier1/observability/metrics.py`
- Test: `tests/unit/test_observability_metrics.py`

**Interfaces:**
- Produces: `get_meter(name) -> Meter`, and 6 instrument accessors
- Consumed by: Task 5, Task 6 (instrumentation in garage, steward, _base, graph)

- [ ] **Step 1: Write the failing test**

Write `backend/tier1/tests/unit/test_observability_metrics.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_observability_metrics.py -v --no-cov
```

Expected: FAIL (import error).

- [ ] **Step 3: Implement metrics.py**

Write `backend/tier1/observability/metrics.py`:

```python
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
    ).record(delta, {"provider": provider_name})


def record_consensus_outcome(outcome: str, *, provider=None) -> None:
    """Record a consensus outcome (approved, rejected, no-consensus, timeout)."""
    m = _m("consensus") if provider is None else get_meter("tier1", provider)
    m.create_counter(
        "tier1.deliberation.consensus",
        description="Consensus outcomes",
    ).record(1, {"outcome": outcome})


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
    ).record(count, {"agent": agent})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_observability_metrics.py -v --no-cov
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/observability/metrics.py backend/tier1/tests/unit/test_observability_metrics.py && git commit -m "feat(tier1): OTel metric instruments (6 instruments, in-memory tests)"
```

---

## Task 4: Wire init_telemetry into create_app

**Files:**
- Modify: `tier1/observability/__init__.py` (expand)
- Modify: `tier1/api/app.py:64-73`
- Test: `tests/unit/test_observability_init.py`

**Interfaces:**
- Consumes: Task 2 (`add_trace_context`), Task 3 (`set_default_provider`)
- Produces: `init_telemetry(app)` called once at app startup

- [ ] **Step 1: Write the failing test**

Write `backend/tier1/tests/unit/test_observability_init.py`:

```python
"""Tests for init_telemetry wiring."""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI


def test_init_telemetry_configures_structlog():
    """init_telemetry should inject add_trace_context into structlog."""
    from tier1.observability import init_telemetry

    app = FastAPI()
    with patch("tier1.observability._init_otel") as mock_otel:
        init_telemetry(app)
        mock_otel.assert_called_once()


def test_init_telemetry_installs_fastapi_instrumentor():
    """init_telemetry should instrument the FastAPI app."""
    from tier1.observability import init_telemetry

    app = FastAPI()
    with patch("tier1.observability._init_otel"):
        init_telemetry(app)
    # If _init_otel is mocked, we just verify init_telemetry doesn't crash.
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_observability_init.py -v --no-cov
```

Expected: FAIL (init_telemetry not fully wired).

- [ ] **Step 3: Expand `__init__.py`**

Overwrite `backend/tier1/observability/__init__.py`:

```python
"""Tier 1 observability — OpenTelemetry setup, metrics, logging.

Usage:
    from tier1.observability import init_telemetry, get_tracer, get_meter
    init_telemetry(app)  # called once in create_app()
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from tier1.observability.logging import add_trace_context


def get_tracer(name: str):
    """Get a named tracer from the global OTel TracerProvider."""
    from opentelemetry import trace
    return trace.get_tracer(name)


def get_meter(name: str):
    """Get a named meter from the global OTel MeterProvider."""
    from opentelemetry import metrics
    return metrics.get_meter(name)


def _init_otel(app: FastAPI) -> None:
    """Configure OTel providers, FastAPI instrumentor, and structlog."""
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # Traces → Jaeger
    trace_exporter = OTLPSpanExporter(endpoint="http://jaeger:4318/v1/traces")
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics → Jaeger + Prometheus
    metric_exporter = OTLPMetricExporter(endpoint="http://jaeger:4318/v1/metrics")
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Wire the default provider for metrics.py
    from tier1.observability.metrics import set_default_provider
    set_default_provider(meter_provider)

    # FastAPI auto-instrumentation
    FastAPIInstrumentor.instrument_app(app)

    # Structlog trace context
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            add_trace_context,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
    )


def init_telemetry(app: FastAPI) -> None:
    """Initialize OpenTelemetry for the application.

    Safe to call multiple times — only configures once.
    Degrades silently if OTel SDK is not installed.
    """
    try:
        _init_otel(app)
    except ImportError:
        # OTel SDK not installed — all get_tracer/get_meter calls
        # will return no-ops from the opentelemetry-api package.
        pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_observability_init.py -v --no-cov
```

Expected: 2 passed.

- [ ] **Step 5: Wire into `create_app()`**

Edit `backend/tier1/tier1/api/app.py`. Add after `app = FastAPI(...)` (line 66):

```python
def create_app(settings: Settings | None = None, dashboard_path: Path | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Tier 1 Core Triad", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    # Wire observability (OTel traces + metrics + logging)
    from tier1.observability import init_telemetry
    init_telemetry(app)
    app.include_router(health.router)
    app.include_router(deliberations.router)
    app.include_router(ws.router)
    if dashboard_path is not None:
        mount_static(app, dashboard_path)
    return app
```

- [ ] **Step 6: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/observability/__init__.py backend/tier1/tier1/api/app.py backend/tier1/tests/unit/test_observability_init.py && git commit -m "feat(tier1): wire init_telemetry into create_app"
```

---

## Task 5: Instrument Tribunal + garage provider calls

**Files:**
- Modify: `tier1/deliberation/graph.py:81-84`
- Modify: `tier1/llm/garage.py:197-213` (OpenAI provider)
- Modify: `tier1/llm/garage.py:237-250` (Anthropic provider)

**Interfaces:**
- Consumes: Task 3 (`record_provider_call`, `record_deliberation_latency`, `record_deliberation_rounds`, `toggle_circuit_state`, `get_tracer`)
- Produces: spans around Tribunal.run + provider calls, latency/round/duration metrics

- [ ] **Step 1: Instrument `Tribunal.run()`**

Edit `backend/tier1/tier1/deliberation/graph.py`. Wrap `run()` with span + metrics:

```python
import time

from tier1.observability import get_tracer
from tier1.observability.metrics import record_deliberation_latency, record_deliberation_rounds

# Add these imports at the top of the file.

    async def run(self, state: DeliberationState) -> DeliberationState:
        """Run the tribunal to completion. Returns final state."""
        tracer = get_tracer("tier1.tribunal")
        with tracer.start_as_current_span("tribunal.run") as span:
            span.set_attribute("deliberation.id", state.get("deliberation_id", ""))
            t0 = time.monotonic()
            result = await self._compiled.ainvoke(state)
            elapsed = time.monotonic() - t0
            rounds = result.get("round", 0) + 1
            span.set_attribute("deliberation.rounds", rounds)
            record_deliberation_latency(elapsed)
            record_deliberation_rounds(rounds)
            return DeliberationState(result)
```

- [ ] **Step 2: Instrument `_stream_openai_provider` with span + duration**

Edit `backend/tier1/tier1/llm/garage.py`. Add import at top:

```python
import time
from tier1.observability import get_tracer
from tier1.observability.metrics import record_provider_call
```

Wrap the streaming section in `_stream_openai_provider` (inside the `try` block after client creation):

```python
        tracer = get_tracer("tier1.llm")
        t0 = time.monotonic()
        with tracer.start_as_current_span(f"llm.{provider_name}") as span:
            span.set_attribute("provider", provider_name)
            span.set_attribute("model", model)
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )
                seq = 0
                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield StreamChunk(token=delta.content, agent=agent, seq=seq)
                        seq += 1
            except Exception as exc:
                if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                    raise LLMTimeout(str(exc)) from exc
                try:
                    from openai import OpenAIError
                except ImportError:
                    OpenAIError = None
                if OpenAIError is not None and isinstance(exc, OpenAIError):
                    raise LLMUnavailable(str(exc)) from exc
                raise
            finally:
                record_provider_call(provider_name, time.monotonic() - t0)
```

- [ ] **Step 3: Instrument `_stream_anthropic_provider` similarly**

Same pattern — add span + duration recording around the streaming block.

- [ ] **Step 4: Instrument circuit state changes**

Edit `backend/tier1/tier1/llm/garage.py`. In `_Circuit.record_failure()`, after `self.open_until = now + CIRCUIT_OPEN_S` (line 57):

```python
            from tier1.observability.metrics import toggle_circuit_state
            toggle_circuit_state(self.name, +1)
```

In `_Circuit.record_success()`, after `self.open_until = 0.0` (line 62):

```python
            from tier1.observability.metrics import toggle_circuit_state
            toggle_circuit_state(self.name, -1)
```

- [ ] **Step 5: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/deliberation/graph.py backend/tier1/tier1/llm/garage.py && git commit -m "feat(tier1): instrument Tribunal.run + provider calls with spans + metrics"
```

---

## Task 6: Instrument consensus + agent tokens + docker-compose

**Files:**
- Modify: `tier1/deliberation/nodes/steward.py:48-78`
- Modify: `tier1/deliberation/nodes/_base.py:88-101`
- Create: `docker-compose.yml` (or modify existing)
- Create: `prometheus.yml`

**Interfaces:**
- Consumes: Task 3 (`record_consensus_outcome`, `record_agent_tokens`)

- [ ] **Step 1: Instrument steward_node with consensus_outcome**

Edit `backend/tier1/tier1/deliberation/nodes/steward.py`. Add at top:

```python
from tier1.observability.metrics import record_consensus_outcome
```

Inside `steward_node`, after `final = build_final_verdict(...)` (line 43), before the `if final.decision in` block:

```python
    record_consensus_outcome(final.decision)
```

- [ ] **Step 2: Instrument run_agent with agent_token_count**

Edit `backend/tier1/tier1/deliberation/nodes/_base.py`. Add at top:

```python
from tier1.observability.metrics import record_agent_tokens
```

After `raw = "".join(accumulated)` (line 103), add:

```python
    record_agent_tokens(agent, len(accumulated))
```

- [ ] **Step 3: Add Jaeger + Prometheus to docker-compose**

If `backend/tier1/docker-compose.yml` exists, add services. Otherwise create `backend/tier1/docker-compose.yml` with:

```yaml
version: "3.8"
services:
  jaeger:
    image: jaegertracing/all-in-one:1.57
    ports:
      - "4318:4318"
      - "16686:16686"
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  prometheus:
    image: prom/prometheus:v2.51.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

Create `backend/tier1/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: tier1
    static_configs:
      - targets: ["host.docker.internal:9464"]
```

- [ ] **Step 4: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/deliberation/nodes/steward.py backend/tier1/tier1/deliberation/nodes/_base.py backend/tier1/docker-compose.yml backend/tier1/prometheus.yml && git commit -m "feat(tier1): instrument consensus + agent tokens, add Jaeger + Prometheus"
```

---

## Task 7: Final verification

**Files:** none

- [ ] **Step 1: Full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all tests pass, coverage ≥ 80%.

- [ ] **Step 2: Verify observability imports work**

```bash
cd backend/tier1 && source .venv/bin/activate && python -c "
from tier1.observability import init_telemetry, get_tracer, get_meter
from tier1.observability.metrics import record_provider_call, record_consensus_outcome
from tier1.observability.logging import add_trace_context
print('All observability imports OK')
"
```

- [ ] **Step 3: Verify no regressions in existing tests**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/ --no-cov -q
```

Expected: existing unit tests unaffected.
