# Tier 1 MiniMax Integration Tests — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)
**Author:** John Smith + Claude (brainstorming session)

## Context

Tier 1 Core Triad is on `main` with real LLM wiring (commit `7be68b06`). Provider implementation in `tier1/llm/garage.py` uses native openai/anthropic SDKs. Today, only mocked HTTP tests cover it. Real-provider behavior — SDK signature drift, API contract changes, auth flow, base_url routing — is uncovered. This spec adds live + recorded integration coverage for the primary provider (MiniMax).

## Goals

1. Prove MiniMax SDK + key + base_url still work against the real API.
2. Pin our code's contract against recorded HTTP exchanges so SDK drift breaks us loudly.
3. Keep PR CI fast (no API calls per PR); gate live calls behind env.
4. Prevent credential leaks via cassette scrubbing + test-of-tests.

## Non-goals

- Multi-provider coverage (deferred). Only MiniMax in this spec.
- Load/soak testing.
- Cost controls (one smoke call per CI run ≈ negligible).
- New Tier 1 features.

## Architecture

Two test tiers, one provider scope (MiniMax), no shared state:

```
tests/integration/
├── conftest.py              # env-gating, fixture loader, marker registration
├── smoke/                   # live only, env-gated, never replayed
│   └── test_minimax_smoke.py
└── behavior/                # fixtures always, live refresh on demand
    ├── conftest.py          # cassette load/save via vcrpy
    └── test_minimax_behavior.py
```

**smoke/** runs only when `MINIMAX_API_KEY` set; one happy-path call proving SDK + key + base_url all work; skipped otherwise. No cassette, no replay.

**behavior/** runs always via cassette replay; tests the provider implementation against recorded HTTP exchanges. Refresh by deleting cassette + setting `RECORD_MINIMAX=1`.

Smoke proves the wire still works. Behavior proves our code's contract against the wire shape we last saw. Separate concerns.

## Components

### A. `tests/integration/conftest.py`

Session-scoped fixtures:
- `minimax_api_key`: read env; auto-skip smoke tests if absent
- `cassette_dir`: `tests/integration/behavior/cassettes/`
- `record_mode`: `RECORD_MINIMAX=1` → record; else replay
- Registers `integration` marker

### B. `smoke/test_minimax_smoke.py` — 2 tests, live only

- `test_smoke_returns_tokens`: prompt → assert ≥1 chunk, has `token`/`agent`/`seq`
- `test_smoke_uses_minimax_url`: capture kwargs, assert `base_url` matches `minimax_base_url`

No cassette. No replay. No mocking. Real call or skip.

### C. `behavior/conftest.py`

Wraps openai SDK with vcrpy:
- `vcr.VCR(record_mode=...)` mounted on `openai.AsyncOpenAI.chat.completions.create`
- Cassette per test: `test_minimax_stream_tokens.yaml`
- Cassettes committed to repo, scrubbed of auth headers
- Library: `vcrpy` (evaluate `pytest-vcr` only if its decorators beat `vcr.use_cassette`)

### D. `behavior/test_minimax_behavior.py` — 4 tests, replay+record

- `test_stream_tokens`: yields expected token sequence
- `test_monotonic_seq`: seq increments
- `test_empty_stream`: empty response yields no chunks
- `test_error_response`: 401/429/500 → correct exception type raised

Asserts on shape, not exact provider text (provider may change wording).

## Data flow

**PR CI (no key):**
```
behavior tests → cassette replay (always runs)
smoke tests    → skipped (no key) → CI green
```

**Main merge (key set):**
```
behavior tests → cassette replay
smoke tests    → live API call
               → assert ≥1 chunk
               → exit non-zero on any failure
```

**Local dev cassette refresh:**
```
rm cassette → RECORD_MINIMAX=1 pytest → vcrpy records live → commit new cassette
```

## Error handling

| Situation | Behavior |
|---|---|
| `MINIMAX_API_KEY` unset on PR CI | smoke tests `pytest.skip()`; behavior tests replay cassettes; CI green |
| `MINIMAX_API_KEY` set on main-merge CI | smoke tests live-call; failure → CI red |
| Cassette missing on behavior test | `vcrpy` auto-records in dev (`RECORD_MINIMAX=1`); in CI fails fast with clear "cassette missing" message |
| Cassette desync (provider API changed) | Behavior test fails on first replay; developer runs `RECORD_MINIMAX=1`, reviews diff, commits new cassette |
| Network down on smoke test | Provider raises `LLMUnavailable`; test fails with full traceback; CI red |
| MiniMax rate limit | Same as network down — propagated as `LLMUnavailable` |
| Auth header leak into cassette | `vcrpy` `before_record` callback scrubs `Authorization: Bearer *` → `Authorization: Bearer REDACTED`; pre-commit hook verifies no live key in any cassette file |
| Cassette file too large | Cap at 1 MB per cassette; tests with larger cassettes use `match_on` only on path/headers, not body |

Auth scrubbing is the most important item — a leaked key in git is a security incident.

## CI integration

Two workflows in `.github/workflows/`:

### `tier1-ci.yml` (existing, updated)

- Triggers: PR, push to main
- Runs: `pytest -m "not integration"` (existing unit/integration-as-of-today)
- No secrets needed
- Fast (~3 min)

### `tier1-integration.yml` (new)

- Triggers: push to main, manual `workflow_dispatch`, nightly cron
- Runs: `pytest -m integration` with `MINIMAX_API_KEY` from repo secret
- Failure: posts PR comment if PR exists; blocks merge via required-check only on main branch
- Cost: 1 real API call per run (smoke), cassettes replay for behavior

`pyproject.toml`:
- `addopts = "-m 'not integration'"` as default to keep PR CI fast
- Override on integration workflow: `pytest -m integration`
- Marker in `pytest.ini_options`:
  ```toml
  [tool.pytest.ini_options.ini]
  markers = [
      "integration: real-provider tests, env-gated",
  ]
  ```

## Testing the tests

A test suite that isn't itself verified is a trap. Three checks:

### A. Cassette scrub check (unit test, always runs)

Lives in `tests/unit/test_cassette_safety.py`:
- Read every `*.yaml` in `cassettes/`
- Assert no string matches `sk-[a-zA-Z0-9]{20,}` (OpenAI-style live key)
- Assert no `Authorization: Bearer <non-REDACTED>` lines
- CI: hard fail if any cassette contains live credentials

### B. Marker leak check (unit test)

Lives in `tests/unit/test_markers.py`:
- `pytest --collect-only -q` parsed
- Assert every test in `tests/integration/` is marked `@pytest.mark.integration`
- Prevents new integration tests from accidentally running in PR CI

### C. Smoke sanity (manual only, not in CI)

- Documented in spec: developer can verify their cassette is realistic by running smoke + behavior back-to-back and diffing output

## Implementation order

1. Add `vcrpy` (and `pytest-vcr` if useful) to dev deps
2. Create `tests/integration/conftest.py` with env-gating
3. Create `behavior/conftest.py` with vcrpy config + auth scrubbing
4. Record initial cassettes via `RECORD_MINIMAX=1 pytest` with a real MiniMax key
5. Write `behavior/test_minimax_behavior.py`
6. Write `smoke/test_minimax_smoke.py`
7. Add `.github/workflows/tier1-integration.yml`
8. Add cassette scrub check + marker leak check tests
9. Update `pyproject.toml` markers and addopts

## Open questions (none — all resolved in brainstorming)

- Which provider: MiniMax only (decided)
- Test format: live + recorded (decided)
- CI gating: marker-based, two workflows (decided)
- Cassette leak prevention: scrub + test-of-tests (decided)
