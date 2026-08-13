"""Tests for Beta — receives Alpha's verdict in its prompt."""

from __future__ import annotations

from tier1.config import Settings
from tier1.deliberation.nodes.beta import beta_node
from tier1.deliberation.state import AgentVerdict, initial_state
from tier1.llm.garage import ModelGarage, StreamChunk


def _garage_capturing_prompt(captured: list[str]) -> ModelGarage:
    g = ModelGarage(Settings(minimax_api_key="sk-test"))

    async def fake_stream(prompt, *, agent):
        captured.append(prompt)
        for token in [
            '{"position": "approve", "confidence": 0.5, "concerns": [], "reasoning": "x"}'
        ]:
            yield StreamChunk(token=token, agent=agent, seq=0)

    g.stream_chat = fake_stream  # type: ignore[assignment]
    return g


async def test_beta_prompt_includes_alpha_verdict():
    captured: list[str] = []
    garage = _garage_capturing_prompt(captured)
    state = initial_state(deliberation_id="abc", problem="the problem")
    state["alpha_verdict"] = AgentVerdict(
        agent="alpha",
        position="approve",
        confidence=0.7,
        concerns=["x"],
        reasoning="alpha says ok",
    )
    await beta_node(state, garage)
    assert len(captured) == 1
    assert "ALPHA'S VERDICT" in captured[0]
    assert "alpha says ok" in captured[0]


async def test_beta_emits_beta_verdict_event():
    garage = _garage_capturing_prompt([])
    state = initial_state(deliberation_id="abc", problem="x")
    result = await beta_node(state, garage)
    assert result["beta_verdict"] is not None
    assert any(e.kind == "beta_verdict" for e in result["events"])


async def test_beta_works_without_alpha_verdict():
    """Beta can still run if Alpha hasn't produced a verdict (defensive)."""
    captured: list[str] = []
    garage = _garage_capturing_prompt(captured)
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = None
    result = await beta_node(state, garage)
    assert "ALPHA'S VERDICT" not in captured[0]
    assert result["beta_verdict"] is not None
