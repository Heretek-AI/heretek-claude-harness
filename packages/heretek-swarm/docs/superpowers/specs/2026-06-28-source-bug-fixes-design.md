# Source Bug Fixes — Design

**Date:** 2026-06-28
**Status:** Approved
**Author:** brainstorming session
**Scope:** 2 surgical source-line fixes plus 2 missing test cases

## Goal

Fix two latent source bugs flagged during the Tier 1 Coverage Lift review. Add one test for each bug to prevent regression. No other source or test changes.

## Out of scope

- Any other source modifications
- Refactors, cleanup, or new functionality
- Test refactors beyond the 2 missing cases

## Bug 1 — `tier1/memory/qdrant_store.py:106` missing `MemoryType` import

**Root cause:** Line 9 imports only `MemoryEntry`. Line 106 references `MemoryType(payload.get("memory_type", "episodic"))`. If `_query` is called with non-empty results, `NameError` is raised.

**Latent because:** Existing `test_qdrant_store.py` exercises `_query` only via `client.search.return_value = []`, never hitting line 106. Real usage would trigger `NameError`.

**Fix:**
- File: `backend/tier1/tier1/memory/qdrant_store.py`
- Change line 9:
  ```diff
  - from tier1.memory import MemoryEntry
  + from tier1.memory import MemoryEntry, MemoryType
  ```
- One-line change.

**Test:** add `test_query_uses_memory_type_from_payload` to `backend/tier1/tests/unit/test_qdrant_store.py`. Mock `client.search.return_value = [ScoredPoint(...)]` with non-empty payload containing `memory_type="episodic"`. Verify result `MemoryEntry.memory_type == MemoryType.episodic`. Also assert a non-default payload value (e.g., `memory_type="semantic"`) is parsed correctly.

## Bug 2 — `tier1/llm/garage.py:172` 3-arg call to 2-arg signature

**Root cause:** Dispatch table (lines 163-168) maps provider name to bound method. Call site (line 172) passes `(prompt, agent, provider)`. `_stream_anthropic_provider` only accepts `(prompt, agent)` — would raise `TypeError` if dispatch path were exercised for anthropic.

**Latent because:** Anthropic is never routed through `_stream_from_provider` in production (callers test it directly). Task 2 review's `test_stream_from_provider_dispatches_by_name` monkeypatches `_stream_from_provider` itself, so line 172 is never executed.

**Fix:**
- File: `backend/tier1/tier1/llm/garage.py`
- Change lines 163-172 to encode `provider_name` per entry:
  ```diff
    dispatch = {
  -     "minimax": self._stream_openai_provider,
  -     "anthropic": self._stream_anthropic_provider,
  -     "openai": self._stream_openai_provider,
  -     "local": self._stream_openai_provider,
  +     "minimax": lambda p, a: self._stream_openai_provider(p, a, "minimax"),
  +     "anthropic": self._stream_anthropic_provider,
  +     "openai": lambda p, a: self._stream_openai_provider(p, a, "openai"),
  +     "local": lambda p, a: self._stream_openai_provider(p, a, "local"),
    }
    fn = dispatch.get(provider)
    if fn is None:
        raise LLMUnavailable(f"unknown provider: {provider!r}")
  - async for chunk in fn(prompt, agent, provider):
  + async for chunk in fn(prompt, agent):
        yield chunk
  ```
- `_stream_openai_provider` signature unchanged: `(self, prompt, agent, provider_name)`
- `_stream_anthropic_provider` signature unchanged: `(self, prompt, agent)`

**Test:** add `test_stream_from_provider_dispatches_to_correct_handler` to `backend/tier1/tests/unit/test_llm_garage.py`. Mock all 4 stream methods (3 lambdas + anthropic) as `AsyncMock` returning async generators. Call `_stream_from_provider("anthropic", "hi", "alpha")` and verify only `_stream_anthropic_provider` was invoked with `(prompt, agent)`. Repeat for `minimax` and verify `_stream_openai_provider` invoked with `(prompt, agent, "minimax")`.

## Stop condition

- All 420 tests pass (418 existing + 2 new)
- `--cov-fail-under=80` gate holds
- Coverage on `qdrant_store.py` ≥97% (unchanged or higher)
- Coverage on `garage.py` ≥97% (unchanged or higher)

## Risks

- **Lambda closure over `self`** — dispatch lambdas capture `self`. No memory risk (one closure per call, GC'd after dispatch returns).
- **Signature asymmetry remains** — `_stream_openai_provider` takes 3 args, `_stream_anthropic_provider` takes 2. Documented in the dispatch table; no caller sees this directly.
- **Test isolation** — `_stream_openai_provider` test (existing) uses direct calls. New dispatch test mocks the methods via `unittest.mock.patch.object(garage, "_stream_openai_provider")` to avoid real SDK calls.

## Success

- 2 bugs fixed at source
- 2 new tests prevent regression
- No collateral changes
- One PR off `main`
