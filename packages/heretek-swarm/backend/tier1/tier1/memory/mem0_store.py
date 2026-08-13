"""Mem0 semantic memory backend — wraps mem0ai library."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


class Mem0Backend:
    def __init__(self, api_key: str | None = None, vector_store: str = "qdrant") -> None:
        self._api_key = api_key
        self._vector_store = vector_store
        self._enabled = bool(api_key)
        self._client = None

    def _ensure_client(self) -> None:
        if not self._enabled:
            return
        if self._client is None:
            from mem0ai import MemoryClient

            self._client = MemoryClient(api_key=self._api_key)

    async def add(self, text: str, user_id: str, metadata: dict | None = None) -> str | None:
        if not self._enabled:
            return None
        try:
            self._ensure_client()
            result = self._client.add(text, user_id=user_id, metadata=metadata or {})
            return result.get("id")
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_add_failed", error=str(exc))
            return None

    async def search(self, query: str, user_id: str, top_k: int = 5) -> list[dict]:
        if not self._enabled:
            return []
        try:
            self._ensure_client()
            result = self._client.search(query, user_id=user_id, limit=top_k)
            return result.get("results", []) if isinstance(result, dict) else result
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_search_failed", error=str(exc))
            return []

    async def update(self, memory_id: str, text: str) -> bool:
        if not self._enabled:
            return False
        try:
            self._ensure_client()
            self._client.update(memory_id, text)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_update_failed", error=str(exc))
            return False

    async def delete(self, memory_id: str) -> bool:
        if not self._enabled:
            return False
        try:
            self._ensure_client()
            self._client.delete(memory_id)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_delete_failed", error=str(exc))
            return False
