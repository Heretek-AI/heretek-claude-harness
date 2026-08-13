"""Tests for the /health endpoint."""


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "components" in body
    assert body["components"]["api"]["status"] == "ok"


def test_health_response_shape(client):
    response = client.get("/health")
    body = response.json()
    assert set(body.keys()) == {"status", "components"}
    assert "api" in body["components"]
