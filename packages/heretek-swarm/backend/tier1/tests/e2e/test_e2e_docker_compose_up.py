"""E2E: docker-compose up + /health all green.

Gated on TIER1_E2E_DOCKER=1 so it doesn't run by default. Brings up the
backend/tier1 docker-compose stack, waits for the API, asserts /health reports
status=ok for api + postgres + redis + nats, then tears the stack down.
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest
import requests


@pytest.mark.skipif(
    os.environ.get("TIER1_E2E_DOCKER") != "1",
    reason="set TIER1_E2E_DOCKER=1 to run docker-compose E2E",
)
def test_docker_compose_up_health():
    subprocess.run(
        ["docker", "compose", "-f", "docker/docker-compose.yml", "up", "-d"],
        check=True,
        cwd="backend/tier1",
    )
    try:
        # Wait for API to be ready.
        r = None
        for _ in range(30):
            try:
                r = requests.get("http://localhost:8000/health", timeout=2)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            pytest.fail("API did not become ready")

        body = r.json()
        assert body["status"] == "ok"
        for component in ("postgres", "redis", "nats"):
            assert body["components"][component]["status"] == "ok"
    finally:
        subprocess.run(
            ["docker", "compose", "-f", "docker/docker-compose.yml", "down"],
            cwd="backend/tier1",
        )
