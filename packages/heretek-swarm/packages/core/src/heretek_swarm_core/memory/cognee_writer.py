"""
CogneeMemoryWriter — Write-path client backed by Cognee.

Cognee is a knowledge graph + vector memory engine. This writer provides
a thin async HTTP client that supplements the existing memory store with
Cognee's add/cognify operations. Designed for sidecar mode: the writer
is fully optional and never raises — it returns False / 0 on failure
so the primary memory path is never broken by an optional source.

M-arch PR #5: Add Cognee as write-path source for symmetry with the
read-only :class:`CogneeMemoryReader` introduced in PR #2. See
PLAN.md §M-arch for the broader migration context.

Configuration via env vars (all optional):
    COGNEE_API_URL: Cognee service base URL (default: ``http://cognee:8000``)
    COGNEE_TIMEOUT_SECONDS: HTTP timeout (default: 10 — writes are slower)
    COGNEE_ENABLED: Master switch (default: ``false``)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class CogneeMemoryWriter:
    """Async write-path client for Cognee's REST API.

    The writer wraps Cognee's ``add`` and ``cognify`` endpoints with
    graceful fallback: if Cognee is disabled, unreachable, or errors,
    ``add()`` / ``cognify()`` return ``False`` rather than raising.
    This is intentional — supplemental memory sources must never
    break the primary memory path.

    Args:
        api_url: Cognee service base URL (default: ``http://cognee:8000``)
        timeout_seconds: HTTP timeout (default: 10 — writes are slower
            than reads because cognify is a multi-step process)
        enabled: Master switch (default: ``None`` → reads from
            ``COGNEE_ENABLED`` env var)
        client: Optional pre-configured ``httpx.AsyncClient`` (for
            testing). If ``None``, one is created lazily.
    """

    def __init__(
        self,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
        enabled: bool | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_url = (api_url or os.getenv("COGNEE_API_URL", "http://cognee:8000")).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(
            os.getenv("COGNEE_TIMEOUT_SECONDS", "10")
        )
        if enabled is None:
            enabled = os.getenv("COGNEE_ENABLED", "false").lower() in ("true", "1", "yes")
        self.enabled = enabled
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=self.timeout_seconds,
            )
        return self._client

    async def add(
        self,
        data: str | list[str],
        dataset: str = "default",
    ) -> bool:
        """Add ``data`` to the named Cognee ``dataset``.

        ``data`` may be a single string or a list of strings. Each item
        is sent as a separate ``add`` call (Cognee's API expects
        per-item payloads).

        Returns:
            ``True`` if every item was accepted (HTTP 2xx), ``False``
            otherwise. Never raises.
        """
        if not self.enabled:
            return False
        if isinstance(data, str):
            data = [data]
        try:
            client = await self._get_client()
            for item in data:
                payload: dict[str, Any] = {"data": item, "dataset": dataset}
                response = await client.post("/api/v1/add", json=payload)
                if response.status_code >= 300:
                    logger.warning(
                        "cognee_add_http_error",
                        status=response.status_code,
                        dataset=dataset,
                    )
                    return False
        except httpx.HTTPError as e:
            logger.warning(
                "cognee_add_http_error",
                error=str(e),
                dataset=dataset,
            )
            return False
        except Exception as e:
            logger.error(
                "cognee_add_unexpected_error",
                error=str(e),
                dataset=dataset,
            )
            return False

        logger.info(
            "cognee_add_ok",
            dataset=dataset,
            item_count=len(data),
        )
        return True

    async def cognify(self, datasets: list[str] | None = None) -> bool:
        """Trigger Cognee's entity/relation extraction (``cognify``).

        ``datasets`` defaults to ``["default"]``. Cognee's cognify
        endpoint is async on the server side; we just trigger it and
        return whether the call was accepted.

        Returns:
            ``True`` if Cognee accepted the cognify request, ``False``
            otherwise. Never raises.
        """
        if not self.enabled:
            return False
        if datasets is None:
            datasets = ["default"]
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/cognify",
                json={"datasets": datasets},
            )
            if response.status_code >= 300:
                logger.warning(
                    "cognee_cognify_http_error",
                    status=response.status_code,
                    datasets=datasets,
                )
                return False
        except httpx.HTTPError as e:
            logger.warning(
                "cognee_cognify_http_error",
                error=str(e),
                datasets=datasets,
            )
            return False
        except Exception as e:
            logger.error(
                "cognee_cognify_unexpected_error",
                error=str(e),
                datasets=datasets,
            )
            return False

        logger.info("cognee_cognify_ok", datasets=datasets)
        return True

    async def store(
        self,
        content: str,
        dataset: str = "default",
        cognify_after: bool = True,
    ) -> bool:
        """Convenience: ``add`` then optional ``cognify`` in one call.

        Returns ``True`` only if both steps succeed. If ``cognify_after``
        is ``False``, only ``add`` is called.
        """
        added = await self.add(data=content, dataset=dataset)
        if not added:
            return False
        if cognify_after:
            return await self.cognify(datasets=[dataset])
        return True

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
        return f"CogneeMemoryWriter(api_url={self.api_url!r}, enabled={self.enabled})"


def _env_use_cognee_writer() -> bool:
    """Check env var ``HERETEK_USE_COGNEE_WRITER`` (default: False).

    Default OFF so the existing in-memory memory wrapper remains the
    production path until Cognee sidecar parity is validated. Flip
    to ``true`` after the 1-week observation window required by
    PLAN.md §M-arch.
    """
    return os.getenv("HERETEK_USE_COGNEE_WRITER", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def get_memory_writer() -> CogneeMemoryWriter:
    """Factory: return a configured :class:`CogneeMemoryWriter`.

    Always returns a Cognee-backed writer (the legacy memory wrapper
    is left in place for now per PLAN.md §M-arch — "do not delete
    custom code until its replacement is proven in production").

    The factory exists so callers don't have to know about the
    ``COGNEE_ENABLED`` env var directly. The writer itself honors
    ``COGNEE_ENABLED`` at runtime; if it's false, all write operations
    become no-ops.
    """
    if _env_use_cognee_writer():
        logger.info("memory_writer_backend_selected", backend="cognee")
    return CogneeMemoryWriter()
