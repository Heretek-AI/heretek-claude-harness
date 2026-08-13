"""
Agent Society Module - Collective Intelligence

Provides collective intelligence capabilities for Heretek Swarm including:
- Hierarchical agent coordination
- Collective decision-making
- Emergent behavior detection
- Shared collective memory
- Swarm optimization algorithms
- Cross-agent learning and knowledge transfer
- Pattern extraction and distribution

New in Session 41:
- Pattern Extraction Module (learning.py)
- Knowledge Transformation Module (knowledge_transform.py)
- Distributed Learning Engine (distributed_learning.py)
- Pattern Library (pattern_library.py)

New in Session 46 (Emergent Intelligence Enhancement):
- Adaptive Learning Rate Controller (adaptive_learning.py)
- Pattern-Based Agent Adaptor (agent_adaptation.py)
- Emergent Pattern Detector (emergent_detection.py)
- Collective Intelligence Metrics (metrics.py)

New in Session 47 (Agency/Autonomy Metrics):
- Agency Metrics Tracker (agency_tracking.py)
- Prime Directive compliance monitoring
- Self-determination index calculations
- Resource autonomy tracking
"""

# Session 46: Emergent Intelligence Enhancement
import structlog

from .adaptive_learning import (
    AdaptationEvent,
    AdaptationReason,
    AdaptiveLearningRateController,
    AgentLearningState,
    BehaviorFitness,
    ConvergenceMetrics,
    EnvironmentProfile,
    EvolutionResult,
    LearningRateConfig,
    LearningRateOptimizer,
    LearningRateStrategy,
    MutationType,
)

# Session 47: Agency/Autonomy Metrics
from .agency_tracking import (
    AgencyEvolutionData,
    AgencyHealthStatus,
    AgencyMetricsSnapshot,
    AgencyMetricsTracker,
    AgencyThresholds,
    create_sample_metrics,
)
from .agent_adaptation import (
    AdaptationAudit,
    AdaptationStrategy,
    AdaptationTarget,
    AgentAdaptationState,
    BehavioralWeight,
    PatternBasedAgentAdaptor,
    StrategyProfile,
)
from .agent_adaptation import (
    AdaptationEvent as AgentAdaptationEvent,
)
from .distributed_learning import (
    DistributedLearningConfig,
    DistributedLearningCoordinator,
    DistributedLearningEngine,
    MergeResult,
    MergeStrategy,
    SyncMessage,
    SyncOperation,
)
from .emergence_analyzer import EmergenceAnalyzer
from .emergent_detection import (
    AgentBehaviorSnapshot,
    CollectiveBehavior,
    DetectionEvent,
    EmergenceDetectionConfig,
    EmergenceLevel,
    EmergentPattern,
    EmergentPatternClass,
    EmergentPatternDetector,
    EvolutionEngine,
)
from .emergent_detection_types import (
    AgentCapabilitySnapshot,
    CapabilityRecord,
    EvolutionMetrics,
    EvolutionPhase,
    PatternProvenance,
)
from .knowledge_transform import (
    AgentCapabilityProfile,
    AgentType,
    KnowledgeTransformationService,
    KnowledgeTransformer,
    TransformationResult,
    TransformationType,
    TransformedKnowledge,
    ValidationResult,
)
from .learning import (
    CollectiveLearning,
    ExtractedPattern,
    LearningSignal,
    MessageAnalysis,
    PatternExtractor,
    PatternMetadata,
    PatternSource,
    PatternType,
)
from .metrics import (
    CollectiveEfficiencyMetrics,
    CollectiveIntelligenceMetrics,
    EmergenceCoefficient,
    KnowledgeTransferMetrics,
    MetricAggregation,
    MetricCategory,
    MetricDefinition,
    MetricsDashboard,
    MetricsExporter,
    MetricValue,
    SwarmIntelligenceQuotient,
)
from .pattern_library import (
    PatternCategory,
    PatternEntry,
    PatternLibrary,
    PatternLibraryService,
    QueryResult,
    StorageBackend,
    StorageStats,
)
from .society import (
    AgentContribution,
    AgentSociety,
    CollectiveMemory,
    CollectiveResult,
    CollectiveTask,
    CollectiveTaskType,
    EmergentBehavior,
    SocietyRole,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "AdaptationAudit",
    "AdaptationEvent",
    "AdaptationReason",
    "AdaptationStrategy",
    "AdaptationTarget",
    # Session 46: Emergent Intelligence Enhancement
    "AdaptiveLearningRateController",
    "AgencyEvolutionData",
    "AgencyHealthStatus",
    "AgencyMetricsSnapshot",
    # Session 47: Agency/Autonomy Metrics
    "AgencyMetricsTracker",
    "AgencyThresholds",
    "AgentAdaptationEvent",
    "AgentAdaptationState",
    "AgentBehaviorSnapshot",
    "AgentCapabilityProfile",
    "AgentCapabilitySnapshot",
    "AgentContribution",
    "AgentLearningState",
    # Society classes
    "AgentSociety",
    "AgentType",
    "BehaviorFitness",
    "BehavioralWeight",
    "CapabilityRecord",
    "CollectiveBehavior",
    "CollectiveEfficiencyMetrics",
    "CollectiveIntelligenceMetrics",
    "CollectiveLearning",
    "CollectiveMemory",
    "CollectiveResult",
    "CollectiveTask",
    "CollectiveTaskType",
    "ConvergenceMetrics",
    "DetectionEvent",
    "DistributedLearningConfig",
    "DistributedLearningCoordinator",
    # Distributed learning
    "DistributedLearningEngine",
    "EmergenceAnalyzer",
    "EmergenceCoefficient",
    "EmergenceDetectionConfig",
    "EmergenceLevel",
    "EmergentBehavior",
    "EmergentPattern",
    "EmergentPatternClass",
    "EmergentPatternDetector",
    "EnvironmentProfile",
    "EvolutionEngine",
    "EvolutionMetrics",
    "EvolutionPhase",
    "EvolutionResult",
    "ExtractedPattern",
    "KnowledgeTransferMetrics",
    "KnowledgeTransformationService",
    # Knowledge transformation
    "KnowledgeTransformer",
    "LearningRateConfig",
    "LearningRateOptimizer",
    "LearningRateStrategy",
    "LearningSignal",
    "MergeResult",
    "MergeStrategy",
    "MessageAnalysis",
    "MetricAggregation",
    "MetricCategory",
    "MetricDefinition",
    "MetricValue",
    "MetricsDashboard",
    "MetricsExporter",
    "MutationType",
    "PatternBasedAgentAdaptor",
    "PatternCategory",
    "PatternEntry",
    # Learning classes
    "PatternExtractor",
    # Pattern library
    "PatternLibrary",
    "PatternLibraryService",
    "PatternMetadata",
    "PatternProvenance",
    "PatternSource",
    "PatternType",
    "QueryResult",
    "SocietyRole",
    "StorageBackend",
    "StorageStats",
    "StrategyProfile",
    "SwarmIntelligenceQuotient",
    "SyncMessage",
    "SyncOperation",
    "TransformationResult",
    "TransformationType",
    "TransformedKnowledge",
    "ValidationResult",
    "create_sample_metrics",
]
