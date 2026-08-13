# Packages Extraction — Design Spec

**Date:** 2026-06-26
**Status:** Approved (pending implementation)

## Context

The heretek-swarm monolith at `backend/heretek_swarm/` contains ~465 Python files and ~180K LOC in a single package. Two package stubs (`packages/core/` and `packages/api/`) exist with re-export bridges but no source files have moved. The workspace is committed but inactive. This extraction splits the monolith into two focused packages with clean dependency boundaries.

## Goals

1. Move all sub-packages from `backend/heretek_swarm/` into `packages/core/` and `packages/api/`
2. Update all imports across the codebase to use new namespaces (`heretek_swarm_core.*`, `heretek_swarm_api.*`)
3. Activate the uv workspace
4. Remove re-export bridge `__init__.py` files
5. All existing tests pass after extraction

## Non-goals

- Rewriting or refactoring any code (just moving files + updating imports)
- Changing the package API surface
- Adding new features
- Modifying the tier1 backend (it stays as-is)

## Architecture

```
heretek-swarm/
├── packages/
│   ├── core/
│   │   ├── src/heretek_swarm_core/
│   │   │   ├── actors/          # 23 agents, base class, 10 mixins
│   │   │   ├── consensus/       # MAKER, deliberation, swarm intelligence
│   │   │   ├── memory/          # MemoryStore Protocol + adapters
│   │   │   ├── gateway/         # Auth, TokenStore, A2A protocol
│   │   │   ├── runtime/         # Main loop, wiring, autonomous runtime
│   │   │   ├── security/        # Immune system + rate limiting only
│   │   │   ├── llm/             # LLM router, provider adapters
│   │   │   ├── embedding/       # Embedding models
│   │   │   ├── models/          # Shared Pydantic models
│   │   │   ├── schemas/         # API schemas
│   │   │   ├── config/          # Configuration (lib portion)
│   │   │   ├── utils/           # Shared utilities
│   │   │   ├── validation/      # Message + LLM output validation
│   │   │   ├── channels/        # Channel definitions
│   │   │   └── orchestrations/  # Workflow orchestration
│   │   └── pyproject.toml
│   └── api/
│       ├── src/heretek_swarm_api/
│       │   ├── api/             # FastAPI app + 22 routers
│       │   ├── observability/   # Metrics, tracing, alerting
│       │   ├── security/        # Zero-trust, DDoS, guardrails (minus immune + rate_limiter)
│       │   ├── mcp/             # MCP server/client
│       │   ├── integrations/    # External integrations
│       │   ├── plugins/         # Plugin manager
│       │   ├── agents/          # HTTP registration, routing
│       │   └── rag/             # RAG orchestration
│       └── pyproject.toml
├── backend/heretek_swarm/        # REMOVED: source files moved to packages/
└── pyproject.toml                # MODIFIED: workspace members activated
```

## Sub-package Mapping

### Core (`heretek-swarm-core`)

No FastAPI dependency. Contains the sovereign service library.

| Sub-package | Source | Destination | Notes |
|---|---|---|---|
| actors/ | `backend/heretek_swarm/actors/` | `packages/core/src/heretek_swarm_core/actors/` | 23 agents, AgentActor base, 10 mixins |
| consensus/ | `backend/heretek_swarm/consensus/` | `packages/core/src/heretek_swarm_core/consensus/` | MAKER, EnhancedMAKER, SwarmDeliberation |
| memory/ | `backend/heretek_swarm/memory/` | `packages/core/src/heretek_swarm_core/memory/` | MemoryStore Protocol + cognee/mem0/null adapters |
| gateway/ | `backend/heretek_swarm/gateway/` | `packages/core/src/heretek_swarm_core/gateway/` | Bearer auth, TokenStore, A2A protocol |
| runtime/ | `backend/heretek_swarm/runtime/` | `packages/core/src/heretek_swarm_core/runtime/` | Main loop, wiring, autonomous runtime |
| security/ | `backend/heretek_swarm/security/immune.py` + `rate_limiter.py` | `packages/core/src/heretek_swarm_core/security/` | Immune system + rate limiting only |
| llm/ | `backend/heretek_swarm/llm/` | `packages/core/src/heretek_swarm_core/llm/` | LLM router, provider adapters |
| embedding/ | `backend/heretek_swarm/embedding/` | `packages/core/src/heretek_swarm_core/embedding/` | Embedding models |
| models/ | `backend/heretek_swarm/models/` | `packages/core/src/heretek_swarm_core/models/` | Shared Pydantic models |
| schemas/ | `backend/heretek_swarm/schemas/` | `packages/core/src/heretek_swarm_core/schemas/` | API schemas |
| config/ | `backend/heretek_swarm/config/` | `packages/core/src/heretek_swarm_core/config/` | Configuration (lib portion) |
| utils/ | `backend/heretek_swarm/utils/` | `packages/core/src/heretek_swarm_core/utils/` | Shared utilities |
| validation/ | `backend/heretek_swarm/validation/` | `packages/core/src/heretek_swarm_core/validation/` | Message + LLM output validation |
| channels/ | `backend/heretek_swarm/channels/` | `packages/core/src/heretek_swarm_core/channels/` | Channel definitions |
| orchestrations/ | `backend/heretek_swarm/orchestrations/` | `packages/core/src/heretek_swarm_core/orchestrations/` | Workflow orchestration |

### API (`heretek-swarm-api`)

FastAPI HTTP surface. Depends on `heretek-swarm-core>=0.2.0`.

| Sub-package | Source | Destination | Notes |
|---|---|---|---|
| api/ | `backend/heretek_swarm/api/` | `packages/api/src/heretek_swarm_api/api/` | FastAPI app + 22 routers |
| observability/ | `backend/heretek_swarm/observability/` | `packages/api/src/heretek_swarm_api/observability/` | Metrics, tracing, alerting |
| security/ | `backend/heretek_swarm/security/` (minus immune.py + rate_limiter.py) | `packages/api/src/heretek_swarm_api/security/` | Zero-trust, DDoS, guardrails |
| mcp/ | `backend/heretek_swarm/mcp/` | `packages/api/src/heretek_swarm_api/mcp/` | MCP server/client |
| integrations/ | `backend/heretek_swarm/integrations/` | `packages/api/src/heretek_swarm_api/integrations/` | External integrations |
| plugins/ | `backend/heretek_swarm/plugins/` | `packages/api/src/heretek_swarm_api/plugins/` | Plugin manager |
| agents/ | `backend/heretek_swarm/agents/` | `packages/api/src/heretek_swarm_api/agents/` | HTTP registration, routing |
| rag/ | `backend/heretek_swarm/rag/` | `packages/api/src/heretek_swarm_api/rag/` | RAG orchestration |

## Import Update Strategy

All imports across the codebase update to new namespaces:

```python
# Before:
from heretek_swarm.actors import AutonomousSwarm
from heretek_swarm.api.main import create_app
from heretek_swarm.security.zero_trust import ZeroTrustMiddleware

# After:
from heretek_swarm_core.actors import AutonomousSwarm
from heretek_swarm_api.api.main import create_app
from heretek_swarm_api.security.zero_trust import ZeroTrustMiddleware
```

The root `heretek-swarm` package keeps its existing imports working via compatibility shims in its `__init__.py` that re-export from the new packages.

## Data flow

```
User code
  ↓ imports from heretek_swarm_core.*
  ↓ imports from heretek_swarm_api.*
  ↓
packages/core/src/heretek_swarm_core/   (source of truth)
packages/api/src/heretek_swarm_api/     (source of truth)
  ↓
backend/heretek_swarm/                  (REMOVED after extraction)
```

## Error handling

- Build fails if imports are wrong — caught at `pip install -e .` time
- Tests fail if imports are wrong — caught at `pytest` time
- Bridge `__init__.py` files removed once extraction is complete

## Testing

- All existing tests must pass after extraction
- Import paths in test files update too
- New smoke test: `python -c "from heretek_swarm_core import AutonomousSwarm; from heretek_swarm_api import create_app"`

## Implementation order

1. Create directory structure in packages/core and packages/api
2. Move core sub-packages (actors, consensus, memory, gateway, runtime, security/immune+rate_limiter, llm, embedding, models, schemas, config, utils, validation, channels, orchestrations)
3. Move api sub-packages (api, observability, security/minus-immune, mcp, integrations, plugins, agents, rag)
4. Update all imports across codebase to new namespaces
5. Update pyproject.toml files (dependencies, build config)
6. Activate workspace in root pyproject.toml
7. Remove bridge __init__.py files
8. Run full test suite
9. Verify package builds
