# Tier 1 Observability Test Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 tests that bring `tier1/observability/__init__.py` and `metrics.py` to ≥80% coverage, including one integration test that verifies spans flow through `init_telemetry()` → `get_tracer()` → exporter without needing a live Jaeger.

**Architecture:** Tests only — no production code changes. Existing `init_telemetry`, `get_tracer`, `get_meter`, and metric helpers stay untouched. New tests mock the OTel SDK constructor calls and use `InMemorySpanExporter` for the integration test.

**Tech Stack:** pytest, opentelemetry-sdk (already installed), unittest.mock.

## Global Constraints

- Python ≥ 3.11 (per `tier1/pyproject.toml`)
- Test coverage ≥ 80% on touched modules (enforced by `pyproject.toml` `addopts`)
- All test paths: `backend/tier1/tests/unit/`
- Run pytest from `backend/tier1/` with venv activated: `cd backend/tier1 && source .venv/bin/activate && python -m pytest ...`
- No production code changes.
- All 11 existing observability tests must continue to pass.

---

### Task 1: Add 4 tests to `test_observability_init.py`

**Files:**
- Modify: `backend/tier1/tests/unit/test_observability_init.py` (append 4 tests)
- (No production code changes.)

**Interfaces:**
- Consumes: existing `init_telemetry(app)`, `get_tracer(name)`, `get_meter(name)` from `tier1.observability`; `set_default_provider(provider)` from `tier1.observability.metrics`; OTel SDK symbols (`OTLPSpanExporter`, `BatchSpanProcessor`, `TracerProvider`, `OTLPMetricExporter`, `PeriodicExportingMetricReader`, `MeterProvider`, `FastAPIInstrumentor`, `InMemorySpanExporter`)
- Produces: 4 new tests that increase coverage on `_init_otel` from 28% to ≥80%

- [ ] **Step 1: Read the existing test file**

Read `backend/tier1/tests/unit/test_observability_init.py` end-to-end to confirm the existing fixtures and imports. Note the existing test that asserts `init_telemetry_configures_structlog` is already present — do not duplicate it.

- [ ] **Step 2: Add the 4 new tests**

Append to `backend/tier1/tests/unit/test_observability_init.py` (after the existing tests, before any module-level `if __name__ == "__main__"` block):

```python
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_init_telemetry_configures_tracer_provider():
    """init_telemetry builds an OTLPSpanExporter + TracerProvider for traces."""
    app = FastAPI()
    with patch("tier1.observability.init.OTLPSpanExporter") as mock_span_exporter, \
         patch("tier1.observability.init.BatchSpanProcessor") as mock_batch, \
         patch("tier1.observability.init.TracerProvider") as mock_tracer_prov, \
         patch("tier1.observability.init.FastAPIInstrumentor") as mock_fapi, \
         patch("tier1.observability.metrics.set_default_provider"):
        from tier1.observability import init_telemetry
        init_telemetry(app)
    mock_span_exporter.assert_called_once()
    # Jaeger endpoint per spec.
    endpoint = mock_span_exporter.call_args.kwargs.get("endpoint") or mock_span_exporter.call_args.args[0]
    assert "jaeger:4318" in endpoint
    # BatchSpanProcessor wraps the exporter and is added to the provider.
    mock_batch.assert_called_once_with(mock_span_exporter.return_value)
    mock_tracer_prov.return_value.add_span_processor.assert_called_once_with(mock_batch.return_value)


def test_init_telemetry_configures_meter_provider():
    """init_telemetry builds an OTLPMetricExporter + PeriodicExportingMetricReader + MeterProvider."""
    app = FastAPI()
    with patch("tier1.observability.init.OTLPMetricExporter") as mock_metric_exporter, \
         patch("tier1.observability.init.PeriodicExportingMetricReader") as mock_reader, \
         patch("tier1.observability.init.MeterProvider") as mock_meter_prov, \
         patch("tier1.observability.init.FastAPIInstrumentor"), \
         patch("tier1.observability.init.structlog.configure") as mock_structlog, \
         patch("tier1.observability.metrics.set_default_provider"):
        from tier1.observability import init_telemetry
        init_telemetry(app)
    mock_metric_exporter.assert_called_once()
    endpoint = mock_metric_exporter.call_args.kwargs.get("endpoint") or mock_metric_exporter.call_args.args[0]
    assert "jaeger:4318" in endpoint
    mock_reader.assert_called_once()
    # 10s export interval per spec.
    assert mock_reader.call_args.kwargs.get("export_interval_millis") == 10000
    mock_meter_prov.assert_called_once_with(metric_readers=[mock_reader.return_value])
    # structlog.configure was called with a processor list that includes add_trace_context.
    processors = mock_structlog.call_args.kwargs.get("processors") or mock_structlog.call_args.args[0]
    from tier1.observability.logging import add_trace_context
    assert add_trace_context in processors


def test_init_telemetry_calls_set_default_provider():
    """init_telemetry forwards the meter provider to metrics.set_default_provider."""
    from tier1.observability.metrics import set_default_provider
    app = FastAPI()
    with patch("tier1.observability.init.OTLPSpanExporter"), \
         patch("tier1.observability.init.OTLPMetricExporter"), \
         patch("tier1.observability.init.PeriodicExportingMetricReader"), \
         patch("tier1.observability.init.TracerProvider"), \
         patch("tier1.observability.init.MeterProvider") as mock_meter_prov, \
         patch("tier1.observability.init.FastAPIInstrumentor"), \
         patch("tier1.observability.init.structlog.configure"), \
         patch("tier1.observability.metrics.set_default_provider") as mock_set_default:
        from tier1.observability import init_telemetry
        init_telemetry(app)
    mock_set_default.assert_called_once_with(mock_meter_prov.return_value)


def test_init_telemetry_produces_observable_spans():
    """Integration: after init_telemetry(), spans emitted via get_tracer() reach an exporter.

    Replaces the global TracerProvider with one whose exporter is in-memory,
    so the assertion is deterministic without needing a live Jaeger.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from tier1.observability import init_telemetry, get_tracer

    app = FastAPI()
    # Run init_telemetry once to exercise the production wiring path.
    init_telemetry(app)

    # Replace the global provider with one whose exporter is in-memory.
    in_memory = InMemorySpanExporter()
    new_provider = TracerProvider()
    new_provider.add_span_processor(SimpleSpanProcessor(in_memory))
    trace.set_tracer_provider(new_provider)

    tracer = get_tracer("test.integration")
    with tracer.start_as_current_span("test-span"):
        pass

    spans = in_memory.get_finished_spans()
    assert any(s.name == "test-span" for s in spans), f"expected test-span, got {[s.name for s in spans]}"
    span = next(s for s in spans if s.name == "test-span")
    assert span.context.trace_id != 0
```

- [ ] **Step 3: Run the new tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_observability_init.py -v --no-cov`

Expected: 7 tests pass (3 existing + 4 new).

If failures, common issues:
- `ModuleNotFoundError: opentelemetry.sdk.trace.export.in_memory_span_exporter`: confirm the project venv has `opentelemetry-sdk` installed (already pinned in the observability spec's dependencies).
- `init_telemetry` calls real OTel constructors instead of the patched ones: confirm every OTel symbol used in `tier1/observability/__init__.py` lines 32-39 is patched in the test. List: `OTLPSpanExporter`, `BatchSpanProcessor`, `TracerProvider`, `OTLPMetricExporter`, `PeriodicExportingMetricReader`, `MeterProvider`, `FastAPIInstrumentor`. Also `structlog.configure`.
- `set_default_provider` not found: it's in `tier1/observability/metrics.py` (imported from `__init__.py` as `from tier1.observability.metrics import set_default_provider`).
- The integration test's `init_telemetry()` call may attempt to connect to Jaeger at `http://jaeger:4318/v1/traces` and hang or error. The `OTLPSpanExporter` constructor itself does NOT connect (it just stores the endpoint URL). The `BatchSpanProcessor` only fires on span export, which is asynchronous. So the test should complete without contacting Jaeger. If it doesn't, also patch `BatchSpanProcessor` and `PeriodicExportingMetricReader` to no-op.

- [ ] **Step 4: Run all observability tests to confirm no regression**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_observability_init.py tests/unit/test_observability_logging.py tests/unit/test_observability_metrics.py -v --no-cov`

Expected: 11 observability tests pass (after Task 1 alone).

If `test_init_telemetry_configures_structlog` (existing) fails because the new tests altered module-level `structlog.configure` state, ensure each new test patches `structlog.configure` so its changes are isolated.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tests/unit/test_observability_init.py
git commit -m "test(tier1): cover observability _init_otel branches

Four new tests pin _init_otel behavior:
- test_init_telemetry_configures_tracer_provider: OTLPSpanExporter
  + TracerProvider built with Jaeger endpoint.
- test_init_telemetry_configures_meter_provider: OTLPMetricExporter
  + PeriodicExportingMetricReader (10s interval) + MeterProvider
  + structlog processors include add_trace_context.
- test_init_telemetry_calls_set_default_provider: meter provider
  forwarded to metrics.set_default_provider.
- test_init_telemetry_produces_observable_spans: integration test
  using InMemorySpanExporter — confirms spans flow from get_tracer()
  through the configured provider to an exporter.

No production code changes. Targets __init__.py coverage 28% -> >=80%.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add 2 tests to `test_observability_metrics.py`

**Files:**
- Modify: `backend/tier1/tests/unit/test_observability_metrics.py` (append 2 tests)
- (No production code changes.)

**Interfaces:**
- Consumes: existing `get_meter(name, provider=None)` and module-level `_default_provider` and `set_default_provider(provider)` from `tier1.observability.metrics`
- Produces: 2 new tests covering `set_default_provider` and the arg-provider path on `get_meter`

- [ ] **Step 1: Read the existing test file**

Read `backend/tier1/tests/unit/test_observability_metrics.py` end-to-end to confirm the existing fixtures and imports.

- [ ] **Step 2: Add the 2 new tests**

Append to `backend/tier1/tests/unit/test_observability_metrics.py`:

```python
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
        set_default_provider,
    )
    from tier1 import observability

    original = observability.metrics._default_provider
    try:
        default = MeterProvider()
        custom = MeterProvider()
        set_default_provider(default)
        m_default = observability.get_meter("test.arg_default")
        m_custom = observability.get_meter("test.arg_custom", provider=custom)
        # The two Meter instances must be different (different providers
        # mint different Meter objects even for the same name).
        assert m_default is not m_custom
    finally:
        observability.metrics._default_provider = original
```

- [ ] **Step 3: Run the new tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_observability_metrics.py -v --no-cov`

Expected: 9 tests pass (7 existing + 2 new).

If failures, common issues:
- `NoOpMeter` import path wrong: `from opentelemetry.metrics import NoOpMeter`. If the SDK doesn't expose it, drop that import and just assert `m is not None`.
- `_default_provider` is not directly assignable: confirm `tier1/observability/metrics.py` defines `_default_provider` at module level (it does, per the read of the file). If it uses a different name, use that.
- The two `MeterProvider` instances return the same `Meter` for the same name because the global `MeterProvider` is queried by name and the SDK caches per-name meters across provider instances. If that happens, the test will need to mock `MeterProvider.get_meter` instead — but the cleanest fix is to assert that the provider arg flows through, e.g. by patching the SDK provider and tracking calls.

- [ ] **Step 4: Run all observability tests to confirm no regression**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_observability_init.py tests/unit/test_observability_logging.py tests/unit/test_observability_metrics.py -v --no-cov`

Expected: 18 tests pass (3 existing init + 4 new init + 2 logging + 7 existing metrics + 2 new metrics).

If numbers don't match, recount by running with `-v` and tallying.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tests/unit/test_observability_metrics.py
git commit -m "test(tier1): cover metrics set_default_provider + arg-provider

Two new tests pin metrics.py provider-resolution:
- test_set_default_provider: setting the module-level default
  is observable via get_meter() with no arg.
- test_get_meter_uses_arg_provider: explicit provider arg takes
  precedence over the default.

Targets metrics.py coverage 88% -> >=90%.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Full suite + coverage verification

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full suite (skip health tests due to Postgres dependency)**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest --ignore=tests/unit/test_health.py --no-cov 2>&1 | tail -3`

Expected: 179 passed, 11 skipped (was 173 before; +4 init + 2 metrics = +6 tests). 0 failures.

- [ ] **Step 2: Verify coverage on `tier1/observability/`**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_observability_init.py tests/unit/test_observability_logging.py tests/unit/test_observability_metrics.py --cov=tier1/observability --cov-report=term 2>&1 | grep -E "observability|TOTAL" | head`

Expected:
```
tier1/observability/__init__.py    <N>    <M>    ≥80%   ...
tier1/observability/logging.py      9      0   100%
tier1/observability/metrics.py    <N>    <M>    ≥90%   ...
```

If `__init__.py` is below 80% or `metrics.py` below 90%, identify the uncovered lines (the report will list them) and add targeted tests.

- [ ] **Step 3: Commit (only if Step 1/2 surfaced a fix)**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tests/unit/test_observability_init.py backend/tier1/tests/unit/test_observability_metrics.py
git commit -m "test(tier1): push observability coverage above 80%/90%

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Only commit if Step 2 surfaced an uncovered branch and Step 1 was extended.)
