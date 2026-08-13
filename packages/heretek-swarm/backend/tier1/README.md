# Tier 1 Core Triad

Multi-turn deliberation MVP. The Steward orchestrates Alpha (analysis),
Beta (validation), and Charlie (challenge) through a LangGraph Tribunal.
Live reasoning streams to a React dashboard.

## Quick start

    cd backend/tier1
    docker compose -f docker/docker-compose.yml up -d
    pip install -e ".[dev]"
    export TIER1_MINIMAX_API_KEY=...
    python -m tier1 serve

    # In another terminal:
    cd swarm-dashboard
    npm install
    npm run dev

Open http://localhost:5173 (Vite dev) or http://localhost:8000/dashboard (production-style build).

## Architecture

See `docs/superpowers/specs/2026-06-24-tier-1-core-triad-rebuild-design.md`.

## Tests

    cd backend/tier1
    pytest tests/ -v

## Notes

- This module is greenfield — separate from the legacy 180k LoC `heretek_swarm/` package.
- We preserve the doctrinal infrastructure (NATS/Postgres/Redis/Qdrant/cognee/mem0).
- We do NOT carry over the other 19 agents, consciousness layers, or wizard code.

## Limitations

**`_stream_from_provider` in `tier1/llm/garage.py` is currently a stub.**
The method raises `NotImplementedError("provider {provider!r} not yet wired — see Task 3.5")`
for every provider in the chain (`minimax`, `anthropic`, `openai`, `local`).

Without a real provider wired (follow-up Task 3.5+), **no deliberation
can complete against a live LLM.** Calling `POST /api/deliberations`
will start the LangGraph run, the Steward will finalize on a real LLM
absence, and the deliberation will be marked `failed` in `/api/deliberations`.

The infrastructure layer is fully wired:
- `/health` probes postgres, redis, nats, qdrant (hard-required) plus
  cognee and mem0 (advisory — see `tier1/api/routes/health.py`).
- NATS event publishing, Postgres state persistence, Redis hot cache,
  and Qdrant collection wiring are all in place.
- The Steward, consensus, and Tribunal graph are deterministic and
  testable without an LLM.

Wire a real provider (Task 3.5+) before relying on end-to-end
deliberation.
