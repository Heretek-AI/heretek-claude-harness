---
name: heretek-backend-development
description: >-
  Backend development patterns for Heretek Swarm Python/FastAPI services. Use when
  building API endpoints, creating agent actors, implementing memory operations,
  or working with async Python patterns. Covers project structure, conventions,
  and common pitfalls specific to this codebase.
---

# Heretek Swarm Backend Development

## Project Structure

```
backend/heretek_swarm/
├── actors/             # Agent implementations (23 classes)
├── api/                # FastAPI routers (27 routers, 175+ endpoints)
├── channels/           # Channel + Group registries
├── collective/         # Learning, metrics, emergent detection
├── config/             # ConfigurationService (1,366-LOC crud.py + per-entity modules)
├── consensus/          # Triad consensus (4 algos + immune relocated to security/)
│   ├── protocol.py     # ConsensusEngine Protocol (Phase 3.1)
│   ├── maker.py        # MAKERConsensus (base)
│   ├── maker_enhanced.py  # 1,228 LOC (was 1,496)
│   ├── maker_enhanced_types.py  # 7 data classes
│   ├── deliberation.py  # 1,081 LOC (was 1,487)
│   ├── deliberation_types.py   # 13 data classes
│   └── immune.py        # 42-LOC re-export shim → security/
├── consciousness/      # FEP, GWT, AST, IIT
├── gateway/            # NATS JetStream + A2A protocol
│   ├── nats_event_mesh.py    # 1,370 LOC (was 1,888) — Phase 2.5 partial
│   ├── nats_connection.py    # 174 LOC
│   ├── nats_fallback.py      # 136 LOC — InMemoryFallback
│   ├── nats_tls.py           # 160 LOC
│   ├── nats_types.py         #  61 LOC — ConnectionState, Subscription, NATSMessage
│   └── nats_actor_bridge.py  # 389 LOC — NATS ↔ actor bridge
├── governance/         # Tribunal, election governance
├── heretek_swarm_api/  # Phase 4 re-export shim (multi-pkg monorepo)
├── heretek_swarm_core/ # Phase 4 re-export shim (multi-pkg monorepo)
├── infrastructure/     # Cross-cutting infra
│   ├── a2a/            # JSON-RPC 2.0 A2A protocol
│   ├── nats/           # NATS pub/sub + JetStream
│   └── otel/           # OpenTelemetry (canonical tracing)
├── llm/                # LLM integration
│   ├── model_garage.py # 5 LLM providers + headroom.wrap() + @opik.track
│   ├── headroom_compat.py  # Phase 1.4 — token compression
│   ├── hindsight_compat.py # Phase 1.6 — training memory
│   └── providers/      # Provider plugins
├── mcp/                # Model Context Protocol servers
├── memory/             # Cognee + mem0 + null backends
│   ├── store.py        # MemoryStore Protocol + get_default_store() resolver
│   ├── cognee_reader.py
│   ├── cognee_writer.py
│   ├── mem0_backend.py # Phase 1.1 — mem0ai wrapper
│   ├── eliza_memory.py # Importance-decay
│   ├── access_patterns.py
│   └── prefetcher.py
├── observability/      # 90-LOC re-export shim (Phase 2.9)
│   ├── opik_compat.py  # Phase 1.3 — LLM/agent observability
├── orchestration/      # LangGraph HeavySwarm (Phase 1.2 cutover)
├── plugins/            # Plugin system
├── rag/                # RAG pipelines
├── runtime/            # AutonomousSwarm lifecycle
│   ├── main_loop.py    # 1,740 LOC (was 1,791)
│   ├── initializers/   # 10 per-concern free functions (Phase 2.6)
│   └── wiring.py       # orchestrator wiring (Phase 2.2)
├── security/           # Zero-trust security
│   ├── auth.py         # TokenStore (Phase 2.10)
│   ├── rate_limiter.py # slowapi wrapper (Phase 1.5)
│   ├── immune.py       # 58-LOC re-export shim
│   ├── immune_types.py # 4 enums + 6 dataclasses
│   └── immune_engine.py # ImmuneResponseBuilding + Engine
├── services/           # Phase 5 sovereign services
│   ├── grpc_servers.py # gRPC service implementations
│   ├── grpc_clients.py # gRPC client resolvers
│   ├── consensus_svc.py
│   ├── memory_svc.py
│   ├── realtime_svc.py
│   └── observability_svc.py
└── tools/              # Tool integrations
```

## Conventions

### Code Style
- **Type hints required** on all public APIs
- **async/await** for all I/O operations
- **pathlib.Path** for file operations
- **Google-style docstrings** with max 120 chars per line
- **Ruff** for linting (target Python 3.11)
- **Pin versions properly** in pyproject.toml — the audit
  (§1.9, Phase 0.3) flagged impossible version ranges
  (`swarms>=12.0.1,<10.0.0`, `setuptools>=82.0.1,<81`) that
  silently broke clean installs. Always validate pins with
  `tomllib.load` + a `lower >= upper` checker.

### Agent Development
- Base class: `AgentActor` in `actors/base/core.py`
- Use mixins from `actors/mixins/` for cross-cutting concerns
- Compose, don't subclass for multiple inheritance
- Ruff ignores `N801` in `actors/` (class names like `AgentActor` allowed)
- `MemoryMixin` (Phase 1.1 follow-up) tolerates a missing
  `access_analyzer`; new agents should use `_get_memory_store()`
  to access the canonical `MemoryStore` Protocol

### API Development
- FastAPI with async dependencies
- Input validation mandatory on all handlers
- Structured error responses
- OpenAPI/Redoc at `/docs` when running
- `api/main.py` lifespan calls `_init_sovereign_services()`
  (Phase 5) which resolves the 4 `get_*_grpc_client()` from
  env vars. Routes that need to dispatch through the gRPC
  client should resolve it through the same `services.grpc_clients`
  resolvers, not by importing the client class directly.

### Memory System
- Cognee HTTP API is the default backend
- Use the `MemoryStore` Protocol via `get_default_store()` —
  not the legacy `CogneeMemoryReader`/`CogneeMemoryWriter` directly
- `MemoryType` enum (EPISODIC/SEMANTIC/PROCEDURAL/WORKING) maps
  to cognee dataset name via `MemoryType.to_dataset(identifier)`
- `Mem0Backend` is an alternative backend, opt-in via
  `MEM0_ENABLED=1`
- No legacy in-process memory (DualTierMemory, PersistentMemory deleted)
- Access patterns in `access_patterns.py` for tiering/classification

### LLM Provider Pattern (Phase 1.3 + 1.4)

All 5 LLM providers in `llm/model_garage.py` follow the same
canonical pattern:

```python
class SomeProvider(LLMProvider):
    @_opik_track_llm
    async def complete(self, request: LLMRequest) -> LLMResponse:
        # ...
        with _opik_timed("llm_<provider>_complete", tags={...}):
            _compression = _headroom_wrap(payload.get("messages", []))
        if isinstance(_compression.data, list):
            payload["messages"] = _compression.data
        # ...
```

- `@_opik_track_llm` (gated by `OPIK_ENABLED`) — opik captures
  the call as an 'llm' span
- `_headroom_wrap` (Phase 1.4) — token compression
- `_opik_timed` (Phase 1.3) — duration timing

Add a new provider by following the same pattern. The decorator
is a no-op stub when opik is not installed.

## Development Workflow

### Setup
```bash
# Install dependencies (preferred)
uv sync

# Fallback
pip install -e .
```

### Verification
```bash
# Lint (target specific dirs, NOT full project)
ruff check backend/ tests/

# Type check
mypy backend/heretek_swarm/

# Tests
pytest tests/ -v

# Single file
pytest tests/test_memory.py -v
```

### Docker Operations
```bash
# Full stack
docker compose up

# Health check
heretek-swarm status --json

# In-memory mode (no Docker)
heretek-swarm run --no-infra --prompt "Hello"
```

## Common Patterns

### Creating a New Agent
1. Create directory under `actors/<agent_name>/`
2. Implement class inheriting from `AgentActor`
3. Add mixins as needed (audit, deliberation, memory, etc.)
4. Register in `actors/__init__.py`
5. Add tests in `tests/`

### Adding API Endpoint
1. Create router in `api/<feature>/`
2. Use async dependencies
3. Add input validation with Pydantic
4. Register router in `api/__init__.py`
5. Add OpenAPI documentation

### Memory Operations
```python
# Reading
reader = CogneeMemoryReader()
results = await reader.search(query, limit=10)

# Writing
writer = CogneeMemoryWriter()
await writer.add(content, metadata)
await writer.cognify()  # Process into knowledge graph
```

## Gotchas

1. **Ruff scope**: Always run `ruff check backend/ tests/` - full project picks up non-Python files
2. **NATS mTLS**: Certs in `certs/` must be regenerated when docker network changes
3. **Container entrypoint**: Runs migrations first - rebuild image if migrations change
4. **No eval/exec**: Dynamic code execution forbidden anywhere
5. **Input validation**: Mandatory on every agent message handler

## Testing Patterns

- pytest with asyncio
- Use `pytest-asyncio` mode=auto for Python 3.14 compatibility
- Negative assertions verify legacy code doesn't creep back
- Test both happy path and error conditions
- Mock external services (Cognee, NATS) in unit tests

## Security Requirements

- Zero-trust: All inter-agent messages authenticated
- No secrets in code - use SOPS-encrypted files
- Input validation mandatory
- Audit trails for all operations
- Tool allowlisting in `.github/instructions/agent_safety.instructions.md`
