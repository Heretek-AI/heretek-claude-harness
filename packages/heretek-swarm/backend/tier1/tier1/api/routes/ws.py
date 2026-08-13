"""WebSocket endpoint: live deliberation stream + replay."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tier1.events.channels import subject_for

router = APIRouter()


@router.websocket("/ws/deliberations/{deliberation_id}")
async def deliberation_socket(websocket: WebSocket, deliberation_id: str):
    await websocket.accept()

    # Resolve clients from app.state so we work the same in tests and prod.
    pg = websocket.app.state.pg
    nats = websocket.app.state.nats

    # Replay persisted events.
    events = await pg.get_events(deliberation_id)
    for event in events:
        await websocket.send_json({"kind": "event", "event": event.model_dump()})
    await websocket.send_json({"kind": "replay_done", "count": len(events)})

    # Subscribe to NATS for new events.
    subject = subject_for(deliberation_id)

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def consume():
        async for payload in nats.subscribe(subject):
            await queue.put(payload)
        await queue.put(None)

    consumer_task = asyncio.create_task(consume())

    try:
        while True:
            # Read pings from client to keep the connection alive.
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                data = json.loads(msg)
                if data.get("kind") == "ping":
                    await websocket.send_json({"kind": "pong"})
            except asyncio.TimeoutError:
                pass

            # Forward any NATS messages.
            try:
                payload = queue.get_nowait()
                if payload is None:
                    break
                event_dict = json.loads(payload)
                await websocket.send_json({"kind": "event", "event": event_dict})
            except asyncio.QueueEmpty:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        consumer_task.cancel()
