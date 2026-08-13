"""
Heretek Swarm Tools Base Module.

Provides base classes for tool execution in the swarm.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ToolStatus(Enum):
    """Tool execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ToolMetadata:
    """Metadata for a tool."""

    name: str
    description: str
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class ToolContext:
    """Context for tool execution."""

    agent_id: str
    session_id: str
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionResult:
    """Result of tool execution."""

    tool_name: str
    status: ToolStatus
    output: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutionError(Exception):
    """Error during tool execution."""


class BaseTool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str, metadata: ToolMetadata | None = None):
        self.name = name
        self.description = description
        self.metadata = metadata or ToolMetadata(name=name, description=description)

    @abstractmethod
    async def execute(self, context: ToolContext, **kwargs) -> ToolExecutionResult:
        """Execute the tool with the given context.

        Subclasses must implement this method.
        """
        ...

    async def validate(self, **_kwargs) -> bool:
        """Validate tool parameters."""
        return True


class SimpleTool(BaseTool):
    """Simple tool that wraps a synchronous function."""

    def __init__(self, name: str, description: str, func: callable, **kwargs):
        super().__init__(name, description, **kwargs)
        self.func = func

    async def execute(self, _context: ToolContext, **kwargs) -> ToolExecutionResult:
        """Execute the wrapped function."""
        start = datetime.now(UTC)
        try:
            result = self.func(**kwargs)
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=result,
                execution_time_ms=(datetime.now(UTC) - start).total_seconds() * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time_ms=(datetime.now(UTC) - start).total_seconds() * 1000,
            )


__all__ = [
    "BaseTool",
    "SimpleTool",
    "ToolContext",
    "ToolExecutionError",
    "ToolExecutionResult",
    "ToolMetadata",
    "ToolStatus",
]
