"""Async Qdrant vector store for memory entries."""

from __future__ import annotations

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from tier1.memory import MemoryEntry, MemoryType

log = structlog.get_logger(__name__)


class QdrantVectorStore:
    def __init__(
        self, url: str, collection: str, embedding_model: str, embedding_dimensions: int
    ) -> None:
        self.url = url
        self.collection = collection
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self._client: QdrantClient | None = None
        self._openai_client = None

    def connect(self) -> None:
        self._client = QdrantClient(url=self.url)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        assert self._client is not None
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection not in existing:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.embedding_dimensions, distance=Distance.COSINE
                ),
            )

    async def _embed(self, text: str) -> list[float]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return [0.0] * self.embedding_dimensions
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI()
        resp = await self._openai_client.embeddings.create(model=self.embedding_model, input=text)
        return resp.data[0].embedding

    def _upsert(self, entry: MemoryEntry) -> None:
        assert self._client is not None
        self._client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=entry.id,
                    vector=entry.embedding or [0.0] * self.embedding_dimensions,
                    payload={
                        "content": entry.content,
                        "memory_type": entry.memory_type.value,
                        "source": entry.source,
                        "deliberation_id": entry.deliberation_id,
                        "agent": entry.agent,
                        "created_at": entry.created_at,
                        "metadata": entry.metadata,
                    },
                )
            ],
        )

    def _delete(self, entry_id: str) -> None:
        assert self._client is not None
        self._client.delete(collection_name=self.collection, points_selector=[entry_id])

    async def store(self, entry: MemoryEntry) -> None:
        """Embed content and upsert to Qdrant. Best-effort."""
        try:
            entry.embedding = await self._embed(entry.content)
        except Exception:  # noqa: BLE001
            log.warning("embedding_failed", entry_id=entry.id)
            entry.embedding = None
        self._upsert(entry)

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Embed query, cosine search, return top_k entries."""
        try:
            query_vec = await self._embed(query)
        except Exception:  # noqa: BLE001
            return []
        return self._query(query_vec, top_k=top_k)

    def _query(self, query_vec: list[float], *, top_k: int = 5) -> list[MemoryEntry]:
        assert self._client is not None
        results = self._client.search(
            collection_name=self.collection,
            query_vector=query_vec,
            limit=top_k,
        )
        entries = []
        for hit in results:
            payload = hit.payload or {}
            entries.append(
                MemoryEntry(
                    id=str(hit.id),
                    content=payload.get("content", ""),
                    memory_type=MemoryType(payload.get("memory_type", "episodic")),
                    source=payload.get("source", ""),
                    deliberation_id=payload.get("deliberation_id"),
                    agent=payload.get("agent", ""),
                    created_at=payload.get("created_at", ""),
                    metadata=payload.get("metadata", {}),
                )
            )
        return entries

    async def delete(self, entry_id: str) -> None:
        self._delete(entry_id)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
