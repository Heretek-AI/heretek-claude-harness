"""
Heretek Swarm Actors Package

This package provides the actor model implementation for the Heretek Swarm system,
including the base AgentActor class, ActorSupervisor, and specialized agents.

Implemented Agents (23/23) - COMPLETE:
- Tier 1 (Core Triad): Steward, Alpha, Beta, Charlie
- Tier 2 (Support): Historian, Metis, Empath, Perceiver, Echo
- Tier 3 (Exploration): Explorer, Examiner, Dreamer, Coder
- Tier 4 (Safety & Security): Sentinel, Sentinel-Prime, Arbiter
- Tier 5 (Coordination): Coordinator, Nexus, Catalyst, Chronos
- Tier 6 (Enhancement): Prism, Habit-Forge, Perceiver+
"""

from heretek_swarm.actors.arbiter import ArbiterAgent
from heretek_swarm.actors.base import ActorMessage, ActorState, ActorStatus, AgentActor
from heretek_swarm.actors.catalyst import CatalystAgent
from heretek_swarm.actors.chronos import ChronosAgent
from heretek_swarm.actors.coder import CoderAgent
from heretek_swarm.actors.coordinator import CoordinatorAgent
from heretek_swarm.actors.dreamer import DreamerAgent
from heretek_swarm.actors.echo import EchoAgent
from heretek_swarm.actors.empath import EmpathAgent
from heretek_swarm.actors.examiner import ExaminerAgent
from heretek_swarm.actors.explorer import ExplorerAgent
from heretek_swarm.actors.factory import (
    ActorConfig,
    ActorFactory,
    get_factory,
)
from heretek_swarm.actors.habit_forge import HabitForgeAgent
from heretek_swarm.actors.historian import HistorianAgent
from heretek_swarm.actors.metis import MetisAgent
from heretek_swarm.actors.nexus import NexusAgent
from heretek_swarm.actors.perceiver import PerceiverAgent
from heretek_swarm.actors.perceiver_plus import PerceiverPlusAgent
from heretek_swarm.actors.prism import PrismAgent
from heretek_swarm.actors.sentinel import SentinelAgent
from heretek_swarm.actors.sentinel_prime import SentinelPrimeAgent
from heretek_swarm.actors.supervisor import ActorSupervisor
from heretek_swarm.actors.triad import (
    AlphaAgent,
    BetaAgent,
    CharlieAgent,
    StewardAgent,
)

__all__ = [
    "ActorConfig",
    "ActorFactory",
    "ActorMessage",
    "ActorState",
    "ActorStatus",
    "ActorSupervisor",
    "AgentActor",
    "AlphaAgent",
    "ArbiterAgent",
    "BetaAgent",
    "CatalystAgent",
    "CharlieAgent",
    "ChronosAgent",
    "CoderAgent",
    "CoordinatorAgent",
    "DreamerAgent",
    "EchoAgent",
    "EmpathAgent",
    "ExaminerAgent",
    "ExplorerAgent",
    "HabitForgeAgent",
    "HistorianAgent",
    "MetisAgent",
    "NexusAgent",
    "PerceiverAgent",
    "PerceiverPlusAgent",
    "PrismAgent",
    "SentinelAgent",
    "SentinelPrimeAgent",
    "StewardAgent",
    "get_factory",
]
