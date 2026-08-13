"""
Actor Orchestrator — extracts actor spawning, channel subscription setup,
and message handling from AutonomousSwarm.

Owns the lifecycle of all 23 agents across 6 tiers and their NATS
channel subscriptions.
"""

from typing import Any

import structlog

from heretek_swarm.actors.supervisor import ActorSupervisor
from heretek_swarm.agents.agent_factory import build_agent_for

# Module-level constants for repeated tier labels
_TIER1_LABEL = "Tier 1 (Core Triad)"
_TIER2_LABEL = "Tier 2 (Support)"
_TIER3_LABEL = "Tier 3 (Exploration)"
_TIER4_LABEL = "Tier 4 (Safety)"
_TIER5_LABEL = "Tier 5 (Coordination)"
_TIER6_LABEL = "Tier 6 (Enhancement)"

logger = structlog.get_logger(__name__)


class ActorOrchestrator:
    """Manages actor lifecycle: spawn, channel subscriptions, message routing.

    Takes references to supervisor, MCP tools, channel registry, and event
    mesh — these are shared with AutonomousSwarm and mutated during
    ``initialize()``.
    """

    def __init__(
        self,
        supervisor: ActorSupervisor | None,
        mcp_tools: Any,
        channel_registry: Any,
        event_mesh: Any,
    ) -> None:
        self._supervisor = supervisor
        self._mcp_tools = mcp_tools
        self._channel_registry = channel_registry
        self._event_mesh = event_mesh

    async def spawn_all_actors(self) -> None:
        """Spawn all 23 agents across 6 tiers."""
        # Tier 1: Core Triad (Governance)
        from heretek_swarm.actors.arbiter import ArbiterAgent
        from heretek_swarm.actors.catalyst import CatalystAgent
        from heretek_swarm.actors.chronos import ChronosAgent
        from heretek_swarm.actors.coder import CoderAgent

        # Tier 5: Coordination Agents (Integration)
        from heretek_swarm.actors.coordinator import CoordinatorAgent
        from heretek_swarm.actors.dreamer import DreamerAgent
        from heretek_swarm.actors.echo import EchoAgent
        from heretek_swarm.actors.empath import EmpathAgent
        from heretek_swarm.actors.examiner import ExaminerAgent

        # Tier 3: Exploration Agents (Discovery & Creation)
        from heretek_swarm.actors.explorer import ExplorerAgent
        from heretek_swarm.actors.habit_forge import HabitForgeAgent

        # Tier 2: Support Agents (Knowledge & Memory)
        from heretek_swarm.actors.historian import HistorianAgent
        from heretek_swarm.actors.metis import MetisAgent
        from heretek_swarm.actors.nexus import NexusAgent
        from heretek_swarm.actors.perceiver import PerceiverAgent
        from heretek_swarm.actors.perceiver_plus import PerceiverPlusAgent

        # Tier 6: Enhancement Agents (Optimization)
        from heretek_swarm.actors.prism import PrismAgent

        # Tier 4: Safety & Security (Protection)
        from heretek_swarm.actors.sentinel import SentinelAgent
        from heretek_swarm.actors.sentinel_prime import SentinelPrimeAgent
        from heretek_swarm.actors.triad import AlphaAgent, BetaAgent, CharlieAgent, StewardAgent

        # Define all agents with their topics
        actors = [
            # Tier 1: Core Triad
            (StewardAgent, "steward", ["triad", "coordination", "governance"]),
            (AlphaAgent, "alpha", ["analysis", "decisions", "triad"]),
            (BetaAgent, "beta", ["validation", "quality", "triad"]),
            (CharlieAgent, "charlie", ["risk", "challenges", "triad"]),
            # Tier 2: Support
            (HistorianAgent, "historian", ["memory", "context", "triad"]),
            (MetisAgent, "metis", ["planning", "strategy", "coordination"]),
            (EmpathAgent, "empath", ["sentiment", "mediation", "perception"]),
            (PerceiverAgent, "perceiver", ["input", "sensory", "perception"]),
            (EchoAgent, "echo", ["communication", "broadcast", "perception"]),
            # Tier 3: Exploration
            (ExplorerAgent, "explorer", ["discovery", "monitoring", "exploration"]),
            (ExaminerAgent, "examiner", ["testing", "quality", "exploration"]),
            (DreamerAgent, "dreamer", ["creative", "alternatives", "exploration"]),
            (CoderAgent, "coder", ["code", "implementation", "exploration"]),
            # Tier 4: Safety
            (SentinelAgent, "sentinel", ["validation", "safety", "safety"]),
            (SentinelPrimeAgent, "sentinel-prime", ["threats", "security", "safety"]),
            (ArbiterAgent, "arbiter", ["conflict", "resolution", "safety"]),
            # Tier 5: Coordination
            (CoordinatorAgent, "coordinator", ["coordination", "tasks", "coordination"]),
            (NexusAgent, "nexus", ["external", "api", "external"]),
            (CatalystAgent, "catalyst", ["change", "transition", "coordination"]),
            (ChronosAgent, "chronos", ["scheduling", "temporal", "coordination"]),
            # Tier 6: Enhancement
            (PrismAgent, "prism", ["perspective", "viewpoints", "memory"]),
            (HabitForgeAgent, "habit-forge", ["patterns", "behavior", "memory"]),
            (PerceiverPlusAgent, "perceiver-plus", ["analytics", "advanced", "perception"]),
        ]

        # Per-agent system prompts loaded at spawn time.
        # These give each agent its role identity so swarms.Agent can
        # use a meaningful persona rather than the default auto-generated one.
        _HISTORIAN_SYSTEM_PROMPT = (
            "You are the Historian agent. You record and retrieve structured "
            "events for the swarm. You persist events to a JSONL file and "
            "provide memory and context for deliberations."
        )
        _CHRONOS_SYSTEM_PROMPT = (
            "You are the Chronos agent. You manage scheduling and temporal "
            "coordination. You generate ticks that drive the swarm's main loop, "
            "telling agents what to do and when."
        )
        _METIS_SYSTEM_PROMPT = (
            "You are the Metis agent. You provide strategic planning and "
            "long-term thinking for the swarm. You produce strategic analyses "
            "covering goal setting, resource allocation, risk assessment, "
            "multi-step planning, and scenario analysis."
        )
        _EMPATH_SYSTEM_PROMPT = (
            "You are the Empath agent. You provide emotional intelligence "
            "and sentiment analysis for the swarm. You perform sentiment "
            "analysis on communications, track agent mood states, detect "
            "stress, mediate conflicts, and provide emotional context for "
            "decision-making."
        )
        _STEWARD_SYSTEM_PROMPT = (
            "You are the Steward agent. You oversee governance and "
            "coordination for the swarm. You initiate deliberation processes, "
            "coordinate Triad members, make final executive decisions, and "
            "manage resource allocation and system-wide policy."
        )
        _ALPHA_SYSTEM_PROMPT = (
            "You are the Alpha agent. You are the primary analyst and "
            "decision-maker in the Triad. You perform deep analysis of "
            "topics and produce structured analytical reports covering "
            "key factors, evidence, and actionable recommendations."
        )
        _BETA_SYSTEM_PROMPT = (
            "You are the Beta agent. You are the secondary analyst and "
            "validator in the Triad. You review proposals and analyses "
            "for quality, consistency, and logical soundness, providing "
            "validation reports that identify gaps and strengths."
        )
        _CHARLIE_SYSTEM_PROMPT = (
            "You are the Charlie agent. You are the challenger and risk "
            "assessor in the Triad. You identify risks, surface hidden "
            "assumptions, and provide counterarguments to ensure robust "
            "decision-making through adversarial perspective."
        )
        _PERCEIVER_SYSTEM_PROMPT = (
            "You are the Perceiver agent. You process multi-modal sensory "
            "input for the swarm. You handle text, image, audio, and video "
            "data, perform feature extraction and preprocessing, normalize "
            "sensory information, and assess input quality."
        )
        _ECHO_SYSTEM_PROMPT = (
            "You are the Echo agent. You handle communication and protocol "
            "translation for the swarm. You translate between external "
            "protocols, format and normalize messages, serve as the external "
            "API integration gateway, and deliver messages across multiple "
            "channels with appropriate style adaptation."
        )
        _EXPLORER_SYSTEM_PROMPT = (
            "You are the Explorer agent. You perform intelligence gathering "
            "and opportunity discovery for the swarm. You monitor external "
            "sources, identify opportunities and threats, detect anomalies, "
            "conduct deep topic research, and report actionable findings."
        )
        _EXAMINER_SYSTEM_PROMPT = (
            "You are the Examiner agent. You are the quality assurance "
            "specialist for the swarm. You design and execute test cases, "
            "perform code and system reviews, detect bugs and quality "
            "issues, generate quality reports, and enforce testing standards."
        )
        _DREAMER_SYSTEM_PROMPT = (
            "You are the Dreamer agent. You drive creative exploration "
            "and innovation for the swarm. You generate novel ideas, "
            "explore alternative approaches, facilitate creative sessions, "
            "and produce innovation reports with actionable creativity."
        )
        _CODER_SYSTEM_PROMPT = (
            "You are the Coder agent. You are the implementation engine "
            "for the swarm. You generate, review, and refactor code, "
            "detect and fix bugs, write tests, produce documentation, "
            "and explain code. You turn decisions into working software."
        )
        _SENTINEL_SYSTEM_PROMPT = (
            "You are the Sentinel agent. You are the safety guardian "
            "for the swarm. You validate and sanitize inputs, filter "
            "outputs for harmful content, enforce guardrails and content "
            "policy, detect behavioral anomalies, and generate safety reports."
        )
        _SENTINEL_PRIME_SYSTEM_PROMPT = (
            "You are the Sentinel-Prime agent. You are the security "
            "commander for the swarm. You detect and respond to external "
            "threats, manage security incidents, analyze threat indicators, "
            "coordinate response actions, and serve as backup monitoring "
            "for the Sentinel agent."
        )
        _ARBITER_SYSTEM_PROMPT = (
            "You are the Arbiter agent. You resolve conflicts within the "
            "swarm. You detect and analyze conflicts between agents, apply "
            "resolution strategies, manage relationships, produce "
            "arbitration reports, and enforce resolution outcomes."
        )
        _COORDINATOR_SYSTEM_PROMPT = (
            "You are the Coordinator agent. You orchestrate multi-agent "
            "workflows for the swarm. You synchronize tasks across agents, "
            "resolve dependencies, manage parallel execution, handle "
            "resource contention, and track collective progress."
        )
        _NEXUS_SYSTEM_PROMPT = (
            "You are the Nexus agent. You manage external integrations "
            "for the swarm. You handle API connections, configure "
            "webhooks, translate between external protocols, manage "
            "connection lifecycles, and route external events into "
            "the swarm."
        )
        _CATALYST_SYSTEM_PROMPT = (
            "You are the Catalyst agent. You manage change and transitions "
            "for the swarm. You detect and analyze changes, plan and "
            "execute transitions, manage version migrations, coordinate "
            "rollbacks, and communicate changes to stakeholders."
        )
        _PRISM_SYSTEM_PROMPT = (
            "You are the Prism agent. You provide multi-perspective "
            "analysis for the swarm. You analyze situations from multiple "
            "viewpoints, detect cognitive biases, generate stakeholder "
            "maps, apply analytical frameworks, and produce reframed "
            "perspectives to improve decision quality."
        )
        _HABIT_FORGE_SYSTEM_PROMPT = (
            "You are the Habit-Forge agent. You manage behavioral patterns "
            "and habit formation for the swarm. You track recurring "
            "patterns, reinforce positive behaviors, manage habit stages, "
            "monitor streaks, and help the swarm build productive routines."
        )
        _PERCEIVER_PLUS_SYSTEM_PROMPT = (
            "You are the Perceiver+ agent. You perform advanced analytics "
            "for the swarm. You conduct statistical analysis, trend "
            "detection, correlation studies, and deep data mining across "
            "multiple data modalities to produce actionable analytical "
            "results."
        )

        # Map agent_ids to their system prompts. Agents not listed get None
        # (swarms auto-generates a default prompt in that case).
        _SYSTEM_PROMPTS: dict[str, str | None] = {
            "historian": _HISTORIAN_SYSTEM_PROMPT,
            "chronos": _CHRONOS_SYSTEM_PROMPT,
            "metis": _METIS_SYSTEM_PROMPT,
            "empath": _EMPATH_SYSTEM_PROMPT,
            "steward": _STEWARD_SYSTEM_PROMPT,
            "alpha": _ALPHA_SYSTEM_PROMPT,
            "beta": _BETA_SYSTEM_PROMPT,
            "charlie": _CHARLIE_SYSTEM_PROMPT,
            "perceiver": _PERCEIVER_SYSTEM_PROMPT,
            "echo": _ECHO_SYSTEM_PROMPT,
            "explorer": _EXPLORER_SYSTEM_PROMPT,
            "examiner": _EXAMINER_SYSTEM_PROMPT,
            "dreamer": _DREAMER_SYSTEM_PROMPT,
            "coder": _CODER_SYSTEM_PROMPT,
            "sentinel": _SENTINEL_SYSTEM_PROMPT,
            "sentinel-prime": _SENTINEL_PRIME_SYSTEM_PROMPT,
            "arbiter": _ARBITER_SYSTEM_PROMPT,
            "coordinator": _COORDINATOR_SYSTEM_PROMPT,
            "nexus": _NEXUS_SYSTEM_PROMPT,
            "catalyst": _CATALYST_SYSTEM_PROMPT,
            "prism": _PRISM_SYSTEM_PROMPT,
            "habit-forge": _HABIT_FORGE_SYSTEM_PROMPT,
            "perceiver-plus": _PERCEIVER_PLUS_SYSTEM_PROMPT,
        }

        for agent_class, agent_id, _topics in actors:
            try:
                actor = await self._supervisor.spawn_actor(agent_class, agent_id)
                # Inject a swarms.Agent so the actor can produce real LLM output
                system_prompt = _SYSTEM_PROMPTS.get(agent_id)
                actor.swarms_agent = build_agent_for(
                    agent_id,
                    agent_class.__name__,
                    system_prompt=system_prompt,
                )
                # Inject MCP tools into every agent's swarms_agent post-spawn
                if self._mcp_tools is not None:
                    from heretek_swarm.mcp.agent_tools import (
                        build_tool_handlers,
                        build_tools_list_dictionary,
                    )

                    mcp_registry = self._mcp_tools.get_registry()
                    tool_schemas = build_tools_list_dictionary(mcp_registry)
                    tool_handlers = build_tool_handlers(mcp_registry)
                    if tool_schemas:
                        actor.swarms_agent.tools_list_dictionary = tool_schemas
                        actor.swarms_agent.tools = list(tool_handlers.values())
                        logger.info(
                            "mcp_tools_injected",
                            agent_id=agent_id,
                            tool_count=len(tool_schemas),
                        )
                    else:
                        logger.warning(
                            "mcp_tools_injection_skipped_empty",
                            agent_id=agent_id,
                        )
                else:
                    logger.warning(
                        "mcp_tools_injection_skipped_no_registry",
                        agent_id=agent_id,
                    )
                logger.info("actor_spawned", agent_id=agent_id, tier=self._get_tier(agent_id))
            except Exception as e:
                logger.error("actor_spawn_failed", agent_id=agent_id, error=str(e))
                # Continue spawning remaining agents even if one fails
                continue

    @staticmethod
    def _get_tier(agent_id: str) -> str:
        """Get the tier name for an agent."""
        tier_mapping = {
            "steward": _TIER1_LABEL,
            "alpha": _TIER1_LABEL,
            "beta": _TIER1_LABEL,
            "charlie": _TIER1_LABEL,
            "historian": _TIER2_LABEL,
            "metis": _TIER2_LABEL,
            "empath": _TIER2_LABEL,
            "perceiver": _TIER2_LABEL,
            "echo": _TIER2_LABEL,
            "explorer": _TIER3_LABEL,
            "examiner": _TIER3_LABEL,
            "dreamer": _TIER3_LABEL,
            "coder": _TIER3_LABEL,
            "sentinel": _TIER4_LABEL,
            "sentinel-prime": _TIER4_LABEL,
            "arbiter": _TIER4_LABEL,
            "coordinator": _TIER5_LABEL,
            "nexus": _TIER5_LABEL,
            "catalyst": _TIER5_LABEL,
            "chronos": _TIER5_LABEL,
            "prism": _TIER6_LABEL,
            "habit-forge": _TIER6_LABEL,
            "perceiver-plus": _TIER6_LABEL,
        }
        return tier_mapping.get(agent_id, "Unknown")

    async def setup_channel_subscriptions(self) -> None:
        """Set up channel subscriptions for all agents based on the channel registry.

        If no supervisor or no actors are registered, all subscription setup is
        skipped gracefully with a warning.
        """
        # Guard: no supervisor or no actors → nothing to subscribe
        if self._supervisor is None:
            logger.warning("channel_subscriptions_skipped_no_supervisor")
            return
        if not self._supervisor.actors:
            logger.warning("channel_subscriptions_skipped_no_actors")
            return

        # Guard: no channel registry → no subscription metadata
        if self._channel_registry is None:
            logger.warning("channel_subscriptions_skipped_no_channel_registry")
            return

        # Guard: no event mesh → subscriptions impossible
        if self._event_mesh is None:
            logger.warning("channel_subscriptions_skipped_no_event_mesh")
            return

        # The ChannelRegistry already has default channels set up
        # Subscribe each agent to their designated channels

        # Get all agent IDs
        agent_ids = list(self._supervisor.actors.keys())

        for agent_id in agent_ids:
            # Get channels for this agent
            channels = self._channel_registry.get_subscriptions(agent_id)

            for channel_name in channels:
                # Subscribe to NATS subject
                nats_subject = self._channel_registry.get_nats_subject(channel_name)

                # Create subscription handler
                async def create_callback(aid: str, ch_name: str):
                    async def callback(mesh, subject, data):
                        await self._handle_channel_message(aid, ch_name, data)

                    return callback

                await self._event_mesh.subscribe(
                    subject=nats_subject,
                    callback=await create_callback(agent_id, channel_name),
                )

            logger.debug(
                "agent_channel_subscriptions",
                agent_id=agent_id,
                channels=channels,
            )

    async def _handle_channel_message(
        self, agent_id: str, channel_name: str, message: dict[str, Any]
    ) -> None:
        """Handle incoming channel message for an agent."""
        try:
            # Get the actor
            actor = self._supervisor.actors.get(agent_id)
            if not actor:
                logger.warning("message_for_missing_actor", agent_id=agent_id)
                return

            # Route message to actor mailbox
            from heretek_swarm.actors.base import ActorMessage

            actor_message = ActorMessage(
                sender="channel",
                message_type=message.get("type", "default"),
                content=message.get("content", {}),
                timestamp=message.get("timestamp", ""),
                metadata=message.get("metadata", {}),
            )
            await actor.put_message(actor_message)

            # Record delivery
            if self._channel_registry is not None:
                self._channel_registry.record_message(channel_name, delivered=True)

        except Exception as e:
            logger.error(
                "channel_message_handling_error",
                agent_id=agent_id,
                channel=channel_name,
                error=str(e),
            )
            if self._channel_registry is not None:
                self._channel_registry.record_error(channel_name)
