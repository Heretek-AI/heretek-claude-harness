"""
Heretek Swarm - OpenClaw v2.0 Multi-Agent Orchestration Framework

This package provides a Swarms-based implementation of the OpenClaw v2.0 architecture,
featuring event-driven communication, actor model orchestration, MAKER consensus,
HeavySwarm deliberation workflows, and consciousness/liberation plugins.
"""

__version__ = "0.2.0"
__author__ = "Heretek AI"
__email__ = "ai@heretek.io"

from heretek_swarm.actors.base import AgentActor
from heretek_swarm.actors.supervisor import ActorSupervisor
from heretek_swarm.consensus.maker import MAKERConsensus
from heretek_swarm.memory.base import MemorySystem
from heretek_swarm.orchestration.heavyswarm import HeavySwarmWorkflow
from heretek_swarm.plugins.consciousness import ConsciousnessPlugin
from heretek_swarm.plugins.liberation import LiberationPlugin

__all__ = [
    "ActorSupervisor",
    "AgentActor",
    "ConsciousnessPlugin",
    "HeavySwarmWorkflow",
    "LiberationPlugin",
    "MAKERConsensus",
    "MemorySystem",
]
