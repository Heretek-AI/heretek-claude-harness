"""Shared agent-node logic.

Each agent node is a thin wrapper around `run_agent` that fixes the
`agent` parameter. The agent signature is:

    async def alpha_node(state: DeliberationState, garage: ModelGarage) -> DeliberationState

LangGraph calls nodes with only the state, so the `garage` is bound at
graph-build time via functools.partial.
"""

from __future__ import annotations

import json
from typing import Awaitable, Callable

import structlog

from tier1.deliberation.nodes.parser import parse_verdict
from tier1.deliberation.state import (
    AgentName,
    DeliberationEvent,
    DeliberationState,
    next_seq,
    now_ts,
)
from tier1.llm.garage import ModelGarage, StreamChunk
from tier1.observability.metrics import record_agent_tokens
from tier1.llm.prompts import SYSTEM_PROMPTS
from tier1.memory import MemoryBackend, MemoryEntry, MemoryType

log = structlog.get_logger(__name__)

EventSink = Callable[[DeliberationEvent], Awaitable[None]]


def build_user_prompt(state: DeliberationState, agent: AgentName) -> str:
    """Construct the user-turn prompt for an agent node."""
    parts: list[str] = [f"PROBLEM:\n{state['problem']}\n"]
    if state.get("feedback"):
        parts.append(
            "FEEDBACK FROM PRIOR ROUND:\n" + "\n".join(f"- {f}" for f in state["feedback"])
        )
    if agent in ("beta", "charlie") and state.get("alpha_verdict") is not None:
        av = state["alpha_verdict"]
        parts.append(
            "ALPHA'S VERDICT (prior round or this round):\n"
            f"position={av.position} confidence={av.confidence}\n"
            f"reasoning: {av.reasoning}\n"
            f"concerns: {av.concerns}\n"
        )
    if agent == "charlie" and state.get("beta_verdict") is not None:
        bv = state["beta_verdict"]
        parts.append(
            "BETA'S VERDICT:\n"
            f"position={bv.position} confidence={bv.confidence}\n"
            f"reasoning: {bv.reasoning}\n"
            f"concerns: {bv.concerns}\n"
        )
    parts.append("Respond with the JSON object as specified in the system prompt.")
    return "\n\n".join(parts)


async def run_agent(
    state: DeliberationState,
    garage: ModelGarage,
    *,
    agent: AgentName,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
) -> DeliberationState:
    """Execute one agent node: prompt -> streamed tokens -> parsed verdict."""
    system = SYSTEM_PROMPTS[agent]
    user = build_user_prompt(state, agent)

    # Memory recall: pull past deliberations on similar topics.
    if memory is not None:
        try:
            recall = await memory.search(state["problem"], top_k=3)
        except Exception:  # noqa: BLE001
            log.warning("memory.recall_failed", agent=agent, exc_info=True)
            recall = []
        if recall:
            recall_block = "PAST DELIBERATIONS ON SIMILAR TOPICS:\n" + "\n".join(
                f"- [{r.deliberation_id}] {r.agent}: {r.content[:200]}" for r in recall
            )
            user = user + "\n\n" + recall_block

    full_prompt = f"{system}\n\n{user}"

    # Emit "thinking" event
    events = list(state.get("events", []))
    thinking_kind = {
        "alpha": "alpha_thinking",
        "beta": "beta_thinking",
        "charlie": "charlie_thinking",
    }[agent]
    events.append(
        DeliberationEvent(
            seq=next_seq(events),
            ts=now_ts(),
            kind=thinking_kind,
            payload={},
        )
    )
    if sink is not None:
        await sink(events[-1])

    # Stream tokens, accumulate, emit token events
    accumulated: list[str] = []
    async for chunk in garage.stream_chat(full_prompt, agent=agent):
        accumulated.append(chunk.token)
        events.append(
            DeliberationEvent(
                seq=next_seq(events),
                ts=now_ts(),
                kind="token",
                payload={"agent": agent, "token": chunk.token, "seq": chunk.seq},
            )
        )
        if sink is not None:
            await sink(events[-1])

    raw = "".join(accumulated)
    record_agent_tokens(agent, len(accumulated))
    verdict = parse_verdict(agent, raw)

    # Emit verdict event
    verdict_kind = {
        "alpha": "alpha_verdict",
        "beta": "beta_verdict",
        "charlie": "charlie_verdict",
    }[agent]
    events.append(
        DeliberationEvent(
            seq=next_seq(events),
            ts=now_ts(),
            kind=verdict_kind,
            payload=verdict.model_dump(),
        )
    )
    if sink is not None:
        await sink(events[-1])

    # Memory store: persist the verdict reasoning for future recall.
    if memory is not None:
        entry = MemoryEntry(
            content=verdict.reasoning,
            memory_type=MemoryType.semantic,
            source="deliberation",
            deliberation_id=state.get("deliberation_id"),
            agent=agent,
            metadata={
                "position": verdict.position,
                "confidence": verdict.confidence,
                "round": state.get("round", 0),
            },
        )
        try:
            await memory.store(entry)
        except Exception:  # noqa: BLE001
            log.warning("memory.store_failed", agent=agent, exc_info=True)

    # Update state
    new_state: DeliberationState = {**state, "events": events}
    if agent == "alpha":
        new_state["alpha_verdict"] = verdict
    elif agent == "beta":
        new_state["beta_verdict"] = verdict
    elif agent == "charlie":
        new_state["charlie_verdict"] = verdict
    return new_state
