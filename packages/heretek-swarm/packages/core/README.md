# heretek-swarm-core

Sovereign service library for the Heretek Swarm.

Phase 4 of `PLAN.md` (Zero-Trust Architecture Audit, 2026-06-03)
carves this package out of the single `heretek-swarm` pip
package. Today, the corresponding code lives under
`backend/heretek_swarm/` in the same repo. Activating the
split is a multi-PR effort; this directory is the destination.

## What lives here

- `actors/` — 23 agent implementations across 6 tiers, plus the
  `AgentActor` base class and 10 mixins
- `consensus/` — MAKER, EnhancedMAKER, SwarmDeliberation, and
  Deliberation engines, all behind the `ConsensusEngine` Protocol
  (Phase 3.1)
- `memory/` — `MemoryStore` Protocol + cognee / mem0 / null
  adapters
- `gateway/` — Bearer auth, `TokenStore`, A2A protocol
- `runtime/` — `main_loop`, `wiring`, autonomous runtime
- `security/` — immune, rate_limiter
- `llm/` — LLM router, `headroom_compat`, `hindsight_compat`
- `embeddings/`, `models/`, `schemas/`, `swarm_logging/`,
  `config/` (lib portion), `utils/`, `validation/`, `channels/`

## What does NOT live here

- `api/` — FastAPI application, all 22+ routers
- `mcp/`, `integrations/`, `plugins/` — request-handling layers
- `rag/` (orchestration-specific bits)
- `security/zero_trust.py` (auth is in core; the zero-trust
  middleware lives in the api package)

## Dependencies (this package does NOT depend on FastAPI)

```
pydantic, structlog, tenacity,
cognee, langgraph, opik, headroom-ai, slowapi, mem0ai,
nats-py, opentelemetry-api, PyJWT, httpx
```

## Status

Stub. The actual split is a multi-PR effort; this directory
exists so the workspace structure is in place and the audit's
Phase 4 deliverable is structurally committed.
