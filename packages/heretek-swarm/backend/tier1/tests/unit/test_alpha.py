"""Tests for Alpha agent node, with mocked ModelGarage."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.deliberation.nodes.alpha import alpha_node
from tier1.deliberation.state import (
    DeliberationEvent,
    DeliberationState,
    initial_state,
    next_seq,
    now_ts,
)
from tier1.llm.errors import LLMMalformed
from tier1.llm.garage import ModelGarage, StreamChunk


def _garage_with_chunks(chunks: list[str]) -> ModelGarage:
    g = ModelGarage(Settings(minimax_api_key="sk-test"))

    async def fake_stream(prompt, *, agent):
        for token in chunks:
            yield StreamChunk(token=token, agent=agent, seq=0)

    g.stream_chat = fake_stream  # type: ignore[assignment]
    return g


async def test_alpha_emits_thinking_and_verdict_events():
    raw = '{"position": "approve", "confidence": 0.9, "concerns": [], "reasoning": "looks fine"}'
    garage = _garage_with_chunks([raw])
    state = initial_state(deliberation_id="abc", problem="hello")
    result = await alpha_node(state, garage)

    kinds = [e.kind for e in result["events"]]
    assert "alpha_thinking" in kinds
    assert "alpha_verdict" in kinds
    assert kinds.index("alpha_thinking") < kinds.index("alpha_verdict")
    assert result["alpha_verdict"] is not None
    assert result["alpha_verdict"].position == "approve"
    assert result["alpha_verdict"].confidence == 0.9


async def test_alpha_streams_tokens_and_emits_token_events():
    garage = _garage_with_chunks(
        ['{"position":', ' "approve"', ', "confidence":', " 0.5,", ' "reasoning": "x"}']
    )
    state = initial_state(deliberation_id="abc", problem="x")
    result = await alpha_node(state, garage)
    token_events = [e for e in result["events"] if e.kind == "token"]
    assert len(token_events) == 5
    assert token_events[0].payload["token"] == '{"position":'
    assert result["alpha_verdict"].position == "approve"


async def test_alpha_handles_markdown_fenced_json():
    raw = '```json\n{"position": "reject", "confidence": 0.8, "concerns": ["x"], "reasoning": "no"}\n```'
    garage = _garage_with_chunks([raw])
    state = initial_state(deliberation_id="abc", problem="x")
    result = await alpha_node(state, garage)
    assert result["alpha_verdict"].position == "reject"
    assert result["alpha_verdict"].concerns == ["x"]


async def test_alpha_raises_on_malformed_output():
    garage = _garage_with_chunks(["this is not json"])
    state = initial_state(deliberation_id="abc", problem="x")
    with pytest.raises(LLMMalformed):
        await alpha_node(state, garage)


async def test_alpha_emits_events_in_monotonic_seq():
    raw = '{"position": "approve", "confidence": 0.5, "concerns": [], "reasoning": "x"}'
    garage = _garage_with_chunks([raw])
    state = initial_state(deliberation_id="abc", problem="x")
    result = await alpha_node(state, garage)
    seqs = [e.seq for e in result["events"]]
    assert seqs == sorted(seqs)
    assert seqs == list(range(len(seqs)))


async def test_alpha_sink_receives_events():
    raw = '{"position": "approve", "confidence": 0.5, "concerns": [], "reasoning": "x"}'
    garage = _garage_with_chunks([raw])
    state = initial_state(deliberation_id="abc", problem="x")
    received: list[DeliberationEvent] = []

    async def sink(e):
        received.append(e)

    await alpha_node(state, garage, sink=sink)
    assert len(received) >= 2  # thinking + verdict
    assert any(e.kind == "alpha_verdict" for e in received)
