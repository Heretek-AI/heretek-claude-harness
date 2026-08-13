"""Qdrant vector-store client wrapper.

Wraps `qdrant_client.QdrantClient` so we can lazy-init on first probe
and report a clean `health()` result for the /health endpoint. The
client is synchronous (qdrant-client exposes both sync and async; we
use sync because the only operation we run on this code path is a
health check against a remote service).
"""

from __future__ import annotations

from qdrant_client import QdrantClient


class QdrantStore:
    def __init__(self, url: str, collection: str) -> None:
        self.url = url
        self.collection = collection
        self.client: QdrantClient | None = None

    def connect(self) -> None:
        # QdrantClient lazy-connects; constructing it does not open a socket.
        self.client = QdrantClient(url=self.url)

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:  # noqa: BLE001
                pass
            self.client = None

    def health(self) -> bool:
        """Return True iff the qdrant service is reachable."""
        assert self.client is not None
        # get_collections() hits the HTTP /collections endpoint and is the
        # standard cheap liveness probe (see qdrant-client docs).
        self.client.get_collections()
        return True
