"""Agent Management API - submodule imports."""

from heretek_swarm.api.agents import (
    chat as chat,
)
from heretek_swarm.api.agents import (
    core as core,
)
from heretek_swarm.api.agents import (
    instances as instances,
)
from heretek_swarm.api.agents import (
    jetstream as jetstream,
)
from heretek_swarm.api.agents import (
    lifecycle,
    profiling,
    routing_control,
    routing_rules,
)

__all__ = [
    "chat",
    "core",
    "instances",
    "jetstream",
    "lifecycle",
    "profiling",
    "routing_control",
    "routing_rules",
]
