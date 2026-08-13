# Tier 1 Coverage Scrub — Design Spec

**Date:** 2026-06-28
**Status:** Approved

## Context

This session shipped four slices on `backend/tier1/`:
- LLM provider wiring (`garage.py`, `config.py`, `pyproject.toml`)
- Memory wiring (4 node factories + `_base.run_agent` + `Tribunal` + new test file)
- Cognee → Kùzu rewrite (`cognee_store.py`, `MemoryBackend.__init__`/`.store()`, 3 test files)
- Observability test coverage (3 test files, no production changes)

Coverage on the touched modules, scoped to the existing tests:

| Module | Coverage |
|---|---|
| `deliberation/nodes/_base.py` | 83% — meets ≥ 80% gate |
| `memory/cognee_store.py` | 86% — meets ≥ 80% gate |
| `deliberation/graph.py` | 53% — `Tribunal.run()` and `Tribunal.stream()` uncovered |
| `memory/__init__.py` | 49% — `MemoryBackend.store()` tier branches uncovered |

`graph.py` and `memory/__init__.py` are below the gate. Both are touched
this session (memory wiring added the `memory` param to `Tribunal`;
Cognee → Kùzu added the `cognee` field to `MemoryBackend`). Coverage
gaps lie on the production paths we introduced.

## Goals

1. `tier1/deliberation/graph.py` ≥ 80% covered.
2. `tier1/memory/__init__.py` ≥ 80% covered.
3. No production code changes — tests only.
4. All existing tests continue to pass.
5. Full suite stays ≥ 80% on touched modules.

## Non-goals

- Coverage on `access_patterns.py`, `prefetcher.py`, `mem0_store.py`,
  `nats_client.py`, `dashboard/`, `routes/health.py` — not touched
  this session.
- Coverage on the underlying stores (`qdrant_store.py`, `redis_cache.py`,
  `postgres_store.py`) — separate concern, deferred.
- Production code changes.

## Architecture

Two test files: one new, one extended. No production code touched.

### A. New: `tests/unit/test_deliberation.py`

Covers `Tribunal.run()` (lines 88-100 of `graph.py`) and
`Tribunal.stream()` (lines 102-142).

Tests:

1. `test_tribunal_run_returns_final_state` — invoke
   `Tribunal(settings, garage).run(state)` with a stub garage that
   yields a verdict JSON for each agent. Assert the returned
   `DeliberationState` has `status == "completed"` and a non-None
   `final_verdict`.

2. `test_tribunal_run_records_metrics` — patch
   `tier1.deliberation.graph.record_deliberation_latency` and
   `record_deliberation_rounds`. Run the tribunal. Assert both
   `record_deliberation_latency` and `record_deliberation_rounds`
   were called once each, and that the latency arg is a positive
   float and rounds arg is `>= 1`.

3. `test_tribunal_stream_yields_events_in_order` — invoke
   `Tribunal(settings, garage).stream(state)`. Collect events.
   Assert the stream yields at least one token event, the
   `steward_feedback`/`consensus_reached`/`consensus_failed`
   verdict, and a `completed` event. Order matters: tokens
   before verdict, verdict before completed.

4. `test_tribunal_stream_drains_after_run_completes` — patch the
   compiled graph's `ainvoke` so we can drive the queue from
   outside. Verify a `None` sentinel terminates the stream.

### B. Extend: `tests/unit/test_memory_backend.py`

Currently the file tests `MemoryBackend` via mock Qdrant/Redis/Postgres.
Add 5 tests for the `store()` tier branches.

Tests:

1. `test_store_calls_qdrant_redis_postgres` — mock all three async
   stores; call `backend.store(entry)`; assert each was awaited
   once with the entry. Returned id equals `entry.id`.

2. `test_store_swallows_qdrant_failure` — qdrant raises
   `RuntimeError("qdrant down")`; redis/postgres mocks still
   called; `store()` returns the entry id without raising.

3. `test_store_calls_mem0_when_set` — pass `mem0=AsyncMock()` to
   `MemoryBackend`. Call `store(entry)`. Assert
   `mem0.add.await_count == 1` and the call's args include
   `entry.content` as the first positional.

4. `test_store_calls_cognee_when_set` — pass
   `cognee=AsyncMock()` to `MemoryBackend`. Call `store(entry)`.
   Assert `cognee.add.await_count == 1` and the call's args include
   `entry.content` and `entry.metadata`.

5. `test_store_swallows_cognee_failure` — cognee raises
   `RuntimeError("kuzu down")`; other tiers still called;
   `store()` returns entry id without raising.

## Components touched

| File | Change |
|---|---|
| `tests/unit/test_deliberation.py` (new) | 4 tests covering `Tribunal.run()` + `Tribunal.stream()` |
| `tests/unit/test_memory_backend.py` (extend) | 5 tests covering `MemoryBackend.store()` tier branches |

No source files modified.

## Error handling

The new tests use `AsyncMock` and `MagicMock` to simulate tier
failures. They verify that `store()` swallows qdrant/redis/cognee
failures (best-effort paths) and propagates `LLMUnavailable` from
the postgres tier (which is the only critical path in
`MemoryBackend.store()`). No new error paths.

## Testing

9 new tests across 2 files:

| Test | File | Coverage delta |
|---|---|---|
| `test_tribunal_run_returns_final_state` | `test_deliberation.py` | `graph.py:88-100` |
| `test_tribunal_run_records_metrics` | `test_deliberation.py` | `graph.py:98-99` |
| `test_tribunal_stream_yields_events_in_order` | `test_deliberation.py` | `graph.py:102-142` |
| `test_tribunal_stream_drains_after_run_completes` | `test_deliberation.py` | `graph.py:130-142` |
| `test_store_calls_qdrant_redis_postgres` | `test_memory_backend.py` | `memory/__init__.py:47-72` |
| `test_store_swallows_qdrant_failure` | `test_memory_backend.py` | `memory/__init__.py:51-53` |
| `test_store_calls_mem0_when_set` | `test_memory_backend.py` | `memory/__init__.py:64-69` |
| `test_store_calls_cognee_when_set` | `test_memory_backend.py` | `memory/__init__.py:73-79` |
| `test_store_swallows_cognee_failure` | `test_memory_backend.py` | `memory/__init__.py:77-79` |

## Implementation order

1. Create `tests/unit/test_deliberation.py` with the 4 tests.
2. Extend `tests/unit/test_memory_backend.py` with the 5 tests.
3. Run targeted tests, iterate on failures.
4. Run full suite (skip `test_health.py` for Postgres dependency).
5. Verify coverage on `graph.py` ≥ 80% and `memory/__init__.py`
   ≥ 80%.

## Dependencies

None new. All required mocks (`AsyncMock`, `MagicMock`,
`pytest-asyncio`) already used by the project.
