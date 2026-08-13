"""Agent model routing package."""

from .model_router import (
    AgentModelRouter,
    RouterProviderConfig,
    RoutingDecision,
    TaskComplexity,
    get_router,
)

# Re-export old name for backward compatibility until all callers migrate
ProviderConfig = RouterProviderConfig

__all__ = [
    "AgentModelRouter",
    "ProviderConfig",
    "RouterProviderConfig",
    "RoutingDecision",
    "TaskComplexity",
    "get_router",
]
