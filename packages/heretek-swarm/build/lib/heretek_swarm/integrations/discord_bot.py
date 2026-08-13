"""
Discord Bot Integration - PraisonAI Pattern

Discord bot for agent interaction and notifications.
Reference: PraisonAI Discord integration
"""

import os
from typing import TYPE_CHECKING, Optional

import structlog

try:
    import discord
    from discord.ext import commands

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    commands = None

# TYPE_CHECKING ensures type hints are not evaluated at runtime when discord is None
if TYPE_CHECKING:
    from discord import Embed, Intents, Message

logger = structlog.get_logger(__name__)


class DiscordBot:
    """
    Discord bot for Heretek Swarm interaction.

    Features:
    - Chat with agents via DM or channels
    - Task submission commands
    - Status notifications
    - Handoff updates
    - Embed-based rich responses
    """

    def __init__(
        self,
        token: str | None = None,
        agent_runtime=None,
        handoff_manager=None,
        intents: "Intents | None" = None,
    ):
        self.token = token or os.getenv("DISCORD_BOT_TOKEN")
        self.agent_runtime = agent_runtime
        self.handoff_manager = handoff_manager
        self._bot = None
        self._running = False

        if not DISCORD_AVAILABLE:
            logger.warning("discord_bot_unavailable", message="discord.py not installed")
            return

        # Set up intents - lazy import to avoid AttributeError at class definition
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True

        # Initialize bot
        self._bot = commands.Bot(
            command_prefix="!",
            intents=intents,
            help_command=None,  # Custom help
        )

        # Register events
        self._bot.event(self.on_ready)
        self._bot.event(self.on_message)

        # Register commands
        self._register_commands()

    def _register_commands(self) -> None:
        """Register Discord commands."""

        @self._bot.command(name="start")
        async def start(ctx):
            """Welcome message."""
            embed = discord.Embed(
                title="🤖 Welcome to Heretek Swarm!",
                description="I'm your Discord assistant for interacting with the AI agent collective.",  # noqa: E501
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Commands",
                value=(
                    "`!help` - Show this help\n"
                    "`!status` - Check swarm status\n"
                    "`!agents` - List available agents\n"
                    "`!chat <agent> <message>` - Chat with specific agent"
                ),
                inline=False,
            )
            embed.add_field(
                name="Example",
                value="`!chat steward Analyze this codebase`",
                inline=False,
            )
            await ctx.send(embed=embed)

        @self._bot.command(name="help")
        async def help_cmd(ctx):
            """Show help."""
            embed = discord.Embed(
                title="📖 Heretek Swarm Help",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Chat with Agents",
                value="Just type your message in #agent-chat or DM me, and I'll route it to the appropriate agent.",  # noqa: E501
                inline=False,
            )
            embed.add_field(
                name="Available Agents",
                value=(
                    "🎯 Steward (Orchestrator)\n"
                    "🔬 Alpha (Analysis)\n"
                    "✅ Beta (Validation)\n"
                    "💻 Coder (Development)\n"
                    "🛡️ Sentinel (Safety)\n"
                    "📚 Historian (Memory)"
                ),
                inline=False,
            )
            await ctx.send(embed=embed)

        @self._bot.command(name="status")
        async def status(ctx):
            """Show swarm status."""
            embed = discord.Embed(
                title="📊 Swarm Status",
                color=discord.Color.purple(),
            )

            if self.agent_runtime:
                status_text = ""
                for agent_id, runtime in self.agent_runtime.items():
                    status = runtime.get_status()
                    emoji = "🟢" if status.get("state") == "idle" else "🟡"
                    status_text += f"{emoji} **{agent_id}**: {status.get('state')}\n"
                embed.add_field(name="Active Agents", value=status_text, inline=False)
            else:
                embed.add_field(name="Status", value="Swarm status unavailable", inline=False)

            await ctx.send(embed=embed)

        @self._bot.command(name="agents")
        async def agents(ctx):
            """List available agents."""
            embed = discord.Embed(
                title="🤖 Available Agents",
                color=discord.Color.gold(),
            )
            embed.add_field(
                name="🎯 Steward",
                value="Orchestrator - Routes tasks and manages consensus",
                inline=False,
            )
            embed.add_field(
                name="🔬 Alpha",
                value="Analyst - Deep analysis and research",
                inline=False,
            )
            embed.add_field(
                name="✅ Beta",
                value="Validator - Quality assurance and testing",
                inline=False,
            )
            embed.add_field(
                name="💻 Coder",
                value="Developer - Code generation and refactoring",
                inline=False,
            )
            embed.add_field(
                name="🛡️ Sentinel",
                value="Safety - Ethics and constraint enforcement",
                inline=False,
            )
            embed.add_field(
                name="📚 Historian",
                value="Memory - RAG and context management",
                inline=False,
            )
            await ctx.send(embed=embed)

        @self._bot.command(name="chat")
        async def chat(ctx, agent: str, *, message: str):
            """Chat with specific agent."""
            await ctx.typing()

            response = await self._route_message(f"{agent}: {message}", str(ctx.author.id))

            embed = discord.Embed(
                title=f"🤖 {agent.title()}'s Response",
                description=response,
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Requested by {ctx.author.name}")
            await ctx.send(embed=embed)

    async def on_ready(self) -> None:
        """Bot ready event."""
        logger.info(
            "discord_bot_ready",
            user=self._bot.user.name,
            id=self._bot.user.id,
            guilds=len(self._bot.guilds),
        )
        self._running = True

    async def on_message(self, message: "Message") -> None:
        """Message received event."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore commands (handled separately)
        if message.content.startswith("!"):
            await self._bot.process_commands(message)
            return

        # Route message in DMs or agent-chat channel
        if isinstance(message.channel, discord.DMChannel) or (
            hasattr(message.channel, "name") and message.channel.name == "agent-chat"
        ):
            await message.channel.typing()

            user_id = str(message.author.id)
            response = await self._route_message(message.content, user_id)

            embed = discord.Embed(
                description=response,
                color=discord.Color.blue(),
            )
            await message.channel.send(embed=embed)

    async def initialize(self) -> bool:
        """Initialize bot."""
        if not DISCORD_AVAILABLE:
            return False

        if not self.token:
            logger.warning("discord_token_missing")
            return False

        logger.info("discord_bot_initialized")
        return True

    async def start(self) -> None:
        """Start bot."""
        if not self._bot:
            await self.initialize()

        await self._bot.start(self.token)

    async def stop(self) -> None:
        """Stop bot."""
        self._running = False

        if self._bot:
            await self._bot.close()

        logger.info("discord_bot_stopped")

    async def _route_message(self, message: str, user_id: str) -> str:
        """
        Route message to appropriate agent.

        Args:
            message: User message
            user_id: Discord user ID

        Returns:
            Agent response
        """
        message_lower = message.lower()

        # Determine agent from message
        if any(word in message_lower for word in ["code", "program", "script", "debug"]):
            agent_id = "coder"
        elif any(word in message_lower for word in ["analyze", "research", "investigate"]):
            agent_id = "alpha"
        elif any(word in message_lower for word in ["validate", "test", "check", "verify"]):
            agent_id = "beta"
        elif any(word in message_lower for word in ["memory", "remember", "history", "context"]):
            agent_id = "historian"
        elif any(word in message_lower for word in ["safe", "ethic", "constraint"]):
            agent_id = "sentinel"
        else:
            agent_id = "steward"

        logger.info(
            "discord_message_routed",
            agent=agent_id,
            user=user_id,
        )

        # Get agent response
        if self.agent_runtime and agent_id in self.agent_runtime:
            try:
                runtime = self.agent_runtime[agent_id]
                response = await runtime.think(message)
                return f"**{agent_id.title()}**: {response}"
            except Exception as e:
                logger.error("agent_response_error", error=str(e))
                return f"⚠️ Error: {e!s}"

        return f"🤖 Agent {agent_id} is unavailable."

    async def send_notification(
        self,
        channel_id: int,
        message: str,
        embed: "Embed | None" = None,
    ) -> bool:
        """
        Send notification to channel.

        Args:
            channel_id: Discord channel ID
            message: Message text
            embed: Optional embed

        Returns:
            True if sent
        """
        if not self._bot:
            return False

        try:
            channel = self._bot.get_channel(channel_id)
            if channel:
                if embed:
                    await channel.send(content=message, embed=embed)
                else:
                    await channel.send(message)
                return True
        except Exception as e:
            logger.error(
                "discord_notification_failed",
                channel_id=channel_id,
                error=str(e),
            )
        return False

    async def notify_handoff(
        self,
        channel_id: int,
        handoff_context: dict,
    ) -> None:
        """
        Send handoff notification.

        Args:
            channel_id: Channel to notify
            handoff_context: Handoff details
        """
        embed = discord.Embed(
            title="🔄 Task Handoff",
            color=discord.Color.orange(),
        )
        embed.add_field(name="From", value=handoff_context.get("source_agent"), inline=True)
        embed.add_field(name="To", value=handoff_context.get("target_agent"), inline=True)
        embed.add_field(
            name="Priority",
            value=handoff_context.get("priority", "normal"),
            inline=True,
        )
        embed.add_field(
            name="Task",
            value=handoff_context.get("task_description"),
            inline=False,
        )

        await self.send_notification(channel_id, "", embed=embed)


# Global bot instance
discord_bot: Optional["DiscordBot"] = None


def get_discord_bot() -> Optional["DiscordBot"]:
    """Get global bot instance."""
    return discord_bot


async def start_discord_bot(
    agent_runtime=None,
    handoff_manager=None,
) -> None:
    """Start Discord bot."""
    global discord_bot

    if not DISCORD_AVAILABLE:
        logger.warning("discord_not_available")
        return

    discord_bot = DiscordBot(
        agent_runtime=agent_runtime,
        handoff_manager=handoff_manager,
    )

    await discord_bot.initialize()
    await discord_bot.start()


async def stop_discord_bot() -> None:
    """Stop Discord bot."""
    global discord_bot

    if discord_bot:
        await discord_bot.stop()
        discord_bot = None
