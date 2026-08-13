"""Tests for Charlie — sees both Alpha and Beta verdicts."""

from __future__ import annotations

from tier1.config import Settings
from tier1.deliberation.nodes.charlie import charlie_node
from tier1.deliberation.state import AgentVerdict, initial_state
from tier1.llm.garage import ModelGarage, StreamChunk


def _garage_capturing(captured: list[str]) -> ModelGarage:
    g = ModelGarage(Settings(minimax_api_key="sk-test"))

    async def fake_stream(prompt, *, agent):
        captured.append(prompt)
        for token in [
            '{"position": "challenge", "confidence": 0.8, "concerns": ["risk"], "reasoning": "I disagree"}'
        ]:
            yield StreamChunk(token=token, agent=agent, seq=0)

    g.stream_chat = fake_stream  # type: ignore[assignment]
    return g


async def test_charlie_prompt_includes_alpha_and_beta():
    captured: list[str] = []
    garage = _garage_capturing(captured)
    state = initial_state(deliberation_id="abc", problem="the problem")
    state["alpha_verdict"] = AgentVerdict(
        agent="alpha", position="approve", confidence=0.6, concerns=[], reasoning="alpha"
    )
    state["beta_verdict"] = AgentVerdict(
        agent="beta", position="reject", confidence=0.5, concerns=["flaw"], reasoning="beta"
    )
    await charlie_node(state, garage)
    assert "ALPHA'S VERDICT" in captured[0]
    assert "BETA'S VERDICT" in captured[0]
    assert "alpha" in captured[0]
    assert "beta" in captured[0]


async def test_charlie_emits_charlie_verdict_event():
    garage = _garage_capturing([])
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = AgentVerdict(
        agent="alpha", position="approve", confidence=0.5, concerns=[], reasoning="x"
    )
    result = await charlie_node(state, garage)
    assert result["charlie_verdict"] is not None
    assert result["charlie_verdict"].position == "challenge"
    assert any(e.kind == "charlie_verdict" for e in result["events"])
