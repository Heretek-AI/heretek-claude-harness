"""
Heretek Swarm Tools Package

Re-exports tools from backend/heretek_swarm/tools for heretek_swarm namespace compatibility.
This module provides backward compatibility for imports referencing heretek_swarm.tools.
"""

from heretek_swarm.tools.base import (
    BaseTool,
    SimpleTool,
    ToolContext,
    ToolExecutionError,
    ToolExecutionResult,
    ToolMetadata,
    ToolStatus,
)
from heretek_swarm.tools.examples import (
    ConsensusVoteTool,
    HealthCheckTool,
    MemorySearchTool,
)
from heretek_swarm.tools.registry import (
    ToolRegistry,
    ToolRegistryConfig,
    ToolRegistryEntry,
    get_registry,
    initialize_registry,
)

__all__ = [
    # Base classes
    "BaseTool",
    "ConsensusVoteTool",
    "HealthCheckTool",
    # Example tools
    "MemorySearchTool",
    "SimpleTool",
    "ToolContext",
    "ToolExecutionError",
    "ToolExecutionResult",
    "ToolMetadata",
    # Registry
    "ToolRegistry",
    "ToolRegistryConfig",
    "ToolRegistryEntry",
    "ToolStatus",
    "get_registry",
    "initialize_registry",
]

__version__ = "0.2.0"
