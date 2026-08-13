"""
RaftElection - Raft Consensus Leader Election for Heretek Swarm

This module implements Raft consensus leader election:
- RequestVote RPC for election requests
- AppendEntries RPC for heartbeat and log replication
- Leader state management
- Integration with existing MAKER consensus

Reference: Raft consensus algorithm (https://github.com/rqlite/rqlite)
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("RaftElection")


class RaftState(Enum):
    """Raft node states."""

    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class Vote:
    """
    Vote dataclass for Raft consensus.

    Attributes:
        term: Candidate's term
        candidate_id: ID of candidate requesting vote
        vote_granted: True if vote was granted
    """

    term: int
    candidate_id: str
    vote_granted: bool


@dataclass
class RequestVoteRequest:
    """
    RequestVote RPC request.

    Attributes:
        term: Candidate's term
        candidate_id: ID of candidate requesting vote
        last_log_index: Index of candidate's last log entry
        last_log_term: Term of candidate's last log entry
    """

    term: int
    candidate_id: str
    last_log_index: int = 0
    last_log_term: int = 0


@dataclass
class RequestVoteResponse:
    """
    RequestVote RPC response.

    Attributes:
        term: Current term
        vote_granted: True if vote was granted
    """

    term: int
    vote_granted: bool


@dataclass
class AppendEntriesRequest:
    """
    AppendEntries RPC request (heartbeat or log replication).

    Attributes:
        term: Leader's term
        leader_id: ID of leader
        prev_log_index: Index of log entry before new entries
        prev_log_term: Term of prev_log_index entry
        entries: Log entries to append
        leader_commit: Leader's commit index
    """

    term: int
    leader_id: str
    prev_log_index: int = 0
    prev_log_term: int = 0
    entries: list["LogEntry"] = field(default_factory=list)
    leader_commit: int = 0


@dataclass
class AppendEntriesResponse:
    """
    AppendEntries RPC response.

    Attributes:
        term: Current term
        success: True if entries matched
        match_index: Highest index known to be matched
    """

    term: int
    success: bool
    match_index: int = 0


@dataclass
class LogEntry:
    """Log entry for Raft log."""

    index: int
    term: int
    data: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class LeaderState:
    """
    Current leader state.

    Attributes:
        leader_id: Current leader ID
        term: Leader term
        commit_index: Committed log index
        last_applied: Last applied index
    """

    leader_id: str | None = None
    term: int = 0
    commit_index: int = 0
    last_applied: int = 0


class RaftElection:
    """
    Raft consensus leader election implementation.

    Provides:
    - Leader election via RequestVote RPC
    - Heartbeat via AppendEntries RPC
    - Log replication
    - Integration with MAKERConsensus

    Example:
        ```python
        # Initialize as leader node
        raft = RaftElection(
            node_id="node-1",
            peers=["node-2", "node-3"],
            election_timeout_min=1.5,
            election_timeout_max=3.0
        )
        await raft.start()

        # Check leadership
        if raft.is_leader:
            logger.info("raft_leader_elected_local", leader_id=raft.leader_id)

        # Request vote from other nodes
        response = await raft.request_vote(
            "node-2",
            RequestVoteRequest(term=1, candidate_id="node-1")
        )
        ```
    """

    def __init__(
        self,
        node_id: str,
        peers: list[str] | None = None,
        election_timeout_min: float = 1.5,
        election_timeout_max: float = 3.0,
        heartbeat_interval: float = 0.5,
        max_log_entries: int = 1000,
    ) -> None:
        """
        Initialize RaftElection.

        Args:
            node_id: Unique node identifier
            peers: List of peer node IDs
            election_timeout_min: Min election timeout in seconds
            election_timeout_max: Max election timeout in seconds
            heartbeat_interval: Heartbeat interval in seconds
            max_log_entries: Max log entries to retain
        """
        self.node_id = node_id
        self.peers = peers or []

        # Timeouts
        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval
        self.max_log_entries = max_log_entries

        # State
        self._state = RaftState.FOLLOWER
        self._current_term = 0
        self._voted_for: str | None = None
        self._voted_nodes: set[str] = set()

        # Log
        self._log: list[LogEntry] = []
        self._log_index = 0

        # Leader state
        self._leader_state = LeaderState()

        # Election timeout
        self._election_timeout: float = 0.0
        self._reset_election_timeout()

        # Tasks
        self._running = False
        self._election_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

        # Peer connections (peer_id -> connection)
        self._peer_connections: dict[str, RaftElection] = {}

        # Callbacks
        self._on_leader_change: callable | None = None
        self._on_log_append: callable | None = None

        logger.info(
            f"RaftElection initialized for {node_id}",
            extra={
                "node_id": node_id,
                "peers": peers,
                "state": self._state.value,
            },
        )

    @property
    def is_leader(self) -> bool:
        """Check if this node is leader."""
        return self._state == RaftState.LEADER

    @property
    def is_candidate(self) -> bool:
        """Check if this node is candidate."""
        return self._state == RaftState.CANDIDATE

    @property
    def is_follower(self) -> bool:
        """Check if this node is follower."""
        return self._state == RaftState.FOLLOWER

    @property
    def leader_id(self) -> str | None:
        """Get current leader ID."""
        return self._leader_state.leader_id

    @property
    def term(self) -> int:
        """Get current term."""
        return self._current_term

    @property
    def node_state(self) -> RaftState:
        """Get current state."""
        return self._state

    def _reset_election_timeout(self) -> None:
        """Reset election timeout to random value."""
        self._election_timeout = random.uniform(
            self.election_timeout_min,
            self.election_timeout_max,
        )

    async def start(self) -> None:
        """Start Raft node."""
        self._running = True
        self._election_task = asyncio.create_task(self._election_loop())
        logger.info("RaftElection started for {self.node_id}")

    async def stop(self) -> None:
        """Stop Raft node."""
        self._running = False

        if self._election_task:
            self._election_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        logger.info("RaftElection stopped for {self.node_id}")

    async def _election_loop(self) -> None:
        """Election timeout loop."""
        while self._running:
            try:
                await asyncio.sleep(0.1)
                self._election_timeout -= 0.1

                if self._election_timeout <= 0:
                    await self._start_election()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Election loop error: {e}")

    async def _start_election(self) -> None:
        """Start leader election."""
        # Become candidate
        self._state = RaftState.CANDIDATE
        self._current_term += 1
        self._voted_for = self.node_id
        self._voted_nodes = {self.node_id}

        logger.info(
            "Starting election",
            extra={
                "node_id": self.node_id,
                "term": self._current_term,
            },
        )

        # Request votes from all peers
        vote_count = 1  # My vote
        for peer_id in self.peers:
            try:
                response = await self._request_vote_from_peer(peer_id)
                if response and response.vote_granted:
                    vote_count += 1
            except Exception:
                logger.error("Failed to get vote from {peer_id}: {e}")

        # Check if won election
        majority = (len(self.peers) + 1) // 2 + 1
        if vote_count >= majority:
            await self._become_leader()
        else:
            # Lost election, become follower
            self._state = RaftState.FOLLOWER
            self._reset_election_timeout()

            logger.info(
                "Election lost",
                extra={"vote_count": vote_count, "majority": majority},
            )

    async def _become_leader(self) -> None:
        """Become leader."""
        self._state = RaftState.LEADER
        self._leader_state = LeaderState(
            leader_id=self.node_id,
            term=self._current_term,
        )

        logger.info(
            "Became leader",
            extra={
                "node_id": self.node_id,
                "term": self._current_term,
            },
        )

        # Start sending heartbeats
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Notify leader change
        if self._on_leader_change:
            try:
                await self._on_leader_change(self.node_id)
            except Exception:
                logger.error("Leader change callback error: {e}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to followers."""
        while self._running and self._state == RaftState.LEADER:
            try:
                for peer_id in self.peers:
                    try:
                        await self._send_heartbeat(peer_id)
                    except Exception:
                        logger.error("Failed to send heartbeat to {peer_id}: {e}")

                await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Heartbeat loop error: {e}")

    async def _request_vote_from_peer(
        self,
        peer_id: str,
    ) -> RequestVoteResponse | None:
        """Request vote from a peer node."""
        peer = self._peer_connections.get(peer_id)
        if peer is None:
            # Simulate remote call
            return await self.request_vote(
                RequestVoteRequest(
                    term=self._current_term,
                    candidate_id=self.node_id,
                    last_log_index=self._log_index,
                    last_log_term=self._get_last_log_term(),
                )
            )

        # Direct call to peer
        return await peer.request_vote(
            RequestVoteRequest(
                term=self._current_term,
                candidate_id=self.node_id,
                last_log_index=self._log_index,
                last_log_term=self._get_last_log_term(),
            )
        )

    async def _send_heartbeat(self, peer_id: str) -> None:
        """Send heartbeat to peer."""
        request = AppendEntriesRequest(
            term=self._current_term,
            leader_id=self.node_id,
            prev_log_index=self._log_index,
            prev_log_term=self._get_last_log_term(),
            entries=[],
            leader_commit=self._leader_state.commit_index,
        )

        peer = self._peer_connections.get(peer_id)
        if peer is None:
            # Simulate remote call
            await self.append_entries(request)
        else:
            await peer.append_entries(request)

    def _get_last_log_term(self) -> int:
        """Get term of last log entry."""
        if self._log:
            return self._log[-1].term
        return 0

    async def request_vote(
        self,
        request: RequestVoteRequest,
    ) -> RequestVoteResponse:
        """
        Handle RequestVote RPC.

        Args:
            request: RequestVote request

        Returns:
            RequestVote response
        """
        # Update term if needed
        if request.term > self._current_term:
            await self._step_down(request.term)

        # Grant vote if:
        # 1. Term >= current term
        # 2. Haven't voted for another candidate (or this is same candidate)
        # 3. Candidate's log is at least as up-to-date
        vote_granted = False

        if request.term >= self._current_term:
            if self._voted_for is None or self._voted_for == request.candidate_id:
                if self._is_log_up_to_date(request.last_log_index, request.last_log_term):
                    self._voted_for = request.candidate_id
                    vote_granted = True
                    self._reset_election_timeout()

        logger.debug(
            "RequestVote response",
            extra={
                "request_candidate": request.candidate_id,
                "vote_granted": vote_granted,
                "current_term": self._current_term,
            },
        )

        return RequestVoteResponse(
            term=self._current_term,
            vote_granted=vote_granted,
        )

    async def append_entries(
        self,
        request: AppendEntriesRequest,
    ) -> AppendEntriesResponse:
        """
        Handle AppendEntries RPC (heartbeat or log replication).

        Args:
            request: AppendEntries request

        Returns:
            AppendEntries response
        """
        # Update term if needed
        if request.term > self._current_term:
            await self._step_down(request.term)

        # If leader term is stale, reject
        if request.term < self._current_term:
            return AppendEntriesResponse(
                term=self._current_term,
                success=False,
            )

        # Update leader state
        self._leader_state = LeaderState(
            leader_id=request.leader_id,
            term=request.term,
        )

        # Reset election timeout
        self._reset_election_timeout()

        # Handle heartbeat or log entries
        success = True
        match_index = request.prev_log_index

        if request.entries:
            # Log replication
            if request.prev_log_index < len(self._log):
                # Check if existing entry matches
                existing = self._log[request.prev_log_index]
                if existing.term != request.prev_log_term:
                    success = False
                else:
                    # Append new entries
                    self._log = self._log[: request.prev_log_index + 1]
                    self._log.extend(request.entries)
                    match_index = len(self._log) - 1

                    # Apply committed entries
                    if request.leader_commit > self._leader_state.commit_index:
                        self._leader_state.commit_index = request.leader_commit

            else:
                success = False

        # Commit entries if leader committed
        if request.leader_commit > self._leader_state.commit_index:
            self._leader_state.commit_index = request.leader_commit

        logger.debug(
            "AppendEntries response",
            extra={
                "leader": request.leader_id,
                "success": success,
                "match_index": match_index,
            },
        )

        return AppendEntriesResponse(
            term=self._current_term,
            success=success,
            match_index=match_index,
        )

    async def _step_down(self, new_term: int) -> None:
        """Step down to follower state."""
        self._current_term = new_term
        self._state = RaftState.FOLLOWER
        self._voted_for = None
        self._leader_state = LeaderState(term=new_term)
        self._reset_election_timeout()

        logger.debug("Stepped down to term {new_term}")

    def _is_log_up_to_date(self, last_index: int, last_term: int) -> bool:
        """Check if candidate's log is up-to-date."""
        if not self._log:
            return True

        my_last_term = self._log[-1].term

        # More recent entry wins
        if last_term != my_last_term:
            return last_term > my_last_term

        # Longer log wins
        return last_index >= len(self._log) - 1

    async def append_log(self, data: dict[str, Any]) -> int:
        """
        Append entry to log (leader only).

        Args:
            data: Log entry data

        Returns:
            Log index
        """
        if not self.is_leader:
            raise RuntimeError("Only leader can append log entries")

        self._log_index += 1
        entry = LogEntry(
            index=self._log_index,
            term=self._current_term,
            data=data,
        )

        self._log.append(entry)

        # Replicate to followers
        for peer_id in self.peers:
            try:
                await self._replicate_to_peer(peer_id, entry)
            except Exception:
                logger.error("Failed to replicate to {peer_id}: {e}")

        logger.debug("Appended log entry {self._log_index}")
        return self._log_index

    async def _replicate_to_peer(self, peer_id: str, entry: LogEntry) -> None:
        """Replicate log entry to peer."""
        request = AppendEntriesRequest(
            term=self._current_term,
            leader_id=self.node_id,
            prev_log_index=entry.index - 1,
            prev_log_term=entry.term,
            entries=[entry],
            leader_commit=self._leader_state.commit_index,
        )

        peer = self._peer_connections.get(peer_id)
        if peer:
            await peer.append_entries(request)

    def get_log_entry(self, index: int) -> LogEntry | None:
        """Get log entry by index."""
        if 0 <= index < len(self._log):
            return self._log[index]
        return None

    def get_commit_index(self) -> int:
        """Get commit index."""
        return self._leader_state.commit_index

    def get_leader_state(self) -> LeaderState:
        """Get current leader state."""
        return self._leader_state

    def register_peer(self, peer_id: str, peer: "RaftElection") -> None:
        """Register peer connection."""
        self._peer_connections[peer_id] = peer
        logger.debug("Registered peer {peer_id}")

    def unregister_peer(self, peer_id: str) -> None:
        """Unregister peer connection."""
        if peer_id in self._peer_connections:
            del self._peer_connections[peer_id]
            logger.debug("Unregistered peer {peer_id}")

    def set_leader_change_callback(self, callback: callable) -> None:
        """Set callback for leader changes."""
        self._on_leader_change = callback

    def set_log_append_callback(self, callback: callable) -> None:
        """Set callback for log appends."""
        self._on_log_append = callback

    def get_status(self) -> dict[str, Any]:
        """Get node status."""
        return {
            "node_id": self.node_id,
            "state": self._state.value,
            "term": self._current_term,
            "leader_id": self._leader_state.leader_id,
            "commit_index": self._leader_state.commit_index,
            "log_length": len(self._log),
            "peers": list(self._peer_connections.keys()),
        }


class MAKERConsensusWithRaft:
    """
    MAKER Consensus with optional Raft layer for leader-based coordination.

    Example:
        ```python
        consensus = MAKERConsensusWithRaft(
            node_id="node-1",
            peers=["node-2", "node-3"],
            maker_config={"ahead_by_k": 2, "min_votes": 3}
        )
        await consensus.start()

        # Use Raft for leadership
        if consensus.is_leader:
            result = await consensus.run_consensus(...)
        ```
    """

    def __init__(
        self,
        node_id: str,
        peers: list[str] | None = None,
        maker_config: dict[str, Any] | None = None,
        raft_config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize MAKERConsensusWithRaft.

        Args:
            node_id: Unique node identifier
            peers: List of peer node IDs
            maker_config: Configuration for MAKER consensus
            raft_config: Configuration for Raft election
        """
        from heretek_swarm_core.consensus.maker import MAKERConsensus

        self.node_id = node_id
        self.peers = peers or []

        # MAKER consensus
        self._maker = MAKERConsensus(**(maker_config or {}))

        # Raft election
        raft_cfg = raft_config or {}
        raft_cfg["node_id"] = node_id
        raft_cfg["peers"] = peers
        self._raft = RaftElection(**raft_cfg)

        # Set leader change callback
        self._raft.set_leader_change_callback(self._on_leader_change)

        logger.info(
            "MAKERConsensusWithRaft initialized",
            extra={"node_id": node_id, "peers": peers},
        )

    @property
    def is_leader(self) -> bool:
        """Check if this node is Raft leader."""
        return self._raft.is_leader

    @property
    def leader_id(self) -> str | None:
        """Get current leader ID."""
        return self._raft.leader_id

    async def start(self) -> None:
        """Start consensus with Raft."""
        await self._raft.start()
        logger.info("MAKERConsensusWithRaft started")

    async def stop(self) -> None:
        """Stop consensus."""
        await self._raft.stop()
        logger.info("MAKERConsensusWithRaft stopped")

    async def run_consensus(
        self,
        consensus_id: str,
        agents: list[str],
        decision_func: callable,
        timeout: float = 30.0,
    ) -> Any:
        """
        Run MAKER consensus (only on leader).

        Args:
            consensus_id: Consensus process identifier
            agents: List of agent IDs
            decision_func: Function to get agent decisions
            timeout: Consensus timeout

        Returns:
            MAKER consensus result
        """
        if not self.is_leader:
            logger.debug("Not leader, skipping consensus")
            return None

        return await self._maker.run_consensus(
            consensus_id=consensus_id,
            agents=agents,
            decision_func=decision_func,
            timeout=timeout,
        )

    async def _on_leader_change(self, _new_leader_id: str) -> None:
        """Handle leader change."""
        logger.info("Leader changed to {new_leader_id}")

        # Could trigger re-election of MAKER consensus here

    def get_status(self) -> dict[str, Any]:
        """Get consensus status."""
        return {
            "node_id": self.node_id,
            "is_leader": self.is_leader,
            "raft_status": self._raft.get_status(),
            "maker_status": self._maker.get_statistics(),
        }
