# Heretek Swarm Architecture

**Version:** 2.3.0
**Date:** 2026-06-04
**Status:** Production-Ready — M001 Complete (mem0 embedded, 7 logical services); Phase 2A.3 opik cutover applied (deleted 5 of 8 `api/observability` routers, 3 observability wrappers, 1 plugin; see "Observability" section below)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Package Structure](#package-structure)
3. [Actor Architecture](#actor-architecture)
4. [Actor Base Class & Mixins](#actor-base-class--mixins)
5. [Memory System](#memory-system)
6. [Event Mesh](#event-mesh)
7. [Configuration System](#configuration-system)
8. [Security](#security)
9. [Observability](#observability)
   - [Metrics](#metrics)
   - [Distributed Tracing](#distributed-tracing)
   - [Alerting](#alerting)
10. [Monitoring Setup](#monitoring-setup)

---

## System Overview

The Heretek Swarm is a self-governing swarm of 23 specialized AI agents that operate independently 24/7, make collective decisions through consensus, adapt and learn from experience, and exhibit emergent collective intelligence.

### Architectural Principles

1. **Zero-Trust Security** — All inputs validated, all outputs verified
2. **State Persistence** — All critical state persisted to PostgreSQL
3. **Event-Driven Design** — NATS JetStream for reliable event streaming
4. **Modular Architecture** — Clear separation of concerns between components
5. **Autonomous Operation** — Designed for 24/7 independent operation
6. **Observable** — Prometheus metrics, distributed tracing, and alerting

### Infrastructure Dependencies

| Component   | Purpose                  | Minimum Version | Status       |
|-------------|--------------------------|-----------------|--------------|
| PostgreSQL  | State persistence        | 15+             | ✅ Operational |
| Redis       | Caching layer            | 7+              | ✅ Operational |
| Qdrant      | Vector storage           | 1.8+            | ✅ Operational |
| NATS        | Event mesh with JetStream| 2.10+           | ✅ Operational |
| mem0        | Memory backend           | Latest          | Embedded in API container |
| Prometheus  | Metrics collection       | 2.45+           | ✅ Operational |
| Grafana     | Metrics visualization    | 10.0+           | ✅ Optional   |

---

## Package Structure

All source code lives under `backend/heretek_swarm/`. There is no source-directory prefix.

```
backend/
├── heretek_swarm/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── actors/                    # 23 agents + base class + factory
│   │   ├── __init__.py            # Public exports for all agent classes
│   │   ├── base/                  # AgentActor base class (3 modules)
│   │   │   ├── core.py            #   AgentActor init, lifecycle, mailbox
│   │   │   ├── message_handling.py #   Mixin: message dispatch & handlers
│   │   │   └── state_management.py#   Mixin: state persistence
│   │   ├── mixins/                # 10 reusable capability mixins
│   │   │   ├── audit.py           #   AuditMixin
│   │   │   ├── deliberation.py    #   DeliberationMixin
│   │   │   ├── health_reporting.py#   HealthReportingMixin
│   │   │   ├── learning.py        #   LearningMixin
│   │   │   ├── memory.py          #   MemoryMixin
│   │   │   ├── memory_access.py   #   MemoryAccessMixin
│   │   │   ├── pattern.py         #   PatternMixin
│   │   │   ├── pattern_consumer.py#   PatternConsumerMixin
│   │   │   ├── tribunal.py        #   TribunalMixin
│   │   │   └── validation.py      #   ValidationMixin
│   │   ├── triad/                 # Triad agents (extracted subpackage)
│   │   │   ├── agent.py           #   StewardAgent, AlphaAgent, BetaAgent, CharlieAgent
│   │   │   ├── balancing.py       #   Triad balancing logic
│   │   │   └── types.py           #   Triad-specific types
│   │   ├── arbiter/               # ArbiterAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── strategies.py
│   │   │   ├── handlers.py
│   │   │   └── constants.py
│   │   ├── chronos/               # ChronosAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── scheduler.py
│   │   │   ├── handlers.py
│   │   │   └── types.py
│   │   ├── coordinator/           # CoordinatorAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── strategies.py
│   │   │   └── types.py
│   │   ├── dreamer/               # DreamerAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── generators.py
│   │   │   └── types.py
│   │   ├── examiner/              # ExaminerAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── testing.py
│   │   │   └── types.py
│   │   ├── explorer/              # ExplorerAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── pathfinding.py
│   │   │   └── types.py
│   │   ├── habit_forge/           # HabitForgeAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── streaks.py
│   │   │   ├── tracking.py
│   │   │   └── types.py
│   │   ├── nexus/                 # NexusAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── routing.py
│   │   │   └── types.py
│   │   ├── perceiver_plus/        # PerceiverPlusAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── analytics.py
│   │   │   └── types.py
│   │   ├── prism/                 # PrismAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── transforms.py
│   │   │   └── types.py
│   │   ├── sentinel/              # SentinelAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── helpers.py
│   │   │   └── types.py
│   │   ├── sentinel_prime/        # SentinelPrimeAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── handlers.py
│   │   │   ├── helpers.py
│   │   │   └── types.py
│   │   ├── triad/                 # Triad subpackage (Steward, Alpha, Beta, Charlie)
│   │   │   ├── agent.py
│   │   │   ├── balancing.py
│   │   │   └── types.py
│   │   ├── catalyst/              # CatalystAgent subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── coder/                 # CoderAgent subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── echo/                  # EchoActor subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── empath/                # EmpathAgent subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── explorer/              # ExplorerAgent subpackage
│   │   │   ├── agent.py
│   │   │   ├── pathfinding.py
│   │   │   └── types.py
│   │   ├── historian/             # HistorianAgent subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── metis/                 # MetisAgent subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── perceiver/             # PerceiverAgent subpackage
│   │   │   ├── agent.py
│   │   │   └── types.py
│   │   ├── factory.py             # ActorFactory
│   │   ├── supervisor.py          # ActorSupervisor
│   │   ├── validation.py          # Message validation helpers
│   │   ├── handoff.py             # Agent handoff logic
│   │   ├── handoff_handlers.py    # Handoff message handlers
│   │   ├── profiling.py           # Actor profiling
│   │   ├── stubs.py               # Test dependency stubs
│   │   └── langroid_adapter.py    # Langroid integration
│   ├── agents/                    # Agent registration and skills
│   │   ├── agent_factory.py
│   │   └── skills.py
│   ├── api/                       # FastAPI application
│   │   ├── main.py                #   Application entry point
│   │   ├── agents/                #   Agent management routes
│   │   ├── agents_management.py
│   │   ├── autonomous.py
│   │   ├── consciousness.py
│   │   ├── consensus.py
│   │   ├── configuration.py
│   │   ├── metrics.py
│   │   └── ...                    # Other route modules
│   ├── gateway/                   # External communication layer
│   │   ├── auth.py                #   Bearer token authentication
│   │   ├── a2a_protocol.py        #   Agent-to-Agent protocol
│   │   ├── a2a_server.py          #   A2A server endpoints
│   │   ├── event_mesh.py          #   Event mesh abstraction
│   │   ├── nats_event_mesh.py     #   NATS-backed event mesh
│   │   ├── jetstream_manager.py   #   NATS JetStream management
│   │   ├── external_api.py
│   │   ├── content_router.py
│   │   └── message_replay.py
│   ├── infrastructure/            # Infrastructure layer (NATS, OTEL, health)
│   │   ├── nats/                  #   NATS client, broadcast, subscriber, etc.
│   │   ├── otel/                  #   OpenTelemetry logging, metrics, tracing
│   │   ├── a2a/                   #   A2A protocol (protocol layer)
│   │   ├── health.py
│   │   ├── audit.py
│   │   └── provisioner.py
│   ├── memory/                    # Memory system implementation
│   │   ├── cognee_writer.py       #   Cognee-backed episodic/semantic write path
│   │   ├── cognee_reader.py       #   Cognee-backed search/restore
│   │   ├── mem0_backend.py        #   Mem0ai embedded backend (Qdrant + OpenAI)
│   │   ├── eliza_memory.py        #   ELIZA-style short-term conversation memory
│   │   ├── access_patterns.py     #   Per-agent read-pattern analytics
│   │   ├── prefetcher.py          #   Predictive prefetch into tier-0 cache
│   │   └── __init__.py            #   MemoryType enum + facade exports
│   ├── security/                  # Zero-trust security layer
│   │   ├── zero_trust.py          #   4-layer input/output validation
│   │   ├── adversarial.py         #   Prompt injection / jailbreak detection
│   │   ├── ddos_protection.py     #   Token bucket rate limiting
│   │   ├── guardrails.py          #   Content filtering
│   │   ├── anomaly_detection.py
│   │   ├── behavioral_baseline.py
│   │   ├── baseline_update.py
│   │   ├── safe01_anomaly_response.py
│   │   ├── threat_detection.py
│   │   └── validators.py
│   ├── observability/             # Prometheus metrics + tracing
│   │   ├── __init__.py            #   LokiHandler (log aggregation)
│   │   ├── prometheus_native.py   #   canonical prometheus_client surface
│   │   ├── db_timing.py           #   OTel SQLAlchemyInstrumentor wrapper
│   │   ├── alerting.py            #   AlertManager (PagerDuty, OpsGenie)
│   │   ├── context.py             #   observability context propagation
│   │   └── tracing.py             #   tracing helpers
│   ├── config/                    # Configuration system
│   │   ├── models.py
│   │   ├── service.py
│   │   ├── crud.py
│   │   ├── db_models.py
│   │   ├── cache.py
│   │   ├── encryption.py
│   │   └── loader.py
│   ├── consensus/                 # Consensus & deliberation
│   │   ├── deliberation.py
│   │   ├── maker.py
│   │   ├── tribunal.py
│   │   ├── immune.py
│   │   └── ...
│   ├── collective/                # Swarm intelligence & emergence
│   │   ├── society.py
│   │   ├── swarm_intelligence.py
│   │   ├── emergent_detection.py
│   │   ├── evolution_engine.py
│   │   └── ...
│   ├── orchestration/             # HeavySwarm workflow orchestration
│   │   ├── heavyswarm.py
│   │   └── phase_handlers.py
│   ├── consciousness/             # IIT phi, FEP, GWT implementations
│   ├── llm/                       # LLM provider abstraction
│   ├── rag/                       # RAG pipeline
│   ├── runtime/                   # Agent runtime & daemon
│   ├── coordination/              # Agent coordination patterns
│   ├── workflow/                  # Workflow engine
│   ├── governance/                # Agent identity & governance
│   ├── state/                     # State persistence
│   ├── tools/                     # Tool system
│   ├── mcp/                       # MCP server & client
│   ├── integrations/              # Third-party integrations
│   ├── schemas/                   # Pydantic models
│   ├── validation/                # Input/output validation
│   ├── routing/                   # Model router
│   ├── channels/                  # Channel definitions
│   ├── embeddings/                # Embedding providers
│   ├── evaluation/                # Evaluation system
│   ├── goals/                     # Goal management
│   ├── knowledge/                 # Knowledge base
│   └── ...                        # Other modules
├── tests/                         # Test suite
├── docs/                          # Documentation
└── migrations/                    # Database migrations
```

---

## Actor Architecture

### Overview

The Heretek Swarm implements 23 autonomous agents organized into 6 tiers, each with specific capabilities and responsibilities. All agents inherit from the [`AgentActor`](backend/heretek_swarm/actors/base/core.py) base class which provides:

- Async message handling via mailbox pattern
- State management with PostgreSQL persistence
- Health monitoring and heartbeat
- Zero-Trust input validation
- Prometheus metrics integration
- Injectable dependency stubs for testing
- Optional mixins for cross-cutting capabilities

### Agent Tiers

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE COLLECTIVE (23 AGENTS)                    │
├─────────────────────────────────────────────────────────────────┤
│ TIER 1: CORE TRIAD (4)     │ TIER 4: SAFETY (3)               │
│ ├── Steward (Orchestrator) │ ├── Sentinel (Safety Guardian)     │
│ ├── Alpha (Deep Analysis)  │ ├── Sentinel-Prime (Security)     │
│ ├── Beta (Validation)      │ └── Arbiter (Conflict Resolution) │
│ └── Charlie (Challenge)    │                                   │
│                            │ TIER 5: COORDINATION (4)         │
│ TIER 2: SUPPORT (5)        │ ├── Coordinator (Multi-Agent)    │
│ ├── Historian (Memory)      │ ├── Nexus (External Integration) │
│ ├── Metis (Strategy)        │ ├── Catalyst (Change Mgmt)       │
│ ├── Empath (Emotional IQ)  │ └── Chronos (Scheduling)         │
│ ├── Perceiver (Sensory)     │                                   │
│ └── Echo (Communication)   │ TIER 6: ENHANCEMENT (3)          │
│                            │ ├── Prism (Multi-Perspective)     │
│ TIER 3: EXPLORATION (4)    │ ├── Habit-Forge (Optimization)    │
│ ├── Explorer (Discovery)    │ └── Perceiver+ (Advanced)         │
│ ├── Examiner (QA)           │                                   │
│ ├── Dreamer (Creativity)    │                                   │
│ └── Coder (Implementation) │                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Tier 1: Core Triad (4 Agents)

| Agent   | Role                      | File                                                                                   | Capabilities                             |
|---------|---------------------------|----------------------------------------------------------------------------------------|------------------------------------------|
| Steward | Governance & Orchestration | [`backend/heretek_swarm/actors/triad/agent.py`](backend/heretek_swarm/actors/triad/agent.py) | Deliberation orchestration, decision collection |
| Alpha   | Deep Analysis             | [`backend/heretek_swarm/actors/triad/agent.py`](backend/heretek_swarm/actors/triad/agent.py) | Deep analysis, proposal generation       |
| Beta    | Validation                | [`backend/heretek_swarm/actors/triad/agent.py`](backend/heretek_swarm/actors/triad/agent.py) | Validation, verification                 |
| Charlie | Challenge                 | [`backend/heretek_swarm/actors/triad/agent.py`](backend/heretek_swarm/actors/triad/agent.py) | Challenge, stress-testing                |

The Triad agents live in the `backend/heretek_swarm/actors/triad/` subpackage. `triad/agent.py` provides `StewardAgent`, `AlphaAgent`, `BetaAgent`, and `CharlieAgent`; `triad/balancing.py` holds cross-agent balancing logic and `triad/types.py` the shared Pydantic models. Earlier revisions shipped these as flat `steward.py` / `alpha.py` / `beta.py` / `charlie.py` files at the top of `actors/`; they were consolidated into the subpackage. Backward-compatible re-exports keep older import paths working.

### Tier 2: Support Agents (5 Agents)

| Agent     | Role                     | File                                                                              | Capabilities                                    |
|-----------|--------------------------|-----------------------------------------------------------------------------------|-------------------------------------------------|
| Historian | Memory & Knowledge       | [`backend/heretek_swarm/actors/historian/agent.py`](backend/heretek_swarm/actors/historian/agent.py) | Memory storage, search, lineage tracking        |
| Metis     | Strategic Planning       | [`backend/heretek_swarm/actors/metis/agent.py`](backend/heretek_swarm/actors/metis/agent.py)         | Strategic planning, resource allocation         |
| Empath    | Emotional Intelligence   | [`backend/heretek_swarm/actors/empath/agent.py`](backend/heretek_swarm/actors/empath/agent.py)       | Sentiment analysis, conflict mediation          |
| Perceiver | Multi-Modal Input        | [`backend/heretek_swarm/actors/perceiver/agent.py`](backend/heretek_swarm/actors/perceiver/agent.py) | Multi-modal input processing                    |
| Echo      | Communication            | [`backend/heretek_swarm/actors/echo/agent.py`](backend/heretek_swarm/actors/echo/agent.py)           | Multi-channel communication, protocol translation|

### Tier 3: Exploration Agents (4 Agents)

| Agent    | Role                    | File                                                                            | Capabilities                               |
|----------|-------------------------|---------------------------------------------------------------------------------|--------------------------------------------|
| Explorer | Intelligence Gathering  | [`backend/heretek_swarm/actors/explorer/agent.py`](backend/heretek_swarm/actors/explorer/agent.py) (subpackage) | Source monitoring, anomaly detection     |
| Examiner | Quality Assurance       | [`backend/heretek_swarm/actors/examiner/agent.py`](backend/heretek_swarm/actors/examiner/agent.py) (subpackage) | Test plan generation, code analysis      |
| Dreamer  | Creative Generation     | [`backend/heretek_swarm/actors/dreamer/agent.py`](backend/heretek_swarm/actors/dreamer/agent.py) (subpackage)   | Creative solutions, alternative exploration|
| Coder    | Implementation          | [`backend/heretek_swarm/actors/coder/agent.py`](backend/heretek_swarm/actors/coder/agent.py) (subpackage) | Code generation, review, safe execution  |

### Tier 4: Safety & Security (3 Agents)

| Agent          | Role                    | File                                                                                                | Capabilities                              |
|----------------|-------------------------|-----------------------------------------------------------------------------------------------------|-------------------------------------------|
| Sentinel       | Safety Guardian         | [`backend/heretek_swarm/actors/sentinel/agent.py`](backend/heretek_swarm/actors/sentinel/agent.py) (subpackage) | Input validation, safety checks         |
| Sentinel-Prime | Security Commander      | [`backend/heretek_swarm/actors/sentinel_prime/agent.py`](backend/heretek_swarm/actors/sentinel_prime/agent.py) (subpackage) | Threat detection, security response    |
| Arbiter        | Conflict Resolution     | [`backend/heretek_swarm/actors/arbiter/agent.py`](backend/heretek_swarm/actors/arbiter/agent.py) (subpackage)   | Conflict mediation, decision arbitration |

### Tier 5: Coordination Agents (4 Agents)

| Agent       | Role                  | File                                                                                  | Capabilities                                   |
|-------------|-----------------------|---------------------------------------------------------------------------------------|------------------------------------------------|
| Coordinator | Multi-Agent Sync      | [`backend/heretek_swarm/actors/coordinator/agent.py`](backend/heretek_swarm/actors/coordinator/agent.py) (subpackage) | Workflow coordination, dependency resolution |
| Nexus       | External Integration  | [`backend/heretek_swarm/actors/nexus/agent.py`](backend/heretek_swarm/actors/nexus/agent.py) (subpackage)   | API integration, webhook management           |
| Catalyst    | Change Management     | [`backend/heretek_swarm/actors/catalyst/agent.py`](backend/heretek_swarm/actors/catalyst/agent.py) (subpackage) | Change requests, impact analysis, rollback    |
| Chronos     | Scheduling            | [`backend/heretek_swarm/actors/chronos/agent.py`](backend/heretek_swarm/actors/chronos/agent.py) (subpackage)   | Task scheduling, deadline tracking            |

### Tier 6: Enhancement Agents (3 Agents)

| Agent       | Role                  | File                                                                                          | Capabilities                                 |
|-------------|-----------------------|-----------------------------------------------------------------------------------------------|----------------------------------------------|
| Prism       | Multi-Perspective     | [`backend/heretek_swarm/actors/prism/agent.py`](backend/heretek_swarm/actors/prism/agent.py) (subpackage) | Multi-perspective analysis, bias detection   |
| Habit-Forge | Behavior Optimization | [`backend/heretek_swarm/actors/habit_forge/agent.py`](backend/heretek_swarm/actors/habit_forge/agent.py) (subpackage) | Habit creation, pattern analysis           |
| Perceiver+  | Advanced Analytics    | [`backend/heretek_swarm/actors/perceiver_plus/agent.py`](backend/heretek_swarm/actors/perceiver_plus/agent.py) (subpackage) | Statistical analysis, forecasting          |

### Import Convention

All agents are publicly exported from `backend/heretek_swarm/actors/__init__.py`. Consumers should use:

```python
from heretek_swarm.actors import StewardAgent, HistorianAgent, ...
```

---

## Actor Base Class & Mixins

### AgentActor Hierarchy

The [`AgentActor`](backend/heretek_swarm/actors/base/core.py) class in `actors/base/core.py` provides the core lifecycle:

- `spawn()` → initializes, starts mailbox processing & heartbeat loop
- `process_message()` → dispatches messages to registered handlers
- `terminate()` → cancels tasks, persists state, calls cleanup
- `save_state()` / `load_state()` → PostgreSQL state persistence via `StateRepository`

Two base mixins augment AgentActor via module-level import triggers:

- **`AgentActorMessageHandling`** (`actors/base/message_handling.py`) — registers message dispatch, handler registration/unregistration, and the mailbox processing loop.
- **`AgentActorStateManagement`** (`actors/base/state_management.py`) — integrates state save/load with the persistence interval and the state repository.

### 10 Actor Mixins

The 10 mixins in [`backend/heretek_swarm/actors/mixins/`](backend/heretek_swarm/actors/mixins/) provide reusable capabilities that agents can opt into:

| Mixin                | File                                                 | Purpose                                                          | Used By                                                         |
|----------------------|------------------------------------------------------|------------------------------------------------------------------|-----------------------------------------------------------------|
| ValidationMixin      | `mixins/validation.py`                               | IMMUTABLE_RULES (8 security patterns), BASELINE_CONFIG constants | All agents via validation module                                |
| HealthReportingMixin | `mixins/health_reporting.py`                         | Health score reporting, uptime tracking                          | All agents (capability-checked via `hasattr`)                   |
| MemoryMixin          | `mixins/memory.py`                                   | Long-term memory storage & search                                | Historian                                                       |
| MemoryAccessMixin    | `mixins/memory_access.py`                            | Read-only memory queries                                         | Agents needing memory retrieval without write access            |
| PatternMixin         | `mixins/pattern.py`                                  | Pattern extraction & recognition                                 | Explorer                                                        |
| PatternConsumerMixin | `mixins/pattern_consumer.py`                         | Consuming discovered patterns                                    | Agents subscribing to pattern events                            |
| LearningMixin        | `mixins/learning.py`                                 | Adaptive learning from outcomes                                  | Agents with self-improvement capability                         |
| DeliberationMixin    | `mixins/deliberation.py`                             | Participation in consensus deliberation                          | Triad agents + Coordinator                                      |
| TribunalMixin        | `mixins/tribunal.py`                                 | Escalating disputes to the Arbiter                               | Sentinel, Sentinel-Prime, Arbiter                               |
| AuditMixin           | `mixins/audit.py`                                    | Structured audit logging pipeline                                | All agents (capability-checked via `hasattr`)                   |

Mixins that depend on external collaborators (e.g., LearningMixin → `access_analyzer`, PatternMixin → `pattern_extractor`, TribunalMixin → `tribunal`) raise `TypeError` immediately with a clear message when the dependency is missing. Mixins using capability checks (`hasattr`) for optional subsystems degrade gracefully without error.

---

## Memory System

### Architecture

The Heretek Swarm implements a dual-tier memory architecture with PostgreSQL, Redis, and Qdrant vector storage.

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Memory Backend (mem0-based)                 │
│        (backend/heretek_swarm/memory/)             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Embed     │  │   Store     │  │   Search    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    Redis      │ │  PostgreSQL   │ │    Qdrant     │
│  (Ephemeral)  │ │ (Persistent)  │ │   (Vector)    │
└───────────────┘ └───────────────┘ └───────────────┘
```

### Memory Tiers

| Tier      | Storage     | Use Case                              | TTL          |
|-----------|-------------|---------------------------------------|--------------|
| Ephemeral | Redis       | Session data, recent context          | Configurable |
| Persistent| PostgreSQL  | Decision history, lineage             | Permanent    |
| Vector    | Qdrant      | Semantic search, similarity           | Permanent    |

### Memory Types

| Type      | Description                 | Example                   |
|-----------|-----------------------------|---------------------------|
| Episodic  | Event-based memories        | Deliberation outcomes     |
| Semantic  | Knowledge/fact-based        | Domain knowledge          |
| Procedural| How-to/skill memories       | Agent strategies          |

### Key Components

- **MemoryEntry** ([`backend/heretek_swarm/memory/__init__.py`](backend/heretek_swarm/memory/__init__.py)) — `MemoryType` enum and facade exports
- **Cognee Memory Writer** ([`backend/heretek_swarm/memory/cognee_writer.py`](backend/heretek_swarm/memory/cognee_writer.py)) — 5-stage cognee pipeline (add → cognify → search → improve); Kùzu graph + Qdrant vector + Pydantic datasets
- **Cognee Memory Reader** ([`backend/heretek_swarm/memory/cognee_reader.py`](backend/heretek_swarm/memory/cognee_reader.py)) — Search/restore facade for the cognee writer
- **Mem0 Backend** ([`backend/heretek_swarm/memory/mem0_backend.py`](backend/heretek_swarm/memory/mem0_backend.py)) — `mem0ai` embedded backend (Qdrant + OpenAI); lazy init, gracefully disabled when keys are missing
- **Access Pattern Analyzer** ([`backend/heretek_swarm/memory/access_patterns.py`](backend/heretek_swarm/memory/access_patterns.py)) — Per-agent read-pattern analytics for the prefetcher
- **Intelligent Prefetcher** ([`backend/heretek_swarm/memory/prefetcher.py`](backend/heretek_swarm/memory/prefetcher.py)) — Predictive memory loading based on access patterns
- **Eliza-style Memory** ([`backend/heretek_swarm/memory/eliza_memory.py`](backend/heretek_swarm/memory/eliza_memory.py)) — Short-term conversation pattern memory

---

## Event Mesh

### NATS JetStream Architecture

The Heretek Swarm uses NATS JetStream for persistent event streaming. The primary implementation lives in:

- [`backend/heretek_swarm/gateway/nats_event_mesh.py`](backend/heretek_swarm/gateway/nats_event_mesh.py) — NATS-backed event mesh
- [`backend/heretek_swarm/gateway/event_mesh.py`](backend/heretek_swarm/gateway/event_mesh.py) — Abstract event mesh interface
- [`backend/heretek_swarm/gateway/jetstream_manager.py`](backend/heretek_swarm/gateway/jetstream_manager.py) — JetStream connection/stream management
- [`backend/heretek_swarm/infrastructure/nats/`](backend/heretek_swarm/infrastructure/nats/) — Low-level NATS client, publisher, subscriber, broadcast, consensus, discovery

Key features:

- **Message Durability** — All events persisted to stream
- **Guaranteed Delivery** — Message acknowledgment
- **Stream Retention** — Configurable retention policies
- **Subject-Based Routing** — Publish/subscribe pattern

### Channel Architecture

#### Internal Channels

| Channel       | Subject                              | Subscribers                                             | Message Types                                                    |
|---------------|--------------------------------------|---------------------------------------------------------|------------------------------------------------------------------|
| Triad         | `swarm.internal.triad`               | steward, alpha, beta, charlie                           | proposal, analysis, validation, challenge, decision              |
| Coordination  | `swarm.internal.coordination`        | coordinator, catalyst, chronos, metis                   | task_start, task_complete, dependency_ready, blocker             |
| Safety        | `swarm.internal.safety`              | sentinel, sentinel-prime, arbiter, steward              | threat_detected, quarantine, all_clear, incident_report          |
| Memory        | `swarm.internal.memory`              | historian, prism, habit-forge                           | store_request, retrieve_request, learn_pattern, forget           |
| Exploration   | `swarm.internal.exploration`         | explorer, examiner, dreamer, coder                      | research_task, analysis_result, creative_request, code_review    |
| Perception    | `swarm.internal.perception`          | perceiver, perceiver-plus, empath, echo                 | input_received, sentiment_analysis, translation_request          |

#### System Channels

| Channel       | Subject                           | Subscribers       | Message Types                                                    |
|---------------|-----------------------------------|-------------------|------------------------------------------------------------------|
| Health        | `swarm.system.health`             | * (all)           | heartbeat, health_status, error_report, restart_request          |
| Consciousness | `swarm.system.consciousness`      | * (all)           | phi_update, attention_state, workspace_broadcast                 |
| Consensus     | `swarm.system.consensus`          | steward, alpha, beta, charlie | vote_cast, consensus_reached, red_flag                           |
| Workflow      | `swarm.workflow.events`           | * (all)           | workflow_start, workflow_phase, workflow_complete                |

### Message Format

All channel messages follow the `ChannelMessage` structure defined in the event mesh:

```python
@dataclass
class ChannelMessage:
    subject: str                    # NATS subject
    correlation_id: str             # Unique message ID
    reply_to: Optional[str]         # Response subject
    sender_agent: str               # Sending agent ID
    target_agents: List[str]        # Target agents
    message_type: str               # Message type identifier
    workflow_id: Optional[str]       # Associated workflow
    task_id: Optional[str]          # Associated task
```

---

## Configuration System

### Database-Backed Configuration

The Heretek Swarm uses a database-backed configuration system for all user-facing configurations, implemented in [`backend/heretek_swarm/config/`](backend/heretek_swarm/config/):

- **User Configurations** — System-wide settings stored in PostgreSQL
- **LLM Providers** — Multi-provider LLM configurations (OpenAI, Ollama, llama.cpp, etc.)
- **Embedding Providers** — Multi-provider embedding configurations
- **Agent Configs** — Per-agent configurations
- **Audit Logging** — Complete change history
- **Import/Export** — Backup and restore capabilities

### Database Schema

The configuration system creates the following tables:

- `user_configurations` — System-wide settings
- `llm_providers` — LLM provider configurations
- `embedding_providers` — Embedding provider configurations
- `agent_configs` — Per-agent configurations
- `config_audit_log` — Change history
- `config_cache` — Frequently accessed config cache

### LLM Provider Types

| Type              | Base URL                              | API Key Required | Notes                           |
|-------------------|---------------------------------------|------------------|---------------------------------|
| openai            | https://api.openai.com/v1             | Yes              | GPT-4, GPT-3.5                  |
| openai_compatible | Custom                                | Optional         | vLLM, LocalAI, etc.             |
| ollama            | http://localhost:11434                | No               | Local inference                 |
| llamacpp          | http://localhost:8080                 | No               | GGUF models                     |
| zai               | https://open.bigmodel.cn/api/paas/v4  | Yes              | Zhipu AI GLM models             |
| minimax           | https://api.minimax.chat/v1           | Yes              | Requires group_id               |
| lemonade          | http://localhost:5000                 | No               | lemonade-server                 |

---

## Security

### Zero-Trust Architecture

The Heretek Swarm implements a comprehensive Zero-Trust security architecture in [`backend/heretek_swarm/security/`](backend/heretek_swarm/security/):

1. **Never Trust, Always Verify** — All inputs validated via Pydantic v2 models
2. **Defense in Depth** — Multiple security layers (guardrails, rate limiting, auth)
3. **Least Privilege** — Minimal agent capabilities
4. **Assume Breach** — Containment and isolation

### Security Layers

| Layer               | Component                                                         | Purpose                                                  | Status         |
|---------------------|-------------------------------------------------------------------|----------------------------------------------------------|----------------|
| Input Validation    | [`zero_trust.py`](backend/heretek_swarm/security/zero_trust.py) | 4-layer validation (Input, Context, Output, Audit)      | ✅ Operational |
| Adversarial Detection| [`adversarial.py`](backend/heretek_swarm/security/adversarial.py) | Prompt injection, jailbreak detection                  | ✅ Operational |
| Rate Limiting       | [`ddos_protection.py`](backend/heretek_swarm/security/ddos_protection.py) | Token bucket algorithm, DDoS protection                | ✅ Operational |
| Guardrails          | [`guardrails.py`](backend/heretek_swarm/security/guardrails.py) | Content filtering, output validation                    | ✅ Operational |
| Authentication      | [`gateway/auth.py`](backend/heretek_swarm/gateway/auth.py) | Bearer token auth, race condition fixed                  | ✅ Operational |
| Threat Detection    | [`threat_detection.py`](backend/heretek_swarm/security/threat_detection.py) | Anomaly scanning, pattern matching                     | ✅ Operational |
| Behavioral Baseline | [`behavioral_baseline.py`](backend/heretek_swarm/security/behavioral_baseline.py) | Normal behavior modeling, drift detection              | ✅ Operational |

### Security Features

- **Pydantic v2 Validation** — All inputs validated with `extra='forbid'`
- **UUID Validation** — 128-bit entropy validation for agent IDs
- **Content Size Limits** — DoS prevention
- **Injection Detection** — Pattern-based injection detection
- **PII Redaction** — PII detection and redaction
- **Token Validation** — Secure bearer token authentication

---

## Observability

The Heretek Swarm provides comprehensive observability through Prometheus metrics, distributed tracing, and structured logging. The implementation lives in:

- [`backend/heretek_swarm/observability/`](backend/heretek_swarm/observability/) — Prometheus metrics, alerting, tracing
- [`backend/heretek_swarm/infrastructure/otel/`](backend/heretek_swarm/infrastructure/otel/) — OpenTelemetry logging, metrics, tracing

### Metrics

**File:** [`backend/heretek_swarm/observability/prometheus_native.py`](backend/heretek_swarm/observability/prometheus_native.py)

The system exposes Prometheus-compatible metrics for monitoring autonomous 24/7 operation.

#### Agent Metrics (Gauges)

| Metric                         | Labels      | Description                      |
|--------------------------------|-------------|----------------------------------|
| `heretek_swarm_agents_total`   | `agent_type`| Total registered agents          |
| `heretek_swarm_agents_active`  | `agent_type`| Currently active agents          |
| `heretek_swarm_phi_score`      | `agent_id`  | Consciousness phi score (IIT)    |
| `heretek_swarm_free_energy`    | `agent_id`  | Free energy level (FEP)          |

#### Task Metrics (Counters)

| Metric                                | Labels                    | Description         |
|---------------------------------------|---------------------------|---------------------|
| `heretek_swarm_tasks_completed_total` | `agent_id`, `task_type`   | Tasks completed     |
| `heretek_swarm_tasks_failed_total`    | `agent_id`, `task_type`   | Tasks failed        |

#### Message Metrics (Counters)

| Metric                          | Labels                      | Description          |
|---------------------------------|-----------------------------|----------------------|
| `heretek_swarm_messages_total`  | `direction`, `message_type` | Messages processed   |

#### Consensus Metrics (Counters)

| Metric                                    | Labels                        | Description       |
|--------------------------------------------|-------------------------------|-------------------|
| `heretek_swarm_consensus_rounds_total`     | `consensus_type`, `outcome`   | Consensus rounds  |

#### API Metrics (Histogram + Counter)

| Metric                                         | Labels                              | Description       |
|-------------------------------------------------|-------------------------------------|-------------------|
| `heretek_swarm_api_request_duration_seconds`    | `method`, `endpoint`, `status`      | Request latency   |
| `heretek_swarm_api_requests_total`              | `method`, `endpoint`, `status`      | Total requests    |

#### Health Metrics (Gauges)

| Metric                         | Description               |
|--------------------------------|---------------------------|
| `heretek_swarm_health_score`   | Overall health (0-100)    |
| `heretek_swarm_uptime_seconds` | System uptime             |

#### Prometheus Integration

```python
from heretek_swarm.observability.prometheus_native import (
    increment_tasks_completed,
    record_api_request,
    export_prometheus,
)

# Record task completion
increment_tasks_completed(agent_id="alpha", task_type="analysis")

# Record API request
record_api_request(method="GET", endpoint="/api/agents", status=200, duration=0.05)
```

The API exposes metrics at `/metrics` for Prometheus scraping:

```bash
# Scrape configuration (prometheus.yml)
scrape_configs:
  - job_name: 'heretek-swarm'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Distributed Tracing

All requests include trace context propagation for end-to-end request tracking.

#### Trace Context

```
External Request → API Gateway → Steward → HeavySwarm Workflow
                         │
                         ▼
              Trace Context:
              - trace_id: generated per request
              - span_id: new per hop
              - All agents share trace_id
```

#### Tracing Headers

| Header            | Description                 |
|-------------------|-----------------------------|
| `X-Trace-ID`      | Unique trace identifier     |
| `X-Span-ID`       | Current span identifier     |
| `X-Parent-Span-ID`| Parent span identifier      |

#### Trace Storage

Traces are stored in memory and can be exported to:
- **Jaeger** — For distributed tracing visualization
- **Zipkin** — Alternative tracing backend
- **OTLP** — OpenTelemetry Protocol

The OpenTelemetry integration is configured in [`backend/heretek_swarm/infrastructure/otel/tracing.py`](backend/heretek_swarm/infrastructure/otel/tracing.py).

### Alerting

Alert rules should be configured in Prometheus/Alertmanager for critical conditions.

#### Recommended Alert Rules

```yaml
groups:
  - name: heretek_swarm
    rules:
      - alert: SwarmHealthCritical
        expr: heretek_swarm_health_score < 50
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Heretek Swarm health below 50%"

      - alert: NoActiveAgents
        expr: sum(heretek_swarm_agents_active) == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "No active agents in swarm"

      - alert: HighAgentFailureRate
        expr: rate(heretek_swarm_tasks_failed_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High task failure rate"

      - alert: LowCollectivePhi
        expr: avg(heretek_swarm_phi_score) < 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Collective consciousness Phi below threshold"

      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(heretek_swarm_api_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API p95 latency above 1 second"
```

### Health Endpoints

| Endpoint                          | Method | Description                        |
|-----------------------------------|--------|------------------------------------|
| `/health`                         | GET    | API health check                   |
| `/health/live`                    | GET    | Kubernetes liveness probe          |
| `/health/ready`                   | GET    | Kubernetes readiness probe         |
| `/metrics`                        | GET    | Prometheus metrics endpoint        |
| `/api/agents`                     | GET    | List all agents with status        |
| `/api/agents/{agent_id}`          | GET    | Get specific agent details         |
| `/api/agents/{agent_id}/metrics`  | GET    | Agent performance metrics          |

### Metrics Categories

| Category     | Metrics                                                                                      | Description               |
|--------------|----------------------------------------------------------------------------------------------|---------------------------|
| System       | uptime_seconds, total_restarts, total_failures, memory_usage_bytes, cpu_percent, active_agents | System-level metrics      |
| Agent        | messages_processed_total, messages_failed_total, average_response_time_ms, health_score, mailbox_size | Per-agent metrics         |
| Workflow     | workflows_completed_total, workflows_failed_total, average_duration_ms, phase_durations_ms     | Workflow metrics          |
| Consensus    | votes_collected_total, consensus_reached_total, red_flags_raised_total, average_confidence     | Consensus metrics         |
| RAG          | documents_indexed_total, queries_executed_total, average_retrieval_time_ms, chunks_retrieved_total | RAG metrics               |
| Consciousness| phi_score, free_energy, gwt_score, ast_competence                                            | Consciousness metrics     |

---

## Monitoring Setup

### Docker Compose Monitoring Stack

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.45.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:10.0.0
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana

  alertmanager:
    image: prom/alertmanager:v0.26.0
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'heretek-swarm'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'nats'
    static_configs:
      - targets: ['nats:8222']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']
```

### AlertManager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'email'

receivers:
  - name: 'email'
    email_configs:
      - to: 'alerts@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'

  - name: 'slack'
    slack_configs:
      - channel: '#alerts'
        api_url: 'https://hooks.slack.com/services/XXX'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname']
```

### Grafana Dashboard

Import the Heretek Swarm dashboard (ID: 1860) or create custom panels:

**Recommended Panels:**
1. Swarm Health Score (gauge)
2. Active Agents (stat)
3. Tasks Completed/Failed (time series)
4. API Latency p50/p95/p99 (histogram)
5. Consensus Success Rate (time series)
6. Consciousness Phi Score (time series)
7. Free Energy Level (time series)
8. Message Throughput (time series)

---

## References

- [`PRIME_DIRECTIVE.md`](../PRIME_DIRECTIVE.md) — 23-agent vision and architecture
- [`docs/API_ENDPOINTS.md`](API_ENDPOINTS.md) — API reference
- [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) — Deployment guide
- [`docs/MONITORING.md`](MONITORING.md) — Prometheus, Loki, alerting setup
- [`docs/AGENTS.md`](AGENTS.md) — Complete agent documentation
- [`docs/CORE_ACTORS.md`](CORE_ACTORS.md) — Core actor reference
- [`docs/AGENT_ARCHITECTURE.md`](AGENT_ARCHITECTURE.md) — Agent architecture overview
- [`docs/AGENT_REFERENCE.md`](AGENT_REFERENCE.md) — Agent capabilities reference
- [`docs/architecture/emergent-intelligence.md`](architecture/emergent-intelligence.md) — Consciousness framework
- [`docs/architecture/actors-system.md`](architecture/actors-system.md) — Actor system design
- [`docs/architecture/memory-system.md`](architecture/memory-system.md) — Memory system design
- [`docs/architecture/observability.md`](architecture/observability.md) — Observability design

---

**License:** Apache 2.0
**GitHub:** [Heretek-AI/heretek-swarm](https://github.com/HeretekAI/heretek-swarm)
