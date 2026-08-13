"""
Channel Registry for Heretek Swarm

Provides formal communication channel architecture for agent-to-agent
communication using NATS subjects and A2A protocol patterns.
"""

from heretek_swarm.channels.registry import (
    ChannelDefinition,
    ChannelMessage,
    ChannelRegistry,
    ChannelType,
    CommunicationGroup,
    GroupRegistry,
    QoSLevel,
)

__all__ = [
    "ChannelDefinition",
    "ChannelMessage",
    "ChannelRegistry",
    "ChannelType",
    "CommunicationGroup",
    "GroupRegistry",
    "QoSLevel",
]
