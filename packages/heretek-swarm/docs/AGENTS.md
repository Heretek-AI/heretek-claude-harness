# Heretek Swarm — AI Agent Instructions

## Project Overview

Heretek Swarm is a distributed multi-agent swarm intelligence system with 23 specialized agents across 6 tiers, built on Python 3.11+ with FastAPI, NATS message broker, PostgreSQL, Redis, and Qdrant. The frontend dashboard is React/TypeScript.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Swarms framework
- **Frontend**: TypeScript, React, Vite (`swarm-dashboard/`)
- **Messaging**: NATS with mTLS
- **Databases**: PostgreSQL, Redis, Qdrant (vector)
- **Infrastructure**: Docker Compose
- **Testing**: pytest (backend), Playwright (frontend)

## Build & Test Commands

```bash
# Install backend
pip install -e backend/

# Run backend tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth_endpoints.py -v

# Run frontend tests
cd swarm-dashboard && npm test

# Run Playwright E2E tests
cd swarm-dashboard && npx playwright test

# Type check
mypy backend/heretek_swarm/

# Lint (Python)
ruff check backend/

# Lint (TypeScript)
cd swarm-dashboard && npm run lint
```

## Architecture

### Agent Tiers
- **Tier 1 — Core Triad**: Steward (governance), Alpha (analysis), Beta (validation), Charlie (challenge)
- **Tier 2 — Support**: Historian, Metis, Empath, Perceiver, Echo
- **Tier 3 — Exploration**: Scout, Pathfinder, Surveyor
- **Tier 4 — Safety & Security**: Sentinel, Guardian, Warden
- **Tier 5 — Coordination**: Orchestrator, Arbiter, Mediator
- **Tier 6 — Enhancement**: Innovator, Optimizer, Refiner

### Key Patterns
- **Mixin-based extension**: AgentActor uses mixins for message handling, state management
- **Three-tier fallback**: Event mesh → Direct registry → Queue
- **HeavySwarm workflow**: Research → Analysis → Alternatives → Verification → Decision
- **Zero-Trust input validation**: All agent inputs validated

### Module Map
- `backend/heretek_swarm/actors/` — Agent implementations (nested subpackage)
- `backend/heretek_swarm/orchestration/` — Workflow orchestration
- `backend/heretek_swarm/memory/` — Memory and knowledge management
- `backend/heretek_swarm/api/` — FastAPI REST endpoints
- `backend/heretek_swarm/consensus/` — Consensus algorithms
- `backend/heretek_swarm/collective_learning/` — Collective intelligence

## Code Conventions

### Python
- Type hints required on all public functions
- Use `async/await` for I/O operations
- Follow PEP 8 with ruff enforcement
- Docstrings in Google style

### TypeScript
- Use functional components with hooks
- Prefer `useCallback` for memoized callbacks
- API calls through `fetch` with proper error handling
- Environment variables prefixed with `VITE_`

## Security

- Never commit secrets — use `secrets/encrypted.env` with SOPS
- All NATS communication uses mTLS
- API keys passed via `Authorization: Bearer` header
- Input validation on all agent message handlers
- See `SECURITY.md` for vulnerability reporting
