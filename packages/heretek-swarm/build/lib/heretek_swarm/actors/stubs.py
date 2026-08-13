"""
Stub implementations for injectable actor dependencies.

Provides lightweight, test-friendly stand-ins for the 6 injectable
dependencies used by AgentActor and its mixins::

    agent = AlphaAgent(
        access_analyzer=StubAccessAnalyzer(),
        pattern_extractor=StubPatternExtractor(),
        tribunal=StubTribunal(),
        deliberation_engine=StubDeliberationEngine(),
        llm_provider=StubLLMProvider(canned_response="mock_result"),
        event_mesh=StubEventMesh(),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Stub data containers (kept here to avoid importing real types at runtime)
# ---------------------------------------------------------------------------


@dataclass
class _StubAccessProfile:
    """Minimal stand-in for MemoryAccessProfile."""

    memory_id: str = ""
    access_count: int = 0
    access_timestamps: list[str] = field(default_factory=list)
    first_access: str | None = None
    last_access: str | None = None
    access_types: dict[str, int] = field(default_factory=dict)
    agents_accessed: set[str] = field(default_factory=set)
    sessions_accessed: set[str] = field(default_factory=set)
    frequency_score: float = 0.0
    recency_score: float = 0.0
    tier: str = "cold"


@dataclass
class _StubAccessStatistics:
    """Minimal stand-in for AccessStatistics."""

    total_accesses: int = 0
    unique_memories: int = 0
    hot_count: int = 0
    warm_count: int = 0
    cold_count: int = 0
    frozen_count: int = 0
    avg_frequency: float = 0.0
    avg_recency: float = 0.0
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    predicted_hits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_accesses": self.total_accesses,
            "unique_memories": self.unique_memories,
            "tier_distribution": {
                "hot": self.hot_count,
                "warm": self.warm_count,
                "cold": self.cold_count,
                "frozen": self.frozen_count,
            },
            "frequency": {
                "avg_frequency": self.avg_frequency,
                "avg_recency": self.avg_recency,
            },
            "cache_performance": {
                "hit_rate": self.hit_rate,
                "miss_rate": self.miss_rate,
            },
            "predictions": {"predicted_hits": self.predicted_hits},
        }


@dataclass
class _StubMessageAnalysis:
    """Minimal stand-in for MessageAnalysis."""

    message_id: str = ""
    sender: str = ""
    recipient: str = ""
    message_type: str = ""
    sentiment_score: float = 0.0
    complexity_score: float = 0.0
    topic: str = ""
    intent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubExtractedPattern:
    """Minimal stand-in for ExtractedPattern."""

    pattern_id: str = ""
    pattern_type: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    support: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubTribunalCase:
    """Minimal stand-in for TribunalCase."""

    case_id: str = ""
    original_decision_id: str = ""
    original_consensus_id: str = ""
    appellant_agent_id: str = ""
    grounds: str = ""
    description: str = ""
    status: str = "open"
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    closed_at: str | None = None


@dataclass
class _StubTribunalEvidence:
    """Minimal stand-in for TribunalEvidence."""

    evidence_id: str = ""
    case_id: str = ""
    agent_id: str = ""
    content: str = ""
    evidence_type: str = "document"
    source: str | None = None
    reliability_score: float = 0.5


@dataclass
class _StubTribunalRuling:
    """Minimal stand-in for TribunalRuling."""

    ruling_id: str = ""
    case_id: str = ""
    ruling_type: str = ""
    reasoning: str = ""
    issued_by: str = ""
    confidence: float = 1.0
    timestamp: str = ""
    precedent_id: str | None = None


@dataclass
class _StubDeliberationRound:
    """Minimal stand-in for DeliberationRound."""

    round_number: int = 0
    positions: dict[str, Any] = field(default_factory=dict)
    arguments: list[dict[str, Any]] = field(default_factory=list)
    consensus_score: float = 0.0


# ---------------------------------------------------------------------------
# Stub classes — each implements a subset of the real interface so mixins
# that type-check against ``X | None`` can operate on the stub instead.
# ---------------------------------------------------------------------------


class StubAccessAnalyzer:
    """
    Minimal stand-in for AccessPatternAnalyzer.

    Records accesses in-memory and returns placeholder profiles and
    statistics.  Does not require real infrastructure.

    Implements the methods called by MemoryMixin and LearningMixin:
    - ``record_access``
    - ``get_profile``
    - ``predict_agent_access``
    - ``get_statistics``  (returns an object with ``.to_dict()``)
    """

    def __init__(self) -> None:
        self._profiles: dict[str, _StubAccessProfile] = {}
        self._total_accesses = 0

    def record_access(
        self,
        memory_id: str,
        access_type: str = "read",
        agent_id: str | None = None,
        session_id: str | None = None,
        access_latency_ms: float = 0.0,  # noqa: ARG002
        success: bool = True,  # noqa: ARG002
    ) -> _StubAccessProfile:
        """Record a memory access event.  Returns a stub profile."""
        now = datetime.now(UTC).isoformat()
        if memory_id not in self._profiles:
            self._profiles[memory_id] = _StubAccessProfile(memory_id=memory_id)

        profile = self._profiles[memory_id]
        profile.access_count += 1
        profile.access_timestamps.append(now)
        if profile.first_access is None:
            profile.first_access = now
        profile.last_access = now
        profile.access_types[access_type] = profile.access_types.get(access_type, 0) + 1
        if agent_id:
            profile.agents_accessed.add(agent_id)
        if session_id:
            profile.sessions_accessed.add(session_id)
        self._total_accesses += 1
        return profile

    def get_profile(self, memory_id: str) -> _StubAccessProfile | None:
        """Get the access profile for a memory, or None."""
        return self._profiles.get(memory_id)

    def predict_agent_access(self, _agent_id: str) -> list[str]:
        """Predict future accesses for an agent.  Returns empty list."""
        return []

    def get_statistics(self) -> _StubAccessStatistics:
        """Return stub access statistics."""
        return _StubAccessStatistics(
            total_accesses=self._total_accesses,
            unique_memories=len(self._profiles),
        )


class StubPatternExtractor:
    """
    Minimal stand-in for PatternExtractor.

    Accepts and stores message analyses, returns empty pattern lists.
    Exposes ``_message_cache`` and ``_validated_patterns`` dicts expected
    by LearningMixin and PatternMixin.
    """

    def __init__(self) -> None:
        self._message_cache: list[_StubMessageAnalysis] = []
        self._pattern_candidates: dict[str, _StubExtractedPattern] = {}
        self._validated_patterns: dict[str, _StubExtractedPattern] = {}
        self._extraction_hooks: list[Any] = []

    async def analyze_message(
        self,
        message_id: str,
        sender: str,
        recipient: str,
        message_type: str,
        content: dict[str, Any],
        timestamp: str | None = None,
    ) -> _StubMessageAnalysis:
        """Analyze a message and cache the analysis."""
        timestamp or datetime.now(UTC).isoformat()
        analysis = _StubMessageAnalysis(
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            metadata={"content_length": len(str(content))},
        )
        self._message_cache.append(analysis)
        return analysis

    async def extract_patterns(
        self,
        time_window_hours: int = 24,  # noqa: ARG002
        pattern_types: list[Any] | None = None,  # noqa: ARG002
    ) -> list[_StubExtractedPattern]:
        """Return validated patterns that meet confidence threshold."""
        return [p for p in self._validated_patterns.values() if p.confidence >= 0.7]

    def register_extraction_hook(self, hook: Any) -> None:
        """Register a post-extraction hook (no-op in stub)."""
        self._extraction_hooks.append(hook)


class StubTribunal:
    """
    Minimal stand-in for Tribunal.

    Accepts cases and evidence in-memory, returns stub rulings.
    Implements the methods called by TribunalMixin:
    - ``create_case``
    - ``submit_evidence``
    - ``get_case``
    - ``issue_ruling``
    - ``get_precedents``
    - ``find_similar_precedents``
    """

    def __init__(self) -> None:
        self._cases: dict[str, _StubTribunalCase] = {}
        self._evidence: dict[str, _StubTribunalEvidence] = {}
        self._rulings: dict[str, _StubTribunalRuling] = {}
        self._precedents: list[str] = []

    def create_case(
        self,
        original_decision_id: str,
        appellant_agent_id: str,
        grounds: str,
        description: str,
        original_consensus_id: str | None = None,
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> _StubTribunalCase:
        """Create and return a stub tribunal case."""
        now = datetime.now(UTC).isoformat()
        case_id = f"stub_case_{len(self._cases) + 1}"
        case = _StubTribunalCase(
            case_id=case_id,
            original_decision_id=original_decision_id,
            original_consensus_id=original_consensus_id or "",
            appellant_agent_id=appellant_agent_id,
            grounds=grounds,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._cases[case_id] = case
        return case

    def submit_evidence(
        self,
        agent_id: str,
        case_id: str,
        content: str,
        evidence_type: Any = None,
        source: str | None = None,
        reliability_score: float = 0.5,
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> _StubTribunalEvidence:
        """Submit and return a stub evidence record."""
        evidence_id = f"stub_ev_{len(self._evidence) + 1}"
        evidence = _StubTribunalEvidence(
            evidence_id=evidence_id,
            case_id=case_id,
            agent_id=agent_id,
            content=content,
            evidence_type=str(getattr(evidence_type, "value", evidence_type) or "document"),
            source=source,
            reliability_score=reliability_score,
        )
        self._evidence[evidence_id] = evidence
        if case_id in self._cases:
            self._cases[case_id].evidence_ids.append(evidence_id)
        return evidence

    def get_case(self, case_id: str) -> _StubTribunalCase | None:
        """Get a case by ID, or None."""
        return self._cases.get(case_id)

    def issue_ruling(
        self,
        case_id: str,
        ruling_type: Any,
        reasoning: str,
        issued_by: str = "tribunal",
        confidence: float = 1.0,
        precedent_id: str | None = None,
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> _StubTribunalRuling:
        """Issue and return a stub ruling."""
        now = datetime.now(UTC).isoformat()
        ruling = _StubTribunalRuling(
            ruling_id=f"stub_ruling_{len(self._rulings) + 1}",
            case_id=case_id,
            ruling_type=str(getattr(ruling_type, "value", ruling_type)),
            reasoning=reasoning,
            issued_by=issued_by,
            confidence=confidence,
            timestamp=now,
            precedent_id=precedent_id,
        )
        self._rulings[ruling.ruling_id] = ruling
        return ruling

    def get_precedents(
        self,
        limit: int = 10,
        ruling_type: Any = None,
    ) -> list[_StubTribunalRuling]:
        """Return stub precedent rulings."""
        result = []
        for rid in self._precedents:
            r = self._rulings.get(rid)
            if r:
                target = str(getattr(ruling_type, "value", ruling_type))
                if ruling_type is None or r.ruling_type == target:
                    result.append(r)
        return result[:limit]

    def find_similar_precedents(
        self,
        grounds: str,  # noqa: ARG002
        limit: int = 5,  # noqa: ARG002
    ) -> list[_StubTribunalRuling]:
        """Return stub similar precedents (empty)."""
        return []


class StubDeliberationEngine:
    """
    Minimal stand-in for SwarmDeliberationEngine.

    Stores deliberation state in-memory and returns placeholder round
    results and statistics.  Implements the subset needed by
    LearningMixin (``get_statistics``) and DeliberationMixin.
    """

    def __init__(self) -> None:
        self.active_deliberations: dict[str, dict[str, Any]] = {}
        self.deliberation_states: dict[str, str] = {}
        self.current_rounds: dict[str, int] = {}
        self.round_results: dict[str, list[_StubDeliberationRound]] = {}

    def start_deliberation(
        self,
        deliberation_id: str,
        proposal: str,
        participants: list[str],
        domain: str | None = None,
    ) -> None:
        """Start a stub deliberation."""
        self.active_deliberations[deliberation_id] = {
            "proposal": proposal,
            "participants": participants,
            "domain": domain,
            "started_at": datetime.now(UTC).isoformat(),
        }
        self.deliberation_states[deliberation_id] = "active"
        self.current_rounds[deliberation_id] = 0
        self.round_results[deliberation_id] = []

    def submit_position(
        self,
        deliberation_id: str,
        agent_id: str,
        position: str,
        confidence: float = 0.5,
    ) -> None:
        """Submit a stub position."""
        if deliberation_id not in self.active_deliberations:
            return
        positions = self.active_deliberations[deliberation_id].setdefault("positions", {})
        positions[agent_id] = {"position": position, "confidence": confidence}

    def submit_argument(
        self,
        deliberation_id: str,
        agent_id: str,
        argument: str,
    ) -> None:
        """Submit a stub argument."""
        if deliberation_id not in self.active_deliberations:
            return
        args = self.active_deliberations[deliberation_id].setdefault("arguments", [])
        args.append({"agent_id": agent_id, "argument": argument})

    def run_deliberation_round(self, deliberation_id: str) -> _StubDeliberationRound | None:
        """Run a stub deliberation round."""
        if deliberation_id not in self.active_deliberations:
            return None
        round_num = self.current_rounds.get(deliberation_id, 0) + 1
        self.current_rounds[deliberation_id] = round_num
        round_result = _StubDeliberationRound(
            round_number=round_num,
            positions=self.active_deliberations[deliberation_id].get("positions", {}),
            arguments=self.active_deliberations[deliberation_id].get("arguments", []),
        )
        self.round_results.setdefault(deliberation_id, []).append(round_result)
        return round_result

    def get_statistics(self) -> dict[str, Any]:
        """Return stub deliberation statistics."""
        return {
            "active_deliberations": len(self.active_deliberations),
            "total_rounds": sum(self.current_rounds.values()),
        }


class StubLLMProvider:
    """
    Canned-response LLM provider for testing.

    Returns a pre-configured response string for every call, allowing
    tests to verify agent behavior without a real LLM.
    """

    def __init__(self, canned_response: str = "stub_llm_response") -> None:
        self._canned_response = canned_response
        self.call_count = 0

    async def generate(
        self,
        prompt: str,  # noqa: ARG002
        *,
        timeout: float = 60.0,  # noqa: ARG002,ASYNC109
        **kwargs: Any,  # noqa: ARG002
    ) -> str:
        """Return the canned response string."""
        self.call_count += 1
        return self._canned_response

    async def generate_stream(
        self,
        prompt: str,  # noqa: ARG002
        *,
        timeout: float = 60.0,  # noqa: ARG002,ASYNC109
        **kwargs: Any,  # noqa: ARG002
    ) -> Any:
        """Yield the canned response as a single chunk."""
        self.call_count += 1
        yield self._canned_response

    def __call__(self, _prompt: str, **_kwargs: Any) -> str:
        """Synchronous convenience call."""
        self.call_count += 1
        return self._canned_response


class StubEventMesh:
    """
    Minimal in-memory stand-in for NATSEventMesh.

    Stores subscriptions and published messages for test inspection.
    All operations succeed without real NATS infrastructure.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[dict[str, Any]]] = {}
        self._published: list[dict[str, Any]] = []
        self._connected = True

    async def connect(self, **_kwargs: Any) -> None:
        """No-op connect."""
        self._connected = True

    async def disconnect(self) -> None:
        """No-op disconnect."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Return whether the stub is connected."""
        return self._connected

    async def publish(
        self,
        subject: str,
        data: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Store a published message for test inspection."""
        self._published.append(
            {
                "subject": subject,
                "data": data,
                "kwargs": kwargs,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    async def subscribe(
        self,
        subject: str,
        handler: Any,
        **kwargs: Any,
    ) -> str:
        """Register a stub subscription. Returns subscription ID."""
        sub_id = f"stub_sub_{len(self._subscriptions) + 1}"
        self._subscriptions.setdefault(subject, []).append(
            {
                "id": sub_id,
                "handler": handler,
                "kwargs": kwargs,
            }
        )
        return sub_id

    async def request(
        self,
        subject: str,  # noqa: ARG002
        data: dict[str, Any],
        *,
        timeout: float = 5.0,  # noqa: ARG002,ASYNC109
        **kwargs: Any,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Return a stub response for request-reply patterns."""
        return {"status": "ok", "data": data}

    def get_subscription_ids(self) -> set[str]:
        """Return all registered subscription IDs."""
        return {sub["id"] for subs in self._subscriptions.values() for sub in subs}

    @property
    def mesh_type(self) -> str:
        """Return the mesh type identifier for observability."""
        return "StubEventMesh"

    def client_count(self) -> int:
        """Return stub client count."""
        return 1 if self._connected else 0

    async def send_to_json(
        self,
        subject: str,
        data: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Store a JSON-serialized message for test inspection."""
        self._published.append(
            {
                "subject": subject,
                "data": data,
                "kwargs": kwargs,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    async def broadcast_json(
        self,
        data: dict[str, Any],
    ) -> None:
        """Store a broadcast message for test inspection."""
        self._published.append(
            {
                "subject": "__broadcast__",
                "data": data,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )


# ---------------------------------------------------------------------------
# Legacy stub functions — preserved for backward compatibility.
# core.py imports ``get_nats_event_mesh`` and ``get_llm_provider`` from this
# module and calls them during ``AgentActor.__init__``.
# ---------------------------------------------------------------------------

_nats_mesh: StubEventMesh | None = None


def get_nats_event_mesh() -> StubEventMesh | None:
    """
    Get the NATS event mesh instance (stub-aware).

    Tries the real NATSEventMesh first; falls back to a lightweight
    StubEventMesh so tests don't need real NATS infrastructure.
    """
    global _nats_mesh
    if _nats_mesh is None:
        try:
            from heretek_swarm.gateway.nats_event_mesh import get_nats_bridge

            bridge = get_nats_bridge()
            if bridge is not None:
                _nats_mesh = bridge.mesh
        except Exception:
            _nats_mesh = StubEventMesh()
    return _nats_mesh


def get_llm_provider() -> StubLLMProvider | None:
    """
    Get a stub LLM provider instance.

    Returns a StubLLMProvider with a default canned response for testing.
    """
    return StubLLMProvider()


def get_db_pool() -> None:
    """
    Get the database connection pool (stub).

    Returns None — the actual implementation is in runtime initialization.
    Tests should patch this to provide a mock DB.
    """
    return
