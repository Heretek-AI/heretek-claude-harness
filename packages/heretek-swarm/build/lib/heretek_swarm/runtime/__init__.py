"""
Heretek Swarm Runtime Package.

Provides agent runtime, character system, and tool registry for the swarm.
"""

import json

# New class-based character system
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from .agent_runtime import AgentContext, AgentRuntime, AgentState

# Support both old dictionary-based and new class-based character systems
from .characters import CHARACTERS, get_character
from .tools import ToolRegistry

logger = structlog.get_logger(__name__)


@dataclass
class CharacterStyle:
    """Defines the character's communication style."""

    all: list[str] = field(default_factory=list)
    chat: list[str] = field(default_factory=list)
    speak: list[str] = field(default_factory=list)


@dataclass
class Character:
    """
    Character definition for an agent.

    Contains all the configuration needed to define an agent's
    personality, knowledge, and behavior patterns.
    """

    name: str
    role: str
    bio: str
    lore: str = ""
    knowledge: list[str] = field(default_factory=list)
    message_examples: list[list[list[str]]] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    style: CharacterStyle = field(default_factory=CharacterStyle)
    adjectives: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        """Create a Character from a dictionary."""
        style_data = data.get("style", {})
        style = CharacterStyle(
            all=style_data.get("all", []),
            chat=style_data.get("chat", []),
            speak=style_data.get("speak", []),
        )
        return cls(
            name=data.get("name", "Unknown"),
            role=data.get("role", "agent"),
            bio=data.get("bio", ""),
            lore=data.get("lore", ""),
            knowledge=data.get("knowledge", []),
            message_examples=data.get("messageExamples", []),
            topics=data.get("topics", []),
            style=style,
            adjectives=data.get("adjectives", []),
            goals=data.get("goals", []),
            constraints=data.get("constraints", []),
        )

    @classmethod
    def from_json(cls, json_path: Path) -> "Character":
        """Load a character from a JSON file."""
        with open(json_path, encoding="utf-8") as f:  # noqa: PTH123
            data = json.load(f)
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """Convert character to dictionary."""
        return {
            "name": self.name,
            "role": self.role,
            "bio": self.bio,
            "lore": self.lore,
            "knowledge": self.knowledge,
            "messageExamples": self.message_examples,
            "topics": self.topics,
            "style": {
                "all": self.style.all,
                "chat": self.style.chat,
                "speak": self.style.speak,
            },
            "adjectives": self.adjectives,
            "goals": self.goals,
            "constraints": self.constraints,
        }


class CharacterRegistry:
    """Registry for loading and managing characters."""

    def __init__(self, characters_dir: Path | None = None):
        if characters_dir is None:
            characters_dir = Path(__file__).parent / "characters"
        self.characters_dir = Path(characters_dir)
        self._characters: dict[str, Character] = {}

    def load_character(self, name: str) -> Character | None:
        """Load a character by name."""
        char_file = self.characters_dir / f"{name.lower()}.json"
        if char_file.exists():
            return Character.from_json(char_file)
        return None

    def get_character(self, name: str) -> Character | None:
        """Get a character, loading if necessary."""
        if name not in self._characters:
            char = self.load_character(name)
            if char:
                self._characters[name] = char
        return self._characters.get(name)


__all__ = [
    "CHARACTERS",
    "AgentContext",
    "AgentRuntime",
    "AgentState",
    "Character",
    "CharacterRegistry",
    "CharacterStyle",
    "ToolRegistry",
    "get_character",
]
