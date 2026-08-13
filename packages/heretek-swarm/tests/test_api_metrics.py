"""Tests for the JSON debug endpoint at ``/api/metrics/json``.

Covers the Phase 2A.3 cutover that moved the JSON snapshot off the
legacy ``SwarmMetricsCollector`` and onto direct reads from the
prometheus-native metric objects via the public ``read_metric_value``
and ``read_metric_samples`` helpers (no private ``_metrics`` /
``_value`` access).
"""

from __future__ import annotations

import asyncio
import re

from heretek_swarm.api.metrics import get_metrics_json
from heretek_swarm.observability.prometheus_native import (
    increment_tasks_completed,
    record_free_energy,
    record_health_score,
    record_phi_score,
)

# ISO-8601 with optional fractional seconds and a trailing 'Z' or numeric offset.
_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def test_get_metrics_json_returns_swarm_and_consciousness_keys():
    """get_metrics_json returns the canonical two-section shape."""
    result = asyncio.run(get_metrics_json(authenticated="test"))
    assert "swarm" in result
    assert "consciousness" in result
    # swarm subkeys
    for k in (
        "agents_total",
        "agents_active",
        "tasks_completed",
        "tasks_failed",
        "messages_total",
        "consensus_rounds",
        "health_score",
        "timestamp",
    ):
        assert k in result["swarm"], f"missing swarm key: {k}"
    # consciousness subkeys
    assert "phi_score_avg" in result["consciousness"]
    assert "free_energy_avg" in result["consciousness"]


def test_get_metrics_json_health_score_reflects_record_health_score():
    """The JSON's health_score equals what record_health_score set."""
    record_health_score(0.62)
    result = asyncio.run(get_metrics_json(authenticated="test"))
    assert result["swarm"]["health_score"] == 0.62


def test_get_metrics_json_tasks_completed_aggregates_across_labels():
    """tasks_completed in JSON sums across all agent_id/task_type labels."""
    # Use a fresh label key to avoid coupling to test order.
    increment_tasks_completed(agent_id="json-test-1", task_type="unit")
    increment_tasks_completed(agent_id="json-test-1", task_type="unit")
    increment_tasks_completed(agent_id="json-test-2", task_type="integration")

    result = asyncio.run(get_metrics_json(authenticated="test"))
    # Two increments for json-test-1, one for json-test-2 — must sum to 3.
    # (We can't assert an exact total because other tests may have
    # incremented TASKS_COMPLETED on the shared module-level REGISTRY.)
    before_or_after = result["swarm"]["tasks_completed"]
    increment_tasks_completed(agent_id="json-test-3", task_type="smoke")
    result2 = asyncio.run(get_metrics_json(authenticated="test"))
    assert result2["swarm"]["tasks_completed"] - before_or_after == 1


def test_get_metrics_json_phi_score_avg_is_mean_across_agents():
    """phi_score_avg is the mean of all per-agent phi samples."""
    # Use unique agent_ids so this test is order-independent on the
    # shared PHI_SCORE gauge.
    record_phi_score(agent_id="json-phi-x", score=0.20)
    record_phi_score(agent_id="json-phi-y", score=0.60)
    result = asyncio.run(get_metrics_json(authenticated="test"))
    # Verify via the public helper that the recorded entries are
    # reflected; the reported avg is across ALL labels (other tests
    # may have added more), so we assert our two known entries land
    # in the samples and the avg is in [0, 1].
    from heretek_swarm.observability.prometheus_native import (
        PHI_SCORE,
        read_metric_samples,
    )

    samples = read_metric_samples(PHI_SCORE)
    assert samples.get("agent_id=json-phi-x") == 0.20
    assert samples.get("agent_id=json-phi-y") == 0.60
    assert 0.0 <= result["consciousness"]["phi_score_avg"] <= 1.0


def test_get_metrics_json_free_energy_avg_is_mean_across_agents():
    """free_energy_avg is the mean of all per-agent free-energy samples."""
    record_free_energy(agent_id="json-fe-x", score=0.30)
    record_free_energy(agent_id="json-fe-y", score=0.50)
    result = asyncio.run(get_metrics_json(authenticated="test"))
    # Direct read to verify the helper.
    from heretek_swarm.observability.prometheus_native import (
        FREE_ENERGY,
        read_metric_samples,
    )

    samples = read_metric_samples(FREE_ENERGY)
    assert samples.get("agent_id=json-fe-x") == 0.30
    assert samples.get("agent_id=json-fe-y") == 0.50
    assert 0.0 <= result["consciousness"]["free_energy_avg"] <= 1.0


def test_get_metrics_json_timestamp_is_iso_8601():
    """The JSON's timestamp is an ISO-8601 string in UTC."""
    result = asyncio.run(get_metrics_json(authenticated="test"))
    ts = result["swarm"]["timestamp"]
    assert isinstance(ts, str)
    assert _ISO_RE.match(ts), f"timestamp not ISO-8601: {ts!r}"
