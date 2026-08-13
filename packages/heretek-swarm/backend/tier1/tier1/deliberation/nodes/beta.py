"""Beta — validation agent node."""

from __future__ import annotations

from functools import partial
from typing import Awaitable, Callable

from tier1.deliberation.nodes._base import run_agent
from tier1.deliberation.state import DeliberationEvent, DeliberationState
from tier1.llm.garage import ModelGarage

EventSink = Callable[[DeliberationEvent], Awaitable[None]]


async def beta_node(
    state: DeliberationState,
    garage: ModelGarage,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
) -> DeliberationState:
    return await run_agent(state, garage, agent="beta", sink=sink, memory=memory)


def make_beta_node(
    garage: ModelGarage,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
):
    if sink is None and memory is None:
        return partial(beta_node, garage=garage)
    if memory is None:
        return partial(beta_node, garage=garage, sink=sink)
    if sink is None:
        return partial(beta_node, garage=garage, memory=memory)
    return partial(beta_node, garage=garage, sink=sink, memory=memory)
