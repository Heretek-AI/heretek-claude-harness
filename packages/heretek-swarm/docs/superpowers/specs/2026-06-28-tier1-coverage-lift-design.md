# Tier 1 Coverage Lift — Design

**Date:** 2026-06-28
**Status:** Approved
**Author:** brainstorming session
**Scope:** `tier1/` only

## Goal

Lift `tier1/` coverage from 40% to ≥80% via mocked unit tests, deep branch coverage per module, one module at a time, one PR per module.

Enforcement already in `pyproject.toml`: `--cov-fail-under=80`. This work makes that gate pass.

## Out of scope

- `heretek_swarm/` coverage (no tests dir; separate decision)
- Integration tests (already exist, env-gated)
- New functionality, refactors, behavior changes in source code

## Ordering — biggest coverage win first

| # | Module(s) | Stmts untested | Current % | Notes |
|---|-----------|---------------:|----------:|-------|
| 1 | `memory/` cluster (9 files) | ~407 | 0% | access_patterns, cognee_store, mem0_store, nats_memory, postgres_store, prefetcher, qdrant_store, redis_cache, __init__ |
| 2 | `llm/garage.py` | 124 | 22% | LLM provider garage |
| 3 | `api/routes/*` (deliberations, health, ws) + `api/app.py` | 172 | 18–28% | FastAPI surface |
| 4 | `persistence/*` (postgres, qdrant, redis) | 81 | 26–39% | Wraps real infra |
| 5 | `observability/__init__, logging` + `dashboard/*` + `events/nats_client` + `deliberation/nodes/steward` | ~125 | 28–55% | Cleanup |
| 6 | `__main__.py` | 25 | 0% | Last — entry glue |

Each row = one PR.

## Per-module deliverable

For each module in the table:

1. New or extend `tests/unit/test_<module>.py` — deep coverage of every public function
2. Every branch covered — happy path + each error path + each edge case (empty list, `None` input, malformed payload)
3. Mock all external deps at the module boundary (see Mock Strategy below)
4. No new dependencies — stdlib + existing test deps only
5. Run `coverage report --include='tier1/<module>.py'` — module must hit ≥80% before merge
6. Run full suite + `--cov-fail-under=80` — final gate after each PR

## Mock strategy

- Memory stores: `AsyncMock` for `connection.execute`, canned rows / `None` / exceptions
- LLM garage: `respx` for HTTP, `AsyncMock` for SDK methods (respx already in test deps)
- NATS client: `AsyncMock` for `nc.publish`, `nc.subscribe`, `nc.request`
- FastAPI routes: `TestClient` + existing `app` fixture from `conftest.py`
- Persistence: `AsyncMock` at the driver boundary

Each module gets ~1.5x its source LOC in tests (deep, not thin).

## Error handling in tests

- Failure-path tests are part of the "deep" requirement, not extra credit
- Each module's tests cover at minimum: success path, empty input, missing dep, infra exception (`ConnectionError`, `TimeoutError`, etc.), malformed payload
- Assertions use `pytest.raises` + `exc.match` for specific error type/message — not bare `with pytest.raises(Exception)`

## Testing cadence

After each module PR:

1. `pytest tests/unit/test_<module>.py -v` — module tests pass
2. `pytest --cov=tier1/<module>.py --cov-report=term-missing` — module ≥80%
3. `pytest` — full suite still green (no regressions)
4. `pytest --cov-fail-under=80` — overall gate holds (or climbs toward it)

If a module gate fails after tests are written, add more tests. Do not lower the threshold.

## Stop criterion

`pytest --cov-fail-under=80` passes on a clean `main` branch. Module-by-module progress tracked in `.superpowers/sdd/progress.md`.

## Risks

- **Tight coupling** — modules like `memory/__init__.py` and `cognee_store.py` may import heavily, making mocking painful. Fallback: refactor test-local imports to be more injectable. No source changes.
- **Coverage drift** — coverage may shift if a merged PR lands between batches. Resolve by re-running on current `main` before each batch.
- **Time-sensitive tests** — `freezegun` is already in deps; use it for any path that touches timestamps or `time.time()`.

## Success

- Coverage report shows ≥80% on `tier1/` total
- `--cov-fail-under=80` passes in CI
- All existing tests still pass
- Each module in the ordering table has a dedicated deep test file
