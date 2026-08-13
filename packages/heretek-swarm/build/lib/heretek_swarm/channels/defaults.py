"""Default channel and group definitions.

This module provides default channel configurations organized by type,
enabling cleaner separation of channel definitions from registration logic.
"""

import structlog

from .registry import ChannelDefinition, ChannelType, QoSLevel

logger = structlog.get_logger(__name__)


def get_internal_channels() -> list[ChannelDefinition]:
    """Get default internal agent channels.

    Returns:
        List of internal channel definitions
    """
    return [
        # Triad Channel - Core governance deliberation
        ChannelDefinition(
            name="swarm.internal.triad",
            description="Core governance deliberation channel",
            channel_type=ChannelType.INTERNAL,
            subscribers=["steward", "alpha", "beta", "charlie"],
            message_types=[
                "proposal",
                "analysis",
                "validation",
                "challenge",
                "decision",
                "deliberation_start",
                "deliberation_complete",
            ],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="24h",
            priority="high",
        ),
        # Coordination Channel - Multi-agent task coordination
        ChannelDefinition(
            name="swarm.internal.coordination",
            description="Multi-agent task coordination channel",
            channel_type=ChannelType.INTERNAL,
            subscribers=["coordinator", "catalyst", "chronos", "metis"],
            message_types=[
                "task_start",
                "task_complete",
                "dependency_ready",
                "blocker",
                "resource_request",
                "status_update",
            ],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="12h",
        ),
        # Safety Channel - Security and safety alerts
        ChannelDefinition(
            name="swarm.internal.safety",
            description="Security and safety alerts channel",
            channel_type=ChannelType.INTERNAL,
            subscribers=["sentinel", "sentinel-prime", "arbiter", "steward"],
            message_types=[
                "threat_detected",
                "quarantine",
                "all_clear",
                "incident_report",
                "validation_request",
                "security_alert",
            ],
            qos=QoSLevel.EXACTLY_ONCE,
            retention="7d",
            priority="critical",
        ),
        # Memory Channel - Memory and knowledge operations
        ChannelDefinition(
            name="swarm.internal.memory",
            description="Memory and knowledge operations channel",
            channel_type=ChannelType.INTERNAL,
            subscribers=["historian", "prism", "habit-forge"],
            message_types=[
                "store_request",
                "retrieve_request",
                "learn_pattern",
                "forget",
                "context_request",
                "lineage_query",
            ],
            qos=QoSLevel.AT_MOST_ONCE,
            retention="1h",
        ),
        # Exploration Channel - Research and implementation
        ChannelDefinition(
            name="swarm.internal.exploration",
            description="Research and implementation channel",
            channel_type=ChannelType.INTERNAL,
            subscribers=["explorer", "examiner", "dreamer", "coder"],
            message_types=[
                "research_task",
                "analysis_result",
                "creative_request",
                "code_review",
                "discovery",
                "implementation_complete",
            ],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="6h",
        ),
        # Perception Channel - Input processing and translation
        ChannelDefinition(
            name="swarm.internal.perception",
            description="Input processing and translation channel",
            channel_type=ChannelType.INTERNAL,
            subscribers=["perceiver", "perceiver-plus", "empath", "echo"],
            message_types=[
                "input_received",
                "sentiment_analysis",
                "translation_request",
                "feature_extracted",
                "format_request",
                "broadcast_request",
            ],
            qos=QoSLevel.AT_MOST_ONCE,
            retention="1h",
        ),
    ]


def get_system_channels() -> list[ChannelDefinition]:
    """Get default system channels.

    Returns:
        List of system channel definitions
    """
    return [
        # Health Channel - Health monitoring (all agents)
        ChannelDefinition(
            name="swarm.system.health",
            description="Health monitoring channel (all agents)",
            channel_type=ChannelType.SYSTEM,
            subscribers=["*"],  # Wildcard - all agents
            message_types=[
                "heartbeat",
                "health_status",
                "error_report",
                "restart_request",
                "scaling_request",
            ],
            qos=QoSLevel.AT_MOST_ONCE,
            retention="1h",
        ),
        # Consciousness Channel - Consciousness metrics broadcast
        ChannelDefinition(
            name="swarm.system.consciousness",
            description="Consciousness metrics broadcast channel",
            channel_type=ChannelType.SYSTEM,
            subscribers=["*"],
            message_types=[
                "phi_update",
                "attention_state",
                "workspace_broadcast",
                "integration_metric",
                "global_state",
            ],
            qos=QoSLevel.AT_MOST_ONCE,
            retention="30m",
        ),
        # Consensus Channel - MAKER consensus voting
        ChannelDefinition(
            name="swarm.system.consensus",
            description="MAKER consensus voting channel",
            channel_type=ChannelType.CONSENSUS,
            subscribers=["steward", "alpha", "beta", "charlie"],
            message_types=[
                "vote_cast",
                "consensus_reached",
                "red_flag",
                "reputation_update",
                "proposal_start",
                "proposal_complete",
            ],
            qos=QoSLevel.EXACTLY_ONCE,
            retention="24h",
            priority="high",
        ),
        # Workflow Channel - Workflow events
        ChannelDefinition(
            name="swarm.workflow.events",
            description="Workflow lifecycle events channel",
            channel_type=ChannelType.SYSTEM,
            subscribers=["*"],
            message_types=[
                "workflow_start",
                "workflow_phase",
                "workflow_complete",
                "workflow_error",
                "workflow_checkpoint",
            ],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="24h",
        ),
    ]


def get_external_channels() -> list[ChannelDefinition]:
    """Get default external integration channels.

    Returns:
        List of external channel definitions
    """
    return [
        # Discord Channel
        ChannelDefinition(
            name="swarm.external.discord",
            description="Discord integration channel",
            channel_type=ChannelType.EXTERNAL,
            subscribers=["nexus", "echo"],
            message_types=["discord_message", "discord_command", "discord_response"],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="1h",
        ),
        # Slack Channel
        ChannelDefinition(
            name="swarm.external.slack",
            description="Slack integration channel",
            channel_type=ChannelType.EXTERNAL,
            subscribers=["nexus", "echo"],
            message_types=["slack_message", "slack_command", "slack_response"],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="1h",
        ),
        # Telegram Channel
        ChannelDefinition(
            name="swarm.external.telegram",
            description="Telegram integration channel",
            channel_type=ChannelType.EXTERNAL,
            subscribers=["nexus", "echo"],
            message_types=["telegram_message", "telegram_command", "telegram_response"],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="1h",
        ),
        # API Channel - External API requests
        ChannelDefinition(
            name="swarm.external.api",
            description="External API requests channel",
            channel_type=ChannelType.EXTERNAL,
            subscribers=["nexus"],
            message_types=["api_request", "api_response", "webhook_event"],
            qos=QoSLevel.AT_LEAST_ONCE,
            retention="1h",
        ),
    ]


def get_all_default_channels() -> list[ChannelDefinition]:
    """Get all default channels.

    Returns:
        List of all default channel definitions
    """
    return get_internal_channels() + get_system_channels() + get_external_channels()
