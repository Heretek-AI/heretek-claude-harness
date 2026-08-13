"""E2E: POST deliberation -> poll until completed -> read events.

Gated on TIER1_E2E_BASE_URL. Submits a problem to the running stack, polls
until status is completed or failed, then asserts all required event kinds
(agent thinking + completed) are present.
"""

from __future__ import annotations

import os
import time

import pytest
import requests


BASE = os.environ.get("TIER1_E2E_BASE_URL", "http://localhost:8000")


@pytest.mark.skipif(
    os.environ.get("TIER1_E2E_BASE_URL") is None,
    reason="set TIER1_E2E_BASE_URL to run E2E",
)
def test_full_deliberation_lifecycle():
    r = requests.post(f"{BASE}/api/deliberations", json={"problem": "E2E test"})
    r.raise_for_status()
    did = r.json()["id"]

    # Poll for up to 60s.
    deadline = time.time() + 60
    while time.time() < deadline:
        r = requests.get(f"{BASE}/api/deliberations/{did}")
        body = r.json()
        if body["status"] in ("completed", "failed"):
            assert body["status"] == "completed", f"failed: {body}"
            assert body["final_verdict"] is not None
            events = body["events"]
            kinds = [e["kind"] for e in events]
            for required in (
                "started",
                "alpha_thinking",
                "beta_thinking",
                "charlie_thinking",
                "completed",
            ):
                assert required in kinds, f"missing {required} in {kinds}"
            return
        time.sleep(1)
    pytest.fail("deliberation did not complete in 60s")
