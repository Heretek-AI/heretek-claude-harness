"""Tests for memory wiring into the deliberation graph."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from tier1.config import Settings
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.nodes._base import run_agent
from tier1.deliberation.state import initial_state


def _settings() -> Settings:
    return Settings(
        minimax_api_key="",
        anthropic_api_key="",
        openai_api_key="",
    )


def _fake_memory(entries=None, search_error=None, store_error=None):
    """Build a mocked MemoryBackend."""
    mem = AsyncMock()
    if search_error:
        mem.search = AsyncMock(side_effect=search_error)
    else:
        mem.search = AsyncMock(return_value=entries or [])
    if store_error:
        mem.store = AsyncMock(side_effect=store_error)
    else:
        mem.store = AsyncMock(return_value="entry-id")
    return mem


def _fake_garage():
    """ModelGarage stub that yields a valid verdict-shaped string."""
    garage = MagicMock()
    return garage


def _make_capturing_stream(garage, captured):
    async def capturing_stream(prompt, *, agent):
        captured.append(prompt)
        yield MagicMock(
            token='{"position":"approve","confidence":0.7,"reasoning":"ok","concerns":[]}',
            agent=agent,
            seq=0,
        )

    garage.stream_chat = capturing_stream
    return garage


_VERDICT_JSON = '{"position":"approve","confidence":0.7,"reasoning":"ok","concerns":[]}'


async def test_run_agent_recalls_before_streaming():
    memory = _fake_memory(
        entries=[
            MagicMock(deliberation_id="d1", agent="alpha", content="past reasoning"),
        ]
    )
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="new", problem="test problem")

    await run_agent(state, garage, agent="alpha", memory=memory)

    memory.search.assert_awaited_once()
    assert memory.search.await_args.kwargs["top_k"] == 3
    assert memory.search.await_args.args[0] == "test problem"
    assert "PAST DELIBERATIONS" in captured[0]
    assert "[d1]" in captured[0]
    assert "past reasoning" in captured[0]


async def test_run_agent_stores_after_verdict():
    memory = _fake_memory()
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="abc", problem="x")

    await run_agent(state, garage, agent="alpha", memory=memory)

    memory.store.assert_awaited_once()
    entry = memory.store.await_args.args[0]
    assert entry.deliberation_id == "abc"
    assert entry.agent == "alpha"
    assert entry.content == "ok"
    assert entry.metadata["position"] == "approve"


async def test_run_agent_without_memory_is_unchanged():
    """memory=None must produce identical behavior to old code."""
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="x", problem="y")

    result = await run_agent(state, garage, agent="alpha")  # no memory kwarg

    assert result.get("alpha_verdict") is not None
    assert result["alpha_verdict"].position == "approve"
    assert "PAST DELIBERATIONS" not in captured[0]


async def test_run_agent_search_failure_does_not_break():
    memory = _fake_memory(search_error=RuntimeError("qdrant down"))
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="x", problem="y")

    result = await run_agent(state, garage, agent="alpha", memory=memory)

    assert result.get("alpha_verdict") is not None


async def test_run_agent_store_failure_does_not_break():
    memory = _fake_memory(store_error=RuntimeError("postgres down"))
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="x", problem="y")

    result = await run_agent(state, garage, agent="alpha", memory=memory)

    assert result.get("alpha_verdict") is not None


async def test_tribunal_accepts_memory():
    """Tribunal constructs with a memory backend without error."""
    settings = _settings()
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    memory = _fake_memory()

    tribunal = Tribunal(settings, garage, memory=memory)

    assert tribunal.memory is memory


async def test_tribunal_without_memory_default():
    """Tribunal() with no memory still constructs and is callable."""
    settings = _settings()
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)

    tribunal = Tribunal(settings, garage)

    assert tribunal.memory is None
    assert tribunal._compiled is not None
