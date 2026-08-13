# Tier 1 Observability — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)

## Context

Tier 1 Core Triad is on `main` with real LLM wiring and integration tests. Today, observability is limited to structlog output with no trace correlation, no metrics endpoint, and no way to visualize deliberation performance. This spec adds full observability via OpenTelemetry: metrics, structured logs with trace context, and distributed traces through the Tribunal state machine.

## Goals

1. Prometheus-compatible `/metrics` endpoint with deliberation latency, consensus outcome, provider call duration, and circuit state metrics.
2. Structured log lines carry `trace_id` and `span_id` for correlation.
3. Distributed traces via Jaeger: full timeline from HTTP request → Tribunal → agent calls → consensus.
4. Degrades gracefully when OTel or Jaeger is unavailable.

## Non-goals

- SLO dashboards (deferred — metrics exist, dashboards are a separate concern).
- Alerting rules (deferred — needs production traffic patterns first).
- Multi-service tracing (Tier 2+ agents not yet built).

## Architecture

One new module `tier1/observability/` owns all OTel setup. Three exports: `init_telemetry(app)`, `get_tracer(name)`, `get_meter(name)`. Everything else is instrumentation calls inside existing code.

```
tier1/observability/
├── __init__.py    # init_telemetry(), get_tracer(), get_meter()
├── metrics.py     # Meter instruments: histograms, counters, gauges
└── logging.py     # structlog processor that injects trace_id + span_id
```

Exported interfaces:
- `init_telemetry(app: FastAPI)` — configures TracerProvider (OTLP → Jaeger), MeterProvider (OTLP → Jaeger + Prometheus exporter), FastAPI instrumentor, structlog processor. Called once.
- `get_tracer(name: str)` → `opentelemetry.trace.Tracer`
- `get_meter(name: str)` → `opentelemetry.metrics.Meter`

Jaeger runs as a docker-compose sidecar on `:4318` (OTLP HTTP). Prometheus scrapes the OTel SDK's built-in Prometheus reader at `:9464`.

## Components

### A. `tier1/observability/__init__.py`

`init_telemetry(app)`:
1. Configures `TracerProvider` with `OTLPSpanExporter(endpoint="http://jaeger:4318/v1/traces")`
2. Configures `MeterProvider` with `OTLPMetricExporter(endpoint="http://jaeger:4318/v1/metrics")` AND a `PrometheusMetricReader` bound to port `9464`
3. Installs `FastAPIInstrumentor` (auto-instruments request latency, status codes, in-flight)
4. Injects a structlog processor `add_trace_context` that adds `trace_id` and `span_id` to every log line
5. Sets `TRACER` and `METER` module-level singletons

### B. `tier1/observability/metrics.py`

Instruments (registered lazily, singleton pattern via `_get_or_create`):

| Instrument | Type | Where instrumented | What it measures |
|---|---|---|---|
| `deliberation_latency` | Histogram | `Tribunal.run()` | Seconds from start to verdict |
| `deliberation_rounds` | Histogram | `Tribunal.run()` | Number of rounds before verdict |
| `consensus_outcome` | Counter | `consensus.py` | Labels: `reached`, `timeout`, `no_consensus` |
| `provider_call_duration` | Histogram | `garage.py` | Seconds per provider call |
| `provider_circuit_state` | UpDownCounter | `garage.py` | +1 when circuit opens, −1 when closes |
| `agent_token_count` | Counter | agent nodes (alpha/beta/charlie) | Tokens yielded per agent |

### C. `tier1/observability/logging.py`

One structlog processor:

```python
def add_trace_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

Registered in `init_telemetry()` via `structlog.configure(processors=[..., add_trace_context])`.

## Data flow

```
User → POST /api/deliberations
         │
         ▼
    FastAPIInstrumentor (auto)
    ┌─ span: HTTP POST /api/deliberations ──────────────────┐
    │  Creates DeliberationState, publishes to NATS          │
    │  Spawns asyncio task: Tribunal.run()                   │
    │  Returns NewDeliberationResponse                       │
    └───────────────────────────────────────────────────────┘
         │ (background task)
         ▼
    Tribunal.run() span
    │  round=1 ────────────────────────────────────────────┐
    │  ├─ Alpha span: provider_call_duration(minimax)      │
    │  │   └─ structlog: {trace_id, span_id}               │
    │  ├─ Beta span: provider_call_duration(minimax)       │
    │  └─ Charlie span: provider_call_duration(minimax)    │
    │  consensus_outcome += 1 (label: reached)             │
    └──────────────────────────────────────────────────────┘
    deliberation_latency.record(elapsed)
    deliberation_rounds.record(round_count)
         │
         ▼
    Jaeger ← OTLP spans (trace_id links everything)
    Prometheus ← OTel metrics (histograms, counters)
    structlog → stdout (JSON, includes trace_id per line)
```

Every log line carries `trace_id` + `span_id`. Click a trace in Jaeger → full deliberation timeline. Correlate to logs via trace_id.

## Error handling

OTel SDK is designed to never fail the host app. If Jaeger is unreachable, spans are dropped silently. If Prometheus can't scrape, metrics are absent. No exception handling needed in application code.

If `opentelemetry-sdk` is not installed (dep removed), `opentelemetry-api` provides no-op Tracer/Meter automatically — `get_tracer()` and `get_meter()` return no-ops. Only the SDK + exporters are optional.

## Testing

| Test | What it verifies | Approach |
|---|---|---|
| `test_logging_processor.py` | `add_trace_context` injects `trace_id`/`span_id` | Mock `trace.get_current_span()`, assert keys present in event dict |
| `test_metrics_instruments.py` | Instruments register and update correctly | Use OTel `InMemoryMetricReader`, call instruments, assert recorded values |
| `test_init_telemetry.py` | `init_telemetry()` wires providers + FastAPI instrumentor | Mock OTel providers, verify `FastAPIInstrumentor.instrument_app` called |

All in-memory. No live Jaeger or Prometheus needed for tests.

## Dependencies

New in `pyproject.toml [project.dependencies]`:
```
opentelemetry-api>=1.24
opentelemetry-sdk>=1.24
opentelemetry-exporter-otlp>=1.24
opentelemetry-instrumentation-fastapi>=0.45
```

Docker-compose additions (for local dev):
```yaml
jaeger:
  image: jaegertracing/all-in-one:1.57
  ports: ["4318:4318", "16686:16686"]

prometheus:
  image: prom/prometheus:v2.51.0
  ports: ["9090:9090"]
  volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]
```

Prometheus config:
```yaml
scrape_configs:
  - job_name: tier1
    static_configs:
      - targets: ["host.docker.internal:9464"]
```

## Implementation order

1. Add OTel deps to `pyproject.toml`
2. Create `tier1/observability/__init__.py` with `init_telemetry()`, `get_tracer()`, `get_meter()`
3. Create `tier1/observability/logging.py` with `add_trace_context` processor
4. Create `tier1/observability/metrics.py` with all 6 instruments
5. Wire `init_telemetry(app)` into `create_app()`
6. Instrument `Tribunal.run()` with span + latency/round metrics
7. Instrument `garage.py` provider calls with span + duration metric
8. Instrument `consensus.py` with outcome counter
9. Instrument agent nodes with token count
10. Add Jaeger + Prometheus to docker-compose
11. Write unit tests (logging processor, metrics, init)
12. Run full suite, verify coverage ≥ 80%
