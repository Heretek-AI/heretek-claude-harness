"""REST endpoints for deliberations."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from tier1.api.deps import GarageDep, NatsDep, PgDep, RedisDep
from tier1.api.schemas import (
    DeliberationListResponse,
    InterjectRequest,
    NewDeliberationRequest,
    NewDeliberationResponse,
)
from tier1.dashboard.bridge import make_nats_sink_for
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.state import (
    DeliberationEvent,
    initial_state,
    new_deliberation_id,
    next_seq,
    now_ts,
)
from tier1.events.channels import subject_for
from tier1.llm.errors import LLMUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deliberations")


@router.post("", response_model=NewDeliberationResponse, status_code=status.HTTP_201_CREATED)
async def create_deliberation(
    body: NewDeliberationRequest,
    request: Request,
    pg: PgDep,
    redis: RedisDep,
    nats: NatsDep,
    garage: GarageDep,
) -> NewDeliberationResponse:
    did = new_deliberation_id()
    state = initial_state(
        deliberation_id=did,
        problem=body.problem,
        user_id=getattr(request.state, "user_id", "default"),
    )
    await pg.save_deliberation(state)
    await redis.put_state(state)
    # Publish the started event to NATS AND persist it to Postgres so the
    # WS replay path can deliver it to late-arriving clients.
    started = state["events"][0]
    await nats.publish(subject_for(did), started.model_dump_json().encode())
    await pg.append_event(did, started)

    # Run the tribunal in the background.
    nats_sink = make_nats_sink_for(nats, did, pg=pg)
    tribunal = Tribunal(request.app.state.settings, garage, sink=nats_sink)

    async def run_and_persist():
        try:
            result = await tribunal.run(state)
            await pg.save_deliberation(result)
            await redis.put_state(result)
        except LLMUnavailable as exc:
            logger.exception("tribunal failed: LLM unavailable for %s", did)
            failed_state = {**state, "status": "failed", "failure_reason": str(exc)}
            failed_state["events"] = list(state.get("events", []))
            failed_event = DeliberationEvent(
                seq=next_seq(failed_state["events"]),
                ts=now_ts(),
                kind="consensus_failed",
                payload={"reason": "llm_unavailable"},
            )
            failed_state["events"].append(failed_event)
            await pg.save_deliberation(failed_state)
            await pg.append_event(did, failed_event)
            await redis.put_state(failed_state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("tribunal failed: unexpected error for %s", did)
            failed_state = {**state, "status": "failed", "failure_reason": str(exc)}
            await pg.save_deliberation(failed_state)
            await redis.put_state(failed_state)

    asyncio.create_task(run_and_persist())

    return NewDeliberationResponse(id=did)


@router.get("/{deliberation_id}")
async def get_deliberation(deliberation_id: str, pg: PgDep):
    state = await pg.load_deliberation(deliberation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="deliberation not found")
    events = await pg.get_events(deliberation_id)
    final = state.get("final_verdict")
    return {
        "id": state["deliberation_id"],
        "problem": state["problem"],
        "status": state.get("status", "running"),
        "final_verdict": final.model_dump() if final is not None else None,
        "events": [e.model_dump() for e in events],
    }


@router.post("/{deliberation_id}/interject", status_code=204)
async def interject(
    deliberation_id: str,
    body: InterjectRequest,
    pg: PgDep,
    redis: RedisDep,
    nats: NatsDep,
):
    state = await pg.load_deliberation(deliberation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="deliberation not found")
    if state.get("status") != "running":
        raise HTTPException(status_code=409, detail=f"deliberation is {state.get('status')}")
    feedback = list(state.get("feedback", []))
    feedback.append(body.text)
    state["feedback"] = feedback
    state["events"] = list(state.get("events", []))
    interjection_event = DeliberationEvent(
        seq=next_seq(state["events"]),
        ts=now_ts(),
        kind="user_interjection",
        payload={"text": body.text, "deliberation_id": deliberation_id},
    )
    state["events"].append(interjection_event)
    await pg.save_deliberation(state)
    await pg.append_event(deliberation_id, interjection_event)
    # Publish to NATS so live WS clients (and the running Tribunal sink)
    # see the interjection.
    await nats.publish(subject_for(deliberation_id), interjection_event.model_dump_json().encode())
    await redis.put_state(state)


@router.get("", response_model=DeliberationListResponse)
async def list_deliberations(
    pg: PgDep, limit: int = Query(20, ge=1, le=100)
) -> DeliberationListResponse:
    summaries = await pg.list_deliberations(limit)
    return DeliberationListResponse(items=summaries)
