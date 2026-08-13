"""
Mem0 Backend Adapter — wraps the installed ``mem0ai`` library so the
``/api/mem0/*`` router in ``api/memories.py`` has a live implementation
to talk to.

Why this module exists
----------------------
``api/main.py`` previously did::

    try:
        from memory import MEM0_AVAILABLE, Mem0Backend, Mem0Config
    except ImportError:
        MEM0_AVAILABLE = False

There is no top-level ``memory`` package on ``sys.path`` — ``memory`` is a
sub-package of ``heretek_swarm`` — so the ``ImportError`` branch fired on
every cold start. The router's ``_require_mem0`` guard then 503'd every
``/api/mem0/*`` call, and the ``mem0:`` entry in ``GET /api/health`` was
permanently ``{status: unavailable}``.

This module fixes the import and provides a working adapter. Initialization
is lazy: the underlying ``mem0.Memory`` instance is built only when
``initialize()`` is called and required config (Qdrant host, OpenAI key) is
present. Without those, ``MEM0_AVAILABLE`` is still True (the library is
installed) but the backend reports ``unavailable`` until configured.

See PLAN.md §1.8 — Prime Directive "Persistent Operation" violation.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Module-level flag — True when the mem0ai library import succeeded.
# Distinct from the per-backend ``initialized`` state.
try:
    from mem0 import Memory as _Mem0Memory  # type: ignore[import-untyped]

    MEM0_AVAILABLE = True
except ImportError:  # pragma: no cover — mem0ai is a required dep
    _Mem0Memory = None  # type: ignore[assignment]
    MEM0_AVAILABLE = False


class Mem0Config(BaseModel):
    """Configuration for the Mem0 backend.

    Attributes
    ----------
    qdrant_host:
        Qdrant host. Falls back to the ``QDRANT_HOST`` env var.
    qdrant_port:
        Qdrant port. Falls back to ``QDRANT_PORT`` (default 6333).
    openai_api_key:
        OpenAI API key used by mem0's default LLM + embedder. Falls back
        to ``OPENAI_API_KEY``. Required for production use; in dev the
        backend will still initialize but mem0 calls will fail.
    collection_name:
        Qdrant collection name. Defaults to ``mem0``.
    history_db_path:
        Local SQLite path for mem0's edit history. Defaults to
        ``/tmp/heretek_mem0_history.db``.
    """

    qdrant_host: str | None = None
    qdrant_port: int = 6333
    openai_api_key: str | None = None
    collection_name: str = "mem0"
    history_db_path: str = "/tmp/heretek_mem0_history.db"


class Mem0Backend:
    """Thin async-friendly wrapper around ``mem0.Memory``.

    All public methods that hit mem0 dispatch to ``asyncio.to_thread`` so
    they do not block the event loop. The wrapper is intentionally
    minimal: it preserves the API surface the rest of the codebase
    (mostly ``api/memories.py``) already calls.
    """

    def __init__(self, config: Mem0Config) -> None:
        self._config = config
        self._memory: Any | None = None
        self._lock = asyncio.Lock()
        self.collection_name: str = config.collection_name

    # -- health / introspection ------------------------------------------

    @property
    def client(self) -> Any:
        """Underlying mem0 Memory instance, or None if not initialized.

        ``api/main.py:check_mem0`` reads this attribute to verify the
        backend is healthy.
        """
        return self._memory

    async def initialize(self) -> None:
        """Build the underlying mem0.Memory instance.

        Safe to call multiple times. If required config (Qdrant host or
        OpenAI key) is missing, this is a no-op and the backend stays
        ``unavailable`` — callers should check ``client is not None``.
        """
        if not MEM0_AVAILABLE:
            logger.warning("mem0ai library not installed — backend disabled")
            return
        if self._memory is not None:
            return

        host = self._config.qdrant_host or os.environ.get("QDRANT_HOST")
        port = self._config.qdrant_port or int(os.environ.get("QDRANT_PORT", "6333"))
        api_key = self._config.openai_api_key or os.environ.get("OPENAI_API_KEY")

        if not host or not api_key:
            logger.info(
                "mem0_backend_skipping_init",
                reason="missing qdrant_host or openai_api_key",
                host_present=bool(host),
                api_key_present=bool(api_key),
            )
            return

        try:
            self._memory = await asyncio.to_thread(self._build_memory, host, port, api_key)
            logger.info(
                "mem0_backend_initialized",
                collection=self.collection_name,
                qdrant=f"{host}:{port}",
            )
        except Exception as exc:  # pragma: no cover — mem0 init failure
            logger.warning("mem0_backend_init_failed", error=str(exc))
            self._memory = None

    def _build_memory(self, host: str, port: int, api_key: str) -> Any:
        """Construct the mem0.Memory client. Runs in a worker thread."""
        from mem0.configs.base import MemoryConfig  # type: ignore[import-untyped]
        from mem0.configs.embeddings import EmbedderConfig  # type: ignore[import-untyped]
        from mem0.configs.llms import LlmConfig  # type: ignore[import-untyped]
        from mem0.configs.vector_stores import (  # type: ignore[import-untyped]
            QdrantConfig,
            VectorStoreConfig,
        )

        cfg = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="qdrant",
                config=QdrantConfig(
                    collection_name=self.collection_name,
                    host=host,
                    port=port,
                ),
            ),
            llm=LlmConfig(provider="openai", config={"api_key": api_key}),
            embedder=EmbedderConfig(provider="openai", config={"api_key": api_key}),
            history_db_path=self._config.history_db_path,
        )
        return _Mem0Memory.from_config(cfg)

    async def shutdown(self) -> None:
        """Close the underlying mem0 client and SQLite history."""
        if self._memory is None:
            return
        try:
            await asyncio.to_thread(self._memory.close)
        except Exception as exc:  # pragma: no cover — best-effort shutdown
            logger.debug("mem0_close_failed", error=str(exc))
        self._memory = None

    # -- configuration ----------------------------------------------------

    async def configure(self, config: dict[str, Any]) -> None:
        """Re-apply configuration and rebuild the client.

        Accepts a free-form dict (mirrors the mem0_server contract used
        by ``api/memories.py:configure_mem0``). The wrapper translates a
        subset of keys into ``Mem0Config``; unknown keys are ignored.
        """
        async with self._lock:
            vector_store = config.get("vector_store") or {}
            llm = config.get("llm") or {}
            embedder = config.get("embedder") or {}
            vs_config = vector_store.get("config") or {}

            new_cfg = Mem0Config(
                qdrant_host=vs_config.get("host") or self._config.qdrant_host,
                qdrant_port=int(vs_config.get("port") or self._config.qdrant_port),
                openai_api_key=(
                    (llm.get("config") or {}).get("api_key")
                    or (embedder.get("config") or {}).get("api_key")
                    or self._config.openai_api_key
                ),
                collection_name=vs_config.get("collection_name", self.collection_name),
                history_db_path=config.get(
                    "history_db_path", self._config.history_db_path
                ),
            )
            await self.shutdown()
            self._config = new_cfg
            self.collection_name = new_cfg.collection_name
            await self.initialize()

    # -- CRUD -------------------------------------------------------------

    def _require(self) -> Any:
        if self._memory is None:
            raise RuntimeError("mem0 backend not initialized")
        return self._memory

    async def add(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._require().add, messages, **kwargs)

    async def get_all(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._require().get_all, **kwargs)

    async def get(self, memory_id: str) -> Any:
        return await asyncio.to_thread(self._require().get, memory_id)

    async def update(
        self,
        memory_id: str,
        data: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return await asyncio.to_thread(
            self._require().update, memory_id, data, metadata=metadata
        )

    async def delete_memory(self, memory_id: str) -> Any:
        return await asyncio.to_thread(self._require().delete, memory_id)

    async def history(self, memory_id: str) -> Any:
        return await asyncio.to_thread(self._require().history, memory_id)

    async def delete_all(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._require().delete_all, **kwargs)

    async def search(self, query: str, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._require().search, query, **kwargs)

    async def reset(self) -> Any:
        return await asyncio.to_thread(self._require().reset)


__all__ = ["MEM0_AVAILABLE", "Mem0Backend", "Mem0Config"]
