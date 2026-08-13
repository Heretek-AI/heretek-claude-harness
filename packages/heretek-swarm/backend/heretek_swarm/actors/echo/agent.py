"""
Echo Agent - Communication & Protocol Translation

The Echo agent is responsible for:
- Protocol translation between external systems
- Message formatting and normalization
- External API integration gateway
- Communication style adaptation
- Multi-channel message delivery

This agent ensures clear, contextual communication across all swarm interfaces.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor

# Session 44: Mixin Integration
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    HealthReportingMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)

# Session 44: Zero-Trust Validation
from heretek_swarm_core.security.zero_trust import ZeroTrustValidator

from .types import CommunicationChannel, CommunicationStyle, TranslationRule

logger = structlog.get_logger("EchoAgent")


class EchoAgent(
    HealthReportingMixin,
    ValidationMixin,
    AgentActor,
    PatternMixin,
    DeliberationMixin,
    MemoryMixin,
    LearningMixin,
):
    """
    Echo Agent - Communication & Protocol Translation Specialist

    Responsibilities:
    - Format messages for different audiences and channels
    - Translate between communication protocols
    - Manage communication styles and tone
    - Handle multi-channel message delivery
    - Ensure message consistency across channels
    """

    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
        _pattern_extractor: Any | None = None,
        _deliberation_engine: Any | None = None,
        _access_analyzer: Any | None = None,
        zero_trust_validator: Any | None = None,
    ):
        super().__init__(
            agent_id=agent_id or f"echo-{uuid.uuid4().hex[:8]}",
            actor_type="echo",
        )
        self._config = config or {}

        # Communication state
        self._active_channels: set[str] = set()
        self._message_queue: list[dict[str, Any]] = []
        self._translation_rules: dict[str, TranslationRule] = {}
        self._communication_styles: dict[str, CommunicationStyle] = {}
        self._channel_status: dict[str, Any] = {}  # Per-channel status tracking

        # Channel-specific configurations
        self._channel_configs: dict[str, dict[str, Any]] = {
            CommunicationChannel.INTERNAL.value: {
                "max_length": None,
                "format": "markdown",
                "include_metadata": True,
            },
            CommunicationChannel.API.value: {
                "max_length": 4096,
                "format": "json",
                "include_metadata": False,
            },
            CommunicationChannel.SLACK.value: {
                "max_length": 4000,
                "format": "slack_mrkdwn",
                "include_metadata": False,
            },
            CommunicationChannel.DISCORD.value: {
                "max_length": 2000,
                "format": "markdown",
                "include_metadata": False,
            },
            CommunicationChannel.TELEGRAM.value: {
                "max_length": 4096,
                "format": "html",
                "include_metadata": False,
            },
            CommunicationChannel.EMAIL.value: {
                "max_length": None,
                "format": "html",
                "include_metadata": True,
            },
            CommunicationChannel.CONSOLE.value: {
                "max_length": None,
                "format": "text",
                "include_metadata": True,
            },
        }

        # Default communication style
        self._default_style = CommunicationStyle(
            tone="professional",
            formality=0.7,
            verbosity=0.5,
            emoji_usage=False,
            audience="technical",
        )

        # Statistics
        self._stats = {
            "messages_formatted": 0,
            "messages_translated": 0,
            "messages_sent": 0,
            "channels_used": set(),
            "errors": 0,
        }

        # Session 44: Collective Learning Integration (provided by LearningMixin)
        # Session 44: Consensus Integration (provided by DeliberationMixin)
        # Session 44: Memory Optimization Integration (provided by MemoryMixin)

        # Session 44: Zero-Trust Validation
        self.zero_trust_validator = zero_trust_validator or ZeroTrustValidator()

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        logger.info(
            "Echo agent initialized",
            agent_id=self.agent_id,
            channels=list(self._channel_configs.keys()),
        )

    @property
    def active_channels(self) -> set[str]:
        """Get currently active communication channels."""
        return self._active_channels.copy()

    @property
    def statistics(self) -> dict[str, Any]:
        """Get communication statistics."""
        return {
            **self._stats,
            "channels_used": list(self._stats["channels_used"]),
            "queue_size": len(self._message_queue),
        }

    async def initialize(self) -> None:
        """Initialize the Echo agent."""
        await super().initialize()

        # Register default message handlers
        self.register_handler("format_message", self._handle_format_message)
        self.register_handler("translate_protocol", self._handle_translate_protocol)
        self.register_handler("send_to_channel", self._handle_send_to_channel)
        self.register_handler("set_communication_style", self._handle_set_communication_style)
        self.register_handler("get_channel_status", self._handle_get_channel_status)
        self.register_handler("broadcast_message", self._handle_broadcast_message)

        logger.info("Echo agent handlers registered", agent_id=self.agent_id)

    async def _validate_input(self, content: dict[str, Any]) -> dict[str, Any]:
        """Validate input using shared validation."""
        # Simple validation - just return content
        # The MessageContent model is for full message validation
        return content

    # =========================================================================
    # Message Handlers
    # =========================================================================

    async def _handle_format_message(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Format a message for a specific channel and audience.

        Content schema:
        {
            "content": str,
            "channel": str,
            "style": Optional[Dict],
            "priority": Optional[str]
        }
        """
        try:
            content = await self._validate_input(message.content)
            channel = content.get("channel", "internal")
            style_config = content.get("style")
            priority = content.get("priority", "normal")

            # Get or create communication style
            style = self._get_communication_style(style_config)

            # Format the message
            formatted = await self._format_for_channel(
                content=content.get("content", ""), channel=channel, style=style, priority=priority
            )

            self._stats["messages_formatted"] += 1

            return {
                "status": "success",
                "formatted_message": formatted,
                "channel": channel,
                "style_applied": style.tone,
            }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to format message",
                error=str(e),
                channel=message.content.get("channel", "unknown"),
            )
            return {"status": "error", "error": str(e)}

    async def _handle_translate_protocol(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Translate content between communication protocols.

        Content schema:
        {
            "content": Any,
            "source_format": str,
            "target_format": str
        }
        """
        try:
            content = message.content
            source_format = content.get("source_format", "internal")
            target_format = content.get("target_format", "json")
            payload = content.get("content")

            # Perform translation
            translated = await self._translate_content(
                content=payload, source_format=source_format, target_format=target_format
            )

            self._stats["messages_translated"] += 1

            return {
                "status": "success",
                "translated_content": translated,
                "source_format": source_format,
                "target_format": target_format,
            }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to translate protocol",
                error=str(e),
                source=message.content.get("source_format"),
                target=message.content.get("target_format"),
            )
            return {"status": "error", "error": str(e)}

    async def _handle_send_to_channel(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Send a formatted message to a specific channel.

        Content schema:
        {
            "channel": str,
            "message": str,
            "metadata": Optional[Dict]
        }
        """
        try:
            content = message.content
            channel = content.get("channel", "internal")
            message_text = content.get("message", "")
            metadata = content.get("metadata", {})

            # Validate channel exists
            if channel not in self._channel_configs:
                return {"status": "error", "error": f"Unknown channel: {channel}"}

            # Simulate sending (in production, integrate with actual channel APIs)
            send_result = await self._send_to_channel_impl(
                channel=channel, message=message_text, metadata=metadata
            )

            self._stats["channels_used"].add(channel)

            return {
                "status": "success" if send_result else "partial",
                "channel": channel,
                "delivered": send_result,
            }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to send to channel", error=str(e), channel=message.content.get("channel")
            )
            return {"status": "error", "error": str(e)}

    async def _handle_set_communication_style(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Set or update communication style for a context.

        Content schema:
        {
            "context": str,
            "style": {
                "tone": str,
                "formality": float,
                "verbosity": float,
                "emoji_usage": bool,
                "audience": str
            }
        }
        """
        try:
            content = message.content
            context = content.get("context") or content.get("channel", "default")
            style_config = content.get("style", {})

            # Create and store communication style
            style = CommunicationStyle(
                tone=style_config.get("tone", "professional"),
                formality=style_config.get("formality", 0.7),
                verbosity=style_config.get("verbosity", 0.5),
                emoji_usage=style_config.get("emoji_usage", False),
                audience=style_config.get("audience", "technical"),
            )

            self._communication_styles[context] = style

            return {
                "status": "success",
                "context": context,
                "style": {
                    "tone": style.tone,
                    "formality": style.formality,
                    "verbosity": style.verbosity,
                    "emoji_usage": style.emoji_usage,
                    "audience": style.audience,
                },
            }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to set communication style",
                error=str(e),
                context=message.content.get("context"),
            )
            return {"status": "error", "error": str(e)}

    async def _handle_get_channel_status(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Get status of communication channels.

        Content schema:
        {
            "channel": Optional[str] - Specific channel or all if None
        }
        """
        try:
            channel = message.content.get("channel")

            if channel:
                # Return specific channel status
                config = self._channel_configs.get(channel, {})
                return {
                    "status": "success",
                    "channel": channel,
                    "active": channel in self._active_channels,
                    "config": config,
                }
            # Return all channel statuses
            channel_statuses = {}
            for ch, config in self._channel_configs.items():
                channel_statuses[ch] = {"active": ch in self._active_channels, "config": config}

            return {
                "status": "success",
                "channels": channel_statuses,
                "statistics": self.statistics,
            }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Failed to get channel status", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_broadcast_message(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Broadcast a message to multiple channels.

        Content schema:
        {
            "content": str,
            "channels": List[str],
            "style": Optional[Dict],
            "priority": Optional[str]
        }
        """
        try:
            content = message.content
            message_content = content.get("content", "")
            channels = content.get("channels", ["internal"])
            style_config = content.get("style")
            priority = content.get("priority", "normal")

            # Get communication style
            style = self._get_communication_style(style_config)

            # Broadcast to each channel
            results = {}
            for channel in channels:
                try:
                    formatted = await self._format_for_channel(
                        content=message_content, channel=channel, style=style, priority=priority
                    )

                    send_result = await self._send_to_channel_impl(
                        channel=channel, message=formatted, metadata={"priority": priority}
                    )

                    results[channel] = {
                        "status": "success" if send_result else "failed",
                        "delivered": send_result,
                    }

                    if send_result:
                        self._stats["channels_used"].add(channel)
                        self._stats["messages_sent"] += 1

                except Exception as e:
                    results[channel] = {"status": "error", "error": str(e)}
                    self._stats["errors"] += 1

            self._stats["messages_formatted"] += len(channels)

            return {
                "status": "success",
                "results": results,
                "total_channels": len(channels),
                "successful": sum(1 for r in results.values() if r.get("status") == "success"),
            }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Failed to broadcast message", error=str(e))
            return {"status": "error", "error": str(e)}

    # =========================================================================
    # Communication Formatting
    # =========================================================================

    def _get_communication_style(self, style_config: dict | None) -> CommunicationStyle:
        """Get or create communication style."""
        if style_config:
            return CommunicationStyle(
                tone=style_config.get("tone", "professional"),
                formality=style_config.get("formality", 0.7),
                verbosity=style_config.get("verbosity", 0.5),
                emoji_usage=style_config.get("emoji_usage", False),
                audience=style_config.get("audience", "technical"),
            )
        return self._default_style

    async def _format_for_channel(
        self,
        content: Any,
        channel: Any = "internal",
        style: CommunicationStyle | None = None,
        priority: str = "normal",
    ) -> str:
        """Format content for a specific channel and style."""
        # Normalize channel to string value
        channel_str = channel.value if hasattr(channel, "value") else str(channel)
        config = self._channel_configs.get(channel_str, self._channel_configs.get("internal", {}))
        max_length = config.get("max_length")
        format_type = config.get("format", "text")

        # Apply style transformations
        style = style or CommunicationStyle()
        content_str = str(content) if not isinstance(content, str) else content
        formatted = self._apply_style(content_str, style)

        # Apply channel-specific formatting
        if format_type == "json":
            formatted = self._format_as_json(formatted, priority)
        elif format_type == "slack_mrkdwn":
            formatted = self._format_for_slack(formatted)
        elif format_type == "html":
            formatted = self._format_as_html(formatted, style)
        elif format_type == "markdown":
            formatted = self._format_as_markdown(formatted, style)

        # Truncate if necessary
        if max_length and len(formatted) > max_length:
            formatted = formatted[: max_length - 3] + "..."

        return formatted

    def _apply_style(self, content: str, style: CommunicationStyle) -> str:
        """Apply communication style to content."""
        # Adjust tone
        if style.tone == "friendly":
            content = f"Hello! {content}"
        elif style.tone == "formal":
            content = f"Please be advised: {content}"
        elif style.tone == "urgent":
            content = f"⚠️ URGENT: {content}" if style.emoji_usage else f"URGENT: {content}"

        # Adjust verbosity
        if style.verbosity < 0.3:
            # Make more concise
            content = content[:200] + "..." if len(content) > 200 else content

        # Add emoji if enabled
        if style.emoji_usage and style.tone == "friendly":
            content = content + " ✨"

        return content

    def _format_as_json(self, content: str, priority: str) -> str:
        """Format content as JSON."""
        import json

        return json.dumps(
            {"message": content, "priority": priority, "timestamp": datetime.now(UTC).isoformat()}
        )

    def _format_for_slack(self, content: str) -> str:
        """Format content for Slack."""
        # Convert basic markdown to Slack mrkdwn
        content = content.replace("**", "*")  # Bold
        return content.replace("__", "_")  # Italic

    def _format_as_html(self, content: str, style: CommunicationStyle) -> str:
        """Format content as HTML."""
        # Basic HTML formatting
        content = content.replace("\n", "<br>")
        content = content.replace("**", "<strong>").replace("**", "</strong>")

        if style.tone == "friendly":
            return f"<p style='color: #28a745;'>{content}</p>"
        if style.tone == "urgent":
            return f"<p style='color: #dc3545; font-weight: bold;'>{content}</p>"

        return f"<p>{content}</p>"

    def _format_as_markdown(self, content: str, style: CommunicationStyle) -> str:
        """Format content as markdown."""
        if style.tone == "formal":
            return f"## Message\n\n{content}"
        return content

    # =========================================================================
    # Protocol Translation
    # =========================================================================

    async def _translate_content(
        self,
        content: Any,
        source_format: str | None = None,
        target_format: str | None = None,
        from_lang: str | None = None,
        to_lang: str | None = None,
    ) -> Any:
        # Accept from_lang/to_lang as aliases
        source_format = source_format or from_lang or "text"
        target_format = target_format or to_lang or "text"
        """Translate content between formats."""
        import json

        # Handle common translations
        if source_format == "json" and target_format == "text":
            if isinstance(content, dict):
                return json.dumps(content, indent=2)
            return str(content)

        if source_format == "text" and target_format == "json":
            return {"content": str(content)}

        if source_format == "internal" and target_format == "api":
            # Convert internal format to API response
            return {"success": True, "data": content, "timestamp": datetime.now(UTC).isoformat()}

        if source_format == "api" and target_format == "internal":
            # Extract data from API response
            if isinstance(content, dict):
                return content.get("data", content)
            return content

        # Default: return as-is
        return content

    # =========================================================================
    # Channel Delivery
    # =========================================================================

    async def _send_to_channel_impl(
        self,
        channel: Any,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        content: str | None = None,
        style_config: dict[str, Any] | None = None,
    ) -> bool:
        # Accept 'content' as alias for 'message'
        message = message or content or ""
        metadata = metadata or style_config or {}
        """
        Send message to channel (implementation stub).

        In production, this would integrate with:
        - Slack API
        - Discord API
        - Telegram Bot API
        - Email SMTP/SendGrid
        - WebSocket connections
        """
        # Log the send attempt
        logger.info(
            "Sending to channel", channel=channel, message_length=len(message), metadata=metadata
        )

        # Add to message queue for processing
        self._message_queue.append(
            {
                "channel": channel,
                "message": message,
                "metadata": metadata,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        # Keep queue bounded
        if len(self._message_queue) > 1000:
            self._message_queue = self._message_queue[-1000:]

        # Simulate successful send
        return True

    # =========================================================================
    # Lifecycle
    # =========================================================================

    # =========================================================================
    # Session 44: Collective Learning Integration Methods (now provided by PatternMixin)
    # =========================================================================

    # _emit_pattern and _consume_patterns provided by PatternMixin

    # =========================================================================
    # Session 44: Consensus Deliberation Integration Methods (now provided by DeliberationMixin)
    # =========================================================================

    # _initiate_deliberation, _submit_deliberation_position, _finalize_deliberation
    # provided by DeliberationMixin

    # =========================================================================
    # Session 44: Memory Optimization Integration Methods (now provided by MemoryMixin)
    # =========================================================================

    # _track_memory_access, _get_memory_tier, _prefetch_relevant provided by MemoryMixin
    # get_learning_status provided by LearningMixin

    async def terminate(self) -> None:
        """Terminate the Echo agent."""
        # Process remaining messages
        if self._message_queue:
            logger.info("Processing remaining messages", count=len(self._message_queue))

        await super().terminate()
        logger.info("Echo agent terminated", agent_id=self.agent_id)
