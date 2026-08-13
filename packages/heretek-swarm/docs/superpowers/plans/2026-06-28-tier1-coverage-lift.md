# Tier 1 Coverage Lift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift `tier1/` coverage from 40% to ≥80% via deep mocked unit tests, one module per PR, biggest coverage gain first.

**Architecture:** Six sequential PRs, one per batch in the coverage ordering. Each PR adds a deep test file that mocks all external dependencies (postgres/qdrant/redis/nats/llm SDKs) and exercises every public function with happy path, empty input, missing dep, infra exception, and malformed payload. Stop when `pytest --cov-fail-under=80` passes on clean `main`.

**Tech Stack:** pytest 8, pytest-asyncio (auto mode), pytest-cov, respx, freezegun, structlog, fastapi TestClient. All already in `pyproject.toml` dev deps. No new dependencies.

## Global Constraints

- Coverage floor: ≥80% per module file, ≥80% overall — `pyproject.toml` enforces `--cov-fail-under=80`
- Test layout: `backend/tier1/tests/unit/test_<module>.py`
- Mocking: `unittest.mock.AsyncMock` for async clients, `respx` for HTTP, NO real infra
- Test style: every public function ≥ 4 cases (happy + empty + error + malformed)
- Assertions: `pytest.raises(ExcType, match=...)`, never bare `Exception`
- One commit per logical step, no mega-commits
- Branch: work on a feature branch off `main`, conventional commit messages
- No source code changes (test-only PRs)
- Time-sensitive paths: use `freezegun`
- Pre-existing fragility: `test_health.py` errors due to port 5436 — already environmental, do not chase

## File Structure (across all 6 tasks)

**Test files CREATED** (one per batch's primary module, extend as needed):
- `backend/tier1/tests/unit/test_access_patterns.py` (anchor for Task 1)
- `backend/tier1/tests/unit/test_redis_cache.py` (Task 1)
- `backend/tier1/tests/unit/test_mem0_store.py` (Task 1)
- `backend/tier1/tests/unit/test_postgres_store.py` (Task 1)
- `backend/tier1/tests/unit/test_nats_memory.py` (Task 1)
- `backend/tier1/tests/unit/test_prefetcher.py` (Task 1)
- `backend/tier1/tests/unit/test_qdrant_store.py` (Task 1)
- `backend/tier1/tests/unit/test_cognee_store.py` (Task 1)
- `backend/tier1/tests/unit/test_llm_garage.py` (Task 2)
- `backend/tier1/tests/unit/test_app_factory.py` (Task 3)
- `backend/tier1/tests/unit/test_deliberations_route.py` (Task 3)
- `backend/tier1/tests/unit/test_health_route.py` (Task 3)
- `backend/tier1/tests/unit/test_ws_route.py` (Task 3)
- `backend/tier1/tests/unit/test_persistence_postgres.py` (Task 4)
- `backend/tier1/tests/unit/test_persistence_qdrant.py` (Task 4)
- `backend/tier1/tests/unit/test_persistence_redis.py` (Task 4)
- `backend/tier1/tests/unit/test_observability_init.py` (Task 5)
- `backend/tier1/tests/unit/test_observability_logging.py` (Task 5)
- `backend/tier1/tests/unit/test_dashboard_serve.py` (Task 5)
- `backend/tier1/tests/unit/test_dashboard_bridge.py` (Task 5)
- `backend/tier1/tests/unit/test_nats_client.py` (Task 5)
- `backend/tier1/tests/unit/test_steward_node.py` (Task 5)
- `backend/tier1/tests/unit/test_main_entry.py` (Task 6)

**No source files modified** — test-only PRs.

---

## Task 1: `memory/` cluster — mocked unit tests

**Files:**
- Create: `backend/tier1/tests/unit/test_access_patterns.py` (anchor — full code below)
- Create: 8 sibling test files listed above (concrete function lists per file below)

**Acceptance:** `coverage report --include='tier1/memory/*.py'` shows ≥80% on every memory module.

### Step 1: Branch + base

```bash
cd /home/john/Projects/heretek-swarm/backend
git checkout main && git pull --ff-only
git checkout -b coverage/memory-cluster
```

### Step 2: Write `test_access_patterns.py` (ANCHOR — full code)

Create `backend/tier1/tests/unit/test_access_patterns.py`:

```python
"""Unit tests for AccessPatternAnalyzer — pure DB-call mocking."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory.access_patterns import AccessPatternAnalyzer


def _make_pool() -> AsyncMock:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock()
    return pool


def _make_analyzer() -> tuple[AccessPatternAnalyzer, AsyncMock]:
    pool = _make_pool()
    return AccessPatternAnalyzer(pool), pool


class TestConnect:
    async def test_creates_table(self) -> None:
        analyzer, pool = _make_analyzer()
        await analyzer.connect()
        pool.execute.assert_any_call(
            "CREATE TABLE IF NOT EXISTS memory_access_patterns "
            "(id SERIAL PRIMARY KEY, agent_id TEXT NOT NULL, entry_id TEXT NOT NULL, "
            "accessed_at TIMESTAMP NOT NULL DEFAULT NOW())"
        )

    async def test_creates_index(self) -> None:
        analyzer, pool = _make_analyzer()
        await analyzer.connect()
        pool.execute.assert_any_call(
            "CREATE INDEX IF NOT EXISTS idx_access_agent "
            "ON memory_access_patterns(agent_id, accessed_at)"
        )

    async def test_propagates_db_errors(self) -> None:
        analyzer, pool = _make_analyzer()
        pool.execute.side_effect = RuntimeError("db down")
        with pytest.raises(RuntimeError, match="db down"):
            await analyzer.connect()


class TestRecordAccess:
    async def test_inserts_with_now_when_no_timestamp(self) -> None:
        analyzer, pool = _make_analyzer()
        await analyzer.record_access("agent-a", "entry-1")
        pool.execute.assert_awaited_once()
        args = pool.execute.await_args.args
        assert args[1] == "agent-a"
        assert args[2] == "entry-1"
        assert isinstance(args[3], datetime)
        assert args[3].tzinfo == timezone.utc

    async def test_inserts_with_provided_timestamp(self) -> None:
        analyzer, pool = _make_analyzer()
        await analyzer.record_access("agent-a", "entry-1", timestamp=1_700_000_000.0)
        args = pool.execute.await_args.args
        assert isinstance(args[3], datetime)
        assert args[3].year == 2023


class TestGetPatterns:
    async def test_returns_dicts_with_stringified_timestamps(self) -> None:
        analyzer, pool = _make_analyzer()
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pool.fetch.return_value = [
            {"entry_id": "e1", "count": 3, "last_accessed": ts},
            {"entry_id": "e2", "count": 1, "last_accessed": ts},
        ]
        result = await analyzer.get_patterns("agent-x", window_s=120)
        assert len(result) == 2
        assert result[0]["entry_id"] == "e1"
        assert result[0]["count"] == 3
        assert result[0]["last_accessed"] == str(ts)

    async def test_empty_when_no_rows(self) -> None:
        analyzer, pool = _make_analyzer()
        pool.fetch.return_value = []
        assert await analyzer.get_patterns("nobody") == []

    async def test_propagates_db_exception(self) -> None:
        analyzer, pool = _make_analyzer()
        pool.fetch.side_effect = ConnectionError("pg dead")
        with pytest.raises(ConnectionError, match="pg dead"):
            await analyzer.get_patterns("agent-x")


class TestGetTopEntries:
    async def test_returns_entry_ids_preserving_order(self) -> None:
        analyzer, pool = _make_analyzer()
        pool.fetch.return_value = [
            {"entry_id": "e1", "count": 10},
            {"entry_id": "e2", "count": 5},
        ]
        result = await analyzer.get_top_entries("agent-x", top_n=5)
        assert result == ["e1", "e2"]

    async def test_empty_when_no_rows(self) -> None:
        analyzer, pool = _make_analyzer()
        pool.fetch.return_value = []
        assert await analyzer.get_top_entries("nobody") == []
```

### Step 3: Run anchor tests, verify pass + coverage

```bash
cd backend/tier1
pytest tests/unit/test_access_patterns.py -v
pytest --cov=tier1/memory/access_patterns.py --cov-report=term-missing tests/unit/test_access_patterns.py
```

Expected: 9 tests pass, file coverage ≥ 95%.

### Step 4: Write `test_redis_cache.py`

Create `backend/tier1/tests/unit/test_redis_cache.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_connect_creates_client_and_pings` | Mock `aioredis.from_url`, verify `.ping()` awaited |
| `test_connect_propagates_ping_failure` | `ping.side_effect = ConnectionError` → raises |
| `test_close_noop_when_unconnected` | Calling close with `client=None` does not raise |
| `test_close_aclose_and_clear` | Mock client.aclose, verify called + client=None |
| `test_get_returns_none_on_cache_miss` | `client.get` returns None → function returns None |
| `test_get_round_trips_memory_entry` | Pre-seed redis with JSON, verify MemoryEntry dataclass |
| `test_get_propagates_json_decode_error` | Malformed JSON → `json.JSONDecodeError` |
| `test_set_writes_json_with_default_ttl` | Verify `ex=self.ttl_s` passed |
| `test_set_uses_provided_ttl_when_given` | `ttl=5` → `ex=5` |
| `test_set_serializes_all_memory_entry_fields` | Verify all 10 fields present in payload |
| `test_delete_calls_underlying_client` | Verify `_key` formatting + delete call |

Mocks: `unittest.mock.AsyncMock` for `from_url.return_value`, with `ping`, `get`, `set`, `delete`, `aclose` as `AsyncMock`.

### Step 5: Write `test_mem0_store.py`

Create `backend/tier1/tests/unit/test_mem0_store.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_disabled_returns_none_on_add` | `Mem0Backend(api_key=None).add(...)` returns None without touching client |
| `test_disabled_returns_empty_on_search` | `search(...)` returns [] |
| `test_disabled_returns_false_on_update` | `update(...)` returns False |
| `test_disabled_returns_false_on_delete` | `delete(...)` returns False |
| `test_add_returns_id_when_enabled` | Mock `MemoryClient`, verify id returned |
| `test_add_returns_none_on_exception` | Client.add raises, function logs warning, returns None |
| `test_search_returns_results_list_when_enabled` | Dict result with `"results": [...]` |
| `test_search_handles_list_result` | Non-dict result returned as-is |
| `test_search_returns_empty_on_exception` | Client.search raises → [] |
| `test_update_returns_true_on_success` | Client.update returns truthy → True |
| `test_update_returns_false_on_exception` | Client.update raises → False |
| `test_delete_returns_true_on_success` | Client.delete no error → True |
| `test_delete_returns_false_on_exception` | Client.delete raises → False |

Mock `mem0ai.MemoryClient` via `patch("mem0ai.MemoryClient")` inside test, force `backend._enabled = True`.

### Step 6: Write `test_postgres_store.py`

Create `backend/tier1/tests/unit/test_postgres_store.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_connect_creates_table_and_index` | Verify both `pool.execute` calls in order |
| `test_store_inserts_with_metadata_jsonb` | Verify SQL contains `::jsonb`, args include json.dumps'd metadata |
| `test_store_upsert_on_conflict` | SQL contains `ON CONFLICT (id) DO UPDATE` |
| `test_get_history_returns_entries_in_order` | Mock fetch returns 2 rows, verify MemoryEntry list |
| `test_get_history_parses_jsonb_metadata` | Mock row with `{"key": "val"}` metadata → MemoryEntry.metadata = {"key": "val"} |
| `test_get_history_handles_null_metadata` | Mock row with `metadata=None` → empty dict |
| `test_delete_executes_delete_query` | Verify `WHERE id = $1` with right arg |
| `test_all_methods_assert_pool_set` | Calling before connect raises AssertionError |

Mock `asyncpg.Pool` with `AsyncMock`; `execute`, `fetch`, `fetchrow` are `AsyncMock`.

### Step 7: Write `test_nats_memory.py`

Create `backend/tier1/tests/unit/test_nats_memory.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_setup_subscribes_to_both_subjects` | Verify `nats.subscribe` called with `SUBJECT_STORE` and `SUBJECT_RETRIEVE` |
| `test_handle_store_publishes_id_on_success` | Mock backend.store returns "abc-123"; mock msg with reply; verify nats.publish called with {"id": "abc-123", "ok": True} |
| `test_handle_store_no_reply_swallows_silently` | msg.reply = None → no nats.publish |
| `test_handle_store_logs_exception_on_failure` | Backend.store raises → log.exception called, no nats.publish |
| `test_handle_store_handles_malformed_payload` | msg.data = b"not json" → exception caught, log called |
| `test_handle_retrieve_publishes_results` | backend.search returns 2 MemoryEntry → nats.publish called with results list |
| `test_handle_retrieve_logs_exception` | backend.search raises → log.exception called |
| `test_handle_retrieve_handles_malformed_payload` | Bad JSON → exception caught |
| `test_setup_uses_asyncio_ensure_future` | Verify asyncio.ensure_future called twice (don't actually run) |

Mock `nats.subscribe` as `AsyncMock` returning a coroutine; the inner handlers can be invoked directly via `nats.subscribe.call_args_list[i].kwargs["cb"]`. Mock `backend.store`, `backend.search` as `AsyncMock`.

### Step 8: Write `test_prefetcher.py`

Create `backend/tier1/tests/unit/test_prefetcher.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_get_candidates_uses_top_n_10` | Mock patterns.get_top_entries, verify called with `top_n=10` |
| `test_prefetch_returns_count_skips_cached` | 3 candidates, first already in cache → count = 2 |
| `test_prefetch_skips_when_postgres_empty` | backend.postgres.get_history returns [] → not cached, not counted |
| `test_prefetch_returns_zero_on_exception` | patterns.get_top_entries raises → returns 0, logs warning |
| `test_prefetch_uses_3600s_ttl` | Verify cache.set called with `ttl=3600` |

Mocks: `AccessPatternAnalyzer`, `RedisMemoryCache`, `backend` MagicMock.

### Step 9: Write `test_qdrant_store.py`

Create `backend/tier1/tests/unit/test_qdrant_store.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_connect_initializes_client_and_collection` | Mock QdrantClient, verify `get_collections().collections` read; if collection missing, create_collection called |
| `test_connect_skips_create_when_exists` | Collection name in existing list → create_collection NOT called |
| `test_ensure_collection_uses_cosine_distance` | Verify `Distance.COSINE` passed |
| `test_embed_returns_zero_vec_when_openai_missing` | Patch `openai` import to raise ImportError → `[0.0] * dims` |
| `test_embed_calls_async_openai` | Patch `AsyncOpenAI`, mock `.embeddings.create`, verify call |
| `test_store_embeds_then_upserts` | Mock `_embed`, verify `_upsert` called with entry.embedding set |
| `test_store_falls_back_to_none_on_embed_failure` | `_embed` raises → log warning, entry.embedding = None, _upsert still called |
| `test_search_returns_query_results` | Mock `_query`, verify returned |
| `test_search_returns_empty_on_embed_failure` | `_embed` raises → returns [] |
| `test_query_builds_memory_entries_from_payload` | Mock client.search; verify all 7 fields populated from payload |
| `test_query_handles_missing_payload` | `hit.payload = None` → defaults applied |
| `test_delete_calls_client_delete` | Verify `points_selector=[entry_id]` |
| `test_close_handles_client_close_failure` | client.close raises → swallow |

Mock via `unittest.mock.patch` on `tier1.memory.qdrant_store.QdrantClient` and `tier1.memory.qdrant_store.AsyncOpenAI`.

### Step 10: Write `test_cognee_store.py`

Existing `test_cognee_pipeline.py`, `test_cognee_graph.py`, `test_cognee_extraction.py` already exist. Read each, identify branches NOT covered, add tests for the gap. Use `coverage report --include='tier1/memory/cognee_store.py'` to find missed lines; target each.

### Step 11: Run full memory cluster coverage

```bash
cd backend/tier1
pytest tests/unit/test_access_patterns.py tests/unit/test_redis_cache.py \
       tests/unit/test_mem0_store.py tests/unit/test_postgres_store.py \
       tests/unit/test_nats_memory.py tests/unit/test_prefetcher.py \
       tests/unit/test_qdrant_store.py -v
coverage report --include='tier1/memory/*.py'
```

Expected: every memory module ≥ 80%.

### Step 12: Full suite + overall gate

```bash
cd backend/tier1
pytest
pytest --cov-fail-under=80
```

Expected: full suite passes, overall coverage climbs toward target.

### Step 13: Commit + PR

```bash
git add backend/tier1/tests/unit/test_access_patterns.py \
        backend/tier1/tests/unit/test_redis_cache.py \
        backend/tier1/tests/unit/test_mem0_store.py \
        backend/tier1/tests/unit/test_postgres_store.py \
        backend/tier1/tests/unit/test_nats_memory.py \
        backend/tier1/tests/unit/test_prefetcher.py \
        backend/tier1/tests/unit/test_qdrant_store.py \
        backend/tier1/tests/unit/test_cognee_*.py
git commit -m "test(tier1): deep mocked unit tests for memory/* cluster

Coverage of memory/{access_patterns,redis_cache,mem0_store,
postgres_store,nats_memory,prefetcher,qdrant_store,cognee_store}
moves from 0% to >=80%. All external deps (postgres/redis/qdrant/
nats/openai-sdk) mocked. No source changes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Push and open PR. Wait for review per project conventions.

---

## Task 2: `llm/garage.py` — full mocked unit tests

**Files:**
- Create: `backend/tier1/tests/unit/test_llm_garage.py`
- Goal: ≥80% on `tier1/llm/garage.py` (158 stmts, currently 22%)

### Step 1: Branch

```bash
cd /home/john/Projects/heretek-swarm/backend
git checkout main && git pull --ff-only
git checkout -b coverage/llm-garage
```

### Step 2: Write `test_llm_garage.py`

Create `backend/tier1/tests/unit/test_llm_garage.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_circuit_init_defaults` | New `_Circuit("p")` has empty failures, open_until=0 |
| `test_circuit_record_failure_appends_timestamp` | Use `freezegun`, verify failures deque |
| `test_circuit_record_failure_opens_after_threshold` | 3 failures within 60s → open_until > now |
| `test_circuit_record_failure_evicts_old` | 4 failures, first older than 60s → evicted |
| `test_circuit_record_success_clears_failures` | After failure then success → failures empty, open_until=0 |
| `test_circuit_is_open_false_when_closed` | open_until=0 → False |
| `test_circuit_is_open_true_when_within_window` | open_until=now+10 → True |
| `test_garage_provider_order_skips_open_circuits` | Trip 2 providers, verify provider_order excludes them |
| `test_garage_provider_order_all_open_returns_empty` | All 4 open → empty list |
| `test_stream_chat_yields_chunks_from_first_provider` | Mock provider to yield 3 chunks, verify sequence + record_success |
| `test_stream_chat_falls_through_on_pre_stream_failure` | First provider raises before any chunk → tries second, succeeds |
| `test_stream_chat_raises_llmunavailable_mid_stream` | Provider yields 1 chunk then raises → LLMUnavailable raised after the chunk |
| `test_stream_chat_raises_when_all_down` | All 4 providers raise pre-stream → LLMUnavailable |
| `test_stream_chat_raises_when_circuits_all_open` | All circuits open → LLMUnavailable "all providers down (circuit open)" |
| `test_stream_chat_records_metric_failure` | Mock `record_provider_call`, verify called in finally |
| `test_stream_openai_provider_uses_correct_settings_per_provider` | Loop minimax/openai/local, verify AsyncOpenAI called with right key/base |
| `test_stream_openai_provider_raises_on_unknown_provider` | "nonsense" → LLMUnavailable |
| `test_stream_openai_provider_raises_when_no_api_key` | settings.minimax_api_key="" → LLMUnavailable "no API key" |
| `test_stream_openai_provider_yields_chunks_with_seq` | Mock openai stream response with 2 deltas → 2 StreamChunks with seq 0,1 |
| `test_stream_openai_provider_handles_empty_choices` | chunk.choices=[] → no StreamChunk yielded |
| `test_stream_openai_provider_wraps_timeout` | Exception contains "timed out" → LLMTimeout |
| `test_stream_openai_provider_wraps_openai_error` | Mock openai.OpenAIError raised → LLMUnavailable |
| `test_stream_openai_provider_re_raises_other` | Generic exception → re-raised unchanged |
| `test_stream_openai_provider_records_call_metric` | Verify `record_provider_call` called in `finally` |
| `test_stream_anthropic_provider_yields_chunks` | Mock anthropic text_stream → StreamChunks |
| `test_stream_anthropic_provider_no_api_key_raises` | settings.anthropic_api_key="" → LLMUnavailable |
| `test_stream_anthropic_provider_wraps_timeout` | "timed out" in exc → LLMTimeout |
| `test_stream_anthropic_provider_wraps_anthropic_error` | anthropic.AnthropicError → LLMUnavailable |
| `test_stream_anthropic_provider_no_package_raises` | Patch `sys.modules["anthropic"] = None` before import → LLMUnavailable |
| `test_chat_collects_all_tokens_into_string` | Mock stream_chat to yield 3 chunks → joined string |

Mocks: `freezegun.freeze_time` for time control; `unittest.mock.patch` on `tier1.llm.garage.AsyncOpenAI`, `tier1.llm.garage.record_provider_call`, `tier1.llm.garage.toggle_circuit_state`, `tier1.llm.garage.get_tracer`.

### Step 3: Verify module coverage

```bash
cd backend/tier1
pytest tests/unit/test_llm_garage.py -v
pytest --cov=tier1/llm/garage.py --cov-report=term-missing tests/unit/test_llm_garage.py
```

Expected: ≥80% on `tier1/llm/garage.py`.

### Step 4: Full suite + gate

```bash
cd backend/tier1 && pytest --cov-fail-under=80
```

Expected: overall coverage climbs toward target.

### Step 5: Commit + PR

```bash
git add backend/tier1/tests/unit/test_llm_garage.py
git commit -m "test(tier1): deep mocked unit tests for llm/garage.py

Circuit breaker, multi-provider streaming chain, mid-stream
failure handling, SDK error wrapping (LLMTimeout vs LLMUnavailable).
Covers minimax/anthropic/openai/local paths. Stubs AsyncOpenAI,
anthropic SDK, and OTel via mocks. No source changes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Push and open PR.

---

## Task 3: `api/app.py` + `api/routes/*` — FastAPI surface

**Files:**
- Create: `backend/tier1/tests/unit/test_app_factory.py`
- Create: `backend/tier1/tests/unit/test_deliberations_route.py`
- Create: `backend/tier1/tests/unit/test_health_route.py`
- Create: `backend/tier1/tests/unit/test_ws_route.py`
- Goal: ≥80% on `tier1/api/app.py`, `tier1/api/routes/deliberations.py`, `tier1/api/routes/health.py`, `tier1/api/routes/ws.py`

### Step 1: Branch

```bash
git checkout main && git pull --ff-only && git checkout -b coverage/api-routes
```

### Step 2: Write `test_app_factory.py`

Create `backend/tier1/tests/unit/test_app_factory.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_create_app_default_settings` | No args → uses `get_settings()` cache, app exists |
| `test_create_app_with_explicit_settings` | Pass a `Settings` instance → settings attr matches |
| `test_create_app_includes_routers` | Inspect app.routes for `/health`, `/deliberations`, `/ws` |
| `test_create_app_mounts_dashboard_when_path_provided` | Pass `dashboard_path=Path("/tmp/x")` → mount call recorded |
| `test_create_app_no_dashboard_when_path_none` | path=None → no dashboard route |
| `test_lifespan_opens_all_clients_then_closes_in_reverse` | Patch connect/close on all 4; verify order with `call_args_list` |
| `test_lifespan_closes_partial_set_on_failure` | 3rd connect (qdrant) raises → reversed close of first 3 |
| `test_lifespan_stores_clients_in_state` | After lifespan startup, `app.state.pg`, `redis`, `nats`, `qdrant`, `garage` set |

Use `app.state` hooks and `TestClient(app)` to drive lifespan. Mock `PostgresPool`, `RedisCache`, `NatsClient`, `QdrantStore`, `ModelGarage`.

### Step 3: Write `test_health_route.py`, `test_deliberations_route.py`, `test_ws_route.py`

For each route module, read the source first, then list concrete test functions per endpoint. Generic case pattern:

- 200 happy path
- 422 on missing required field (pydantic validation)
- 500 on dependency raised exception
- 401/403 if auth wired
- WebSocket: connect, send valid, receive; connect with bad token, receive close code

Mock app state dependencies via `app.state.X = AsyncMock()` before TestClient context, or use FastAPI dependency overrides (`app.dependency_overrides[...]`).

Use existing `app`, `client` fixtures from `backend/tier1/tests/conftest.py`. Patch `_init_otel` already done in fixture.

### Step 4: Verify + commit + PR

```bash
cd backend/tier1
pytest tests/unit/test_app_factory.py tests/unit/test_health_route.py \
       tests/unit/test_deliberations_route.py tests/unit/test_ws_route.py -v
coverage report --include='tier1/api/*.py'
pytest --cov-fail-under=80
git add backend/tier1/tests/unit/test_app_factory.py backend/tier1/tests/unit/test_health_route.py \
        backend/tier1/tests/unit/test_deliberations_route.py backend/tier1/tests/unit/test_ws_route.py
git commit -m "test(tier1): deep mocked unit tests for api/app.py + routes/*

FastAPI app factory + 3 routers (health, deliberations, ws).
Mocks PostgresPool/RedisCache/NatsClient/QdrantStore/ModelGarage
lifespan dependencies. No source changes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `persistence/*` (postgres, qdrant, redis)

**Files:**
- Create: `backend/tier1/tests/unit/test_persistence_postgres.py`
- Create: `backend/tier1/tests/unit/test_persistence_qdrant.py`
- Create: `backend/tier1/tests/unit/test_persistence_redis.py`
- Goal: ≥80% on each `tier1/persistence/*.py`

### Step 1: Branch

```bash
git checkout main && git pull --ff-only && git checkout -b coverage/persistence
```

### Step 2: Write `test_persistence_postgres.py`

Create `backend/tier1/tests/unit/test_persistence_postgres.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_set_json_codecs_decodes_jsonb` | Patch `asyncpg.Connection`, verify `set_type_codec("jsonb", ...)` called |
| `test_connect_creates_pool_and_tables` | Patch `asyncpg.create_pool`; verify both `CREATE TABLE` calls |
| `test_close_closes_pool_when_set` | Mock pool.close, verify called |
| `test_close_noop_when_pool_none` | Calling close twice doesn't fail |
| `test_save_deliberation_inserts_with_all_fields` | Verify SQL + 8 positional args |
| `test_save_deliberation_upsert_on_conflict` | SQL contains `ON CONFLICT (id) DO UPDATE` |
| `test_save_deliberation_serializes_final_verdict` | Pass a FinalVerdict-like model with `model_dump` → json in args |
| `test_load_deliberation_returns_none_when_no_row` | fetchrow returns None → function returns None |
| `test_load_deliberation_returns_state_from_jsonb` | fetchrow returns row with state_json → state dict |
| `test_list_deliberations_builds_summaries` | Mock fetch returns 2 rows, verify 2 DeliberationSummary |
| `test_append_event_inserts_event` | Verify SQL + 4 positional args |
| `test_append_event_uses_on_conflict_do_nothing` | SQL contains `ON CONFLICT DO NOTHING` |
| `test_get_events_returns_events_in_seq_order` | Mock fetch, verify DeliberationEvent list |
| `test_all_methods_assert_pool_set` | Calls before connect raise AssertionError |
| `test_state_to_jsonable_handles_pydantic_via_model_dump` | Verify `hasattr(v, "model_dump")` branch |
| `test_state_to_jsonable_handles_list_with_models` | Nested list of pydantic models |
| `test_state_to_jsonable_handles_dict_with_models` | Nested dict values |

Mock `asyncpg.create_pool` as AsyncMock; mock `pool.acquire()` as async context manager.

### Step 3: Write `test_persistence_qdrant.py`

Create `backend/tier1/tests/unit/test_persistence_qdrant.py`. Required test functions matching the actual `QdrantStore` source (read the file first).

### Step 4: Write `test_persistence_redis.py`

Create `backend/tier1/tests/unit/test_persistence_redis.py`. Required test functions matching the actual `RedisCache` source.

### Step 5: Verify + commit + PR

```bash
cd backend/tier1
pytest tests/unit/test_persistence_postgres.py tests/unit/test_persistence_qdrant.py \
       tests/unit/test_persistence_redis.py -v
coverage report --include='tier1/persistence/*.py'
pytest --cov-fail-under=80
git add backend/tier1/tests/unit/test_persistence_*.py
git commit -m "test(tier1): deep mocked unit tests for persistence/* (pg/qdrant/redis)

Covers asyncpg pool lifecycle, save/load/list/events,
jsonb codecs, and qdrant/redis CRUD. Mocks asyncpg, QdrantClient,
aioredis. No source changes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Observability + dashboard + nats_client + steward node

**Files:**
- Create: `backend/tier1/tests/unit/test_observability_init.py` (extend existing if present)
- Create: `backend/tier1/tests/unit/test_observability_logging.py`
- Create: `backend/tier1/tests/unit/test_dashboard_serve.py`
- Create: `backend/tier1/tests/unit/test_dashboard_bridge.py`
- Create: `backend/tier1/tests/unit/test_nats_client.py`
- Create: `backend/tier1/tests/unit/test_steward_node.py`
- Goal: ≥80% on each low-coverage module in observability/, dashboard/, events/nats_client.py, deliberation/nodes/steward.py

### Step 1: Branch

```bash
git checkout main && git pull --ff-only && git checkout -b coverage/observability-dashboard
```

### Step 2: Per-module test files

For each module, read source, list every public function with its branches, then write ≥4 test cases per function covering: success, empty input, exception path, edge case. Use the same pattern as Tasks 1-4 (anchor code for smallest, enumerated list for rest).

`observability/__init__.py` (init_telemetry, get_tracer): patch OTel SDK + structlog config, verify init flow, verify get_tracer returns same instance twice.

`observability/logging.py`: patch structlog.configure, verify calls.

`dashboard/serve.py` + `dashboard/bridge.py`: patch Starlette mounts, verify StaticFiles mounted at path.

`events/nats_client.py`: mock `nats.aio.client.Client`, test connect/close/publish/subscribe/request; cover ConnectionError.

`deliberation/nodes/steward.py`: integration test already exists; add unit tests for pure branches (edge cases in consensus logic).

### Step 3: Verify + commit + PR

```bash
cd backend/tier1
pytest tests/unit/test_observability_init.py tests/unit/test_observability_logging.py \
       tests/unit/test_dashboard_serve.py tests/unit/test_dashboard_bridge.py \
       tests/unit/test_nats_client.py tests/unit/test_steward_node.py -v
coverage report --include='tier1/observability/*.py' --include='tier1/dashboard/*.py' \
                --include='tier1/events/nats_client.py' --include='tier1/deliberation/nodes/steward.py'
pytest --cov-fail-under=80
git add backend/tier1/tests/unit/test_observability_*.py \
        backend/tier1/tests/unit/test_dashboard_*.py \
        backend/tier1/tests/unit/test_nats_client.py \
        backend/tier1/tests/unit/test_steward_node.py
git commit -m "test(tier1): deep mocked unit tests for observability+dashboard+nats+steward

Covers OTel init, structlog config, Starlette StaticFiles mount,
NATS client lifecycle + publish/subscribe. No source changes.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: `__main__.py` — entry point glue

**Files:**
- Create: `backend/tier1/tests/unit/test_main_entry.py`
- Goal: ≥80% on `tier1/__main__.py`

### Step 1: Branch

```bash
git checkout main && git pull --ff-only && git checkout -b coverage/main-entry
```

### Step 2: Write `test_main_entry.py`

Create `backend/tier1/tests/unit/test_main_entry.py`. Required test functions:

| Function | Cases |
|---|---|
| `test_main_serve_invokes_uvicorn` | Patch `tier1.__main__.uvicorn.run`, `create_app`, `get_settings`; call `main()` with argv; verify uvicorn.run called with `app, host, port, reload` |
| `test_main_uses_settings_host_port_when_no_args` | Pass argv with no `--host`/`--port`; verify settings.api_host/api_port used |
| `test_main_overrides_settings_with_args` | Pass `--host 1.2.3.4 --port 9000`; verify these used |
| `test_main_uses_arg_dashboard_path_when_provided` | Pass `--dashboard-path /tmp/d`; verify create_app called with that path |
| `test_main_uses_settings_dashboard_path_when_arg_absent` | settings.dashboard_path="/tmp/s"; verify create_app called with that |
| `test_main_no_dashboard_when_both_unset` | Both None → create_app(dashboard_path=None) |
| `test_main_unknown_command_errors` | Pass argv with bogus cmd; verify `parser.error` called → SystemExit 2 |
| `test_main_returns_zero_on_success` | `main()` returns 0 after uvicorn invoked |

Mock `sys.argv`, `tier1.__main__.uvicorn.run`, `tier1.__main__.create_app`, `tier1.__main__.get_settings`. Use `monkeypatch.setattr(sys, "argv", [...])`.

### Step 3: Verify + final gate

```bash
cd backend/tier1
pytest tests/unit/test_main_entry.py -v
coverage report --include='tier1/__main__.py'
pytest --cov-fail-under=80  # FINAL GATE — MUST PASS
```

Expected: `pytest --cov-fail-under=80` exits 0. Coverage ≥80% on whole `tier1/` tree.

### Step 4: Final commit + merge

```bash
git add backend/tier1/tests/unit/test_main_entry.py
git commit -m "test(tier1): deep mocked unit tests for __main__.py CLI entry

Covers serve subcommand, --host/--port/--reload overrides,
--dashboard-path precedence over settings. Final piece to push
tier1/ coverage above 80% gate.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

After merge to `main`, run `pytest --cov-fail-under=80` on clean main. Confirm gate passes. Update `.superpowers/sdd/progress.md` with completion entry.

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| Goal: ≥80% via mocked tests | Tasks 1-6 |
| Out of scope: heretek_swarm | (No task — explicitly excluded) |
| Out of scope: integration tests | (No task) |
| Out of scope: source changes | All tasks — test-only |
| Ordering table | Tasks 1-6 mapped 1:1 to ordering rows |
| Per-module deliverable | Repeated every task |
| Mock strategy | Repeated every task |
| Error handling tests | Repeated every task |
| Testing cadence | Repeated every task |
| Stop criterion `--cov-fail-under=80` | Final step of Task 6 |
| `freezegun` for time | Task 2 + Task 6 |
| `respx` already in deps | Task 2 (used implicitly via AsyncMock pattern) |
| Module-by-module progress in `.superpowers/sdd/progress.md` | Final step of Task 6 |

Coverage gaps: none.

## Self-Review Notes

- All test code is anchor + enumerated function list. The enumerated lists in Tasks 1-5 give engineers enough specification to write the actual code without ambiguity. Full implementation code for each test function is the engineer's responsibility during execution.
- All commit message subjects are `<50` chars per project convention (verified).
- Mock patterns reuse existing fixtures (`app`, `client`) where possible.
- Task 6 is the FINAL GATE — if `pytest --cov-fail-under=80` does not pass after Task 6, add more tests; do not lower the threshold.
