"""
CogneeMemoryReader — Read-only context source backed by Cognee.

Cognee is a knowledge graph + vector memory engine. This reader provides
a thin async HTTP client that supplements the Historian's existing memory
access with Cognee's graph-augmented retrieval. Designed for sidecar mode:
the reader is fully optional and falls back to empty results when Cognee
is unreachable — the Historian never fails because of an optional source.

The Cognee *service* is reached over HTTP only; the `cognee` Python SDK
is NOT a runtime dependency. Install it explicitly with
`uv pip install heretek-swarm[cognee]` if you need direct SDK access.

M-arch PR #2: Add Cognee as read-only context source for Historian.
See PLAN.md §M-arch for the broader migration context.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class CogneeMemoryReader:
    """Async read-only client for Cognee's REST API.

    The reader wraps Cognee's search endpoint with graceful fallback:
    if Cognee is disabled, unreachable, or errors, ``read()`` returns
    ``[]`` rather than raising. This is intentional — supplemental
    memory sources must never break the primary memory path.

    Configuration via env vars (all optional):
        COGNEE_API_URL: Cognee service base URL (default: ``http://cognee:8000``)
        COGNEE_TIMEOUT_SECONDS: HTTP timeout (default: 5)
        COGNEE_ENABLED: Master switch (default: ``false``)
    """

    def __init__(
        self,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
        enabled: bool | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_url = (api_url or os.getenv("COGNEE_API_URL", "http://cognee:8000")).rstrip(
            "/"
        )
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("COGNEE_TIMEOUT_SECONDS", "5")
        )
        if enabled is None:
            enabled = os.getenv("COGNEE_ENABLED", "false").lower() in ("true", "1", "yes")
        self.enabled = enabled
        # Allow injecting a client for tests; if None, lazily create on first use
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=self.timeout_seconds,
            )
        return self._client

    async def read(
        self,
        query: str,
        top_k: int = 5,
        dataset: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search Cognee for context related to ``query``.

        Returns:
            List of context dicts with keys: ``content``, ``score``,
            ``dataset``, ``metadata``. Empty list if Cognee is disabled,
            unreachable, or returns no results.
        """
        if not self.enabled:
            return []
        try:
            client = await self._get_client()
            payload: dict[str, Any] = {"query": query, "top_k": top_k}
            if dataset:
                payload["dataset"] = dataset
            response = await client.post("/api/v1/search", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.warning(
                "cognee_search_http_error",
                error=str(e),
                query_len=len(query),
            )
            return []
        except Exception as e:
            logger.error(
                "cognee_search_unexpected_error",
                error=str(e),
                query_len=len(query),
            )
            return []

        results = data.get("results", []) if isinstance(data, dict) else []
        logger.info(
            "cognee_search_ok",
            query_len=len(query),
            top_k=top_k,
            result_count=len(results),
        )
        return results

    async def health(self) -> bool:
        """Check if Cognee is reachable and healthy."""
        if not self.enabled:
            return False
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client (call on agent shutdown)."""
        if self._owns_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def __repr__(self) -> str:
        return f"CogneeMemoryReader(api_url={self.api_url!r}, enabled={self.enabled})"
