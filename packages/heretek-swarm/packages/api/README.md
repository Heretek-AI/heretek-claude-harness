# heretek-swarm-api

FastAPI HTTP surface for the Heretek Swarm.

Phase 4 of `PLAN.md` (Zero-Trust Architecture Audit, 2026-06-03)
carves this package out of the single `heretek-swarm` pip
package. Today, the corresponding code lives under
`backend/heretek_swarm/api/` and other request-handling layers
in the same repo.

## What lives here

- `api/` — FastAPI application entry point + 22+ routers
- `observability/` — `opik_compat` shim, alerting, db_timing,
  metrics, prometheus_metrics, timing
- `security/` (auth portion) — zero_trust middleware,
  adversarial detection, ddos_protection, guardrails,
  anomaly_detection, behavioral_baseline, threat_detection
- `mcp/`, `integrations/`, `plugins/`
- `rag/` (orchestration-specific bits)

## What does NOT live here

Everything in `heretek-swarm-core` — actors, consensus, memory,
gateway auth (TokenStore), runtime, security/immune, etc.
This package depends on `heretek-swarm-core` and never the
other way around.

## Dependencies

```
heretek-swarm-core,
fastapi, uvicorn, starlette, pydantic, httpx, redis, qdrant-client,
opentelemetry-api/sdk, prometheus-client, structlog, tenacity, slowapi
```

## Status

Stub. The actual split is a multi-PR effort; this directory
exists so the workspace structure is in place and the audit's
Phase 4 deliverable is structurally committed.
