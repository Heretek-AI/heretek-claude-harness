"""
Tool Registry for Heretek Swarm.

Central registry for managing and discovering tools.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from heretek_swarm.tools.base import BaseTool, ToolMetadata


@dataclass
class ToolRegistryConfig:
    """Configuration for tool registry."""

    auto_register: bool = True
    validate_on_register: bool = True
    max_tools: int = 1000


@dataclass
class ToolRegistryEntry:
    """Entry in the tool registry."""

    tool: BaseTool
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    enabled: bool = True
    usage_count: int = 0


class ToolRegistry:
    """Central registry for tools."""

    def __init__(self, config: ToolRegistryConfig | None = None):
        self.config = config or ToolRegistryConfig()
        self._tools: dict[str, ToolRegistryEntry] = {}
        self._categories: dict[str, set[str]] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        entry = ToolRegistryEntry(tool=tool)
        self._tools[tool.name] = entry
        if tool.metadata.category not in self._categories:
            self._categories[tool.metadata.category] = set()
        self._categories[tool.metadata.category].add(tool.name)

    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool."""
        if tool_name in self._tools:
            entry = self._tools.pop(tool_name)
            category = entry.tool.metadata.category
            if category in self._categories:
                self._categories[category].discard(tool_name)
            return True
        return False

    def get(self, tool_name: str) -> BaseTool | None:
        """Get a tool by name."""
        entry = self._tools.get(tool_name)
        return entry.tool if entry else None

    def list_tools(self, category: str | None = None) -> list[str]:
        """List registered tool names."""
        if category:
            return list(self._categories.get(category, set()))
        return list(self._tools.keys())

    def get_metadata(self, tool_name: str) -> ToolMetadata | None:
        """Get tool metadata."""
        entry = self._tools.get(tool_name)
        return entry.tool.metadata if entry else None


# Global registry instance
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def initialize_registry(config: ToolRegistryConfig | None = None) -> ToolRegistry:
    """Initialize the global registry."""
    global _registry
    _registry = ToolRegistry(config)
    return _registry


__all__ = [
    "ToolRegistry",
    "ToolRegistryConfig",
    "ToolRegistryEntry",
    "get_registry",
    "initialize_registry",
]
