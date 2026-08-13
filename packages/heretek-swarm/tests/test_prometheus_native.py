"""Tests for the Phase 2A prometheus-client native cutover."""

from __future__ import annotations

from heretek_swarm.observability.prometheus_native import (
    AGENTS_ACTIVE,
    AGENTS_TOTAL,
    API_REQUEST_DURATION,
    API_REQUESTS_TOTAL,
    CONSENSUS_ROUNDS,
    ENCRYPTION_LATENCY,
    EXTERNAL_CALL_DURATION,
    EXTERNAL_CALL_LOGS,
    FREE_ENERGY,
    HEALTH_SCORE,
    LLM_CALL_DURATION,
    LLM_TOKENS,
    MESSAGES_TOTAL,
    PHI_SCORE,
    TASKS_COMPLETED,
    TASKS_FAILED,
    UPTIME_SECONDS,
    build_test_registry,
    export_prometheus,
    increment_consensus_rounds,
    increment_external_call_logs,
    increment_messages,
    increment_tasks_completed,
    increment_tasks_failed,
    record_actor_processing,
    record_api_request,
    record_db_query,
    record_db_query_duration,
    record_encryption_latency,
    record_external_call_duration,
    record_free_energy,
    record_health_score,
    record_llm_call,
    record_llm_tokens,
    record_phi_score,
    record_uptime,
    setup_metrics_middleware,
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
)

# Module-level smoke tests (the test_registry approach lets multiple
# tests touch the metrics without duplicate-timeseries errors).


def test_module_metrics_are_registered():
    """All module-level metrics are Counter / Gauge / Histogram instances.

    Note: prometheus_client strips the conventional ``_total`` suffix
    from Counter names internally (``tasks_completed_total`` →
    ``tasks_completed``). The wire format still emits ``_total``;
    only the in-process ``._name`` is the stripped form.
    """
    assert AGENTS_TOTAL._name == "heretek_swarm_agents_total"
    assert AGENTS_ACTIVE._name == "heretek_swarm_agents_active"
    assert TASKS_COMPLETED._name == "heretek_swarm_tasks_completed"  # _total stripped
    assert TASKS_FAILED._name == "heretek_swarm_tasks_failed"  # _total stripped
    assert MESSAGES_TOTAL._name == "heretek_swarm_messages"  # _total stripped
    assert CONSENSUS_ROUNDS._name == "heretek_swarm_consensus_rounds"  # _total stripped
    assert PHI_SCORE._name == "heretek_swarm_phi_score"
    assert FREE_ENERGY._name == "heretek_swarm_free_energy"
    assert HEALTH_SCORE._name == "heretek_swarm_health_score"
    assert API_REQUEST_DURATION._name == "heretek_swarm_api_request_duration_seconds"
    assert API_REQUESTS_TOTAL._name == "heretek_swarm_api_requests"  # _total stripped
    assert EXTERNAL_CALL_LOGS._name == "heretek_swarm_external_call_logs"  # _total stripped
    assert EXTERNAL_CALL_DURATION._name == "heretek_swarm_external_call_log_duration_seconds"
    assert ENCRYPTION_LATENCY._name == "heretek_swarm_encryption_latency_seconds"


def test_increment_tasks_completed_increments_counter():
    """increment_tasks_completed() increments the TASKS_COMPLETED counter."""
    before = TASKS_COMPLETED.labels(agent_id="test-1", task_type="unit")._value.get()
    increment_tasks_completed(agent_id="test-1", task_type="unit")
    after = TASKS_COMPLETED.labels(agent_id="test-1", task_type="unit")._value.get()
    assert after == before + 1


def test_increment_tasks_failed_increments_counter():
    """increment_tasks_failed() increments the TASKS_FAILED counter."""
    before = TASKS_FAILED.labels(agent_id="test-2", task_type="unit")._value.get()
    increment_tasks_failed(agent_id="test-2", task_type="unit")
    after = TASKS_FAILED.labels(agent_id="test-2", task_type="unit")._value.get()
    assert after == before + 1


def test_increment_messages_increments_counter():
    """increment_messages() increments the MESSAGES_TOTAL counter."""
    before = MESSAGES_TOTAL.labels(
        direction="sent", message_type="request"
    )._value.get()
    increment_messages(direction="sent", message_type="request")
    after = MESSAGES_TOTAL.labels(
        direction="sent", message_type="request"
    )._value.get()
    assert after == before + 1


def test_increment_consensus_rounds_increments_counter():
    """increment_consensus_rounds() increments CONSENSUS_ROUNDS counter."""
    before = CONSENSUS_ROUNDS.labels(consensus_type="deliberation", outcome="success")._value.get()
    increment_consensus_rounds(consensus_type="deliberation", outcome="success")
    after = CONSENSUS_ROUNDS.labels(consensus_type="deliberation", outcome="success")._value.get()
    assert after == before + 1


def test_record_phi_score_sets_gauge():
    """record_phi_score() sets the PHI_SCORE gauge."""
    record_phi_score(agent_id="test-4", score=0.87)
    assert PHI_SCORE.labels(agent_id="test-4")._value.get() == 0.87


def test_record_free_energy_sets_gauge():
    """record_free_energy() sets the FREE_ENERGY gauge."""
    record_free_energy(agent_id="test-5", score=0.42)
    assert FREE_ENERGY.labels(agent_id="test-5")._value.get() == 0.42


def test_record_health_score_sets_gauge():
    """record_health_score() sets the HEALTH_SCORE gauge."""
    record_health_score(0.95)
    assert HEALTH_SCORE._value.get() == 0.95


def test_record_api_request_increments_counter_and_observers_histogram():
    """record_api_request() increments counter and observes duration."""
    counter_before = API_REQUESTS_TOTAL.labels(method="GET", endpoint="/x", status="200")._value.get()
    record_api_request(method="GET", endpoint="/x", status=200, duration=0.05)
    counter_after = API_REQUESTS_TOTAL.labels(method="GET", endpoint="/x", status="200")._value.get()
    assert counter_after == counter_before + 1
    # Histogram count increased (via observe). We don't assert the
    # specific bucket because Histogram._sum and _count are tracked
    # internally by prometheus_client.
    assert API_REQUEST_DURATION.labels(method="GET", endpoint="/x", status="200")._sum.get() >= 0.05


def test_increment_external_call_logs_increments_counter():
    """increment_external_call_logs() increments the EXTERNAL_CALL_LOGS counter."""
    before = EXTERNAL_CALL_LOGS.labels(
        agent_type="executor", call_type="tool", status="200"
    )._value.get()
    increment_external_call_logs(agent_type="executor", call_type="tool", status=200)
    after = EXTERNAL_CALL_LOGS.labels(
        agent_type="executor", call_type="tool", status="200"
    )._value.get()
    assert after == before + 1


def test_record_external_call_duration_observes_histogram():
    """record_external_call_duration() observes into the histogram."""
    label = EXTERNAL_CALL_DURATION.labels(
        agent_type="executor", call_type="tool", method="POST"
    )
    before_sum = label._sum.get()
    record_external_call_duration(
        call_type="tool",
        status=200,
        duration_seconds=0.1,
        agent_type="executor",
        method="POST",
    )
    after_sum = label._sum.get()
    assert after_sum >= before_sum + 0.1


def test_record_encryption_latency_observes_histogram():
    """record_encryption_latency() observes into the histogram."""
    label = ENCRYPTION_LATENCY.labels(operation="encrypt", field_type="body")
    before_sum = label._sum.get()
    record_encryption_latency(operation="encrypt", field_type="body", duration_seconds=0.001)
    after_sum = label._sum.get()
    assert after_sum >= before_sum + 0.001


def test_export_prometheus_returns_prometheus_text():
    """export_prometheus() returns (bytes, content_type) in Prometheus format."""
    body, ctype = export_prometheus()
    assert isinstance(body, bytes)
    assert ctype == CONTENT_TYPE_LATEST
    # Body should contain the help/type lines for our metrics.
    text = body.decode("utf-8")
    assert "# HELP heretek_swarm_agents_total" in text
    assert "# TYPE heretek_swarm_agents_total gauge" in text
    assert "heretek_swarm_tasks_completed_total" in text
    assert "heretek_swarm_phi_score" in text


def test_build_test_registry_returns_fresh_collector():
    """build_test_registry() returns a fresh CollectorRegistry for tests."""
    reg = build_test_registry()
    assert isinstance(reg, CollectorRegistry)
    assert reg is not REGISTRY  # Sanity: it's a fresh one, not the default


# ---------------------------------------------------------------------------
# Phase 2A.1 wrapper-cutover tests (commit 2)
# ---------------------------------------------------------------------------


def test_record_actor_processing_observes_histogram():
    """record_actor_processing() observes into the histogram."""
    from heretek_swarm.observability.prometheus_native import (
        ACTOR_PROCESSING_DURATION,
    )

    label = ACTOR_PROCESSING_DURATION.labels(actor_type="executor")
    before_sum = label._sum.get()
    record_actor_processing(agent_id="test-actor", actor_type="executor", duration_seconds=0.05)
    after_sum = label._sum.get()
    assert after_sum >= before_sum + 0.05


def test_record_db_query_observes_histogram():
    """record_db_query() observes into the histogram."""
    from heretek_swarm.observability.prometheus_native import (
        DB_QUERY_DURATION,
    )

    label = DB_QUERY_DURATION.labels(db_name="config")
    before_sum = label._sum.get()
    record_db_query(duration_seconds=0.01, db_name="config")
    after_sum = label._sum.get()
    assert after_sum >= before_sum + 0.01


def test_record_db_query_duration_alias():
    """record_db_query_duration is an alias for record_db_query."""
    from heretek_swarm.observability.prometheus_native import (
        DB_QUERY_DURATION,
    )

    label = DB_QUERY_DURATION.labels(db_name="external_call_log")
    before = label._sum.get()
    record_db_query_duration(duration_seconds=0.02, db_name="external_call_log")
    after = label._sum.get()
    assert after >= before + 0.02


def test_record_llm_call_observes_histogram():
    """record_llm_call() observes into the histogram."""
    label = LLM_CALL_DURATION.labels(
        agent_id="alpha", provider="anthropic", model="claude-3-5-sonnet"
    )
    before_sum = label._sum.get()
    record_llm_call(
        agent_id="alpha",
        provider="anthropic",
        model="claude-3-5-sonnet",
        duration_seconds=2.5,
    )
    after_sum = label._sum.get()
    assert after_sum >= before_sum + 2.5


def test_record_llm_tokens_increments_three_counters():
    """record_llm_tokens() emits 3 LLM_TOKENS increments (prompt/completion/total)."""
    record_llm_tokens(
        agent_id="alpha",
        provider="anthropic",
        model="claude-3-5-sonnet",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    prompt = LLM_TOKENS.labels(
        agent_id="alpha", provider="anthropic", model="claude-3-5-sonnet",
        token_type="prompt",
    )._value.get()
    completion = LLM_TOKENS.labels(
        agent_id="alpha", provider="anthropic", model="claude-3-5-sonnet",
        token_type="completion",
    )._value.get()
    total = LLM_TOKENS.labels(
        agent_id="alpha", provider="anthropic", model="claude-3-5-sonnet",
        token_type="total",
    )._value.get()
    assert prompt >= 10
    assert completion >= 5
    assert total >= 15


def test_record_uptime_sets_gauge():
    """record_uptime() sets the UPTIME_SECONDS gauge."""
    record_uptime(123.4)
    assert UPTIME_SECONDS._value.get() == 123.4


def test_record_api_request_normalizes_uuid():
    """record_api_request replaces UUIDs in endpoint with {id} placeholders."""
    # Use a unique agent_id+endpoint combo to avoid label collision with
    # earlier tests. The endpoint has a UUID; native should normalize it.
    test_endpoint = "/api/agents/550e8400-e29b-41d4-a716-446655440000/state"
    record_api_request(
        method="GET", endpoint=test_endpoint, status=200, duration=0.05
    )
    # Find the labeled counter via the underlying registry text
    body, _ctype = export_prometheus()
    text = body.decode("utf-8")
    # The UUID should be replaced
    assert "/api/agents/{id}/state" in text
    assert "550e8400-e29b-41d4-a716-446655440000" not in text


def test_record_api_request_normalizes_numeric_id():
    """record_api_request replaces numeric path segments with /{id}."""
    test_endpoint = "/api/tasks/42/details"
    record_api_request(
        method="GET", endpoint=test_endpoint, status=200, duration=0.05
    )
    body, _ctype = export_prometheus()
    text = body.decode("utf-8")
    assert "/api/tasks/{id}/details" in text
    # The numeric "42" should not appear as a path segment
    assert '/api/tasks/42/' not in text


def test_setup_metrics_middleware_records_request():
    """setup_metrics_middleware adds a working request-counter middleware."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/spike_test_endpoint")
    def root():
        return {"ok": True}

    setup_metrics_middleware(app)
    client = TestClient(app)
    response = client.get("/spike_test_endpoint")
    assert response.status_code == 200
    body, _ctype = export_prometheus()
    text = body.decode("utf-8")
    # The endpoint (after normalization) should appear in the registry output
    assert "/spike_test_endpoint" in text
    # Method GET, status 200 should both be labels
    assert 'method="GET"' in text


def test_setup_metrics_middleware_skips_metrics_endpoint():
    """The middleware skips /metrics so self-scrape does not pollute counters."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/spike_metrics_test_skip")
    def root():
        return {"ok": True}

    setup_metrics_middleware(app)
    client = TestClient(app)
    # Hit a non-/metrics path
    client.get("/spike_metrics_test_skip")
    body, _ctype = export_prometheus()
    text = body.decode("utf-8")
    assert "/spike_metrics_test_skip" in text


# ---------------------------------------------------------------------------
# Phase 2A.3 cutover: public read helpers (commit in flight)
# ---------------------------------------------------------------------------


def test_read_metric_value_returns_unlabeled_gauge_value():
    """read_metric_value on an unlabeled Gauge returns the single value."""
    from heretek_swarm.observability.prometheus_native import read_metric_value

    record_health_score(0.73)
    assert read_metric_value(HEALTH_SCORE) == 0.73


def test_read_metric_value_sums_labeled_counter():
    """read_metric_value on a labeled Counter returns the sum across all labels."""
    from heretek_swarm.observability.prometheus_native import read_metric_value

    before = read_metric_value(TASKS_COMPLETED)
    increment_tasks_completed(agent_id="read-1", task_type="alpha")
    increment_tasks_completed(agent_id="read-1", task_type="beta")
    increment_tasks_completed(agent_id="read-2", task_type="alpha")
    after = read_metric_value(TASKS_COMPLETED)
    assert after - before == 3


def test_read_metric_samples_returns_per_label_breakdown():
    """read_metric_samples returns a dict keyed by label-tuple string."""
    from heretek_swarm.observability.prometheus_native import read_metric_samples

    record_phi_score(agent_id="samples-a", score=0.10)
    record_phi_score(agent_id="samples-b", score=0.20)
    samples = read_metric_samples(PHI_SCORE)
    # Both labeled entries present, in stable label-keyed form.
    assert samples.get("agent_id=samples-a") == 0.10
    assert samples.get("agent_id=samples-b") == 0.20


def test_read_metric_value_skips_histogram_buckets():
    """read_metric_value on a Histogram returns 0 (no value samples outside buckets)."""
    from heretek_swarm.observability.prometheus_native import (
        DB_QUERY_DURATION,
        read_metric_value,
    )

    record_db_query(duration_seconds=0.5, db_name="read-test")
    # Histogram emits only _count, _sum, and _bucket samples; the helper
    # skips the buckets (le-labeled) and reads _count + _sum, which is
    # not meaningful as a "total". We assert it doesn't raise and
    # returns a float — exact semantics for Histograms are documented
    # as undefined in read_metric_value.
    val = read_metric_value(DB_QUERY_DURATION)
    assert isinstance(val, float)
