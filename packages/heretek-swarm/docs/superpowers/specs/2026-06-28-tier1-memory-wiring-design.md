# Tier 1 Memory Wiring — Design Spec

**Date:** 2026-06-28
**Status:** Approved

## Context

The Tier 1 Memory Foundation spec (2026-06-25) built `MemoryBackend` plus
the three underlying stores (Qdrant, Redis, PostgreSQL) and NATS hooks.
That foundation is implemented and the existing test files pass, but it
is not wired into the deliberation graph: every Core Triad run starts
from zero context, and nothing produced by a run feeds back to the
foundation. This sub-project closes the loop by recalling relevant past
deliberations before each agent turn and storing each verdict as it
is produced.

## Goals

1. Each agent (alpha, beta, charlie) recalls up to 3 relevant past
   deliberations before streaming tokens.
2. Each agent's verdict is stored as a `MemoryEntry` after the verdict
   is parsed.
3. `Tribunal` accepts an optional `memory: MemoryBackend | None`
   parameter. When `None` the graph behaves exactly as before — the
   wiring is fully backward compatible.
4. Memory failures never break a deliberation. `store()` exceptions
   are logged and swallowed; missing recall is treated as no
   additional context.
5. Coverage stays ≥ 80%.

## Non-goals

- Wiring into `create_app()` lifespan (separate change — needs the
  full Postgres/Redis/Qdrant stack running, which the current test
  rig doesn't have).
- REST endpoints for memory (already excluded from the foundation).
- Cognee knowledge graph and mem0 semantic layers (foundation
  sub-projects B and C).
- Refreshing the memory foundation's missing test files for
  `qdrant_store.py`, `redis_cache.py`, `cognee_store.py`,
  `prefetcher.py`, `mem0_store.py` (orthogonal cleanup).

## Architecture

`Tribunal.__init__` gains one new optional parameter:

```python
class Tribunal:
    def __init__(
        self,
        settings: Settings,
        garage: ModelGarage,
        sink: EventSink | None = None,
        memory: MemoryBackend | None = None,
    ) -> None:
        ...
        self.memory = memory
```

The four node factories (`make_alpha_node`, `make_beta_node`,
`make_charlie_node`, `make_steward_node`) take one new optional
parameter that is forwarded to `run_agent` via `functools.partial`.
`run_agent` itself gains one new optional `memory` parameter.

**Recall (before the agent streams tokens):**

```python
if memory is not None:
    try:
        recall = await memory.search(state["problem"], top_k=3)
    except Exception:  # noqa: BLE001
        log.warning("memory.recall_failed", agent=agent, exc_info=True)
        recall = []
    if recall:
        recall_block = "PAST DELIBERATIONS ON SIMILAR TOPICS:\n" + "\n".join(
            f"- [{r.deliberation_id}] {r.agent}: {r.content[:200]}"
            for r in recall
        )
        user = user + "\n\n" + recall_block
```

Recall is appended **after** the existing prompt block (problem +
feedback + prior verdicts), so it functions as ambient context rather
than overriding structured inputs.

**Store (after the verdict is parsed):**

```python
if memory is not None:
    entry = MemoryEntry(
        content=verdict.reasoning,
        memory_type=MemoryType.semantic,
        source="deliberation",
        deliberation_id=state["deliberation_id"],
        agent=agent,
        metadata={
            "position": verdict.position,
            "confidence": verdict.confidence,
            "round": state.get("round", 0),
        },
    )
    try:
        await memory.store(entry)
    except Exception:  # noqa: BLE001
        log.warning("memory.store_failed", agent=agent, exc_info=True)
```

`MemoryBackend.store` already writes to Qdrant (vector), Redis
(ephemeral), and Postgres (lineage) and is best-effort on Qdrant /
Redis. Catching at the call site covers Postgres failure too — same
contract: never break a deliberation.

## Components touched

| File | Change |
|---|---|
| `tier1/deliberation/nodes/_base.py` | Add `memory` parameter to `run_agent`; recall + store blocks |
| `tier1/deliberation/nodes/alpha.py` | `make_alpha_node(garage, sink=None, memory=None)` |
| `tier1/deliberation/nodes/beta.py` | Same |
| `tier1/deliberation/nodes/charlie.py` | Same |
| `tier1/deliberation/nodes/steward.py` | Same (steward does not store; recall only if useful — leave storing to the verdict agents, no change beyond signature) |
| `tier1/deliberation/graph.py` | `Tribunal.__init__` accepts `memory`; `_build` forwards to all four factories |
| `tests/unit/test_memory_wiring.py` (new) | Recall injection, store call, no-memory backward compat, store failure tolerated |

## Data flow

```
deliberation starts
   │
   ▼
alpha_node(state, garage, memory)
   │
   ├─ recall = memory.search(problem, top_k=3)  ← best-effort
   ├─ inject recall into user prompt
   ├─ stream tokens → verdict
   └─ memory.store(MemoryEntry(reasoning, semantic))  ← best-effort
   │
   ▼
beta_node / charlie_node  (same shape, same hooks)
   │
   ▼
steward_node  (no memory changes — tally only)
   │
   ▼
END
```

## Error handling

- `memory.search` raises → log, treat as empty recall, proceed.
- `memory.store` raises → log, swallow. The verdict already lives on
  the deliberation state in Postgres via the existing event sink path;
  memory duplication failure is non-fatal.
- `memory is None` → all hooks skipped. Old call sites (existing
  tests, route handlers that don't pass memory) keep working
  unchanged.

## Testing

`tests/unit/test_memory_wiring.py`:

| Test | Verifies |
|---|---|
| `test_run_agent_recalls_before_streaming` | With memory attached, `memory.search` is awaited once and top-k entries are injected into the user prompt |
| `test_run_agent_stores_after_verdict` | `memory.store` called with a `MemoryEntry` whose `content == verdict.reasoning`, `agent == agent_name`, `deliberation_id` matches state |
| `test_run_agent_without_memory_is_unchanged` | `memory=None` ⇒ no search, no store, no exception, output matches old behavior |
| `test_run_agent_search_failure_does_not_break` | `memory.search` raises ⇒ verdict still produced |
| `test_run_agent_store_failure_does_not_break` | `memory.store` raises ⇒ verdict still produced |
| `test_tribunal_accepts_memory` | `Tribunal(memory=...)` constructs without error and forwards to nodes |
| `test_tribunal_without_memory_default` | `Tribunal()` (no memory) constructs and runs |

All existing tests must continue to pass. Coverage of touched modules
must remain ≥ 80%.

## Implementation order

1. Add `memory` parameter to `run_agent` and the four `make_*_node`
   factories. Default `None`. No behavioral change yet.
2. Add recall + store blocks inside `run_agent`. Behind `if memory is
   not None:` so default behavior is identical.
3. Extend `Tribunal.__init__` and `_build` to forward `memory`.
4. Write `tests/unit/test_memory_wiring.py` with mocked `MemoryBackend`.
5. Run full suite, verify coverage ≥ 80%, all green.

## Dependencies

None new. `MemoryBackend`, `MemoryEntry`, `MemoryType` are already
importable from `tier1.memory`. Logging: use `structlog.get_logger(__name__)`
at module top of `_base.py` (matches `tier1.observability` convention).
No new env vars.
