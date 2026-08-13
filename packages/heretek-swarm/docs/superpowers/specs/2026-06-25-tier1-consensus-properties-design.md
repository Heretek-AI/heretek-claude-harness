# Tier 1 Consensus Property-Based Tests — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)

## Context

Tier 1 consensus logic lives in `tier1/deliberation/nodes/consensus.py` — a pure function `apply()` that takes 3 agent verdicts and returns a decision, plus `build_final_verdict()` that adds round-limit collapse. The Steward node in `steward.py` calls `build_final_verdict` and finalizes the state. These are the most critical correctness paths in the system: wrong consensus means wrong deliberation outcomes.

Current test coverage is deterministic — hand-crafted inputs that exercise known rules. Property-based testing with Hypothesis generates thousands of random inputs, finding edge cases that hand-crafted tests miss.

## Goals

1. Property-based tests for `consensus.apply()` covering all rule branches.
2. Property-based tests for `build_final_verdict()` covering round-limit collapse.
3. Deterministic tests for steward_node finalization behavior.
4. Hypothesis as the primary tool — generates random verdicts, asserts invariants.

## Non-goals

- Tribunal integration testing (already covered by `tests/integration/test_deliberation_*.py`).
- LLM mocking for agent output (integration tests handle this).
- Performance benchmarking of consensus logic.

## Architecture

One new file: `tests/unit/test_consensus_properties.py` using Hypothesis.

```
tests/unit/test_consensus_properties.py
├── test_apply_always_returns_valid_decision      (Hypothesis)
├── test_unanimous_high_confidence_approves        (Hypothesis)
├── test_two_of_three_rejects_rejected             (Hypothesis)
├── test_charlie_veto_overrides_approval           (Hypothesis)
├── test_build_final_verdict_never_exceeds_rounds  (Hypothesis)
├── test_build_final_verdict_round_limit_collapses (deterministic)
├── test_steward_node_finalizes_on_approved        (deterministic, mocked)
├── test_strategy_generates_valid_verdicts         (strategy validation)
└── test_hypothesis_finds_known_edge_case          (seed test)
```

## Properties under test

Properties derived from `consensus.py` rules (verbatim from spec §4):

1. **Decision always valid:** For any combination of 3 verdicts (position ∈ {approve, reject, challenge}, confidence ∈ [0.0, 1.0]), `apply()` returns one of: `approved`, `rejected`, `needs-revision`.
2. **Unanimous high confidence → approved:** If all 3 approve AND min(confidence) ≥ `unanimous_floor`, result is `approved`.
3. **Two-of-three reject → rejected:** If 2+ agents reject, result is `rejected`.
4. **Charlie high-confidence challenge → needs-revision:** If charlie is `challenge` and confidence > `charlie_veto_confidence`, result is `needs-revision` (overrides approval).
5. **Round limit collapse:** `build_final_verdict()` returns `no-consensus` when `round + 1 ≥ max_rounds` AND `apply()` returned `needs-revision`.
6. **Steward finalizes correctly:** `steward_node()` sets `status="completed"` and emits `consensus_reached` or `consensus_failed` event.

## Test design

Each Hypothesis test uses custom strategies to generate random verdicts:

```python
from hypothesis import given, strategies as st

position_strat = st.sampled_from(["approve", "reject", "challenge"])
confidence_strat = st.floats(min_value=0.0, max_value=1.0)
verdict_strat = st.fixed_dictionaries({
    "position": position_strat,
    "confidence": confidence_strat,
    "concerns": st.lists(st.text(max_size=20), max_size=3),
    "reasoning": st.text(max_size=100),
})
```

Tests generate random verdict tuples, assert the property holds. For steward_node test, mock `build_final_verdict` to return controlled decisions and verify event emission.

## Dependencies

New dev dep in `pyproject.toml [project.optional-dependencies].dev`:
```
hypothesis>=6.80
```

## Testing the tests

Two deterministic base-case tests verify Hypothesis strategies aren't degenerate:
- `test_strategy_generates_valid_verdicts`: run strategy 100 times, assert all have valid position/confidence ranges
- `test_hypothesis_finds_known_edge_case`: seed a specific edge case (all challenge, high confidence) to verify Hypothesis can reach it

## Error handling

Hypothesis has built-in shrinking — if a property fails, it finds the minimal counterexample. Test output shows the smallest input that breaks the property. No special error handling needed.

## Implementation order

1. Add `hypothesis>=6.80` to dev deps
2. Create `tests/unit/test_consensus_properties.py` with all 9 tests
3. Run full suite, verify coverage ≥ 80%
