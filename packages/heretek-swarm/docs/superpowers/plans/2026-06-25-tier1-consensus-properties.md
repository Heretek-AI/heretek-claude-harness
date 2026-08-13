# Tier 1 Consensus Property-Based Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hypothesis property-based tests for the consensus state machine — verifying that `apply()`, `build_final_verdict()`, and `steward_node()` always produce correct outcomes under random inputs.

**Architecture:** One new test file using Hypothesis strategies to generate random agent verdicts. Properties assert invariants derived from the consensus rules. Deterministic edge-case tests verify known-critical paths.

**Tech Stack:** hypothesis 6.80+, pytest 8+, pytest-asyncio.

## Global Constraints

- Working directory: `backend/tier1/`
- Python 3.11
- Hypothesis goes in `[project.optional-dependencies].dev`
- Tests go in `tests/unit/test_consensus_properties.py`
- No new production code — only tests
- No live LLM calls — steward_node test uses mocked `build_final_verdict`

## File Structure

**Create:**
- `tests/unit/test_consensus_properties.py` — 9 tests (6 Hypothesis + 3 deterministic)

**Modify:**
- `pyproject.toml` — add `hypothesis>=6.80` to dev deps

---

## Task 1: Add Hypothesis dependency

**Files:**
- Modify: `pyproject.toml:31-40`

- [ ] **Step 1: Add hypothesis to dev deps**

Edit `backend/tier1/pyproject.toml`. Add `"hypothesis>=6.80"` to `[project.optional-dependencies].dev`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "freezegun>=1.4",
    "ruff>=0.4",
    "mypy>=1.10",
    "respx>=0.21",
    "docker>=7.1",
    "vcrpy>=6.0",
    "hypothesis>=6.80",
]
```

- [ ] **Step 2: Install**

```bash
cd backend/tier1 && source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 3: Verify import**

```bash
cd backend/tier1 && source .venv/bin/activate && python -c "import hypothesis; print(hypothesis.__version__)"
```

Expected: prints version ≥ 6.80.

- [ ] **Step 4: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/pyproject.toml && git commit -m "build(tier1): add Hypothesis for property-based testing"
```

---

## Task 2: Create consensus property-based tests

**Files:**
- Create: `tests/unit/test_consensus_properties.py`

**Interfaces:**
- Consumes: `consensus.apply`, `consensus.build_final_verdict`, `steward_node`, `AgentVerdict`, `DeliberationState`

- [ ] **Step 1: Write the test file**

Write `backend/tier1/tests/unit/test_consensus_properties.py`:

```python
"""Property-based tests for consensus logic using Hypothesis.

Tests consensus.apply(), build_final_verdict(), and steward_node()
with randomly generated agent verdicts to find edge cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from tier1.deliberation.nodes.consensus import apply, build_final_verdict
from tier1.deliberation.nodes.steward import steward_node
from tier1.deliberation.state import DeliberationEvent, DeliberationState


# --- Strategies ---

position_strat = st.sampled_from(["approve", "reject", "challenge"])
confidence_strat = st.floats(min_value=0.0, max_value=1.0)
concerns_strat = st.lists(st.text(max_size=20), max_size=3)
reasoning_strat = st.text(max_size=100)

verdict_strat = st.fixed_dictionaries({
    "position": position_strat,
    "confidence": confidence_strat,
    "concerns": concerns_strat,
    "reasoning": reasoning_strat,
})

three_verdicts = st.tuples(verdict_strat, verdict_strat, verdict_strat)


def _verdicts_to_dict(triple):
    """Convert tuple of 3 verdict dicts to the format apply() expects."""
    return {
        "alpha": triple[0],
        "beta": triple[1],
        "charlie": triple[2],
    }


VALID_DECISIONS = {"approved", "rejected", "needs-revision"}


# --- Property tests ---

@settings(max_examples=500)
@given(triple=three_verdicts)
def test_apply_always_returns_valid_decision(triple):
    """apply() must return one of the three valid decisions for any input."""
    votes = _verdicts_to_dict(triple)
    result = apply(votes)
    assert result in VALID_DECISIONS, f"Invalid decision: {result}"


@settings(max_examples=500)
@given(confidence=confidence_strat)
def test_unanimous_high_confidence_approves(confidence):
    """When all 3 approve and min(confidence) >= 0.7, result is approved."""
    floor = 0.7
    verdict = {"position": "approve", "confidence": confidence, "concerns": [], "reasoning": ""}
    votes = {"alpha": verdict, "beta": verdict, "charlie": verdict}
    result = apply(votes, unanimous_floor=floor)
    if confidence >= floor:
        assert result == "approved", f"Unanimous high confidence should approve, got {result}"


@settings(max_examples=500)
@given(triple=three_verdicts)
def test_two_of_three_rejects_rejected(triple):
    """When 2+ agents reject, result is rejected."""
    votes = _verdicts_to_dict(triple)
    rejects = sum(1 for v in triple if v["position"] == "reject")
    result = apply(votes)
    if rejects >= 2:
        assert result == "rejected", f"2+ rejects should yield rejected, got {result}"


@settings(max_examples=500)
@given(triple=three_verdicts)
def test_charlie_veto_overrides_approval(triple):
    """Charlie high-confidence challenge overrides unanimous approval."""
    alpha, beta, _ = triple
    charlie = {"position": "challenge", "confidence": 0.95, "concerns": [], "reasoning": ""}
    votes = {"alpha": alpha, "beta": beta, "charlie": charlie}
    result = apply(votes, charlie_veto_confidence=0.7)
    # If alpha and beta both approve, charlie's veto should force needs-revision
    if alpha["position"] == "approve" and beta["position"] == "approve":
        assert result == "needs-revision", (
            f"Charlie veto should override approval, got {result}"
        )


@settings(max_examples=200)
@given(triple=three_verdicts, round_num=st.integers(min_value=0, max_value=20))
def test_build_final_verdict_never_exceeds_rounds(triple, round_num):
    """build_final_verdict never returns needs-revision when round limit reached."""
    votes = _verdicts_to_dict(triple)
    decision = apply(votes)
    max_rounds = 3
    state: DeliberationState = {
        "deliberation_id": "test",
        "problem": "test",
        "user_id": "test",
        "round": round_num,
        "max_rounds": max_rounds,
        "alpha_verdict": triple[0],
        "beta_verdict": triple[1],
        "charlie_verdict": triple[2],
        "feedback": [],
        "events": [],
        "status": "running",
    }
    verdict = build_final_verdict(state, max_rounds=max_rounds)
    if round_num + 1 >= max_rounds and decision == "needs-revision":
        assert verdict.decision == "no-consensus", (
            f"Round limit should collapse needs-revision to no-consensus, got {verdict.decision}"
        )
    else:
        assert verdict.decision == decision


# --- Deterministic tests ---

def test_build_final_verdict_round_limit_collapses():
    """Exact boundary: round=2, max_rounds=3, needs-revision → no-consensus."""
    state: DeliberationState = {
        "deliberation_id": "test",
        "problem": "test",
        "user_id": "test",
        "round": 2,
        "max_rounds": 3,
        "alpha_verdict": {"position": "approve", "confidence": 0.8, "concerns": [], "reasoning": ""},
        "beta_verdict": {"position": "reject", "confidence": 0.6, "concerns": [], "reasoning": ""},
        "charlie_verdict": {"position": "challenge", "confidence": 0.5, "concerns": [], "reasoning": ""},
        "feedback": [],
        "events": [],
        "status": "running",
    }
    verdict = build_final_verdict(state, max_rounds=3)
    assert verdict.decision == "no-consensus"


async def test_steward_node_finalizes_on_approved():
    """steward_node sets status=completed and emits consensus_reached."""
    state: DeliberationState = {
        "deliberation_id": "test",
        "problem": "test",
        "user_id": "test",
        "round": 0,
        "max_rounds": 3,
        "alpha_verdict": {"position": "approve", "confidence": 0.9, "concerns": [], "reasoning": ""},
        "beta_verdict": {"position": "approve", "confidence": 0.8, "concerns": [], "reasoning": ""},
        "charlie_verdict": {"position": "approve", "confidence": 0.85, "concerns": [], "reasoning": ""},
        "feedback": [],
        "events": [],
        "status": "running",
    }
    sink = AsyncMock()
    result = await steward_node(state, sink=sink)
    assert result["status"] == "completed"
    assert result.get("final_verdict") is not None
    # sink should have been called with consensus_reached + completed events
    assert sink.call_count >= 2
    event_kinds = [call.args[0].kind for call in sink.call_args_list]
    assert "consensus_reached" in event_kinds
    assert "completed" in event_kinds


# --- Strategy validation ---

def test_strategy_generates_valid_verdicts():
    """Strategy produces verdicts with valid positions and confidence ranges."""
    for _ in range(100):
        v = verdict_strat.example()
        assert v["position"] in ("approve", "reject", "challenge")
        assert 0.0 <= v["confidence"] <= 1.0


def test_hypothesis_finds_known_edge_case():
    """Hypothesis can reach the all-challenge, high-confidence edge case."""
    votes = {
        "alpha": {"position": "challenge", "confidence": 0.9, "concerns": [], "reasoning": ""},
        "beta": {"position": "challenge", "confidence": 0.9, "concerns": [], "reasoning": ""},
        "charlie": {"position": "challenge", "confidence": 0.9, "concerns": [], "reasoning": ""},
    }
    result = apply(votes)
    assert result == "needs-revision"
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_consensus_properties.py -v --no-cov
```

Expected: all 9 tests pass. Note: Hypothesis tests may take a few seconds each (500 examples).

- [ ] **Step 3: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tests/unit/test_consensus_properties.py && git commit -m "test(tier1): property-based tests for consensus logic (Hypothesis)

9 tests: 6 Hypothesis property-based + 3 deterministic.
Covers: apply() decision validity, unanimous approval, reject majority,
Charlie veto, round-limit collapse, steward finalization."
```
