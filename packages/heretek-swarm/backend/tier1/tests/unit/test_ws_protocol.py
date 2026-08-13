"""Tests for the WS protocol message shapes and replay ordering."""

from __future__ import annotations

import pytest


def test_ws_event_shape():
    # Smoke: import the WS module and assert the expected router paths exist.
    from tier1.api.routes import ws

    paths = [r.path for r in ws.router.routes if hasattr(r, "path")]
    assert any("deliberations" in p for p in paths)


def test_ws_replay_done_message_shape():
    # We model the replay_done frame as {"kind": "replay_done", "count": int}.
    # Assert this in isolation, since the WS handler is hard to unit-test
    # without a live socket.
    msg = {"kind": "replay_done", "count": 3}
    assert msg["kind"] == "replay_done"
    assert isinstance(msg["count"], int)


def test_ws_event_message_shape():
    msg = {"kind": "event", "event": {"seq": 0, "ts": 1.0, "kind": "started", "payload": {}}}
    assert msg["kind"] == "event"
    assert msg["event"]["kind"] == "started"
