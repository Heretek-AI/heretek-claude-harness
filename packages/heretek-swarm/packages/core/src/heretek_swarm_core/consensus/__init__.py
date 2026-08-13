"""
Heretek Swarm Consensus Package

This package provides comprehensive consensus mechanisms for multi-agent decision making:
- MAKER (Multi-Agent Knowledge Extraction & Reasoning) consensus
- Enhanced MAKER with reasoning chains and rollback
- Swarm Deliberation Engine with multi-round voting
- Agent Expertise Profiling for confidence weighting
- Decision Audit Trail for complete traceability
- Raft-based leader election
- Immune Response Building for pattern learning (CONS-02)
- Behavioral Baseline with quorum updates (CONS-03)
- HXA Connect deliberation mesh for structured debates
"""

import structlog

from heretek_swarm_core.consensus.audit import (
    ArgumentRecord,
    ConsensusAuditTrail,
    DecisionOutcome,
    DecisionRecord,
    QueryResult,
    VoteRecord,
)
from heretek_swarm_core.consensus.complexity import (
    ComplexityHeuristic,
    ComplexityResult,
)
from heretek_swarm_core.consensus.consensus_coordinator import (
    ConsensusCoordinator,
)
from heretek_swarm_core.consensus.deliberation_mesh import (
    HXADebateCycle,
    HXADebateState,
    NATSDeliberationMesh,
)
from heretek_swarm_core.consensus.domain_selector import (
    DEFAULT_FALLBACK_AGENTS,
    DomainSelector,
)
from heretek_swarm_core.consensus.election_manager import (
    GOVERNANCE_AGENT_IDS,
    ElectionManager,
)
from heretek_swarm_core.consensus.expertise import (
    AgentExpertiseProfile,
    AgentExpertiseProfiler,
    DomainExpertise,
    ExpertiseLevel,
)
from heretek_swarm_core.consensus.immune import (
    ImmunePattern,
    ImmuneQuorum,
    ImmuneResponse,
    ImmuneResponseBuilding,
    NovelPatternPreservation,
    PatternClassification,
    ResponseOutcome,
)
from heretek_swarm_core.consensus.maker import (
    ConsensusResult,
    ConsensusState,
    MAKERConsensus,
    Vote,
)
from heretek_swarm_core.consensus.maker_enhanced import (
    DecisionProvenance,
    EnhancedMAKERConsensus,
    EnhancedVote,
    ReasoningChain,
    ReasoningChainStatus,
    ReasoningStep,
    RollbackResult,
)
from heretek_swarm_core.consensus.raft_election import (
    AppendEntriesRequest,
    AppendEntriesResponse,
    LeaderState,
    LogEntry,
    MAKERConsensusWithRaft,
    RaftElection,
    RaftState,
    RequestVoteRequest,
    RequestVoteResponse,
)
from heretek_swarm_core.consensus.swarm_deliberation import (
    AgentPosition,
    Argument,
    DeliberationResult,
    DeliberationRound,
    DeliberationState,
    Position,
    SwarmDeliberationEngine,
)
from heretek_swarm_core.consensus.tribunal import (
    CaseStatus,
    EvidenceType,
    RulingType,
    Tribunal,
    TribunalCase,
    TribunalEvidence,
    TribunalRuling,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "DEFAULT_FALLBACK_AGENTS",
    "GOVERNANCE_AGENT_IDS",
    "AgentExpertiseProfile",
    "AgentExpertiseProfiler",
    "AgentPosition",
    "AppendEntriesRequest",
    "AppendEntriesResponse",
    "Argument",
    "ArgumentRecord",
    "CaseStatus",
    "ComplexityHeuristic",
    "ComplexityResult",
    "ConsensusAuditTrail",
    "ConsensusCoordinator",
    "ConsensusResult",
    "ConsensusState",
    "DecisionOutcome",
    "DecisionProvenance",
    "DecisionRecord",
    "DeliberationResult",
    "DeliberationRound",
    "DeliberationState",
    "DomainExpertise",
    "DomainSelector",
    "ElectionManager",
    "EnhancedMAKERConsensus",
    "EnhancedVote",
    "EvidenceType",
    "ExpertiseLevel",
    "HXADebateCycle",
    "HXADebateState",
    "ImmunePattern",
    "ImmuneQuorum",
    "ImmuneResponse",
    "ImmuneResponseBuilding",
    "LeaderState",
    "LogEntry",
    "MAKERConsensus",
    "MAKERConsensusWithRaft",
    "NATSDeliberationMesh",
    "NovelPatternPreservation",
    "PatternClassification",
    "Position",
    "QueryResult",
    "RaftElection",
    "RaftState",
    "ReasoningChain",
    "ReasoningChainStatus",
    "ReasoningStep",
    "RequestVoteRequest",
    "RequestVoteResponse",
    "ResponseOutcome",
    "RollbackResult",
    "RulingType",
    "SwarmDeliberationEngine",
    "Tribunal",
    "TribunalCase",
    "TribunalEvidence",
    "TribunalRuling",
    "Vote",
    "VoteRecord",
]
