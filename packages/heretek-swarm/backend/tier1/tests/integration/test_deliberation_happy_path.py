"""End-to-end integration test: full 1-round approval flow."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.state import initial_state
from tier1.llm.garage import ModelGarage, StreamChunk


def _settings() -> Settings:
    return Settings(minimax_api_key="sk-test", max_rounds=3)


def _garage_with_responses(responses: dict[str, str]) -> ModelGarage:
    g = ModelGarage(_settings())

    async def fake_stream(prompt, *, agent):
        text = responses[agent]
        # Stream one token at a time.
        for token in text:
            yield StreamChunk(token=token, agent=agent, seq=0)

    g.stream_chat = fake_stream  # type: ignore[assignment]
    return g


@pytest.fixture
def unanimous_responses() -> dict[str, str]:
    return {
        "alpha": '{"position": "approve", "confidence": 0.9, "concerns": [], "reasoning": "fine"}',
        "beta": '{"position": "approve", "confidence": 0.85, "concerns": [], "reasoning": "valid"}',
        "charlie": '{"position": "approve", "confidence": 0.8, "concerns": [], "reasoning": "ok"}',
    }


@pytest.mark.integration
async def test_unanimous_approval_finishes_in_one_round(unanimous_responses):
    garage = _garage_with_responses(unanimous_responses)
    tribunal = Tribunal(_settings(), garage)
    state = initial_state(deliberation_id="abc", problem="test")
    result = await tribunal.run(state)
    assert result["status"] == "completed"
    assert result["final_verdict"] is not None
    assert result["final_verdict"].decision == "approved"
    assert result["round"] == 0  # No feedback round


@pytest.mark.integration
async def test_unanimous_emits_started_thinking_verdict_completed(unanimous_responses):
    garage = _garage_with_responses(unanimous_responses)
    tribunal = Tribunal(_settings(), garage)
    state = initial_state(deliberation_id="abc", problem="test")
    result = await tribunal.run(state)
    kinds = [e.kind for e in result["events"]]
    assert "started" in kinds
    assert "alpha_thinking" in kinds
    assert "beta_thinking" in kinds
    assert "charlie_thinking" in kinds
    assert "consensus_reached" in kinds
    assert "completed" in kinds


@pytest.mark.integration
async def test_alpha_runs_before_beta_runs_before_charlie(unanimous_responses):
    garage = _garage_with_responses(unanimous_responses)
    tribunal = Tribunal(_settings(), garage)
    state = initial_state(deliberation_id="abc", problem="test")
    result = await tribunal.run(state)
    kinds = [e.kind for e in result["events"]]
    a = kinds.index("alpha_verdict")
    b = kinds.index("beta_verdict")
    c = kinds.index("charlie_verdict")
    assert a < b < c


@pytest.mark.integration
async def test_stream_yields_events_as_they_happen(unanimous_responses):
    garage = _garage_with_responses(unanimous_responses)
    tribunal = Tribunal(_settings(), garage)
    state = initial_state(deliberation_id="abc", problem="test")
    seen_kinds: list[str] = []
    async for event in tribunal.stream(state):
        seen_kinds.append(event.kind)
    assert "started" in seen_kinds
    assert "alpha_thinking" in seen_kinds
    assert "completed" in seen_kinds
