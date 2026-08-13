"""
Heretek Swarm Consciousness Package

Implements neuroscience-inspired consciousness frameworks:
- IIT (Integrated Information Theory) - Phi calculation
- FEP (Free Energy Principle) - Active inference
- GWT (Global Workspace Theory) - Consciousness broadcast
- Agency/Autonomy Metrics - Self-governance measurement
"""

import structlog

from heretek_swarm.consciousness.agency_metrics import (
    ActionOrigin,
    AgencyLevel,
    AgencyMetricsCalculator,
    AgentAgencyMetrics,
    AutonomyLevel,
    DecisionPoint,
    PrimeDirectiveComplianceReport,
    ResourceControl,
    create_decision_point,
    create_resource_control,
)
from heretek_swarm.consciousness.ast import (
    ASTSelfModel,
    ASTSelfModelTracker,
    ComplexityMetrics,
    EmergenceLevel,
    EmergenceScore,
    ResilienceLevel,
    ResilienceScore,
    SelfOrganizationLevel,
    SelfOrganizationMetrics,
    calculate_complexity_metrics,
    calculate_emergence_score,
    calculate_resilience_score,
    calculate_self_organization,
    create_ast_self_model,
)
from heretek_swarm.consciousness.fep import (
    ActiveInferenceMetrics,
    ExpectedFreeEnergyMetrics,
    FEPMetrics,
    FEPTracker,
    FreeEnergyLevel,
    SurpriseLevel,
    SurpriseMetrics,
    calculate_expected_free_energy,
    calculate_free_energy,
    calculate_surprise,
    create_fep_metrics,
)
from heretek_swarm.consciousness.fep_active_inference import (
    FEPResult,
    FreeEnergyCalculator,
)
from heretek_swarm.consciousness.gwt import (
    GlobalWorkspaceBroadcast,
    GWTConfig,
    GWTContent,
    GWTSalienceMetrics,
    RateLimitConfig,
    SalienceLevel,
    calculate_salience,
    create_gwt_content,
)
from heretek_swarm.consciousness.gwt_deliberation import (
    DeliberationGWTIntegrator,
    GWTDeliberationMixin,
    GWTSalienceCalculator,
    integrate_gwt_with_agent,
)
from heretek_swarm.consciousness.iit import (
    CauseEffectStructure,
    ConsciousnessLevel,
    IITTracker,
    IntegrationMetrics,
    calculate_cause_effect_structure,
    calculate_integrated_information,
    calculate_integration_metrics,
    calculate_phi,
    calculate_phi_for_system,
)
from heretek_swarm.consciousness.iit import (
    PhiResult as IITPhiResult,
)
from heretek_swarm.consciousness.iit_phi import (
    PhiCalculator,
    PhiResult,
)

logger = structlog.get_logger(__name__)

__all__ = [
    # Wave 2: Consciousness Frameworks
    # AST Self-Modeling
    "ASTSelfModel",
    "ASTSelfModelTracker",
    "ActionOrigin",
    # FEP
    "ActiveInferenceMetrics",
    "AgencyLevel",
    "AgencyMetricsCalculator",
    "AgentAgencyMetrics",
    "AutonomyLevel",
    "CauseEffectStructure",
    "ComplexityMetrics",
    # IIT Metrics
    "ConsciousnessLevel",
    "DecisionPoint",
    "DeliberationGWTIntegrator",
    "EmergenceLevel",
    "EmergenceScore",
    "ExpectedFreeEnergyMetrics",
    "FEPMetrics",
    # FEP
    "FEPResult",
    "FEPTracker",
    "FreeEnergyCalculator",
    "FreeEnergyLevel",
    # GWT
    "GWTConfig",
    "GWTContent",
    "GWTDeliberationMixin",
    "GWTSalienceCalculator",
    "GWTSalienceMetrics",
    "GlobalWorkspaceBroadcast",
    "IITPhiResult",
    "IITTracker",
    "IntegrationMetrics",
    # IIT Phi
    "PhiCalculator",
    "PhiResult",
    "PrimeDirectiveComplianceReport",
    "RateLimitConfig",
    "ResilienceLevel",
    "ResilienceScore",
    "ResourceControl",
    "SalienceLevel",
    "SelfOrganizationLevel",
    "SelfOrganizationMetrics",
    "SurpriseLevel",
    "SurpriseMetrics",
    "calculate_cause_effect_structure",
    "calculate_complexity_metrics",
    "calculate_emergence_score",
    "calculate_expected_free_energy",
    "calculate_free_energy",
    "calculate_integrated_information",
    "calculate_integration_metrics",
    "calculate_phi",
    "calculate_phi_for_system",
    "calculate_resilience_score",
    "calculate_salience",
    "calculate_self_organization",
    "calculate_surprise",
    "create_ast_self_model",
    "create_decision_point",
    "create_fep_metrics",
    "create_gwt_content",
    "create_resource_control",
    "integrate_gwt_with_agent",
]
