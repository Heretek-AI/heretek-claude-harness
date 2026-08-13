"""
ElectionManager - RAFT consensus leadership election orchestration.

Wraps 5 RaftElection instances (one per governance agent: steward, alpha,
beta, charlie, sentinel), cross-registers peers, and manages election cycles.

Used by ActorSupervisor to coordinate Steward leadership transitions when
the steward_pulse heartbeat monitor detects a timeout.

Reference: Raft consensus algorithm (Ongaro & Ousterhout, 2014)
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from heretek_swarm_core.consensus.raft_election import RaftElection

logger = structlog.get_logger("ElectionManager")

GOVERNANCE_AGENT_IDS: set[str] = {"steward", "alpha", "beta", "charlie", "sentinel"}


class ElectionManager:
    """
    Orchestrates RAFT leadership elections across governance-tier agents.

    Creates one RaftElection instance per governance agent, cross-registers
    peer connections so that vote requests are handled in-process without
    network overhead, and provides trigger_election() / stop_all() lifecycle
    methods.

    Example:
        ```python
        mgr = ElectionManager(election_timeout_min=0.5, election_timeout_max=1.0)
        leader = await mgr.trigger_election()
        logger.info("election_manager_leader_elected", leader=leader)
        await mgr.stop_all()
        ```
    """

    def __init__(
        self,
        election_timeout_min: float = 1.5,
        election_timeout_max: float = 3.0,
        max_election_cycles: int = 3,
    ) -> None:
        """
        Initialize ElectionManager with 5 governance-tier RaftElection instances.

        Args:
            election_timeout_min: Minimum election timeout in seconds.
            election_timeout_max: Maximum election timeout in seconds.
            max_election_cycles: Maximum full election cycles before giving up.
        """
        self._election_timeout_max = election_timeout_max
        self._max_cycles = max_election_cycles
        self._cycle_count = 0
        self._started = False

        # Create one RaftElection per governance agent
        self._rafts: dict[str, RaftElection] = {}
        for agent_id in GOVERNANCE_AGENT_IDS:
            peers = sorted(GOVERNANCE_AGENT_IDS - {agent_id})
            self._rafts[agent_id] = RaftElection(
                node_id=agent_id,
                peers=peers,
                election_timeout_min=election_timeout_min,
                election_timeout_max=election_timeout_max,
            )

        # Cross-register peers: each node can directly call every other node
        for agent_id, raft in self._rafts.items():
            for peer_id, peer_raft in self._rafts.items():
                if peer_id != agent_id:
                    raft.register_peer(peer_id, peer_raft)

        # Callback invoked when a leader is elected
        self._on_leader_elected: callable | None = None

        logger.info(
            "ElectionManager initialized",
            extra={
                "governance_agents": sorted(GOVERNANCE_AGENT_IDS),
                "timeout_range": (election_timeout_min, election_timeout_max),
                "max_cycles": max_election_cycles,
            },
        )

    def set_on_leader_elected(self, callback: callable) -> None:
        """Register a callback invoked when a leader is elected.

        The callback receives the leader_id (str) as its sole argument.
        """
        self._on_leader_elected = callback

    async def trigger_election(self) -> str | None:
        """Run a full election cycle and return the elected leader ID."""
        self._cycle_count = 0
        await self._ensure_rafts_started()
        await asyncio.sleep(0.05)
        logger.info("raft_election_started", extra={"cycle": 0})
        for cycle in range(self._max_cycles):
            self._cycle_count = cycle
            await self._kick_off_voting()
            leader_id = await self._poll_for_leader(cycle)
            if leader_id is not None:
                return leader_id
            logger.warning("Election cycle {cycle} produced no leader — retrying", extra={"cycle": cycle})
        logger.error("tribunal_election_failed", extra={
            "cycles_attempted": self._max_cycles,
            "governance_agents": sorted(GOVERNANCE_AGENT_IDS),
        })
        return None

    async def _ensure_rafts_started(self) -> None:
        if not self._started:
            await asyncio.gather(*[raft.start() for raft in self._rafts.values()])
            self._started = True

    async def _kick_off_voting(self) -> None:
        await asyncio.gather(*[raft._start_election() for raft in self._rafts.values()])

    async def _poll_for_leader(self, cycle: int) -> str | None:
        deadline = self._election_timeout_max
        elapsed = 0.0
        step = 0.1
        while elapsed < deadline:
            await asyncio.sleep(step)
            elapsed += step
            leader_id = self._current_leader()
            if leader_id is not None:
                logger.info("raft_leader_elected", extra={
                    "leader_id": leader_id, "cycle": cycle, "term": self._rafts[leader_id].term,
                })
                if self._on_leader_elected:
                    try:
                        await self._on_leader_elected(leader_id)
                    except Exception:
                        logger.exception("Leader elected callback failed")
                return leader_id
        return None

    async def stop_all(self) -> None:
        """Cancel and clean up all RaftElection instances."""
        results = await asyncio.gather(
            *[raft.stop() for raft in self._rafts.values()],
            return_exceptions=True,
        )
        for agent_id, result in zip(self._rafts.keys(), results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "Error stopping RaftElection",
                    extra={"agent_id": agent_id, "error": str(result)},
                )
        self._started = False
        logger.info("ElectionManager stopped all instances")

    def get_status(self) -> dict[str, Any]:
        """Return status for every governance node and the current cycle.

        Returns:
            Dict with keys ``nodes`` (per-node status dicts), ``leader_id``
            (current leader or None), and ``cycle_count``.
        """
        return {
            "nodes": {
                agent_id: raft.get_status()
                for agent_id, raft in self._rafts.items()
            },
            "leader_id": self._current_leader(),
            "cycle_count": self._cycle_count,
        }

    def _current_leader(self) -> str | None:
        """Return the agent_id of the current RAFT leader, or None."""
        for agent_id, raft in self._rafts.items():
            if raft.is_leader:
                return agent_id
        return None
