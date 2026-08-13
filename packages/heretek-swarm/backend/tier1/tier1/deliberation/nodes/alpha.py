"""Alpha — analysis agent node."""

from __future__ import annotations

from functools import partial
from typing import Awaitable, Callable

from tier1.deliberation.nodes._base import run_agent
from tier1.deliberation.state import DeliberationEvent, DeliberationState
from tier1.llm.garage import ModelGarage

EventSink = Callable[[DeliberationEvent], Awaitable[None]]


async def alpha_node(
    state: DeliberationState,
    garage: ModelGarage,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
) -> DeliberationState:
    return await run_agent(state, garage, agent="alpha", sink=sink, memory=memory)


# LangGraph expects nodes to take only state; bind garage at graph-build time.
def make_alpha_node(
    garage: ModelGarage,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
):
    if sink is None and memory is None:
        return partial(alpha_node, garage=garage)
    if memory is None:
        return partial(alpha_node, garage=garage, sink=sink)
    if sink is None:
        return partial(alpha_node, garage=garage, memory=memory)
    return partial(alpha_node, garage=garage, sink=sink, memory=memory)
