"""
Echo subpackage - Communication, protocol translation, and multi-channel messaging.
"""

from heretek_swarm.actors.echo.agent import EchoAgent
from heretek_swarm.actors.echo.types import (
    CommunicationChannel,
    CommunicationStyle,
    MessagePriority,
    TranslationRule,
)

__all__ = [
    "CommunicationChannel",
    "CommunicationStyle",
    "EchoAgent",
    "MessagePriority",
    "TranslationRule",
]
