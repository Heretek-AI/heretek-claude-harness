"""Unit tests for dashboard.serve.mount_static.

Covers all four documented branches:
  1. nonexistent path -> silent no-op
  2. existing path -> registers two api_route handlers (index + catch-all)
  3. GET /dashboard -> serves index.html
  4. GET /dashboard/<existing-asset> -> serves the literal asset
  5. GET /dashboard/<missing-asset> -> SPA fallback to index.html
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tier1.dashboard.serve import mount_static


@pytest.fixture
def dashboard_dir(tmp_path):
    """A directory containing index.html + one asset file."""
    (tmp_path / "index.html").write_text("<html>index</html>")
    (tmp_path / "app.js").write_text("console.log('app')")
    return tmp_path


def test_mount_static_returns_silently_when_path_missing(tmp_path):
    """Nonexistent directory -> no routes registered."""
    app = FastAPI()
    missing = tmp_path / "does-not-exist"
    before = list(app.router.routes)
    mount_static(app, missing)
    after = list(app.router.routes)
    assert before == after, "no routes should be added when path is missing"


def test_mount_static_registers_two_handlers(dashboard_dir):
    """Existing directory -> /dashboard (index) + /dashboard/{path} (assets)."""
    app = FastAPI()
    mount_static(app, dashboard_dir)
    paths = [r.path for r in app.router.routes]
    assert "/dashboard" in paths
    assert "/dashboard/{full_path:path}" in paths


def test_dashboard_index_serves_index_html(dashboard_dir):
    """GET /dashboard returns index.html content."""
    app = FastAPI()
    mount_static(app, dashboard_dir)
    client = TestClient(app)
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "<html>index</html>" in r.text


def test_dashboard_existing_asset_served(dashboard_dir):
    """GET /dashboard/app.js serves the literal asset."""
    app = FastAPI()
    mount_static(app, dashboard_dir)
    client = TestClient(app)
    r = client.get("/dashboard/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_dashboard_missing_asset_falls_back_to_index(dashboard_dir):
    """GET /dashboard/unknown -> SPA fallback to index.html."""
    app = FastAPI()
    mount_static(app, dashboard_dir)
    client = TestClient(app)
    r = client.get("/dashboard/random-spa-route")
    assert r.status_code == 200
    assert "<html>index</html>" in r.text


def test_mount_static_accepts_string_path(dashboard_dir):
    """mount_static coerces str -> Path (covered by Path(path) at line 18)."""
    app = FastAPI()
    mount_static(app, str(dashboard_dir))
    paths = [r.path for r in app.router.routes]
    assert "/dashboard" in paths


def test_dashboard_supports_head(dashboard_dir):
    """HEAD /dashboard returns 200 like GET."""
    app = FastAPI()
    mount_static(app, dashboard_dir)
    client = TestClient(app)
    r = client.head("/dashboard")
    assert r.status_code == 200


def test_dashboard_routes_excluded_from_openapi(dashboard_dir):
    """include_in_schema=False keeps dashboard out of OpenAPI docs."""
    app = FastAPI()
    mount_static(app, dashboard_dir)
    schema = app.openapi()
    # OpenAPI doesn't list routes flagged include_in_schema=False.
    assert "/dashboard" not in schema.get("paths", {})
