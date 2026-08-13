"""
Telegram Bot Integration - PraisonAI Pattern

Telegram bot for agent interaction and notifications.
Reference: PraisonAI Telegram integration
"""

import os
from typing import TYPE_CHECKING

import structlog

try:
    from telegram import Bot, Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
    )

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Update = None
    Bot = None

# TYPE_CHECKING ensures type hints are evaluated only during type checking
if TYPE_CHECKING:
    from telegram.ext import ContextTypes

logger = structlog.get_logger(__name__)


class TelegramBot:
    """
    Telegram bot for agent swarm interaction.

    Features:
    - Chat with agents
    - Task submission
    - Status notifications
    - Handoff updates
    """

    def __init__(
        self,
        token: str | None = None,
        agent_runtime=None,
        handoff_manager=None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.agent_runtime = agent_runtime
        self.handoff_manager = handoff_manager
        self._application = None
        self._running = False

        if not TELEGRAM_AVAILABLE:
            logger.warning("telegram_bot_unavailable", message="python-telegram-bot not installed")

    async def initialize(self) -> bool:
        """Initialize bot."""
        if not TELEGRAM_AVAILABLE:
            return False

        if not self.token:
            logger.warning("telegram_token_missing")
            return False

        # Build application
        self._application = Application.builder().token(self.token).build()

        # Add handlers
        self._application.add_handler(CommandHandler("start", self._handle_start))
        self._application.add_handler(CommandHandler("help", self._handle_help))
        self._application.add_handler(CommandHandler("status", self._handle_status))
        self._application.add_handler(CommandHandler("agents", self._handle_agents))
        self._application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message,
            )
        )

        logger.info("telegram_bot_initialized")
        return True

    async def start(self) -> None:
        """Start bot polling."""
        if not self._application:
            await self.initialize()

        self._running = True
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()

        logger.info("telegram_bot_started")

    async def stop(self) -> None:
        """Stop bot."""
        self._running = False

        if self._application:
            await self._application.stop()
            await self._application.shutdown()

        logger.info("telegram_bot_stopped")

    async def _handle_start(
        self,
        update: Update,
        context: "ContextTypes.DEFAULT_TYPE",  # noqa: ARG002
    ) -> None:
        """Handle /start command."""
        welcome_message = """
🤖 *Welcome to Heretek Swarm!*

I'm your Telegram assistant for interacting with the AI agent collective.

*Commands:*
/help - Show this help
/status - Check swarm status
/agents - List available agents
/chat - Chat with an agent

*Example:*
"Ask Steward to analyze this codebase"
        """

        await update.message.reply_text(
            welcome_message,
            parse_mode="Markdown",
        )

    async def _handle_help(
        self,
        update: Update,
        context: "ContextTypes.DEFAULT_TYPE",  # noqa: ARG002
    ) -> None:
        """Handle /help command."""
        help_text = """
📖 *Heretek Swarm Help*

*Chat with Agents:*
Just type your message and I'll route it to the appropriate agent.

*Available Agents:*
- 🎯 Steward (Orchestrator)
- 🔬 Alpha (Analysis)
- ✅ Beta (Validation)
- 💻 Coder (Development)
- 🛡️ Sentinel (Safety)
- 📚 Historian (Memory)

*Commands:*
/start - Welcome message
/help - This help
/status - Swarm status
/agents - List agents

*Examples:*
"Alpha, analyze this architecture diagram"
"Coder, write a Python script to..."
"Historian, what did we decide about auth?"
        """

        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
        )

    async def _handle_status(
        self,
        update: Update,
        context: "ContextTypes.DEFAULT_TYPE",  # noqa: ARG002
    ) -> None:
        """Handle /status command."""
        # Get swarm status from API
        status_text = "📊 *Swarm Status*\n\n"

        if self.agent_runtime:
            # Get agent statuses
            status_text += "*Active Agents:*\n"
            for agent_id, runtime in self.agent_runtime.items():
                status = runtime.get_status()
                emoji = "🟢" if status["state"] == "idle" else "🟡"
                status_text += f"{emoji} {agent_id}: {status['state']}\n"
        else:
            status_text += "Swarm status unavailable\n"

        await update.message.reply_text(
            status_text,
            parse_mode="Markdown",
        )

    async def _handle_agents(
        self,
        update: Update,
        context: "ContextTypes.DEFAULT_TYPE",  # noqa: ARG002
    ) -> None:
        """Handle /agents command."""
        agents_text = """
🤖 *Available Agents*

🎯 *Steward* - Orchestrator
  Routes tasks and manages consensus

🔬 *Alpha* - Analyst
  Deep analysis and research

✅ *Beta* - Validator
  Quality assurance and testing

💻 *Coder* - Developer
  Code generation and refactoring

🛡️ *Sentinel* - Safety
  Ethics and constraint enforcement

📚 *Historian* - Memory
  RAG and context management
        """

        await update.message.reply_text(
            agents_text,
            parse_mode="Markdown",
        )

    async def _handle_message(
        self,
        update: Update,
        context: "ContextTypes.DEFAULT_TYPE",  # noqa: ARG002
    ) -> None:
        """Handle regular messages."""
        user_message = update.message.text
        user_id = str(update.message.from_user.id)

        # Send typing indicator
        await update.chat_bot.action("typing")

        # Route to appropriate agent
        response = await self._route_message(user_message, user_id)

        # Send response
        await update.message.reply_text(
            response,
            parse_mode="Markdown",
        )

    async def _route_message(
        self,
        message: str,
        user_id: str,
    ) -> str:
        """
        Route message to appropriate agent.

        Args:
            message: User message
            user_id: Telegram user ID

        Returns:
            Agent response
        """
        # Simple routing based on keywords
        message_lower = message.lower()

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
            agent_id = "steward"  # Default orchestrator

        logger.info(
            "telegram_message_routed",
            agent=agent_id,
            user=user_id,
        )

        # Get agent response
        if self.agent_runtime and agent_id in self.agent_runtime:
            try:
                runtime = self.agent_runtime[agent_id]
                response = await runtime.think(message)
                return f"🤖 *{agent_id.title()}*:\n\n{response}"
            except Exception as e:
                logger.error("agent_response_error", error=str(e))
                return f"⚠️ Error getting response: {e!s}"

        return f"🤖 Agent {agent_id} is currently unavailable."

    async def send_notification(
        self,
        chat_id: str,
        message: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        """
        Send notification to specific chat.

        Args:
            chat_id: Telegram chat ID
            message: Message text
            parse_mode: Parse mode (Markdown/HTML)

        Returns:
            True if sent successfully
        """
        if not self._application:
            return False

        try:
            bot = self._application.bot
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            return True
        except Exception as e:
            logger.error(
                "telegram_notification_failed",
                chat_id=chat_id,
                error=str(e),
            )
            return False

    async def notify_handoff(
        self,
        chat_id: str,
        handoff_context: dict,
    ) -> None:
        """
        Send handoff notification.

        Args:
            chat_id: Chat to notify
            handoff_context: Handoff details
        """
        message = f"""
🔄 *Task Handoff*

*From:* {handoff_context.get("source_agent")}
*To:* {handoff_context.get("target_agent")}
*Task:* {handoff_context.get("task_description")}
*Priority:* {handoff_context.get("priority")}
        """

        await self.send_notification(chat_id, message)


# Global bot instance
telegram_bot: TelegramBot | None = None


def get_telegram_bot() -> TelegramBot | None:
    """Get global bot instance."""
    return telegram_bot


async def start_telegram_bot(
    agent_runtime=None,
    handoff_manager=None,
) -> None:
    """Start Telegram bot."""
    global telegram_bot

    telegram_bot = TelegramBot(
        agent_runtime=agent_runtime,
        handoff_manager=handoff_manager,
    )

    await telegram_bot.initialize()
    await telegram_bot.start()


async def stop_telegram_bot() -> None:
    """Stop Telegram bot."""
    global telegram_bot

    if telegram_bot:
        await telegram_bot.stop()
        telegram_bot = None
