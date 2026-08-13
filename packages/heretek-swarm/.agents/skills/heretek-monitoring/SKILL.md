---
name: heretek-monitoring
description: >-
  Monitoring and observability for Heretek Swarm. Use when setting up logging,
  metrics, tracing, or health checks. Covers structured logging, Prometheus
  metrics, and distributed tracing.
---

# Heretek Swarm Monitoring

## Observability Stack

### Components
- **Logging**: Structured logs with structlog
- **Metrics**: Prometheus + Grafana
- **Tracing**: OpenTelemetry (infrastructure/otel/) + Opik (Phase 1.3)
- **Health Checks**: Custom health endpoints
- **Alerting**: Prometheus Alertmanager + Opik Guardrails
- **Token Compression**: headroom_compat (Phase 1.4)

### Data Flow
```
Application → Logs → Log Aggregator → Search/Analysis
            → Metrics → Prometheus → Grafana
            → Traces → Jaeger/Tempo + Opik → Analysis
            → LLM spans → opik_compat.timed() + @opik.track
```

## Opik Integration (Phase 1.3 + 1.3-followups)

The audit (§3.1) recommended opik as the LLM/agent observability
backend (preferred over langfuse). Phase 1.3 introduced the
`opik_compat` shim; subsequent follow-ups wired call-site
integrations.

```python
from heretek_swarm.observability.opik_compat import (
    OPIK_AVAILABLE,
    OPIK_ENABLED,
    timed,
    timed_decorator,
    alert,
    track_metric,
    log_span,
)

# OPIK_AVAILABLE / OPIK_ENABLED are the public flags callers
# should check before adding opik decorators manually.

# 1. As a context manager
with timed("cognee_writer.add", tags={"tier": "episodic"}):
    await writer.add(...)

# 2. As a decorator
@timed_decorator("cognee_writer.add")
async def add(...):
    ...

# 3. Metric increment
track_metric("agent_invocation", value=1.0, tags={"agent": "explorer"})

# 4. Alert
alert("rate_limit_exceeded", severity="warning", message="...", tags={...})
```

### @opik.track on LLM providers (Phase 1.3 follow-up #2)

All 5 LLM provider `complete()` methods in `llm/model_garage.py`
now have `@_opik_track_llm` (gated by `OPIK_ENABLED`). When opik
is enabled, calls are captured as 'llm' spans for the Opik Agent
Optimizer + Guardrails integration. The decorator is a no-op
stub when opik is not installed:

```python
# llm/model_garage.py
class OpenAIProvider(LLMProvider):
    @_opik_track_llm
    async def complete(self, request):
        # When OPIK_ENABLED, opik captures this as a 'llm' span
        ...
```

`OPIK_ENABLED` defaults to `1` (enabled) when the opik package
is importable. Set `OPIK_ENABLED=0` to bypass in dev/CI.

### Architecture (Phase 2.9)

The audit (§1.6) flagged two parallel tracing systems
(`observability/tracing.py` 474 LOC and
`infrastructure/otel/tracing.py` 1,080 LOC). Phase 2.9
consolidated them:
- `infrastructure/otel/tracing.py` is canonical (it has the
  `InstrumentedAsyncClient` that 4 LLM / embedding providers
  depend on).
- `observability/tracing.py` is now a 90-LOC re-export shim
  with a `.. deprecated::` note pointing to the new location.
- `infrastructure/otel/middleware.py` hosts the
  `TelemetryMiddleware` (moved out of `observability/tracing.py`).

```python
# New canonical imports
from heretek_swarm.infrastructure.otel.tracing import (
    TracingConfig, init_tracing, InstrumentedAsyncClient
)
from heretek_swarm.infrastructure.otel.middleware import (
    TelemetryMiddleware, setup_telemetry_middleware
)

# Legacy re-exports (still work)
from heretek_swarm.observability.tracing import (
    initialize_tracing, setup_telemetry_middleware  # → same class
)
```

## headroom_compat (Phase 1.4)

Token compression for LLM prompt paths. Optional Rust+PyO3
binding; when unavailable, the shim returns the input unchanged
with `savings_ratio=0.0` and `strategy="passthrough"`.

```python
from heretek_swarm.llm.headroom_compat import (
    HEADROOM_AVAILABLE,
    HEADROOM_ENABLED,
    wrap,
    unwrap,
)

# 1. Wrap messages before the LLM call
compression = wrap(messages)
if isinstance(compression.data, list):
    messages = compression.data

# 2. Unwrap the response (preserves original text)
result = unwrap(completion)
```

`HEADROOM_ENABLED` defaults to `1`. Set `HEADROOM_ENABLED=0` to
bypass in dev/CI. The 5 LLM provider `complete()` methods in
`llm/model_garage.py` already wire `headroom.wrap()` + `opik.timed()`
around the LLM call (Phase 1.4 + 1.4 follow-up).

## Structured Logging

### Setup
```python
import structlog
from datetime import datetime

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger(__name__)
```

### Log Events
```python
# Application events
logger.info(
    "agent_started",
    agent_name="explorer",
    agent_id="agent_123",
    startup_time=1.5
)

# Business events
logger.info(
    "memory_created",
    memory_id="mem_456",
    agent="explorer",
    importance=0.8,
    tags=["observation", "learning"]
)

# Security events
logger.warning(
    "authentication_failed",
    api_key_prefix="sk-...",
    ip_address="192.168.1.100",
    reason="invalid_key"
)

# Error events
logger.error(
    "agent_message_failed",
    sender="explorer",
    recipient="coordinator",
    error=str(e),
    traceback=traceback.format_exc()
)
```

### Log Levels
```python
# DEBUG - Detailed information for debugging
logger.debug("processing_message", message_id=msg.id)

# INFO - General information
logger.info("agent_started", agent_name="explorer")

# WARNING - Unexpected situation
logger.warning("slow_query", duration=2.5, query="SELECT * FROM agents")

# ERROR - Failure that needs attention
logger.error("agent_failed", agent="explorer", error=str(e))

# CRITICAL - System cannot continue
logger.critical("database_connection_failed", error=str(e))
```

## Metrics

### Prometheus Setup
```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Start metrics server
start_http_server(8001)

# Define metrics
REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'api_request_latency_seconds',
    'Request latency',
    ['method', 'endpoint']
)

ACTIVE_AGENTS = Gauge(
    'active_agents',
    'Number of active agents'
)
```

### Instrumenting Endpoints
```python
from fastapi import Request
import time

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response
```

### Business Metrics
```python
# Agent metrics
AGENT_MESSAGES_SENT = Counter(
    'agent_messages_sent_total',
    'Total agent messages sent',
    ['sender', 'recipient', 'type']
)

AGENT_MESSAGES_RECEIVED = Counter(
    'agent_messages_received_total',
    'Total agent messages received',
    ['recipient', 'type']
)

# Memory metrics
MEMORY_OPERATIONS = Counter(
    'memory_operations_total',
    'Total memory operations',
    ['operation', 'agent']
)

MEMORY_SIZE = Gauge(
    'memory_size_bytes',
    'Memory storage size',
    ['type']
)

# Consensus metrics
CONSENSUS_DECISIONS = Counter(
    'consensus_decisions_total',
    'Total consensus decisions',
    ['outcome']
)

CONSENSUS_LATENCY = Histogram(
    'consensus_latency_seconds',
    'Consensus decision latency'
)
```

## Health Checks

### Basic Health Check
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### Detailed Health Check
```python
@router.get("/health/detailed")
async def detailed_health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "nats": await check_nats(),
        "qdrant": await check_qdrant(),
        "memory_usage": await check_memory_usage()
    }

    healthy = all(checks.values())

    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }

async def check_database():
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False

async def check_redis():
    try:
        await redis.ping()
        return True
    except Exception:
        return False

async def check_nats():
    try:
        return nats.is_connected
    except Exception:
        return False

async def check_qdrant():
    try:
        qdrant.get_collections()
        return True
    except Exception:
        return False
```

### Liveness Probe
```python
@router.get("/health/live")
async def liveness_probe():
    return {"status": "alive"}
```

### Readiness Probe
```python
@router.get("/health/ready")
async def readiness_probe():
    # Check if service is ready to accept traffic
    all_ready = all([
        await check_database(),
        await check_redis(),
        await check_nats()
    ])

    return {
        "status": "ready" if all_ready else "not_ready"
    }
```

## Distributed Tracing

### OpenTelemetry Setup
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Configure tracer
provider = TracerProvider()
processor = BatchSpanExporter(OTLPSpanExporter(endpoint="http://jaeger:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
```

### Instrumenting Code
```python
async def process_message(message):
    with tracer.start_as_current_span("process_message") as span:
        span.set_attribute("message.id", message.id)
        span.set_attribute("message.sender", message.sender)

        # Process message
        result = await handle_message(message)

        span.set_attribute("result.status", "success")
        return result
```

### Custom Spans
```python
async def database_operation():
    with tracer.start_as_current_span("database_query") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.statement", "SELECT * FROM agents")

        # Execute query
        result = await db.fetch(query)

        span.set_attribute("db.rows", len(result))
        return result
```

## Alerting

### Prometheus Alerts
```yaml
# prometheus/alerts.yml
groups:
  - name: heretek
    rules:
      - alert: HighErrorRate
        expr: rate(api_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(api_request_latency_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"

      - alert: AgentDown
        expr: up{job="heretek-swarm"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Agent is down"
```

### Alertmanager Configuration
```yaml
# alertmanager.yml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@heretek.com'
  smtp_auth_username: 'alerts@heretek.com'
  smtp_auth_password: 'password'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    email_configs:
      - to: 'team@heretek.com'
        send_resolved: true
```

## Dashboards

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Heretek Swarm",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(api_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(api_requests_total{status=~\"5..\"}[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      }
    ]
  }
}
```

### Key Metrics
- Request rate and latency
- Error rate by endpoint
- Active agents
- Memory operations
- Consensus decisions
- Database query performance
- Cache hit rates

## Log Aggregation

### ELK Stack
```yaml
# docker-compose.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    environment:
      - discovery.type=single-node

  logstash:
    image: docker.elastic.co/logstash/logstash:8.10.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    ports:
      - "5601:5601"
```

### Log Pipeline
```python
# Structured logs → Logstash → Elasticsearch → Kibana
logger.info(
    "agent_event",
    agent="explorer",
    event="message_sent",
    recipient="coordinator"
)
```

## Debugging with Monitoring

### Correlation IDs
```python
import uuid
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')

def generate_correlation_id():
    return str(uuid.uuid4())

def set_correlation_id(cid: str):
    correlation_id.set(cid)

def get_correlation_id():
    return correlation_id.get()

# Use in requests
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID", generate_correlation_id())
    set_correlation_id(cid)

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid

    return response
```

### Request Tracing
```python
@app.middleware("http")
async def trace_requests(request: Request, call_next):
    start_time = time.time()
    cid = get_correlation_id()

    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        correlation_id=cid
    )

    response = await call_next(request)

    duration = time.time() - start_time

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration=duration,
        correlation_id=cid
    )

    return response
```

## Performance Monitoring

### Database Monitoring
```python
async def monitor_db_queries():
    with tracer.start_as_current_span("db_query") as span:
        start_time = time.time()

        result = await db.fetch(query)

        duration = time.time() - start_time

        DB_QUERY_DURATION.labels(
            query_type="select",
            table="agents"
        ).observe(duration)

        if duration > 1.0:
            logger.warning(
                "slow_query",
                query=query,
                duration=duration
            )

        return result
```

### Cache Monitoring
```python
async def monitor_cache():
    cache_hits = 0
    cache_misses = 0

    # Monitor cache operations
    for _ in range(1000):
        result = await cache.get("key")
        if result:
            cache_hits += 1
        else:
            cache_misses += 1

    CACHE_HIT_RATE.set(cache_hits / (cache_hits + cache_misses))
```

## Gotchas

1. **Don't log secrets** - Sanitize sensitive data
2. **Use correlation IDs** - Trace requests across services
3. **Monitor key metrics** - Know what's important
4. **Set up alerts** - Don't wait for users to report issues
5. **Keep dashboards simple** - Focus on actionable metrics
6. **Test alerting** - Ensure alerts work when needed
7. **Review logs regularly** - Catch issues early
8. **Use structured logging** - Easy to search and analyze
9. **Monitor performance** - Catch slowdowns early
10. **Document monitoring** - Help team understand dashboards

## Best Practices

1. Implement comprehensive logging
2. Use structured log formats
3. Set up metrics collection
4. Create meaningful dashboards
5. Configure appropriate alerts
6. Use correlation IDs
7. Monitor performance metrics
8. Review logs regularly
9. Document monitoring setup
10. Test alerting regularly
