"""WS broadcast bridge — connects LangGraph sink to NATS publish.

This helper wraps the Tribunal so that every event emitted by an agent
node is also published to NATS JetStream on the per-deliberation subject,
and persisted to Postgres `deliberation_events` so the WS replay path
sees the same events the live NATS stream sees.

The same callback is used by the API WebSocket endpoint to forward
events to the connected client.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from tier1.deliberation.state import DeliberationEvent
from tier1.events.channels import subject_for
from tier1.events.nats_client import NatsClient
from tier1.persistence.postgres import PostgresPool

EventSink = Callable[[DeliberationEvent], Awaitable[None]]


def make_nats_sink(nats_client: NatsClient) -> EventSink:
    """Build an event sink that publishes each event to NATS JetStream."""

    async def sink(event: DeliberationEvent) -> None:
        subject = (
            subject_for(event.payload.get("deliberation_id", ""))
            if "deliberation_id" in event.payload
            else None
        )
        if subject is None:
            # The started event payload contains the problem; we need the
            # deliberation id from the running state. Callers should use
            # `make_nats_sink_for(deliberation_id)` instead. As a fallback,
            # we skip publishing for events without an id in payload.
            return
        payload = event.model_dump_json().encode()
        await nats_client.publish(subject, payload)

    return sink


def make_nats_sink_for(
    nats_client: NatsClient,
    deliberation_id: str,
    pg: PostgresPool | None = None,
) -> EventSink:
    """Build a NATS sink bound to a specific deliberation id.

    When `pg` is supplied, each event is also appended to Postgres
    `deliberation_events` so the WS replay path can deliver it to
    clients that connect after the event was emitted.
    """
    subject = subject_for(deliberation_id)

    async def sink(event: DeliberationEvent) -> None:
        payload = event.model_dump_json().encode()
        await nats_client.publish(subject, payload)
        if pg is not None:
            await pg.append_event(deliberation_id, event)

    return sink
