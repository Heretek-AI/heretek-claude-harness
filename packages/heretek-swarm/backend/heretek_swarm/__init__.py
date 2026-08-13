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
from heretek_swarm_core.consensus.maker import MAKERConsensus
from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter
from heretek_swarm.orchestration.langgraph_workflow import (
    LangGraphHeavySwarmWorkflow as HeavySwarmWorkflow,
)
from heretek_swarm.plugins.consciousness import ConsciousnessPlugin
from heretek_swarm.plugins.liberation import LiberationPlugin

# Backward-compat re-export (remove after migration complete)
from heretek_swarm_core.memory import *  # noqa: F401,F403
from heretek_swarm_core.llm import *  # noqa: F401,F403
from heretek_swarm_core.embeddings import *  # noqa: F401,F403
from heretek_swarm_core.models import *  # noqa: F401,F403
from heretek_swarm_core.schemas import *  # noqa: F401,F403
from heretek_swarm_core.swarm_logging import *  # noqa: F401,F403
from heretek_swarm_core.utils import *  # noqa: F401,F403
from heretek_swarm_core.validation import *  # noqa: F401,F403
from heretek_swarm_api.realtime import *  # noqa: F401,F403

__all__ = [
    "ActorSupervisor",
    "AgentActor",
    "CogneeMemoryReader",
    "CogneeMemoryWriter",
    "ConsciousnessPlugin",
    "HeavySwarmWorkflow",
    "LiberationPlugin",
    "MAKERConsensus",
]
