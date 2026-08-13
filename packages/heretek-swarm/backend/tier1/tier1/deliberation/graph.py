"""LangGraph state machine for the Core Triad deliberation.

Graph topology:
    START -> alpha -> beta -> charlie -> steward_tally -> [finalize | feedback_round]
                                                          |                |
                                                          v                v
                                                       END              alpha (loop)

`finalize` triggers when the Steward has set status='completed'
(approved, rejected, or no-consensus). `feedback_round` triggers
otherwise; the graph loops back to alpha with the new feedback list.
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Awaitable, Callable

from tier1.observability import get_tracer
from tier1.observability.metrics import (
    record_deliberation_latency,
    record_deliberation_rounds,
)

from langgraph.graph import END, START, StateGraph

from tier1.config import Settings
from tier1.deliberation.nodes.alpha import make_alpha_node
from tier1.deliberation.nodes.beta import make_beta_node
from tier1.deliberation.nodes.charlie import make_charlie_node
from tier1.deliberation.nodes.steward import make_steward_node
from tier1.deliberation.state import (
    DeliberationEvent,
    DeliberationState,
)
from tier1.llm.garage import ModelGarage
from tier1.memory import MemoryBackend

EventSink = Callable[[DeliberationEvent], Awaitable[None]]


def _should_finalize(state: DeliberationState) -> str:
    """Conditional edge: route to finalize or feedback."""
    if state.get("status") == "completed":
        return "finalize"
    return "feedback"


async def _finalize_node(state: DeliberationState) -> DeliberationState:
    """Terminal node — marks status=completed. No events emitted."""
    return {**state, "status": "completed"}


class Tribunal:
    """Compiled LangGraph that runs one deliberation end-to-end."""

    def __init__(
        self,
        settings: Settings,
        garage: ModelGarage,
        sink: EventSink | None = None,
        memory: "MemoryBackend | None" = None,
    ) -> None:
        self.settings = settings
        self.garage = garage
        self.sink = sink
        self.memory = memory
        self._compiled = self._build(self.sink, self.memory)

    def _build(self, sink: EventSink | None, memory: "MemoryBackend | None" = None):
        g = StateGraph(DeliberationState)
        g.add_node("alpha", make_alpha_node(self.garage, sink, memory))
        g.add_node("beta", make_beta_node(self.garage, sink, memory))
        g.add_node("charlie", make_charlie_node(self.garage, sink, memory))
        g.add_node("steward_tally", make_steward_node(self.settings, sink, memory))
        g.add_node("finalize", _finalize_node)

        g.add_edge(START, "alpha")
        g.add_edge("alpha", "beta")
        g.add_edge("beta", "charlie")
        g.add_edge("charlie", "steward_tally")
        g.add_conditional_edges(
            "steward_tally",
            _should_finalize,
            {"finalize": "finalize", "feedback": "alpha"},
        )
        g.add_edge("finalize", END)
        return g.compile()

    async def run(self, state: DeliberationState) -> DeliberationState:
        """Run the tribunal to completion. Returns final state."""
        tracer = get_tracer("tier1.tribunal")
        with tracer.start_as_current_span("tribunal.run") as span:
            span.set_attribute("deliberation.id", state.get("deliberation_id", ""))
            t0 = time.monotonic()
            result = await self._compiled.ainvoke(state)
            elapsed = time.monotonic() - t0
            rounds = result.get("round", 0) + 1
            span.set_attribute("deliberation.rounds", rounds)
            record_deliberation_latency(elapsed)
            record_deliberation_rounds(rounds)
            return DeliberationState(result)

    async def stream(self, state: DeliberationState) -> AsyncIterator[DeliberationEvent]:
        """Yield events as they happen during the run.

        Wraps the run with an internal collector that pushes every event
        emitted via the sink to a queue, which this method yields. Also
        re-emits any events already on the state (e.g. the initial
        "started" event) so consumers see the full timeline.
        """
        queue: asyncio.Queue[DeliberationEvent | None] = asyncio.Queue()

        async def combined_sink(event: DeliberationEvent) -> None:
            await queue.put(event)
            if self.sink is not None:
                await self.sink(event)

        # Forward pre-existing events (e.g. the initial "started" event
        # from initial_state) before the graph runs.
        for event in state.get("events", []):
            await queue.put(event)
            if self.sink is not None:
                await self.sink(event)

        compiled = self._build(combined_sink)

        run_task = asyncio.create_task(compiled.ainvoke(state))

        # Drain events as they arrive; signal completion by sending None
        # AFTER the run task finishes so the consumer can break.
        async def signal_done() -> None:
            await run_task
            await queue.put(None)

        done_task = asyncio.create_task(signal_done())

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

        await done_task
