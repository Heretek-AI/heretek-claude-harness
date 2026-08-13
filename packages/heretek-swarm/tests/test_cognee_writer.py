"""
Tests for CogneeMemoryWriter — write-path client with graceful fallback.

Per M-arch PR #5: verify the writer's contract (never raises; returns
False/0 on failure) so it can safely be used as an opt-in write
source alongside the existing memory wrapper.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from heretek_swarm_core.memory.cognee_writer import (
    CogneeMemoryWriter,
    get_memory_writer,
)


def _ok(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )


class TestCogneeMemoryWriter:
    """Behavioral tests for the CogneeMemoryWriter class."""

    def test_default_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Writer defaults to disabled (opt-in via env)."""
        monkeypatch.delenv("COGNEE_ENABLED", raising=False)
        w = CogneeMemoryWriter()
        assert w.enabled is False

    def test_enabled_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Writer can be enabled via COGNEE_ENABLED=true."""
        monkeypatch.setenv("COGNEE_ENABLED", "true")
        w = CogneeMemoryWriter()
        assert w.enabled is True

    def test_api_url_trailing_slash_stripped(self) -> None:
        """Trailing slashes are stripped from the API URL."""
        w = CogneeMemoryWriter(api_url="http://cognee:8000/", enabled=True)
        assert w.api_url == "http://cognee:8000"

    def test_timeout_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default timeout is 10s (writes are slower than reads)."""
        monkeypatch.delenv("COGNEE_TIMEOUT_SECONDS", raising=False)
        w = CogneeMemoryWriter(enabled=True)
        assert w.timeout_seconds == 10.0

    def test_timeout_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Timeout can be overridden via COGNEE_TIMEOUT_SECONDS env."""
        monkeypatch.setenv("COGNEE_TIMEOUT_SECONDS", "30")
        w = CogneeMemoryWriter(enabled=True)
        assert w.timeout_seconds == 30.0

    @pytest.mark.asyncio
    async def test_add_disabled_returns_false(self) -> None:
        """add() returns False when the writer is disabled."""
        w = CogneeMemoryWriter(enabled=False)
        assert await w.add("hello", dataset="agents") is False

    @pytest.mark.asyncio
    async def test_add_string_calls_add_endpoint(self) -> None:
        """add() with a string sends one POST to /api/v1/add."""
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured.append(_json.loads(request.content))
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.add("hello world", dataset="agents")
        assert result is True
        assert len(captured) == 1
        assert captured[0]["data"] == "hello world"
        assert captured[0]["dataset"] == "agents"

    @pytest.mark.asyncio
    async def test_add_list_calls_add_endpoint_per_item(self) -> None:
        """add() with a list sends one POST per item."""
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured.append(_json.loads(request.content))
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.add(["a", "b", "c"], dataset="default")
        assert result is True
        assert len(captured) == 3
        assert [c["data"] for c in captured] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_add_returns_false_on_http_error(self) -> None:
        """add() returns False when Cognee returns 5xx."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        assert await w.add("data") is False

    @pytest.mark.asyncio
    async def test_add_returns_false_on_connection_error(self) -> None:
        """add() returns False when the transport raises."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.HTTPError("connection refused")

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        assert await w.add("data") is False

    @pytest.mark.asyncio
    async def test_cognify_disabled_returns_false(self) -> None:
        """cognify() returns False when the writer is disabled."""
        w = CogneeMemoryWriter(enabled=False)
        assert await w.cognify() is False

    @pytest.mark.asyncio
    async def test_cognify_default_dataset(self) -> None:
        """cognify() defaults to ['default'] when no datasets provided."""
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured.append(_json.loads(request.content))
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.cognify()
        assert result is True
        assert captured[0] == {"datasets": ["default"]}

    @pytest.mark.asyncio
    async def test_cognify_with_explicit_datasets(self) -> None:
        """cognify() forwards explicit datasets."""
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured.append(_json.loads(request.content))
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.cognify(datasets=["agents", "tasks"])
        assert result is True
        assert captured[0] == {"datasets": ["agents", "tasks"]}

    @pytest.mark.asyncio
    async def test_cognify_returns_false_on_http_error(self) -> None:
        """cognify() returns False on 5xx."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        assert await w.cognify() is False

    @pytest.mark.asyncio
    async def test_store_calls_add_then_cognify(self) -> None:
        """store() calls add() then cognify() when cognify_after=True."""
        call_log: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            call_log.append(f"{request.method} {request.url.path}")
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.store("some content", dataset="agents")
        assert result is True
        assert call_log == ["POST /api/v1/add", "POST /api/v1/cognify"]

    @pytest.mark.asyncio
    async def test_store_skips_cognify_when_disabled(self) -> None:
        """store() skips cognify when cognify_after=False."""
        call_log: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            call_log.append(f"{request.method} {request.url.path}")
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.store("x", dataset="default", cognify_after=False)
        assert result is True
        assert call_log == ["POST /api/v1/add"]

    @pytest.mark.asyncio
    async def test_store_returns_false_when_add_fails(self) -> None:
        """store() returns False if add() fails (doesn't call cognify)."""
        call_log: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            call_log.append(request.url.path)
            return httpx.Response(500, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        result = await w.store("x", dataset="default")
        assert result is False
        assert call_log == ["/api/v1/add"]  # cognify NOT called

    @pytest.mark.asyncio
    async def test_health_returns_false_when_disabled(self) -> None:
        """health() returns False when the writer is disabled."""
        w = CogneeMemoryWriter(enabled=False)
        assert await w.health() is False

    @pytest.mark.asyncio
    async def test_health_returns_true_on_200(self) -> None:
        """health() returns True when Cognee returns 200."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, request=request)

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        assert await w.health() is True

    @pytest.mark.asyncio
    async def test_health_returns_false_on_error(self) -> None:
        """health() returns False on any exception."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.HTTPError("nope")

        w = CogneeMemoryWriter(enabled=True, client=_ok(handler))
        assert await w.health() is False

    @pytest.mark.asyncio
    async def test_close_does_not_close_injected_client(self) -> None:
        """close() does NOT close a client that was injected by the caller."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, request=request)

        client = _ok(handler)
        w = CogneeMemoryWriter(enabled=True, client=client)
        await w.close()
        assert client.is_closed is False

    def test_repr_includes_key_state(self) -> None:
        """__repr__ exposes api_url and enabled for debugging."""
        w = CogneeMemoryWriter(api_url="http://x:1234", enabled=True)
        r = repr(w)
        assert "http://x:1234" in r
        assert "enabled=True" in r


class TestGetMemoryWriterFactory:
    def test_factory_returns_writer_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_memory_writer() returns a CogneeMemoryWriter."""
        monkeypatch.setenv("COGNEE_ENABLED", "false")
        w = get_memory_writer()
        assert isinstance(w, CogneeMemoryWriter)

    def test_factory_respects_cognee_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Writer is enabled=False when COGNEE_ENABLED=false."""
        monkeypatch.setenv("COGNEE_ENABLED", "false")
        w = get_memory_writer()
        assert w.enabled is False

    def test_factory_respects_cognee_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Writer is enabled=True when COGNEE_ENABLED=true."""
        monkeypatch.setenv("COGNEE_ENABLED", "true")
        w = get_memory_writer()
        assert w.enabled is True
