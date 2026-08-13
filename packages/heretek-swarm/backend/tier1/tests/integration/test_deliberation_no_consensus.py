"""Integration test: 3-round feedback loop ends in no-consensus."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.state import initial_state
from tier1.llm.garage import ModelGarage, StreamChunk


def _settings(max_rounds=3) -> Settings:
    return Settings(minimax_api_key="sk-test", max_rounds=max_rounds)


def _garage_with_per_round_responses(round_responses: list[dict[str, str]]) -> ModelGarage:
    """Each round's responses is a dict of agent -> JSON string."""
    g = ModelGarage(_settings())
    round_idx = {"value": 0}

    async def fake_stream(prompt, *, agent):
        idx = round_idx["value"]
        # Token-stream the response for the current round.
        text = round_responses[idx][agent]
        for token in text:
            yield StreamChunk(token=token, agent=agent, seq=0)
        # When alpha finishes a round (last token emitted), advance the round.
        if agent == "charlie":
            round_idx["value"] += 1

    g.stream_chat = fake_stream  # type: ignore[assignment]
    return g


@pytest.mark.integration
async def test_three_rounds_with_split_votes_ends_no_consensus():
    # Every round produces split verdicts (alpha approve, beta reject, charlie challenge).
    split_round = {
        "alpha": '{"position": "approve", "confidence": 0.7, "concerns": ["a"], "reasoning": "a"}',
        "beta": '{"position": "reject", "confidence": 0.7, "concerns": ["b"], "reasoning": "b"}',
        "charlie": '{"position": "challenge", "confidence": 0.5, "concerns": ["c"], "reasoning": "c"}',
    }
    responses = [split_round] * 3
    garage = _garage_with_per_round_responses(responses)
    tribunal = Tribunal(_settings(max_rounds=3), garage)
    state = initial_state(deliberation_id="abc", problem="hard problem")
    result = await tribunal.run(state)
    assert result["status"] == "completed"
    assert result["final_verdict"] is not None
    assert result["final_verdict"].decision == "no-consensus"


@pytest.mark.integration
async def test_three_rounds_emits_two_feedback_events():
    split_round = {
        "alpha": '{"position": "approve", "confidence": 0.7, "concerns": ["a"], "reasoning": "a"}',
        "beta": '{"position": "reject", "confidence": 0.7, "concerns": ["b"], "reasoning": "b"}',
        "charlie": '{"position": "challenge", "confidence": 0.5, "concerns": ["c"], "reasoning": "c"}',
    }
    responses = [split_round] * 3
    garage = _garage_with_per_round_responses(responses)
    tribunal = Tribunal(_settings(max_rounds=3), garage)
    state = initial_state(deliberation_id="abc", problem="x")
    result = await tribunal.run(state)
    feedback_events = [e for e in result["events"] if e.kind == "steward_feedback"]
    # 3 rounds -> 2 feedback events (between rounds).
    assert len(feedback_events) == 2


@pytest.mark.integration
async def test_consensus_reached_on_round_2_after_feedback():
    round1 = {
        "alpha": '{"position": "approve", "confidence": 0.7, "concerns": ["a"], "reasoning": "a"}',
        "beta": '{"position": "reject", "confidence": 0.7, "concerns": ["b"], "reasoning": "b"}',
        "charlie": '{"position": "challenge", "confidence": 0.5, "concerns": ["c"], "reasoning": "c"}',
    }
    round2 = {
        "alpha": '{"position": "approve", "confidence": 0.9, "concerns": [], "reasoning": "convinced"}',
        "beta": '{"position": "approve", "confidence": 0.9, "concerns": [], "reasoning": "convinced"}',
        "charlie": '{"position": "approve", "confidence": 0.8, "concerns": [], "reasoning": "convinced"}',
    }
    garage = _garage_with_per_round_responses([round1, round2])
    tribunal = Tribunal(_settings(max_rounds=3), garage)
    state = initial_state(deliberation_id="abc", problem="x")
    result = await tribunal.run(state)
    assert result["final_verdict"].decision == "approved"
    assert result["round"] == 1  # Convinced on round 2 (0-indexed: round=1)
