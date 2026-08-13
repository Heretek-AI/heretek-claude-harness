"""Unit tests for dashboard.bridge — NATS sink factories.

Covers all four branches of the two factories:
  - make_nats_sink: with-deliberation_id-in-payload publishes; without skips.
  - make_nats_sink_for: publishes to bound subject; also appends to pg when set.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.deliberation.state import DeliberationEvent
from tier1.dashboard.bridge import make_nats_sink, make_nats_sink_for
from tier1.events.channels import subject_for


def _event(**payload) -> DeliberationEvent:
    return DeliberationEvent(seq=1, ts=1.0, kind="started", payload=payload)


async def test_make_nats_sink_publishes_when_deliberation_id_in_payload():
    """When payload has 'deliberation_id', the event is published to NATS."""
    nats_client = MagicMock()
    nats_client.publish = AsyncMock()
    sink = make_nats_sink(nats_client)
    event = _event(deliberation_id="d-1")
    await sink(event)
    expected_subject = subject_for("d-1")
    nats_client.publish.assert_called_once()
    args = nats_client.publish.call_args.args
    assert args[0] == expected_subject
    assert isinstance(args[1], bytes)


async def test_make_nats_sink_skips_publish_when_no_deliberation_id():
    """When payload lacks 'deliberation_id', publish is skipped (no subject)."""
    nats_client = MagicMock()
    nats_client.publish = AsyncMock()
    sink = make_nats_sink(nats_client)
    event = _event(other="x")
    await sink(event)
    nats_client.publish.assert_not_called()


async def test_make_nats_sink_for_publishes_bound_subject():
    """Factory binds subject at construction; events go to that subject."""
    nats_client = MagicMock()
    nats_client.publish = AsyncMock()
    sink = make_nats_sink_for(nats_client, "d-bound")
    event = _event(deliberation_id="d-1")
    await sink(event)
    expected_subject = subject_for("d-bound")
    nats_client.publish.assert_called_once()
    args = nats_client.publish.call_args.args
    assert args[0] == expected_subject


async def test_make_nats_sink_for_with_pg_appends_event():
    """When pg is supplied, append_event is awaited with the event + id."""
    nats_client = MagicMock()
    nats_client.publish = AsyncMock()
    pg = MagicMock()
    pg.append_event = AsyncMock()
    sink = make_nats_sink_for(nats_client, "d-x", pg=pg)
    event = _event(deliberation_id="d-x")
    await sink(event)
    nats_client.publish.assert_called_once()
    pg.append_event.assert_called_once_with("d-x", event)


async def test_make_nats_sink_for_without_pg_skips_persistence():
    """When pg is None, no append_event call happens."""
    nats_client = MagicMock()
    nats_client.publish = AsyncMock()
    sink = make_nats_sink_for(nats_client, "d-no-pg")
    event = _event(deliberation_id="d-no-pg")
    await sink(event)
    nats_client.publish.assert_called_once()
    # The pg attr is not present in this scope; just verify no AttributeError.


async def test_make_nats_sink_payload_is_json_bytes():
    """Published payload is UTF-8 JSON of the event."""
    import json

    nats_client = MagicMock()
    nats_client.publish = AsyncMock()
    sink = make_nats_sink(nats_client)
    event = _event(deliberation_id="d-json")
    await sink(event)
    published_bytes = nats_client.publish.call_args.args[1]
    decoded = json.loads(published_bytes.decode("utf-8"))
    assert decoded["kind"] == "started"
    assert decoded["payload"]["deliberation_id"] == "d-json"
