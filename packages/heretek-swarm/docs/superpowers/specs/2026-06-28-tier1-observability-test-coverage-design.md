# Tier 1 Observability Test Coverage — Design Spec

**Date:** 2026-06-28
**Status:** Approved

## Context

The Tier 1 Observability spec (2026-06-25) approved a Prometheus + Jaeger
+ structlog observability stack. The production code is largely in place:
`tier1/observability/__init__.py` exposes `init_telemetry(app)`,
`get_tracer(name)`, `get_meter(name)`; `logging.py` provides the
`add_trace_context` structlog processor; `metrics.py` exposes six
instruments. `init_telemetry` is wired into `create_app()`. Docker-compose
includes Jaeger and Prometheus sidecars; `prometheus.yml` scrapes
`host.docker.internal:9464`. Eleven tests already pass.

Gaps remain: `observability/__init__.py` is at 28% coverage — the
`_init_otel` body that wires TracerProvider, MeterProvider, FastAPI
instrumentor, and structlog is almost entirely untested. `metrics.py`
sits at 88% — `set_default_provider` and the `_m()` helper are uncovered.
The existing tests do not verify that spans actually flow from
`get_tracer()` through the configured provider to an exporter.

## Goals

1. `tier1/observability/__init__.py` ≥ 80% covered.
2. `tier1/observability/metrics.py` ≥ 90% covered.
3. `tier1/observability/logging.py` stays ≥ 90% covered (already 100%).
4. One integration test verifies that `init_telemetry()` wires the
   tracer provider such that spans emitted via `get_tracer()` actually
   reach an exporter — without requiring a live Jaeger container.
5. All existing tests continue to pass; full suite ≥ 80% on touched files.

## Non-goals

- Production code changes (`__init__.py`, `metrics.py`, `logging.py`).
- Docker-compose changes (Jaeger and Prometheus already present).
- Live Jaeger container verification.
- Prometheus scrape verification.
- New instruments or metric exports.
- Documentation updates.

## Architecture

Tests only. No production modules change. The existing three test
files (`test_observability_init.py`, `test_observability_logging.py`,
`test_observability_metrics.py`) grow with new test functions.

The integration test uses the OTel SDK's `InMemorySpanExporter`,
which is part of the existing `opentelemetry-sdk` dependency. After
calling `init_telemetry(app)`, the test re-installs a fresh
`TracerProvider` with an `InMemorySpanExporter` attached, gets a
tracer, starts a span, ends it, and asserts the exporter received
the span. This proves the wiring path is correct without needing a
live OTLP endpoint.

## Components touched

| File | Change |
|---|---|
| `tests/unit/test_observability_init.py` | 4 new tests covering `_init_otel` branches |
| `tests/unit/test_observability_metrics.py` | 2 new tests covering `set_default_provider` and arg-provider path |
| `tests/unit/test_observability_logging.py` | No change (already 100%) |

No source files modified.

## Data flow (integration test)

```
test_init_telemetry_produces_observable_spans
  │
  ├── create FastAPI app
  ├── call init_telemetry(app)  → installs TracerProvider + MeterProvider
  ├── re-install TracerProvider with InMemorySpanExporter
  ├── tracer = get_tracer("test.integration")
  ├── with tracer.start_as_current_span("test-span"):
  │     pass
  ├── exporter.get_finished_spans() → must contain "test-span"
  └── assert trace_id is non-zero
```

The re-install step is intentional: `init_telemetry()` already wired
a real `TracerProvider` pointing at Jaeger (unreachable in the test
environment). For the integration test we replace the global
provider with one whose exporter is in-memory, so the assertion is
deterministic.

## Error handling

- The integration test must clean up its global TracerProvider after
  itself (use a fixture or try/finally) so it does not leak state into
  the rest of the suite.
- If `init_telemetry()` raises (e.g. a future OTel SDK change), the
  test fails loudly — the suite cannot run without observability
  initializing cleanly.

## Testing

| Test | File | Verifies |
|---|---|---|
| `test_init_telemetry_configures_tracer_provider` | `test_observability_init.py` | `OTLPSpanExporter` constructed with Jaeger endpoint; `TracerProvider().add_span_processor(BatchSpanProcessor(...))` called |
| `test_init_telemetry_configures_meter_provider` | `test_observability_init.py` | `OTLPMetricExporter` + `PeriodicExportingMetricReader` constructed; `MeterProvider(metric_readers=[...])` built |
| `test_init_telemetry_calls_set_default_provider` | `test_observability_init.py` | `tier1.observability.metrics.set_default_provider(meter_provider)` invoked |
| `test_init_telemetry_configures_structlog` | `test_observability_init.py` | Existing — assert `add_trace_context` in processor list |
| `test_init_telemetry_produces_observable_spans` | `test_observability_init.py` | Integration: after `init_telemetry(app)`, replace provider with `InMemorySpanExporter`, start span, assert exporter received it |
| `test_set_default_provider` | `test_observability_metrics.py` | Set the module-level default; `get_meter(name)` uses it when no arg passed |
| `test_get_meter_uses_arg_provider` | `test_observability_metrics.py` | Pass a custom provider explicitly; verify it is preferred over the default |

Total: 7 new tests across 2 files.

## Implementation order

1. Add 4 tests to `tests/unit/test_observability_init.py`.
2. Add 2 tests to `tests/unit/test_observability_metrics.py`.
3. Run targeted tests; iterate on failures.
4. Run full suite (skip `test_health.py` for Postgres dependency) and
   confirm coverage report shows `tier1/observability/__init__.py` at
   ≥ 80% and `metrics.py` ≥ 90%.
5. Commit.

## Dependencies

None new. `opentelemetry-sdk` already provides `InMemorySpanExporter`
in `opentelemetry.sdk.trace.export.in_memory_span_exporter`.
