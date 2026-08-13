"""
Compute Tier Client

Provides a typed HTTP client that the Sentinel's AnomalyMonitor uses
to query the compute tier service before responding to anomalies.

Exports
-------
- ``ComputeTierResult`` — dataclass holding tier + host details
- ``ComputeTierClient`` — async client with timeout, fallback, and structured logging
"""

from heretek_swarm.compute_tier.client import ComputeTierClient, ComputeTierResult

__all__ = ["ComputeTierClient", "ComputeTierResult"]
