"""Integration test: user interjects between rounds; agents see feedback."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.state import (
    DeliberationEvent,
    initial_state,
    next_seq,
    now_ts,
)
from tier1.llm.garage import ModelGarage, StreamChunk


def _settings() -> Settings:
    return Settings(minimax_api_key="sk-test", max_rounds=3)


def _garage_capturing_prompts(captured: list) -> ModelGarage:
    g = ModelGarage(_settings())
    round_idx = {"value": 0}

    async def fake_stream(prompt, *, agent):
        captured.append((round_idx["value"], agent, prompt))
        # Round 0: split votes. Round 1: unanimous approval.
        if round_idx["value"] == 0:
            text = {
                "alpha": '{"position": "approve", "confidence": 0.6, "concerns": ["need more info"], "reasoning": "a"}',
                "beta": '{"position": "reject", "confidence": 0.6, "concerns": ["missing data"], "reasoning": "b"}',
                "charlie": '{"position": "challenge", "confidence": 0.5, "concerns": ["risk"], "reasoning": "c"}',
            }[agent]
        else:
            text = '{"position": "approve", "confidence": 0.9, "concerns": [], "reasoning": "ok"}'
        for token in text:
            yield StreamChunk(token=token, agent=agent, seq=0)
        if agent == "charlie":
            round_idx["value"] += 1

    g.stream_chat = fake_stream  # type: ignore[assignment]
    return g


@pytest.mark.integration
async def test_interjection_appears_in_next_round_prompt():
    captured: list = []
    garage = _garage_capturing_prompts(captured)
    tribunal = Tribunal(_settings(), garage)
    state = initial_state(deliberation_id="abc", problem="test problem")

    # Inject the interjection before the first agent runs.
    state["feedback"] = ["please consider the safety implications"]

    result = await tribunal.run(state)
    # Round 1's prompts should mention the interjection.
    round1_prompts = [p for (r, a, p) in captured if r == 1]
    assert any("please consider the safety implications" in p for p in round1_prompts)


@pytest.mark.integration
async def test_interjection_event_recorded_when_added_via_api_path(monkeypatch):
    # Smoke: simulating the API path: append a user_interjection event,
    # then run the tribunal.
    captured: list = []
    garage = _garage_capturing_prompts(captured)
    tribunal = Tribunal(_settings(), garage)
    state = initial_state(deliberation_id="abc", problem="test")
    state["events"].append(
        DeliberationEvent(
            seq=next_seq(state["events"]),
            ts=now_ts(),
            kind="user_interjection",
            payload={"text": "user says hello"},
        )
    )
    state["feedback"].append("user says hello")
    result = await tribunal.run(state)
    interjection_events = [e for e in result["events"] if e.kind == "user_interjection"]
    assert len(interjection_events) == 1
