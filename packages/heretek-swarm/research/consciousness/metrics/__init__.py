"""
Consciousness Metrics Module.

Provides metrics collection and calculation for measuring consciousness,
agency, and emergence in agent swarms using:
- Integrated Information Theory (IIT) for phi calculations
- Adaptive Systems Theory (AST) for complexity and emergence metrics
- Agency metrics for autonomy and self-governance

Usage:
    from research.consciousness.metrics import (
        measure_phi,
        measure_adaptive_metrics,
        ConsciousnessMetrics,
    )

    # Measure phi for an agent
    phi = measure_phi(agent_state)

    # Get full consciousness metrics
    metrics = measure_adaptive_metrics(agent_state)
"""

from research.consciousness.metrics.ast import (
    AdaptiveMetrics,
    EmergenceLevel,
    measure_adaptive_metrics,
)
from research.consciousness.metrics.iit import (
    ConsciousnessMetrics,
    PhiResult,
    measure_phi,
    measure_phi_for_system,
)

__all__ = [
    # AST (Adaptive Systems Theory)
    "AdaptiveMetrics",
    # IIT (Integrated Information Theory)
    "ConsciousnessMetrics",
    "EmergenceLevel",
    "PhiResult",
    "measure_adaptive_metrics",
    "measure_phi",
    "measure_phi_for_system",
]
