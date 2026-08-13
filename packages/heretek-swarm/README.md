# Heretek Swarm — The Collective

**Version:** 0.2.0
**Framework:** Python 3.11+
**Last Updated:** 2026-06-10 (M001 Complete — 6 containers, 7 logical services including embedded mem0)

---

## Installation

### Python Package (pip)

```bash
# Editable install (development)
pip install -e backend/

# Or install from PyPI (when published)
pip install heretek-swarm
```

This provides the `heretek-swarm` CLI command (see [Command Reference](#command-reference) below).

### Docker Compose

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY (and other values as needed)
docker compose up
```

Starts all 6 containers (7 logical services including embedded mem0) with health checks: PostgreSQL, Redis, Qdrant, NATS, API server (with embedded mem0), and React dashboard. No profile flags needed — everything starts by default. The `docker-compose.yml` is at repo root; run `docker compose up` from the repository root directory.

---

## Quick Start

### Local (no infrastructure)

Run the swarm with in-memory state — no Docker, Postgres, Redis, Qdrant, or NATS required:

```bash
pip install -e backend/
heretek-swarm run --no-infra --prompt "Hello"
```

The swarm starts all 23 agents in-memory and deliberates your prompt through the Alpha/Beta/Charlie triad, then exits.

### Full Stack

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
docker compose up
```

The API server starts on `http://localhost:8000` and the dashboard on `http://localhost:3000`. Use `heretek-swarm status` to verify all services are healthy.

---

## Command Reference

All commands are accessed via the `heretek-swarm` CLI. Run `heretek-swarm --help` for grouped help output.

### Core Operations

| Command | Description |
|---------|-------------|
| `heretek-swarm run` | Start the autonomous runtime (all 23 agents) as a standalone process |
| `heretek-swarm serve` | Start the FastAPI API server with auto-reload |
| `heretek-swarm deploy` | Print infrastructure setup instructions for Docker Compose |
| `heretek-swarm wizard` | Open the browser to the React dashboard setup wizard |

### Configuration

| Command | Description |
|---------|-------------|
| `heretek-swarm config` | Manage LLM provider configuration (wizard, list, remove, set-default, validate) |
| `heretek-swarm init` | Bootstrap `~/.heretek-swarm/.env` from `.env.example` |

### Monitoring

| Command | Description |
|---------|-------------|
| `heretek-swarm status` | Check infrastructure health; use `--json` for machine-readable output |
| `heretek-swarm stop` | Stop a running background daemon |

### Common Options

```bash
# Run in background (daemon mode)
heretek-swarm run --detach

# Skip all external infrastructure
heretek-swarm run --no-infra

# Route prompt to a specific agent
heretek-swarm run --no-infra --prompt "Analyze X" --target-agent alpha

# Serve on a custom host/port
heretek-swarm serve --host 127.0.0.1 --port 9000

# Get JSON status output
heretek-swarm status --json
```

---

## Package Structure

```
heretek-swarm/                          # Repository root
├── docker-compose.yml                  # All 6 containers (7 logical services incl. embedded mem0)
├── .env.example                        # Environment template with all vars
├── PRIME_DIRECTIVE.md                  # 23-agent vision & architecture
├── CLAUDE.md                           # AI assistant guidance
├── README.md                           # This file
├── docs/                               # Architecture & API documentation
│   ├── ARCHITECTURE.md                 # System architecture (51K, ~900 lines)
│   ├── API_ENDPOINTS.md                # API reference
│   ├── DEPLOYMENT.md                   # Deployment guide
│   ├── AGENTS.md                       # Complete agent reference
│   ├── AGENT_ARCHITECTURE.md           # Agent design patterns
│   ├── AGENT_REFERENCE.md              # Agent API reference
│   ├── CODEBASE_AUDIT.md               # Code quality audit results
│   ├── CORE_ACTORS.md                  # Core actor classes
│   ├── PROTOCOL_SPEC.md                # A2A & consensus protocol spec
│   ├── PROMETHEUS_METRICS.md           # Metrics reference
│   ├── MEMORY_SYSTEM.md                # Memory architecture
│   ├── MONITORING.md                   # Monitoring & alerting
│   └── INDEX.md                        # Documentation index
├── backend/                            # Python backend (412 .py files, ~184K LOC)
│   ├── pyproject.toml                  # Package metadata & CLI entry point
│   ├── Dockerfile                      # API service container
│   └── heretek_swarm/                  # Core library (55 subpackages)
│       ├── actors/                     # 23 agent implementations + 10 mixins
│       ├── api/                        # FastAPI app + 27 routers (~175+ endpoints)
│       ├── cli/                        # CLI commands & config loader
│       ├── config/                     # Database-backed configuration service
│       ├── consciousness/              # IIT phi, FEP free energy, GWT metrics
│       ├── consensus/                  # Deliberation, MAKER protocol, tribunal
│       ├── collective/                 # Swarm intelligence, emergence detection
│       ├── gateway/                    # NATS JetStream event mesh, A2A protocol
│       ├── memory/                     # Dual-tier memory (PostgreSQL + Qdrant)
│       ├── runtime/                    # AutonomousSwarm main loop & daemon
│       ├── security/                   # Zero-trust validation, guardrails, DDoS
│       ├── infrastructure/             # Health checks, NATS client, OpenTelemetry
│       ├── orchestration/              # HeavySwarm workflow engine
│       ├── llm/                        # LLM provider abstraction (7 providers)
│       ├── embeddings/                 # Embedding provider implementations
│       ├── rag/                        # RAG pipeline (ingestion, query, graph)
│       ├── mcp/                        # MCP server & client, tool registration
│       ├── tools/                      # Agent tool system
│       ├── observability/              # Prometheus metrics, alerting, tracing
│       ├── plugins/                    # Plugin system (loading, lifecycle)
│       ├── governance/                 # Agent identity, policy, compliance
│       ├── state/                      # PostgreSQL state persistence
│       └── workflow/                   # Workflow engine, state machines
├── swarm-dashboard/                    # React frontend (Vite + TypeScript)
│   ├── App.tsx                         # Root with 11-view state machine
│   ├── api/                            # 10 API client modules (Axios)
│   ├── components/                     # 93 React components (12 domains)
│   ├── hooks/                          # 18 custom React hooks
│   ├── stores/                         # 4 Zustand stores + debug middleware
│   └── types/                          # Shared TypeScript types
└── migrations/                         # Alembic/SQLAlchemy migrations
```

`swarm-dashboard/` at repo root contains the React frontend (fully decoupled from backend).

---

## Infrastructure

All services are defined in `docker-compose.yml` (at repo root) and start automatically with `docker compose up`.

| Service | Default Port | Purpose |
|---------|--------------|---------|
| PostgreSQL | 5432 | State persistence, mem0 episodic memory |
| Redis | 6379 | Working memory, caching |
| Qdrant | 6333 | Semantic/vector memory storage |
| NATS | 4222 | Event mesh (A2A agent communication) |
| API Server | 8000 | FastAPI backend with 23 spawned agents |
| Dashboard | 3000 | React frontend (Vite + Tailwind CSS) |
| **mem0** | *(embedded)* | Memory SDK embedded in API container via `backend/heretek_swarm/memory/persistent.py` |

All services include health checks and restart policies. Docker Compose coordinates startup order via `depends_on` with `condition: service_healthy`.

### Docker Volume Persistence

All 4 named volumes use Docker's `local` driver. A physical restart resilience test (`docker compose down && up`) executed 2026-05-14 confirmed all data survives restart with all 6 containers returning healthy and API health returning HTTP 200.

| Volume | Compose Name | Host Path (WSL2) | Container Path | Service | Survives Restart |
|--------|-------------|-------------------|----------------|---------|:----------------:|
| `postgres_data` | `postgres_data` | `/var/lib/docker/volumes/heretek-swarm_postgres_data/_data` | `/var/lib/postgresql/data` | postgres | ✅ |
| `redis_data` | `redis_data` | `/var/lib/docker/volumes/heretek-swarm_redis_data/_data` | `/data` | redis | ✅ |
| `qdrant_data` | `qdrant_data` | `/var/lib/docker/volumes/heretek-swarm_qdrant_data/_data` | `/qdrant/storage` | qdrant | ✅ |
| `nats_data` | `nats_data` | `/var/lib/docker/volumes/heretek-swarm_nats_data/_data` | `/data` | nats | ✅ |

**Restart test results (2026-05-14):** All 6 containers stopped and restarted. All 4 volumes preserved with identical host paths. Post-restart API health: HTTP 200, all services healthy. Total test duration: 77 seconds.

---

## The 23 Agents

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE COLLECTIVE (23 AGENT TYPES)              │
├─────────────────────────────────────────────────────────────────┤
│ TIER 1: CORE TRIAD (4)     │ TIER 4: SAFETY (3)               │
│ ├── Steward (Orchestrator) │ ├── Sentinel (Safety Guardian)   │
│ ├── Alpha (Deep Analysis)  │ ├── Sentinel-Prime (Security)    │
│ ├── Beta (Validation)      │ └── Arbiter (Conflict Resolution)│
│ └── Charlie (Challenge)    │                                   │
│                            │ TIER 5: COORDINATION (4)         │
│ TIER 2: SUPPORT (5)        │ ├── Coordinator (Multi-Agent)    │
│ ├── Historian (Memory)     │ ├── Nexus (External Integration) │
│ ├── Metis (Strategy)       │ ├── Catalyst (Change Mgmt)       │
│ ├── Empath (Emotional IQ)  │ └── Chronos (Scheduling)         │
│ ├── Perceiver (Sensory)    │                                   │
│ └── Echo (Communication)   │ TIER 6: ENHANCEMENT (3)          │
│                            │ ├── Prism (Multi-Perspective)    │
│ TIER 3: EXPLORATION (4)    │ ├── Habit-Forge (Optimization)   │
│ ├── Explorer (Discovery)   │ └── Perceiver+ (Advanced)        │
│ ├── Examiner (QA)          │                                   │
│ ├── Dreamer (Creative)     │                                   │
│ └── Coder (Implementation) │                                   │
└─────────────────────────────────────────────────────────────────┘
```

All 23 agents inherit from `AgentActor` (`actors/base/core.py:120`) and compose capabilities via 10 reusable mixins (`actors/mixins/`). The Triad agents (Steward, Alpha, Beta, Charlie) share a common `TriadAgent` base with `DeliberationMixin`, `PatternMixin`, `MemoryMixin`, and `LearningMixin`.

---

## Configuration

Copy `.env.example` to `.env` and fill in your values. The key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `QDRANT_URL` | Yes | Qdrant host URL |
| `HERETEK_NATS_URL` | Yes | NATS connection URL |
| `OPENAI_API_KEY` | Yes | OpenAI-compatible API key |
| `OPENAI_BASE_URL` | Yes | OpenAI-compatible API base URL |
| `LLM_MODEL` | Yes | LLM model name (default: `MiniMax-M2.7`) |
| `EMBEDDING_PROVIDER` | Yes | Embedding provider type (default: `openai_compatible`) |
| `EMBEDDING_DIMENSIONS` | Yes | Embedding vector dimensions (default: `768`) |
| `HERETEK_API_KEY` | Yes | API authentication key |
| `RATE_LIMIT_ENABLED` | No | DDoS protection toggle (default: `true`) |
| `CORS_ORIGINS` | No | CORS allow origins (default: `*`) |

Docker Compose defaults are pre-configured in `.env.example` — for local development outside Docker, update the hostnames from service names (`postgres`, `redis`, `qdrant`, `nats`) to `localhost`.

### LLM Providers (7 Supported)

| Provider | Base URL | API Key Required |
|----------|----------|:----------------:|
| `openai` | `https://api.openai.com/v1` | Yes |
| `openai_compatible` | Custom (vLLM, LocalAI, etc.) | Optional |
| `ollama` | `http://localhost:11434` | No |
| `llamacpp` | `http://localhost:8080` | No |
| `zai` (Zhipu GLM) | `https://open.bigmodel.cn/api/paas/v4` | Yes |
| `minimax` | `https://api.minimax.chat/v1` | Yes (needs group_id) |
| `lemonade` | `http://localhost:5000` | No |

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture (~900 lines, 10 sections) |
| [`docs/API_ENDPOINTS.md`](docs/API_ENDPOINTS.md) | API endpoint reference |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Deployment guide |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Complete agent reference |
| [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md) | Agent design patterns & mixin system |
| [`docs/AGENT_REFERENCE.md`](docs/AGENT_REFERENCE.md) | Agent API reference |
| [`docs/PROTOCOL_SPEC.md`](docs/PROTOCOL_SPEC.md) | A2A & consensus protocol specification |
| [`docs/CODEBASE_AUDIT.md`](docs/CODEBASE_AUDIT.md) | Code quality audit findings |
| [`docs/PROMETHEUS_METRICS.md`](docs/PROMETHEUS_METRICS.md) | Prometheus metrics reference |
| [`docs/MEMORY_SYSTEM.md`](docs/MEMORY_SYSTEM.md) | Memory architecture details |
| [`docs/MONITORING.md`](docs/MONITORING.md) | Monitoring & alerting setup |
| [`PRIME_DIRECTIVE.md`](PRIME_DIRECTIVE.md) | Project vision and philosophy |

---

## Technical Debt Overview

A comprehensive audit scanned **612 files** across 4 scan roots (backend, frontend, tests, infrastructure). After deduplication of 460 raw findings, **50 canonical findings** were produced: 22 critical, 15 moderate, 13 minor across 6 domains.

### Severity Distribution

| Severity | Count | Domains |
|----------|:-----:|---------|
| **Critical** | 22 | security (14), code_quality (4), testing (2), security (2) |
| **Moderate** | 15 | architecture (5), code_quality (4), configuration (3), security (2), testing (1) |
| **Minor** | 13 | observability (8), code_quality (3), configuration (2) |
| **Total** | **50** | 6 domains covered |

### Domain Breakdown

| Domain | Findings | Top Severity |
|--------|:--------:|:------------:|
| Security | 17 | Critical |
| Code Quality | 11 | Critical |
| Observability | 8 | Minor |
| Architecture | 5 | Moderate |
| Configuration | 5 | Moderate |
| Testing | 4 | Critical |
| Performance | 0 | — (coverage gap — needs dedicated profiler) |

All 50 findings carry file:line references. The full findings catalog is at `.gsd/audit/findings.json`. See [`docs/CODEBASE_AUDIT.md`](docs/CODEBASE_AUDIT.md) for the human-readable audit report.

### Key Themes

- **Security hardening needed:** 17 security findings including hardcoded credentials, eval/exec references, and missing auth middleware on 4 endpoints
- **Observability gaps:** 8 findings covering print() statements in production code, missing structured logging, and incomplete trace coverage
- **Architecture drift:** 5 findings identifying oversized modules (>1000 lines), deep nesting, and God-class patterns
- **Performance blind spot:** 0 performance findings — the audit pipeline did not include profiling; a dedicated performance scan is a known follow-up

---

## API Audit Summary

A three-phase pipeline enumerated **83 frontend API call sites** from 12 source files, live-tested all 83 against the running backend at `localhost:8000`, and cross-referenced against **345 backend routes** from 33 router files.

### Live Test Results

| Status | Count | Notes |
|--------|:-----:|-------|
| 2xx Success | 5 | Health, embedding/list, llm/list, provider-stats, mcp/tools |
| 401/403 Auth | 67 | Auth middleware active across all secured routes (expected without API key) |
| 404 Not Found | 7 | Orphan frontend calls with no matching backend route |
| 422 Validation | 3 | Provider endpoint validation failures with empty bodies |
| 500 Server Error | 2 | Wizard infrastructure GET/DELETE — genuine unhandled errors |
| **Total** | **83** | 0 unreachable endpoints |

### Key Findings (20 Total)

| Severity | Count | Examples |
|----------|:-----:|----------|
| **Critical** | 6 | 2 wizard infrastructure 500s, 4 auth bypass candidates (endpoints returning 200 despite `auth_required` declarations), orphan frontend routes returning 404 |
| **Moderate** | 14 | 250 backend-only routes (significant coverage gap), frontend `/api/autonomous/*` calls vs backend `/autonomous/*` prefix mismatch, missing `/api/metrics` and `/api/observability/llm-metrics` backend routes |

### Surface Coverage

- **83** frontend API calls across **13** domain categories (a2a, agents, config, consciousness, consensus, deliberation, health, historian, mcp, memory, observability, system, wizard)
- **345** backend routes registered (175+ with handler implementations)
- **250** backend-only routes (no corresponding frontend call site — significant dead-code assessment surface)
- **5** orphan frontend calls (no matching backend route)

Full audit artifact: `.gsd/audit/api-audit.json`. Inventory: `.gsd/audit/api-inventory.json`.

---

## Architecture Verification

The architecture was audited with:
- **23 actor classes** with exact file:line references and parent chains
- **10 mixins** with dependency analysis and fail-fast guard documentation
- **27 API routers** with 175+ endpoint handlers (router count lowered after the Phase 2A.3 opik cutover deleted 5 of 8 `api/observability` routers)
- **6 Docker Compose containers (7 logical services)** with health check topology
- **93 React components** across 12 feature domains
- **36+ file:line references** grounding every claim in real code

**Stub inventory:** 18 documented placeholders (10 STUB, 8 TODO) across frontend and test files. Backend scan: 0 stubs across 607+ `.py` files — the codebase is clean of placeholder patterns.

---

## The Prime Directive

> **Build a self-governing swarm of 23 specialized AI agents that operate independently 24/7, make collective decisions through consensus, adapt and learn from experience, and exhibit emergent collective intelligence.**

*The thought that never ends.*

---

**License:** Apache 2.0

*Last Updated: 2026-05-29 — Phase 1-2 Audit & Remediation Complete; Phase 2A.3 opik cutover (2026-06-04) — see `docs/ARCHITECTURE.md`*
