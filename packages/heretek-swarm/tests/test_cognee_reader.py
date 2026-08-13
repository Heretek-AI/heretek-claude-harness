"""
Tests for CogneeMemoryReader — read-only Cognee client with graceful fallback.

Per M-arch PR #2: verify the reader's contract (never raises; empty list on
failure) so the Historian can safely use it as a supplemental source.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader


def _ok(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    """Return a real httpx.AsyncClient backed by httpx.MockTransport.

    Using the real transport (not AsyncMock) exercises the production
    code path: ``await client.post(...)`` returns the canned response
    with no network access and no ``is_closed`` spec weirdness.
    """
    return httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(handler),
    )


def _search_200() -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "content": "Some context",
                        "score": 0.92,
                        "dataset": "default",
                        "metadata": {"source": "doc1"},
                    }
                ]
            },
            request=request,
        )

    return handler


def _empty_200() -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []}, request=request)

    return handler


class TestCogneeMemoryReader:
    """Behavioral tests for the CogneeMemoryReader class."""

    def test_default_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reader defaults to disabled (opt-in via env)."""
        monkeypatch.delenv("COGNEE_ENABLED", raising=False)
        reader = CogneeMemoryReader()
        assert reader.enabled is False

    def test_enabled_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reader can be enabled via COGNEE_ENABLED=true."""
        monkeypatch.setenv("COGNEE_ENABLED", "true")
        reader = CogneeMemoryReader()
        assert reader.enabled is True

    def test_api_url_default(self) -> None:
        """Default API URL is the in-network Cognee service."""
        reader = CogneeMemoryReader(enabled=True)
        assert reader.api_url == "http://cognee:8000"

    def test_api_url_trailing_slash_stripped(self) -> None:
        """Trailing slashes are stripped from the API URL."""
        reader = CogneeMemoryReader(api_url="http://cognee:8000/", enabled=True)
        assert reader.api_url == "http://cognee:8000"

    @pytest.mark.asyncio
    async def test_read_returns_empty_when_disabled(self) -> None:
        """Disabled reader returns [] without making any HTTP calls."""
        reader = CogneeMemoryReader(enabled=False)
        result = await reader.read("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_read_returns_empty_on_http_error(self) -> None:
        """HTTPError from the transport is swallowed and returns []."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.HTTPError("connection refused")

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        result = await reader.read("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_read_returns_empty_on_timeout(self) -> None:
        """TimeoutException from the transport is swallowed and returns []."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out")

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        result = await reader.read("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_read_returns_empty_on_5xx(self) -> None:
        """5xx response is treated as a failure and returns []."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, request=request)

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        result = await reader.read("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_read_returns_results_on_success(self) -> None:
        """Successful 200 response with results is returned as a list of dicts."""
        reader = CogneeMemoryReader(enabled=True, client=_ok(_search_200()))
        result = await reader.read("test query", top_k=5)
        assert len(result) == 1
        assert result[0]["content"] == "Some context"
        assert result[0]["score"] == 0.92

    @pytest.mark.asyncio
    async def test_read_includes_dataset_in_payload(self) -> None:
        """Dataset name is included in the search payload when provided."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured["body"] = _json.loads(request.content)
            return httpx.Response(200, json={"results": []}, request=request)

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        await reader.read("test query", dataset="agents")
        assert captured["body"]["dataset"] == "agents"
        assert captured["body"]["query"] == "test query"

    @pytest.mark.asyncio
    async def test_read_handles_unexpected_json_shape(self) -> None:
        """Unexpected JSON shape (e.g., list instead of dict) is handled gracefully."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[], request=request)

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        result = await reader.read("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_health_returns_false_when_disabled(self) -> None:
        """Health check returns False when reader is disabled."""
        reader = CogneeMemoryReader(enabled=False)
        assert await reader.health() is False

    @pytest.mark.asyncio
    async def test_health_returns_true_on_200(self) -> None:
        """Health check returns True when Cognee returns 200."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, request=request)

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        assert await reader.health() is True

    @pytest.mark.asyncio
    async def test_health_returns_false_on_error(self) -> None:
        """Health check returns False on any exception."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.HTTPError("nope")

        reader = CogneeMemoryReader(enabled=True, client=_ok(handler))
        assert await reader.health() is False

    @pytest.mark.asyncio
    async def test_close_does_not_close_injected_client(self) -> None:
        """``close()`` does NOT close a client that was injected by the caller."""
        client = _ok(_empty_200())
        reader = CogneeMemoryReader(enabled=True, client=client)
        await reader.close()
        assert client.is_closed is False

    def test_repr_includes_key_state(self) -> None:
        """__repr__ exposes api_url and enabled for debugging."""
        reader = CogneeMemoryReader(api_url="http://x:1234", enabled=True)
        r = repr(reader)
        assert "http://x:1234" in r
        assert "enabled=True" in r
