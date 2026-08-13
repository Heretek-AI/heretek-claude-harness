# Tier 1 Core Triad Rebuild — Design

**Date:** 2026-06-24
**Status:** Approved (brainstorming complete, awaiting user spec review)
**Branch target:** `rebuild/tier-1-mvp` (branched from `main`)
**Author:** Brainstorming session output

---

## 1. Context and motivation

The `heretek-swarm` repo carries 180k LoC of Python across 465 files implementing the "Collective" — a 23-agent sovereign AI swarm with consciousness-inspired governance, NATS event mesh, cognee/mem0 memory, LangGraph orchestration, and a React 19 dashboard.

**Current state (audit-verified):**

- System cannot boot — smoke import `from heretek_swarm.collective import orchestrator` errors.
- 6 critical issues + 14 moderate per audit: 2 wizard infrastructure 500s, 4 auth bypass candidates, 250 backend-only routes with no frontend wiring, `/api/autonomous/*` vs `/autonomous/*` prefix mismatch.
- 17 security findings: hardcoded credentials, eval/exec references, missing auth middleware on 4 endpoints.
- 8 observability gaps: `print()` in production code, missing structured logging, incomplete trace coverage.
- 5 architecture-drift findings: modules >1000 LoC (God-classes — e.g. `runtime/main_loop.py` 1740 LoC, `actors/perceiver/agent.py` 1587 LoC).
- Top non-Tier-1 files in the 1100-1700 LoC range: 16+ actor `agent.py` files, `api/consensus.py`, `consciousness/fep_active_inference.py`, `api/websockets.py`, `gateway/nats_event_mesh.py`, `config/crud.py`, `collective/learning.py`, `rag/strategies.py`.
- Already mid-cleanup: phases 0/1/2/2a.3/3 completed (deleted `swarms` framework, `opik_compat`, `llm/providers/`, `autonomous_runtime`, 5 observability routers, 3 wrappers, 1 plugin).
- 26 pytest tests for backend, vitest + Playwright for frontend. Coverage is thin.

**Prime Directive** (`README.md`) commits the swarm to a 23-agent sovereign society with unbounded autonomy, organic evolution, consciousness-inspired governance (GWT/AST/IIT/FEP), and persistent self-healing operation. This is effectively AGI-aspirational.

**Rebuild decision:** scope the MVP to the Tier 1 Core Triad (Steward/Alpha/Beta/Charlie) — the governance heart of the doctrine — and rebuild from a clean module. Defer Tiers 2-6, consciousness layers, autonomous self-healing, multi-user auth, and the rest. Use the doctrinal infrastructure (NATS/Postgres/Redis/Qdrant/cognee/mem0/Docker) and LangGraph orchestration. Branch-and-greenfield so the 180k LoC of old code stays untouched until the MVP works.

---

## 2. Project structure

### Branch and module

- **Branch:** `rebuild/tier-1-mvp` (from `main`)
- **New module root:** `backend/tier1/` — clean, sibling to existing `heretek_swarm/`. Old code stays untouched.
- **Cherry-pick from `heretek_swarm/` when needed:** Docker Compose service definitions, LangGraph patterns, pydantic-ai + MiniMax wiring, env/config conventions.
- **Leave behind (no rewrite):** all 19 non-Tier-1 actor packages, `consciousness/`, `fep_active_inference.py`, IIT/FEP theoretical code, `autonomous_runtime/`, `agent_workspace/`, wizard / provisioning / RAG / emergent-intelligence code, 240+ of the 250 backend routes.

### Layout

```
backend/tier1/
  pyproject.toml
  tier1/
    __init__.py
    config.py
    llm/
      garage.py
      prompts.py
    deliberation/
      graph.py
      state.py
      nodes/
        steward.py
        alpha.py
        beta.py
        charlie.py
        consensus.py
    events/
      nats_client.py
      channels.py
    persistence/
      postgres.py
      redis.py
    memory/
      cognee_writer.py
      mem0_backend.py
    observability/
      trace_ai.py
    api/
      app.py
      routes/
        deliberations.py
        ws.py
        health.py
      schemas.py
    dashboard/
      serve.py
      bridge.py
  tests/
    unit/
    integration/
    e2e/
  docker/
    docker-compose.yml
    Dockerfile.api
```

### Frontend

- `swarm-dashboard/` (existing) — keep React 19 + Vite 8 + Tailwind 4 + xyflow + zustand + Vercel AI SDK.
- Add routes: `/` (new deliberation form), `/deliberations` (list), `/deliberations/:id` (live view).
- Drop pages not relevant to Tier 1 (autonomous, wizard, settings, plugin manager, etc.).

### Reference repos integrated into the workflow

- **desloppify** — added as CI gate + pre-commit. Catches dead code, oversized files (>500 LoC override), quality regressions.
- **lobehub patterns** — reference for the Deliberation view layout (agent cards + reasoning stream + history). Not embedded; informs component shape.
- **thClaws "one binary" pattern** — dev mode runs `python -m tier1 serve` and serves API + WS + dashboard. In prod, still Docker Compose.
- **kweaver-core TraceAI** — pattern reference for our `observability/trace_ai.py` (structured per-deliberation audit trace).

---

## 3. Components

### Naming

Code calls them "actors", doctrine calls them "agents". MVP uses **agents** — the doctrinal term and what users see on the dashboard.

### Core agents (4)

**Steward** — orchestrator, owner of the Tribunal loop. Deterministic (no LLM call).
- Receives problem from API/WS.
- Dispatches Alpha → Beta → Charlie sequentially. Each sees all prior reasoning in the round.
- Tallies verdicts, decides consensus.
- On no consensus: emits `steward_feedback` event with concrete feedback and starts another round (max 3).
- Emits final verdict or `no-consensus`.
- Persists state after every node transition.
- Publishes every event on NATS for audit + WS broadcast.

**Alpha** — analysis. Logical deconstruction. LLM-call node.
- Input: problem + prior round context (if any) + user interjections.
- Calls MiniMax (via `ModelGarage`) with Alpha system prompt.
- Streams reasoning tokens to dashboard in real time.
- Emits structured `AgentVerdict`.

**Beta** — validation. Reality-check + blast-radius. LLM-call node.
- Input: problem + Alpha's reasoning + prior-round context + user interjections.
- Calls MiniMax, streams reasoning, emits `AgentVerdict`.

**Charlie** — challenge. Adversarial review + defense counsel. LLM-call node.
- Input: problem + Alpha's reasoning + Beta's reasoning + prior-round context + user interjections.
- Calls MiniMax, streams reasoning, emits `AgentVerdict`.

### Core types

```python
from typing import Literal, TypedDict
from pydantic import BaseModel, Field

class AgentVerdict(BaseModel):
    agent: Literal["steward", "alpha", "beta", "charlie"]
    position: Literal["approve", "reject", "challenge", "abstain"]
    confidence: float = Field(ge=0.0, le=1.0)
    concerns: list[str]
    reasoning: str

class FinalVerdict(BaseModel):
    decision: Literal["approved", "rejected", "needs-revision", "no-consensus"]
    summary: str
    votes: dict[str, AgentVerdict]   # alpha/beta/charlie -> verdict
    rounds: int

class DeliberationEvent(BaseModel):
    seq: int
    ts: float
    kind: Literal[
        "started", "alpha_thinking", "alpha_verdict",
        "beta_thinking", "beta_verdict",
        "charlie_thinking", "charlie_verdict",
        "steward_feedback", "user_interjection",
        "token", "consensus_reached", "consensus_failed", "completed",
    ]
    payload: dict

class DeliberationState(TypedDict):
    deliberation_id: str
    problem: str
    user_id: str
    round: int
    max_rounds: int
    alpha_verdict: AgentVerdict | None
    beta_verdict: AgentVerdict | None
    charlie_verdict: AgentVerdict | None
    feedback: list[str]
    events: list[DeliberationEvent]
    final_verdict: FinalVerdict | None
```

### Infrastructure components

| Component | Role |
|-----------|------|
| **`ModelGarage`** (`llm/garage.py`) | pydantic-ai Model wrapper, MiniMax primary, Anthropic/OpenAI/local fallbacks. Circuit breaker: 3 fails/60s → mark provider down for 5min |
| **LangGraph Tribunal** (`deliberation/graph.py`) | State machine: `steward_dispatch → alpha → (beta ‖ charlie) → steward_tally → {finalize \| feedback_round}`. Conditional edges handle consensus vs loop |
| **NATS event mesh** (`events/nats_client.py`) | Doctrinal transport. JetStream subject `tier1.deliberation.{id}.events`. Durable audit trail |
| **Postgres** (`persistence/postgres.py`) | `deliberations` table (id, problem, user_id, status, final_verdict_json, events_json, created_at, updated_at). State after every node transition |
| **Redis** (`persistence/redis.py`) | Hot-path working memory: current `DeliberationState` for active session. TTL = 1h after last update |
| **Qdrant** (`memory/`) | Vector memory: each `FinalVerdict` embedded and indexed by problem similarity. Advisory; "have we seen this before?" |
| **cognee writer** (`memory/cognee_writer.py`) | Knowledge graph: problem → verdict → concerns. Used to surface patterns across deliberations |
| **mem0 backend** (`memory/mem0_backend.py`) | Episodic memory: per-user history surfaced to agents as context |
| **TraceAI audit** (`observability/trace_ai.py`) | Per-deliberation structured trace: every node call, prompt, token count, verdict, latency. Inspired by kweaver-core |

### Dashboard components

| Component | Role |
|-----------|------|
| **`DeliberationPage`** (`/deliberations/:id`) | Main MVP view. Composes `AgentGraph` + `ReasoningStream` + `InterjectInput` |
| **`AgentGraph`** (xyflow) | Steward at center, Alpha/Beta/Charlie as children. Active node pulses while reasoning streams. Completed nodes show verdict badge |
| **`ReasoningStream`** | Per-agent collapsible panels, token-by-token append, persists after round completes |
| **`InterjectInput`** | Text box visible during deliberation. Submit appends to feedback; next round's agents see it |
| **`DeliberationList`** (`/deliberations`) | Past deliberations, newest first |
| **`NewDeliberation`** (`/`) | Problem form → POST → redirect to live view |
| **`WSBridge`** | Hooks FastAPI WebSocket into Zustand store. Single store for all deliberation state |

### Out of scope for MVP (deferred)

- Multi-user auth (single user assumed)
- Multi-deliberation concurrency per user (one per WS connection)
- The other 19 agents (Tier 2-6)
- Consciousness metrics / IIT / FEP
- The skill system (skills stay as project conventions but not loaded dynamically)
- Auto-scaling / self-healing (operator-driven; doctrine for later)

---

## 4. Data flow

### Lifecycle

```
USER ─POST /api/deliberations {problem}─> API
API  ─create state (round=0)────────────> Postgres + Redis
API  ─201 {id}──────────────────────────> USER
USER ─WS /ws/deliberations/{id}─────────> API
API  ─replay persisted events───────────> USER
API  ─invoke(LangGraph.run, state)──────> LangGraph
LangGraph ─started event───────────────> NATS ────────────────> WS ────> USER
LangGraph ─alpha node──────────────────> Alpha
Alpha ─alpha_thinking event────────────> NATS ────────────────> WS ────> USER
Alpha ─[token events]──────────────────> NATS ────────────────> WS ────> USER
Alpha ─alpha_verdict───────────────────> NATS ────────────────> WS ────> USER
LangGraph ─persist─────────────────────> Postgres
LangGraph ─beta node───────────────────> Beta (sees Alpha's reasoning)
Beta  ─[same shape: thinking → tokens → verdict]──> NATS ──> WS ──> USER
LangGraph ─charlie node────────────────> Charlie (sees Alpha + Beta)
Charlie ─[same shape]────────> NATS ──> WS ──> USER
LangGraph ─steward_tally───────────────> Steward (deterministic)
  ├── consensus → consensus_reached + completed + FinalVerdict
  ├── no consensus, round < max → steward_feedback → round+1 → loop (back to Alpha)
  └── round == max → consensus_failed + completed + no-consensus

USER ─POST /api/deliberations/{id}/interject {text}─> API
API ─append to feedback, emit user_interjection event──> NATS ────> WS
                                                  ↓
                              (next round's agents read feedback)
```

### Event types

All events conform to `DeliberationEvent`. Sequence numbers monotonic per deliberation.

| `kind` | Payload | Fires when |
|--------|---------|-----------|
| `started` | `{problem}` | LangGraph run begins |
| `alpha_thinking` | `{seq}` | Alpha starts |
| `alpha_verdict` | `AgentVerdict` | Alpha done |
| `beta_thinking` | `{seq}` | Beta starts |
| `beta_verdict` | `AgentVerdict` | Beta done |
| `charlie_thinking` | `{seq}` | Charlie starts |
| `charlie_verdict` | `AgentVerdict` | Charlie done |
| `steward_feedback` | `{round, feedback_text}` | Steward sees no consensus |
| `user_interjection` | `{text}` | User posts interjection |
| `token` | `{agent, token, seq}` | LLM token (high-frequency) |
| `consensus_reached` | `{decision, summary}` | 2-of-3 or all 3 agree |
| `consensus_failed` | `{reason}` | No agreement after max rounds |
| `completed` | `FinalVerdict` | Deliberation done |

`token` events are batched on the WS at ~30 Hz (one batched frame every ~33 ms, max 50 tokens per frame). NATS gets each token event raw for audit. WS batching drops intermediate tokens when a frame fills; the next frame carries whatever has accumulated.

### HTTP protocol

```
POST /api/deliberations
  body: { problem: str }
  → 201 { id: str, status: "started" }

GET /api/deliberations/{id}
  → 200 { id, problem, status, final_verdict?, events: [...] }
  status ∈ {"running", "completed", "failed"}

POST /api/deliberations/{id}/interject
  body: { text: str }
  → 204

GET /api/deliberations?limit=20
  → 200 [{ id, problem, status, created_at }]

GET /health
  → 200 { status: "ok", components: { postgres, redis, nats, qdrant, cognee, mem0 } }
```

### WebSocket protocol

```
WS /ws/deliberations/{id}
  Server → Client: { kind: "event", event: DeliberationEvent }
  Server → Client: { kind: "replay_done", count: N }
  Client → Server: { kind: "ping" }
  Server → Client: { kind: "pong" }
  Server → Client: { kind: "error", code: str, message: str }
```

On connect, server replays persisted events from Postgres in seq order, then live-streams new events. Client treats replay + live as one stream.

### Consensus rule

```
if all 3 approve AND min(confidence_alpha, confidence_beta, confidence_charlie) >= 0.7
  → approved (FinalVerdict.decision = "approved", summary written by Steward from verdicts)
if 2-of-3 approve AND charlie position != "challenge" → approved
if 2-of-3 reject → rejected
if charlie "challenge" with confidence > 0.7 → always needs-revision
if round >= max_rounds → no-consensus
else → feedback loop (Steward writes concrete feedback, next round)
```

Max rounds = 3, configurable via env. The first rule (unanimous high-confidence approval) is the "gold path"; the 2-of-3 rule handles partial agreement; Charlie's challenge is a hard veto at high confidence.

---

## 5. Error handling

### Principles

1. Persist aggressively — every node transition writes to Postgres. Crashes are recoverable from the `events` table.
2. Fail loud, never silent. Structured logging with context.
3. Idempotent replay — re-running LangGraph on persisted state produces the same outcome.
4. Every error has a UI representation.
5. Zero-trust input — every user input validated, length-limited, sanitized.

### LLM failures

| Failure | Response | Recovery |
|---------|----------|----------|
| MiniMax 429/503 | Fallback chain: Anthropic → OpenAI → local. Circuit breaker: 3 fails/60s → mark provider down for 5min | Steward emits `consensus_failed` reason `llm_unavailable`; auto-retry next request |
| Content-filter rejection | Single retry with sanitized re-prompt | Second fail → `abstain` with reason `content_filtered`, confidence 0 |
| Timeout (>60s) | Cancel, retry once | If still fails → `abstain` |
| Malformed verdict (missing fields) | Retry once with corrective format prompt | If still fails → `abstain` + log full output |

### Infrastructure failures

| Failure | Response | Recovery |
|---------|----------|----------|
| Postgres down | Buffer writes in memory; exponential backoff (max 30s) | Queue fills or 30s → fail deliberation `infra_unavailable`, write to local fallback file, alert operator |
| Redis down | Continue without hot cache, Postgres-only | On recovery, rebuild hot cache from Postgres |
| NATS down | Buffer events in memory (capped 10k per deliberation) | On recovery, flush. Overflow → fail-fast and persist error |
| Qdrant/cognee/mem0 down | Log warning, continue without memory layer | Advisory; dashboard shows "memory degraded" footer chip |
| LangGraph node throws | LangGraph built-in retry (1 attempt), then `failed` status | Persist partial state + events; user can retry from last persisted round |

### Consensus failures

| Failure | Response |
|---------|----------|
| No consensus after max rounds | `consensus_failed` event with all 3 verdicts + summary. `FinalVerdict.decision = "no-consensus"`. Dashboard shows clearly. User can start new deliberation. |

### User-facing / transport

| Failure | Response |
|---------|----------|
| WS disconnect mid-deliberation | Mark subscriber inactive. Deliberation continues. On reconnect, replay from last persisted event. |
| Problem text > 5000 chars | 400 with field-level error |
| Interjection > 2000 chars | 400 with field-level error |
| Dashboard build fails | API serves minimal fallback HTML with raw JSON state |

### Dashboard error states

| State | UI |
|-------|----|
| `running` | Graph pulsing, reasoning live, interject enabled |
| `completed` | Verdict card prominent, full reasoning archive collapsed |
| `failed` | Red banner: "Deliberation failed: {reason}", retry button |
| `llm_unavailable` | Amber banner: "Primary LLM unavailable, using fallback" |
| `memory_degraded` | Footer chip |
| `infra_unavailable` | Red full-page: "Backend unavailable, retry in {n}s" |

### Explicitly NOT handled in MVP

- Multi-user concurrent deliberation on same id (lock per deliberation; 409 if contended)
- Cross-deliberation dependencies
- Audit log retention policies (keep forever for MVP)
- Per-user rate limiting (reverse proxy in prod)
- Auto-scaling / self-healing

---

## 6. Testing

### Approach

TDD from scratch on the greenfield module. Target 80%+ line, 70%+ branch on `backend/tier1/`. The 180k LoC of old code stays untested (out of scope).

### Layers

**Unit tests** (`backend/tier1/tests/unit/`)
- `test_llm_garage.py` — fallback chain, circuit breaker
- `test_prompts.py` — load, validate, no secret leakage
- `test_alpha.py`, `test_beta.py`, `test_charlie.py` — prompt → verdict shape, mocked LLM
- `test_steward.py` — consensus rule, feedback generation, round counter
- `test_state.py` — Pydantic models, validation, serialization
- `test_nats_client.py` — publish, subscribe, JetStream durability
- `test_postgres.py`, `test_redis.py` — CRUD, hot cache
- `test_ws_protocol.py` — replay-from-disk, live-stream, ping/pong

**Integration tests** (`backend/tier1/tests/integration/`)
- `test_deliberation_happy_path.py` — 1-round approval
- `test_deliberation_no_consensus.py` — 3-round feedback → no-consensus
- `test_deliberation_with_interjection.py` — user interjects between rounds
- `test_llm_failover.py` — MiniMax 503 → fallback
- `test_persistence_crash_recovery.py` — kill API mid-deliberation, restart, resume
- `test_nats_audit_trail.py` — every event published, durable

**E2E** (`backend/tier1/tests/e2e/`)
- `test_e2e_docker_compose_up.py` — `/health` all green
- `test_e2e_full_deliberation.py` — POST, open WS, all events stream, final verdict received

**Frontend** (`swarm-dashboard/tests/`)
- Component tests (Vitest + Testing Library) for `AgentGraph`, `ReasoningStream`, `InterjectInput`, `DeliberationList`
- WebSocket hook tests with mock WS
- Zustand store tests

**E2E browser** (Playwright)
- `deliberation.spec.ts` — submit, watch stream, see verdict, interject mid-flight
- Screenshot per agent state for visual regression

### Coverage targets

- `backend/tier1/` — 80%+ line, 70%+ branch
- `swarm-dashboard/src/deliberations/` — 70%+ line
- Critical paths (consensus rule, LangGraph transitions, LLM failover, WS replay) — 100% line

### Discipline

- **Mock only at the LLM boundary.** Mock MiniMax (deterministic, free). Real Postgres/Redis/NATS in integration tests via docker-compose test profile.
- **Assert behavior, not implementation.** "Given problem X, Alpha emits verdict with position=approve and confidence > 0.5" — not "Alpha called pydantic-ai with these args".
- **Coverage gates in CI.** PR fails below 80% backend, 70% frontend.
- **`desloppify` runs in CI** on every PR. Fails build on dead code or files >500 LoC without explicit override.
- **Snapshot tests only for stable, intentional output** (e.g., Pydantic JSON schema). No screenshot-everything.

### Explicitly NOT tested

- LLM prompt quality (no eval framework — too costly for MVP)
- Cross-deliberation KG queries (Qdrant/cognee advisory; tested only for "doesn't crash")
- Performance / load
- Visual pixel regression

---

## 7. Decisions log

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | MVP scope = Tier 1 Core Triad | Governance heart of doctrine. Fastest to working. |
| 2 | Multi-turn deliberation dashboard | Live Core Triad debate + user interject |
| 3 | Full prod stack preserved (NATS/Postgres/Redis/Qdrant/cognee/mem0/Docker) | Doctrinal infra; "prune later" means later, not now |
| 4 | Branch-and-greenfield | Clean rebuild blast radius. Old 180k LoC untouched. |
| 5 | Full dashboard, Tier-1 wired up | Lobehub pattern reference. xyflow graph + reasoning stream + interject + history. |
| 6 | MiniMax primary LLM | User-specified. Anthropic/OpenAI/local as pydantic-ai fallbacks. |
| 7 | Approach A: LangGraph substrate | Already integrated and tested. Tribunal loop = conditional edges. Streaming = LangGraph stream(). NATS remains doctrinal transport. |
| 8 | desloppify as CI gate | Catches dead code during the cut. |
| 9 | Reference repos surveyed | 17 surveyed; desloppify/lobehub/thClaws/kweaver folded into workflow. PraisonAI/openclaude/oh-my-agent/mateclaw as fallback substrates if picks fail. RedBox/altimate-code/datachain/holaOS/Autonomous-Agents skipped (wrong domain). |
| 10 | Naming: "agents" not "actors" | Doctrinal term. What users see. |
| 11 | Consensus rule: unanimous high-confidence OR 2-of-3 with Charlie override | Maps to doctrine ("Challenge = defense counsel"). Unanimous approval at >=0.7 confidence is the gold path; otherwise 2-of-3 with Charlie high-confidence challenge as hard veto. |
| 12 | Max rounds = 3 | Configurable. Bounds feedback-loop cost. |

---

## 8. Open questions / deferred

- **Auth**: deferred. Single user for MVP. Add behind reverse proxy later.
- **Multi-deliberation concurrency**: deferred. One per WS for MVP.
- **Tiers 2-6 agents**: deferred to subsequent specs.
- **Consciousness / IIT / FEP layers**: deferred. Doctrine for later.
- **Skill system dynamic loading**: deferred.
- **Self-healing / auto-scaling**: deferred.
- **Performance / load testing**: deferred.
- **Cross-deliberation knowledge surfacing**: deferred.

---

## 9. Implementation order (preview — final order in writing-plans skill)

1. `backend/tier1/` skeleton + pyproject + docker-compose + `/health`
2. Pydantic models + state.py + tests
3. ModelGarage (LLM wrapper with fallbacks) + tests
4. NATS client + Postgres + Redis + tests
5. Agent nodes (alpha, beta, charlie) + tests (mocked LLM)
6. Steward + consensus rule + feedback loop + tests
7. LangGraph Tribunal state machine + integration tests
8. FastAPI routes + WebSocket + replay logic + integration tests
9. Dashboard DeliberationPage + AgentGraph + ReasoningStream + InterjectInput
10. Dashboard WS bridge + Zustand store
11. E2E docker-compose test profile + Playwright
12. desloppify CI gate + coverage gates
13. Documentation + smoke run + verify boot

Estimated effort: 1–2 weeks for one engineer to a working MVP.
