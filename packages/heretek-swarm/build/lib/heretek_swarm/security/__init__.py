"""
Security Module for Heretek Swarm

Provides comprehensive security features:
- Zero-trust 4-layer validation (SH-1)
- Adversarial detection for prompt injection (SH-2)
- Rate limiting and DDoS protection (SH-3)
- Guardrails system for input/output filtering
- Behavioral anomaly detection for agent monitoring (SAFE-01)
- Behavioral baseline with quorum-based updates (CONS-02, CONS-03)

Reference: EXPANSION_ROADMAP.md Security Hardening (SH-1, SH-2, SH-3)
Reference: Phase 2 Plan Task 4 (SAFE-01)
Reference: Phase 2 Plan Task 2 (CONS-02), Task 3 (CONS-03)
"""

from heretek_swarm.security.adversarial import (
    AdversarialDetectionResult,
    # Core detector
    AdversarialDetector,
    AttackCategory,
    DetectionMatch,
    JailbreakDetectionConfig,
    OWASPCategory,
    # Reporter
    OWASPComplianceReporter,
    # Configuration
    PromptInjectionConfig,
    # Enums
    ThreatLevel,
    # Convenience functions
    create_default_detector,
    create_strict_detector,
)
from heretek_swarm.security.anomaly_detection import (
    AgentBehaviorProfile,
    AnomalyDetectionConfig,
    AnomalyDetectionResult,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyType,
    BehavioralAnomalyDetector,
    ResponseStatus,
    create_anomaly_detector,
)
from heretek_swarm.security.behavioral_baseline import (
    BaselineChangeRequest,
    BaselineChangeType,
    BaselineMetrics,
    BaselinePattern,
    BaselineStatus,
    BehavioralBaseline,
    QuorumStatus,
    create_behavioral_baseline,
)
from heretek_swarm.security.ddos_protection import (
    DDoSDetectionConfig,
    DDoSDetectionResult,
    DDoSDetector,
    DDoSMitigator,
    # Core protection
    DDoSProtection,
    DDoSSeverity,
    MitigationAction,
    MitigationConfig,
    # Configuration
    RateLimitConfig,
    RateLimiter,
    # Results
    RateLimitResult,
    TierConfig,
    # Token bucket
    TokenBucket,
    # Enums
    UserTier,
    # Convenience functions
    create_default_protection,
    create_strict_protection,
)
from heretek_swarm.security.guardrails import (
    BlockedPattern,
    FilterResult,
    GuardrailsAction,
    GuardrailsConfig,
    GuardrailsSystem,
    ValidationResult,
)
from heretek_swarm.security.zero_trust import (
    AuditLogConfig,
    # Layer 4: Audit Logging
    AuditLogger,
    BehavioralBaseline,  # noqa: F811
    ContextValidationConfig,
    # Layer 2: Context Validation
    ContextValidator,
    # External threat detection
    ExternalInputValidator,
    ExternalThreatConfig,
    InputValidationConfig,
    # Layer 1: Input Validation
    InputValidator,
    LayerResult,
    OutputValidationConfig,
    # Layer 3: Output Validation
    OutputValidator,
    # Severity levels
    Severity,
    ValidatedInput,
    ZeroTrustResult,
    # Core validator
    ZeroTrustValidator,
    # Convenience functions
    create_default_validator,
    create_external_validator,
    create_strict_validator,
)

__all__ = [
    "AdversarialDetectionResult",
    # Adversarial Detection (SH-2)
    "AdversarialDetector",
    "AgentBehaviorProfile",
    "AnomalyDetectionConfig",
    "AnomalyDetectionResult",
    "AnomalyResponse",
    "AnomalySeverity",
    "AnomalyType",
    "AttackCategory",
    "AuditLogConfig",
    "AuditLogger",
    "BaselineChangeRequest",
    "BaselineChangeType",
    "BaselineMetrics",
    "BaselinePattern",
    "BaselineStatus",
    "BehavioralAnomalyDetector",
    "BehavioralBaseline",
    "BlockedPattern",
    "ContextValidationConfig",
    "ContextValidator",
    "DDoSDetectionConfig",
    "DDoSDetectionResult",
    "DDoSDetector",
    "DDoSMitigator",
    # DDoS Protection (SH-3)
    "DDoSProtection",
    "DDoSSeverity",
    "DetectionMatch",
    "ExternalInputValidator",
    "ExternalThreatConfig",
    "FilterResult",
    "GuardrailsAction",
    "GuardrailsConfig",
    # Guardrails
    "GuardrailsSystem",
    "InputValidationConfig",
    "InputValidator",
    "JailbreakDetectionConfig",
    "LayerResult",
    "MitigationAction",
    "MitigationConfig",
    "OWASPCategory",
    "OWASPComplianceReporter",
    "OutputValidationConfig",
    "OutputValidator",
    "PromptInjectionConfig",
    "QuorumStatus",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimiter",
    "ResponseStatus",
    "Severity",
    "ThreatLevel",
    "TierConfig",
    "TokenBucket",
    "UserTier",
    "ValidatedInput",
    "ValidationResult",
    "ZeroTrustResult",

    "ZeroTrustValidator",
    "create_anomaly_detector",
    "create_behavioral_baseline",
    "create_default_detector",
    "create_default_protection",
    "create_default_validator",
    "create_external_validator",
    "create_strict_detector",
    "create_strict_protection",
    "create_strict_validator",
]
import structlog

from heretek_swarm.security.threat_detection import ThreatLevel  # noqa: F811

logger = structlog.get_logger(__name__)
