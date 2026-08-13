"""
Hindsight compatibility shim — transparent training-memory write path.

Implements Phase 1.6 of PLAN.md (Zero-Trust Architecture Audit,
§3.2 Borrow — hindsight).

Why
---
Hindsight (vectorize-io/hindsight on GitHub) is a TypeScript-based
agent memory system designed for the "learned, not just remembered"
property. The audit recommends it as the canonical write path for
Habit-Forge's *training memory* (the data the agent uses to
improve its own prompts / policies over time, distinct from the
episodic memory that cognee / mem0 hold).

Hindsight is not a Python library — it ships as a Node service.
This shim:

* Exposes a small Python API (the audit's "2-line LLM-wrapper
  integration pattern" — ``record(agent_id, payload)`` and
  ``recall(agent_id, query)``).
* If a Hindsight HTTP service is reachable at ``HINDSIGHT_URL``,
  dispatches the calls to it. Treats 404 / network errors as a
  silent no-op so the agent's training loop never breaks on a
  memory backend that is intentionally absent in dev.
* Falls back to a local in-memory store when the service is
  unreachable, so Habit-Forge can keep running with a degraded
  but functional memory surface.

Mirrors the pattern in :mod:`heretek_swarm.memory.mem0_backend`
and :mod:`heretek_swarm_core.llm.headroom_compat` — same facade
shape, same graceful degradation, same single optional dep.

Scope
-----
This module ships the facade. Wiring it into Habit-Forge's
training loop is a follow-up; the interface is stable so the
wiring can land incrementally.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Default Hindsight service URL (matches the docker-compose
# convention used elsewhere in the repo).
HINDSIGHT_URL = os.getenv("HINDSIGHT_URL", "http://hindsight:7700").rstrip("/")

# Whether to call the live service. Set HINDSIGHT_ENABLED=0 to
# force the in-memory fallback (handy in CI / dev).
HINDSIGHT_ENABLED = os.getenv("HINDSIGHT_ENABLED", "1").lower() in (
    "1",
    "true",
    "yes",
)


@dataclass
class HindsightRecord:
    """A single training-memory record.

    Distinct from :class:`heretek_swarm.memory.store.MemoryEntry`
    because training memory is a different shape (small, written
    often, recalled by query, scored by relevance rather than
    by tier).
    """

    agent_id: str
    payload: dict[str, Any]
    created_at: float


class HindsightClient:
    """Thin async client over the Hindsight service (or its
    in-memory fallback).

    The client is intentionally minimal: it does not try to model
    Hindsight's full graph / temporal query surface. The
    Habit-Forge training loop needs two operations — record and
    recall — and that is what this class provides.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        enabled: bool | None = None,
    ) -> None:
        self._base_url = (base_url or HINDSIGHT_URL).rstrip("/")
        self._enabled = HINDSIGHT_ENABLED if enabled is None else enabled
        self._fallback: list[HindsightRecord] = []

    async def record(
        self,
        agent_id: str,
        payload: dict[str, Any],
    ) -> str | None:
        """Record a training-memory entry for ``agent_id``.

        Returns the record id (string) on success, ``None`` on
        any failure. Never raises — callers treat ``None`` as
        "training memory write skipped" and continue.
        """
        if not self._enabled:
            # Force fallback. Useful in tests and in dev when the
            # operator wants to short-circuit the network call.
            return self._record_fallback(agent_id, payload)

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self._base_url}/v1/agents/{agent_id}/memory",
                    json={"payload": payload},
                )
                if response.status_code in (200, 201, 202):
                    data = response.json() if response.content else {}
                    return str(data.get("id", ""))
                # 404 (no service at this URL) or 5xx — fall back.
                logger.debug(
                    "hindsight_record_unavailable",
                    status=response.status_code,
                    agent_id=agent_id,
                )
        except Exception as exc:  # pragma: no cover - network errors
            logger.debug(
                "hindsight_record_failed",
                agent_id=agent_id,
                error=str(exc),
            )

        return self._record_fallback(agent_id, payload)

    async def recall(
        self,
        agent_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[HindsightRecord]:
        """Recall the top-k training-memory entries matching
        ``query`` for ``agent_id``.

        Returns the empty list on any failure.
        """
        if self._enabled:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{self._base_url}/v1/agents/{agent_id}/memory",
                        params={"q": query, "top_k": str(top_k)},
                    )
                    if response.status_code == 200:
                        data = response.json() if response.content else {}
                        records = data.get("records", [])
                        return [
                            HindsightRecord(
                                agent_id=agent_id,
                                payload=r.get("payload", {}),
                                created_at=float(r.get("created_at", time.time())),
                            )
                            for r in records
                        ]
            except Exception as exc:  # pragma: no cover - network errors
                logger.debug(
                    "hindsight_recall_failed",
                    agent_id=agent_id,
                    error=str(exc),
                )

        # Fall back to the in-memory store. Substring match is
        # good enough for dev / degraded mode.
        return self._recall_fallback(agent_id, query, top_k)

    # -- fallback (in-memory) -----------------------------------------

    def _record_fallback(
        self,
        agent_id: str,
        payload: dict[str, Any],
    ) -> str:
        import uuid

        rid = str(uuid.uuid4())
        self._fallback.append(
            HindsightRecord(
                agent_id=agent_id,
                payload=payload,
                created_at=time.time(),
            )
        )
        return rid

    def _recall_fallback(
        self,
        agent_id: str,
        query: str,
        top_k: int,
    ) -> list[HindsightRecord]:
        q = query.lower()
        scored: list[tuple[int, HindsightRecord]] = []
        for record in self._fallback:
            if record.agent_id != agent_id:
                continue
            haystack = " ".join(
                str(v).lower() for v in record.payload.values()
            )
            score = sum(1 for tok in q.split() if tok in haystack)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [r for _, r in scored[:top_k]]


# Module-level default client. New code should call this directly
# rather than instantiating a new client every time.
_default_client: HindsightClient | None = None


def get_hindsight_client() -> HindsightClient:
    """Return the process-wide :class:`HindsightClient`."""
    global _default_client
    if _default_client is None:
        _default_client = HindsightClient()
    return _default_client


async def record(agent_id: str, payload: dict[str, Any]) -> str | None:
    """Convenience wrapper around :meth:`HindsightClient.record`."""
    return await get_hindsight_client().record(agent_id, payload)


async def recall(agent_id: str, query: str, *, top_k: int = 5) -> list[HindsightRecord]:
    """Convenience wrapper around :meth:`HindsightClient.recall`."""
    return await get_hindsight_client().recall(agent_id, query, top_k=top_k)


__all__ = [
    "HindsightClient",
    "HindsightRecord",
    "HINDSIGHT_ENABLED",
    "HINDSIGHT_URL",
    "get_hindsight_client",
    "record",
    "recall",
]
