"""
Echo types - Enums, dataclasses, and configuration for Echo agent.

Types extracted from the original flat echo.py during subpackage conversion.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CommunicationChannel(Enum):
    """Supported communication channels."""

    INTERNAL = "internal"
    API = "api"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    EMAIL = "email"
    CONSOLE = "console"


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class CommunicationStyle:
    """Communication style configuration."""

    tone: str = "professional"
    formality: float = 0.7
    verbosity: Any = 0.5  # Accept float or string ("concise", "verbose")
    emoji_usage: bool = False
    audience: str = "technical"
    format_type: str = "text"
    emoji: bool = False

    def __post_init__(self) -> None:
        # Normalize verbosity to float
        if isinstance(self.verbosity, str):
            verbosity_map = {"concise": 0.3, "normal": 0.5, "verbose": 0.8}
            self.verbosity = verbosity_map.get(self.verbosity, 0.5)
        # Sync emoji and emoji_usage
        if self.emoji and not self.emoji_usage:
            self.emoji_usage = self.emoji


@dataclass
class TranslationRule:
    """Rule for protocol translation."""

    source_format: str
    target_format: str
    transformation: str
    priority: int = 0
