"""
gRPC client wrappers for the 4 sovereign services.

Phase 5 of PLAN.md (§1.13 'Graduated sovereign services').
When the api process is configured with the
``HERETEK_CONSENSUS_GRPC_URL`` env var (and similar for
the other services), it uses these clients instead of the
in-process service stubs.

Backwards compatibility: when the env vars are unset, the
``get_*_grpc_client()`` factories return ``None`` so the
api process falls back to the in-process service stubs.
The api process chooses transport at call time:
``client = get_consensus_grpc_client() or get_consensus_svc()``.
"""

from __future__ import annotations

import json
import os
from typing import Any

import grpc

from heretek_swarm.services.consensus_svc import (
    ConsensusRequest,
    ConsensusServiceStub,
    get_consensus_svc,
)
from heretek_swarm.services.grpc_proto import heretek_services_pb2 as pb
from heretek_swarm.services.grpc_proto import heretek_services_pb2_grpc as pb_grpc
from heretek_swarm.services.memory_svc import (
    MemoryAddRequest,
    MemoryServiceStub,
    get_memory_svc,
)
from heretek_swarm.services.observability_svc import (
    ObservabilityServiceStub,
    get_observability_svc,
)
from heretek_swarm.services.realtime_svc import (
    RealtimeServiceStub,
    get_realtime_svc,
)


# =============================================================================
# Channel management
# =============================================================================


_channels: dict[str, grpc.Channel] = {}


def _get_channel(url: str) -> grpc.Channel:
    """Lazy-init a gRPC channel, cached by URL."""
    if url not in _channels:
        # mTLS is the production path; insecure is fine for dev.
        if url.startswith("https://") or os.getenv("HERETEK_MTLS_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
        ):
            _channels[url] = grpc.secure_channel(
                url,
                grpc.ssl_channel_credentials(),
            )
        else:
            _channels[url] = grpc.insecure_channel(url)
    return _channels[url]


def close_all_channels() -> None:
    """Close all cached gRPC channels (used at shutdown)."""
    for ch in _channels.values():
        ch.close()
    _channels.clear()


# =============================================================================
# Client wrappers
# =============================================================================


class ConsensusGrpcClient:
    """gRPC client for the consensus service."""

    def __init__(self, url: str) -> None:
        self._stub = pb_grpc.ConsensusServiceStub(_get_channel(url))

    async def create_round(
        self, topic: str, participants: list[str], consensus_id: str | None = None
    ) -> str:
        req = pb.CreateRoundRequest(
            topic=topic, participants=participants, consensus_id=consensus_id or ""
        )
        resp = await self._stub.CreateRound(req)
        return resp.consensus_id

    async def add_vote(
        self, consensus_id: str, agent_id: str, decision: str, confidence: float
    ) -> str:
        req = pb.AddVoteRequest(
            consensus_id=consensus_id,
            agent_id=agent_id,
            decision=decision,
            confidence=confidence,
        )
        resp = await self._stub.AddVote(req)
        return resp.state

    async def compute(self, consensus_id: str) -> dict[str, Any] | None:
        req = pb.ComputeRequest(consensus_id=consensus_id)
        resp = await self._stub.Compute(req)
        if resp.state == "UNKNOWN":
            return None
        return {
            "consensus_id": resp.consensus_id,
            "decision": resp.decision,
            "score": resp.score,
            "votes": {k: json.loads(v) for k, v in resp.votes.items()},
        }


class MemoryGrpcClient:
    """gRPC client for the memory service."""

    def __init__(self, url: str) -> None:
        self._stub = pb_grpc.MemoryServiceStub(_get_channel(url))

    async def add(
        self,
        content: str,
        memory_type: str = "episodic",
        identifier: str | None = None,
    ) -> str | None:
        req = pb.AddMemoryRequest(
            content=content, memory_type=memory_type, identifier=identifier or ""
        )
        resp = await self._stub.Add(req)
        return resp.memory_id or None

    async def read(self, memory_id: str, memory_type: str = "episodic"):
        req = pb.ReadMemoryRequest(memory_id=memory_id, memory_type=memory_type)
        return await self._stub.Read(req)

    async def search(
        self, query: str, memory_type: str | None = None, top_k: int = 5
    ):
        req = pb.SearchMemoryRequest(
            query=query, memory_type=memory_type or "", top_k=top_k
        )
        resp = await self._stub.Search(req)
        return resp.entries


class RealtimeGrpcClient:
    """gRPC client for the realtime service."""

    def __init__(self, url: str) -> None:
        self._stub = pb_grpc.RealtimeServiceStub(_get_channel(url))

    async def broadcast_dashboard(self, payload: dict[str, Any]) -> None:
        await self._stub.BroadcastDashboard(
            pb.BroadcastRequest(
                event_type="dashboard",
                payload_json=json.dumps(payload),
            )
        )


class ObservabilityGrpcClient:
    """gRPC client for the observability service."""

    def __init__(self, url: str) -> None:
        self._stub = pb_grpc.ObservabilityServiceStub(_get_channel(url))

    async def track_metric(
        self, name: str, value: float = 1.0, tags: dict[str, str] | None = None
    ) -> None:
        await self._stub.TrackMetric(
            pb.MetricRequest(name=name, value=value, tags=tags or {})
        )

    async def fire_alert(
        self, name: str, severity: str = "warning", message: str = ""
    ) -> None:
        await self._stub.FireAlert(
            pb.AlertRequest(
                name=name, severity=severity, message=message
            )
        )


# =============================================================================
# Process-wide resolver: returns the gRPC client if a URL is configured,
# otherwise None (caller falls back to the in-process stub).
# =============================================================================


def get_consensus_grpc_client() -> ConsensusGrpcClient | None:
    """Return the gRPC consensus client, or None if not configured."""
    url = os.getenv("HERETEK_CONSENSUS_GRPC_URL")
    if not url:
        return None
    return ConsensusGrpcClient(url)


def get_memory_grpc_client() -> MemoryGrpcClient | None:
    """Return the gRPC memory client, or None if not configured."""
    url = os.getenv("HERETEK_MEMORY_GRPC_URL")
    if not url:
        return None
    return MemoryGrpcClient(url)


def get_realtime_grpc_client() -> RealtimeGrpcClient | None:
    """Return the gRPC realtime client, or None if not configured."""
    url = os.getenv("HERETEK_REALTIME_GRPC_URL")
    if not url:
        return None
    return RealtimeGrpcClient(url)


def get_observability_grpc_client() -> ObservabilityGrpcClient | None:
    """Return the gRPC observability client, or None if not configured."""
    url = os.getenv("HERETEK_OBSERVABILITY_GRPC_URL")
    if not url:
        return None
    return ObservabilityGrpcClient(url)


__all__ = [
    "ConsensusGrpcClient",
    "MemoryGrpcClient",
    "RealtimeGrpcClient",
    "ObservabilityGrpcClient",
    "get_consensus_grpc_client",
    "get_memory_grpc_client",
    "get_realtime_grpc_client",
    "get_observability_grpc_client",
    "close_all_channels",
]
