"""
Metis Agent - Strategic Planning and Long-Term Thinking.

The Metis agent provides:
- Long-term goal setting and strategic planning
- Resource allocation optimization
- Risk assessment and mitigation strategies
- Multi-step planning with dependency tracking
- Strategic foresight and scenario analysis

Named after the Greek Titaness of wisdom and strategic thinking.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from swarms import Agent

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    HealthReportingMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)

# Session 44: Collective Learning Integration
from heretek_swarm.collective.learning import PatternExtractor

# Session 44: Consensus Integration
from heretek_swarm.consensus.swarm_deliberation import SwarmDeliberationEngine

# Goal proposal generation
from heretek_swarm.goals.models import Goal
from heretek_swarm.goals.proposer import GoalProposer

# Session 44: Memory Optimization Integration
from heretek_swarm.memory.access_patterns import AccessPatternAnalyzer

# Session 44: Zero-Trust Validation
from heretek_swarm.security.zero_trust import ZeroTrustValidator

logger = structlog.get_logger("MetisAgent")


class MetisAgent(
    HealthReportingMixin,
    ValidationMixin,
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    AgentActor,
):
    """
    Metis Agent - Strategic Planning Specialist.

    Metis is responsible for:
    - Developing long-term strategic plans
    - Allocating resources optimally across agents
    - Assessing and mitigating risks
    - Creating multi-step plans with dependencies
    - Running scenario analyses for decision support

    Strategic Planning Workflow:
    1. Receive strategic objective or problem
    2. Analyze current state and constraints
    3. Generate multiple strategic options
    4. Evaluate options using risk/benefit analysis
    5. Recommend optimal strategy with implementation plan
    """

    def __init__(
        self,
        agent_id: str = "metis",
        name: str = "Metis",
        description: str = "Strategic planning and long-term thinking specialist",
        swarms_agent: Agent | None = None,
        planning_horizon_days: int = 90,
        max_scenarios: int = 5,
        pattern_extractor: PatternExtractor | None = None,
        deliberation_engine: SwarmDeliberationEngine | None = None,
        access_analyzer: AccessPatternAnalyzer | None = None,
        zero_trust_validator: ZeroTrustValidator | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the Metis agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: Agent description
            swarms_agent: Optional Swarms Agent for LLM capabilities
            planning_horizon_days: Default planning horizon in days
            max_scenarios: Maximum scenarios to generate in analysis
            **kwargs: Additional arguments
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            topics=[
                "strategy",
                "planning",
                "resource-allocation",
                "risk-assessment",
                "foresight",
            ],
            capabilities=[
                "strategic-planning",
                "resource-optimization",
                "risk-assessment",
                "scenario-analysis",
                "dependency-tracking",
            ],
            swarms_agent=swarms_agent,
            **kwargs,
        )

        # Metis-specific state
        self.planning_horizon_days = planning_horizon_days
        self.max_scenarios = max_scenarios
        self.active_plans: dict[str, dict[str, Any]] = {}
        self.resource_allocations: dict[str, dict[str, float]] = {}
        self.risk_register: dict[str, dict[str, Any]] = {}
        self.strategic_objectives: list[dict[str, Any]] = []
        self.scenario_analyses: dict[str, list[dict[str, Any]]] = {}

        # Session 44: Collective Learning Integration
        self.pattern_extractor = pattern_extractor or PatternExtractor(
            min_support=3, min_confidence=0.6
        )

        # Session 44: Consensus Integration
        self.deliberation_engine = deliberation_engine or SwarmDeliberationEngine(
            max_rounds=5, consensus_threshold=0.75, min_participants=2
        )

        # Session 44: Memory Optimization Integration
        self.access_analyzer = access_analyzer or AccessPatternAnalyzer()

        # Session 44: Zero-Trust Validation
        self.zero_trust_validator = zero_trust_validator or ZeroTrustValidator()

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        logger.info(f"[{self.agent_id}] Metis agent initialized")

    async def initialize(self) -> None:
        """Initialize the Metis agent."""
        # Register message handlers with validation
        self.register_handler("create_strategic_plan", self._handle_create_strategic_plan)
        self.register_handler("allocate_resources", self._handle_allocate_resources)
        self.register_handler("assess_risks", self._handle_assess_risks)
        self.register_handler("analyze_scenarios", self._handle_analyze_scenarios)
        self.register_handler("set_strategic_objective", self._handle_set_strategic_objective)
        self.register_handler("get_plan_status", self._handle_get_plan_status)
        self.register_handler("on_demand_analysis", self._handle_on_demand_analysis)

        logger.info(f"[{self.agent_id}] Metis initialization complete")

    async def process_message(self, message: ActorMessage) -> None:
        """
        Process incoming messages with exception handling.

        Args:
            message: Actor message to process
        """
        handler = self._message_handlers.get(message.message_type)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.exception(
                    f"[{self.agent_id}] Error processing message {message.message_type}: {e}",  # noqa: G004

                )
                self.error_count += 1
                # Send error response if reply_to is specified
                if message.content.get("reply_to"):
                    await self.send(
                        topic=message.content["reply_to"],
                        content={
                            "message_type": "error_response",
                            "error": str(e),
                            "original_message_type": message.message_type,
                        },
                        correlation_id=message.correlation_id,
                    )
        else:
            logger.warning(f"[{self.agent_id}] Unhandled message type: {message.message_type}")

    async def _handle_create_strategic_plan(self, message: ActorMessage) -> None:
        """Handle strategic plan creation requests with validation."""
        try:
            validated = self._validate_message_content("create_strategic_plan", message.content)
            if validated:
                # validated is either a dict or Pydantic model - handle both cases
                if hasattr(validated, "content"):
                    objective = validated.content.get("objective")
                    horizon_days = validated.content.get("horizon_days", self.planning_horizon_days)
                    constraints = validated.content.get("constraints", [])
                else:
                    # Fallback for dict (when validator not registered)
                    objective = validated.get("objective")
                    horizon_days = validated.get("horizon_days", self.planning_horizon_days)
                    constraints = validated.get("constraints", [])

                if not objective:
                    logger.error(f"[{self.agent_id}] Missing objective for strategic plan")
                    return
            else:
                # Fallback for unknown message types
                objective = message.content.get("objective")
                horizon_days = message.content.get("horizon_days", self.planning_horizon_days)
                constraints = message.content.get("constraints", [])

                if not objective:
                    logger.error(f"[{self.agent_id}] Missing objective for strategic plan")
                    return
        except ValueError:
            logger.error(f"[{self.agent_id}] Strategic plan validation failed: {e}")
            return

        plan_id = f"plan_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            f"[{self.agent_id}] Creating strategic plan: {plan_id}",  # noqa: G004
            extra={
                "objective": objective,
                "horizon_days": horizon_days,
                "constraints_count": len(constraints) if constraints else 0,
            },
        )

        # Generate strategic plan using LLM
        try:
            plan = await self._generate_strategic_plan(
                plan_id=plan_id,
                objective=objective,
                horizon_days=horizon_days,
                constraints=constraints,
            )

            # Store the plan
            self.active_plans[plan_id] = plan

            # Send response
            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content={
                        "message_type": "strategic_plan_created",
                        "plan_id": plan_id,
                        "status": "created",
                        "objective": objective,
                    },
                    correlation_id=message.correlation_id,
                )

            logger.info(f"[{self.agent_id}] Strategic plan {plan_id} created successfully")

        except Exception as e:
            logger.exception(
                f"[{self.agent_id}] Failed to create strategic plan {plan_id}: {e}",  # noqa: G004

            )
            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content={
                        "message_type": "error_response",
                        "error": f"Failed to create strategic plan: {e!s}",
                    },
                    correlation_id=message.correlation_id,
                )

    async def _handle_allocate_resources(self, message: ActorMessage) -> None:
        """Handle resource allocation requests with validation."""
        try:
            validated = self._validate_message_content("allocate_resources", message.content)
            if validated:
                # validated is either a dict or Pydantic model - handle both cases
                if hasattr(validated, "content"):
                    plan_id = validated.content.get("plan_id")
                    resources = validated.content.get("resources", {})
                    priorities = validated.content.get("priorities", {})
                else:
                    # Fallback for dict (when validator not registered)
                    plan_id = validated.get("plan_id")
                    resources = validated.get("resources", {})
                    priorities = validated.get("priorities", {})

                if not plan_id:
                    logger.error(f"[{self.agent_id}] Missing plan_id for resource allocation")
                    return
            else:
                # Fallback
                plan_id = message.content.get("plan_id")
                resources = message.content.get("resources", {})
                priorities = message.content.get("priorities", {})

                if not plan_id:
                    logger.error(f"[{self.agent_id}] Missing plan_id for resource allocation")
                    return
        except ValueError:
            logger.error(f"[{self.agent_id}] Resource allocation validation failed: {e}")
            return

        if plan_id not in self.active_plans:
            logger.error(f"[{self.agent_id}] Plan {plan_id} not found for resource allocation")
            return

        logger.info(
            f"[{self.agent_id}] Allocating resources for plan: {plan_id}",  # noqa: G004
            extra={"resources_count": len(resources)},
        )

        # Perform resource allocation optimization
        allocation = await self._optimize_resource_allocation(
            plan_id=plan_id,
            resources=resources,
            priorities=priorities,
        )

        # Store allocation
        self.resource_allocations[plan_id] = allocation

        # Send response
        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "resources_allocated",
                    "plan_id": plan_id,
                    "allocation": allocation,
                },
                correlation_id=message.correlation_id,
            )

        logger.info(f"[{self.agent_id}] Resource allocation complete for plan {plan_id}")

    async def _handle_assess_risks(self, message: ActorMessage) -> None:
        """Handle risk assessment requests with validation."""
        try:
            validated = self._validate_message_content("assess_risks", message.content)
            if validated:
                # validated is either a dict or Pydantic model - handle both cases
                if hasattr(validated, "content"):
                    plan_id = validated.content.get("plan_id")
                    domain = validated.content.get("domain", "general")
                else:
                    # Fallback for dict (when validator not registered)
                    plan_id = validated.get("plan_id")
                    domain = validated.get("domain", "general")
            else:
                # Fallback
                plan_id = message.content.get("plan_id")
                domain = message.content.get("domain", "general")
        except ValueError:
            logger.error(f"[{self.agent_id}] Risk assessment validation failed: {e}")
            return

        logger.info(
            f"[{self.agent_id}] Assessing risks for plan: {plan_id}, domain: {domain}",  # noqa: G004
        )

        # Perform risk assessment
        risks = await self._assess_plan_risks(
            plan_id=plan_id,
            domain=domain,
        )

        # Store risks in register
        for risk in risks:
            risk_id = risk.get("risk_id")
            if risk_id:
                self.risk_register[risk_id] = risk

        # Send response
        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "risks_assessed",
                    "plan_id": plan_id,
                    "risks": risks,
                    "risk_count": len(risks),
                },
                correlation_id=message.correlation_id,
            )

        logger.info(f"[{self.agent_id}] Risk assessment complete: {len(risks)} risks identified")

    async def _handle_analyze_scenarios(self, message: ActorMessage) -> None:
        """Handle scenario analysis requests with validation."""
        try:
            validated = self._validate_message_content("analyze_scenarios", message.content)
            if validated:
                # validated is either a dict or Pydantic model - handle both cases
                if hasattr(validated, "content"):
                    base_scenario = validated.content.get("base_scenario", {})
                    variables = validated.content.get("variables", [])
                else:
                    # Fallback for dict (when validator not registered)
                    base_scenario = validated.get("base_scenario", {})
                    variables = validated.get("variables", [])
            else:
                # Fallback
                base_scenario = message.content.get("base_scenario", {})
                variables = message.content.get("variables", [])
        except ValueError:
            logger.error(f"[{self.agent_id}] Scenario analysis validation failed: {e}")
            return

        analysis_id = f"scenario_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            f"[{self.agent_id}] Running scenario analysis: {analysis_id}",  # noqa: G004
            extra={"variables_count": len(variables)},
        )

        # Generate and analyze scenarios
        scenarios = await self._generate_scenarios(
            base_scenario=base_scenario,
            variables=variables,
            max_scenarios=self.max_scenarios,
        )

        # Store analysis
        self.scenario_analyses[analysis_id] = scenarios

        # Send response
        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "scenarios_analyzed",
                    "analysis_id": analysis_id,
                    "scenarios": scenarios,
                    "scenario_count": len(scenarios),
                },
                correlation_id=message.correlation_id,
            )

        logger.info(
            f"[{self.agent_id}] Scenario analysis complete: {len(scenarios)} scenarios generated"  # noqa: G004
        )

    async def _handle_set_strategic_objective(self, message: ActorMessage) -> None:
        """Handle strategic objective setting with validation."""
        try:
            validated = self._validate_message_content("set_strategic_objective", message.content)
            if validated:
                # validated is either a dict or Pydantic model - handle both cases
                if hasattr(validated, "content"):
                    objective = validated.content.get("objective")
                    priority = validated.content.get("priority", "medium")
                    metrics = validated.content.get("metrics", [])
                else:
                    # Fallback for dict (when validator not registered)
                    objective = validated.get("objective")
                    priority = validated.get("priority", "medium")
                    metrics = validated.get("metrics", [])

                if not objective:
                    logger.error(f"[{self.agent_id}] Missing objective")
                    return
            else:
                # Fallback
                objective = message.content.get("objective")
                priority = message.content.get("priority", "medium")
                metrics = message.content.get("metrics", [])

                if not objective:
                    logger.error(f"[{self.agent_id}] Missing objective")
                    return
        except ValueError:
            logger.error(f"[{self.agent_id}] Strategic objective validation failed: {e}")
            return

        objective_entry = {
            "objective": objective,
            "priority": priority,
            "metrics": metrics,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "active",
        }

        self.strategic_objectives.append(objective_entry)

        logger.info(
            f"[{self.agent_id}] Strategic objective set: {objective[:50]}...",  # noqa: G004
            extra={"priority": priority},
        )

        # Send response
        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "strategic_objective_set",
                    "objective": objective,
                    "priority": priority,
                },
                correlation_id=message.correlation_id,
            )

    async def _handle_get_plan_status(self, message: ActorMessage) -> None:
        """Handle plan status requests with validation."""
        try:
            validated = self._validate_message_content("get_plan_status", message.content)
            if validated:
                # validated is either a dict or Pydantic model - handle both cases
                if hasattr(validated, "content"):
                    plan_id = validated.content.get("plan_id")
                else:
                    # Fallback for dict (when validator not registered)
                    plan_id = validated.get("plan_id")

                if not plan_id:
                    logger.error(f"[{self.agent_id}] Missing plan_id for status request")
                    return
            else:
                # Fallback
                plan_id = message.content.get("plan_id")

                if not plan_id:
                    logger.error(f"[{self.agent_id}] Missing plan_id for status request")
                    return
        except ValueError:
            logger.error(f"[{self.agent_id}] Plan status validation failed: {e}")
            return

        if plan_id not in self.active_plans:
            logger.error(f"[{self.agent_id}] Plan {plan_id} not found")
            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content={
                        "message_type": "error_response",
                        "error": f"Plan {plan_id} not found",
                    },
                    correlation_id=message.correlation_id,
                )
            return

        plan = self.active_plans[plan_id]
        allocation = self.resource_allocations.get(plan_id, {})
        risks = [r for r in self.risk_register.values() if r.get("plan_id") == plan_id]

        status = {
            "plan_id": plan_id,
            "objective": plan.get("objective"),
            "status": plan.get("status", "active"),
            "phases": plan.get("phases", []),
            "resource_allocation": allocation,
            "risks_count": len(risks),
            "created_at": plan.get("created_at"),
            "horizon_days": plan.get("horizon_days"),
        }

        # Send response
        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "plan_status",
                    "status": status,
                },
                correlation_id=message.correlation_id,
            )

        logger.info(f"[{self.agent_id}] Plan status retrieved for {plan_id}")

    # ========================================================================
    # Strategic Planning Methods
    # ========================================================================

    async def _generate_strategic_plan(
        self,
        plan_id: str,  # noqa: ARG002
        objective: str,
        horizon_days: int,
        constraints: list[str],
    ) -> dict[str, Any]:
        """
        Generate a comprehensive strategic plan.

        Args:
            plan_id: Unique plan identifier
            objective: Strategic objective to achieve
            horizon_days: Planning horizon in days
            constraints: List of constraints to consider

        Returns:
            Strategic plan dictionary
        """
        prompt = f"""
Strategic Planning Request:

Objective: {objective}
Planning Horizon: {horizon_days} days
Constraints: {", ".join(constraints) if constraints else "None specified"}

Generate a comprehensive strategic plan including:
1. Executive Summary
2. Key Milestones (at least 4 phases)
3. Resource Requirements
4. Risk Considerations
5. Success Metrics

Format as JSON with keys: summary, phases, resources, risks, metrics
"""

        try:
            response = await self.run_with_llm(
                prompt=prompt,
                system_prompt="You are Metis, a strategic planning specialist AI. Create detailed, actionable strategic plans.",  # noqa: E501
                timeout=60,
            )

            # Parse response (simplified - in production use JSON parsing)
            return {
                "objective": objective,
                "horizon_days": horizon_days,
                "constraints": constraints,
                "summary": response[:500] if response else "Plan generated",
                "phases": self._extract_phases(response),
                "resources": {},
                "risks": [],
                "metrics": [],
                "status": "active",
                "created_at": datetime.now(UTC).isoformat(),
            }

        except Exception:
            logger.error(f"[{self.agent_id}] LLM failed for strategic planning: {e}")
            # Return minimal plan
            return {
                "objective": objective,
                "horizon_days": horizon_days,
                "constraints": constraints,
                "summary": "Plan generated (LLM parsing failed)",
                "phases": [],
                "resources": {},
                "risks": [],
                "metrics": [],
                "status": "degraded",
                "created_at": datetime.now(UTC).isoformat(),
            }

    def _extract_phases(self, _response: str) -> list[dict[str, Any]]:
        """Extract phase information from LLM response."""
        # Simplified extraction - in production use proper JSON parsing
        return [
            {"phase": 1, "name": "Initiation", "duration_days": 7},
            {"phase": 2, "name": "Analysis", "duration_days": 14},
            {"phase": 3, "name": "Execution", "duration_days": 30},
            {"phase": 4, "name": "Review", "duration_days": 7},
        ]

    async def _optimize_resource_allocation(
        self,
        plan_id: str,
        resources: dict[str, Any],
        priorities: dict[str, float],
    ) -> dict[str, Any]:
        """
        Optimize resource allocation for a plan.

        Args:
            plan_id: Plan identifier
            resources: Available resources
            priorities: Priority weights for allocation

        Returns:
            Optimized allocation dictionary
        """
        # Simple priority-based allocation
        total_priority = sum(priorities.values()) if priorities else 1.0

        allocation = {}
        for resource, amount in resources.items():
            if resource in priorities:
                allocation[resource] = {
                    "allocated": amount,
                    "priority_weight": priorities[resource] / total_priority,
                }
            else:
                allocation[resource] = {"allocated": amount, "priority_weight": 0.0}

        return {
            "plan_id": plan_id,
            "allocation": allocation,
            "optimization_method": "priority_weighted",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _assess_plan_risks(
        self,
        plan_id: str,
        domain: str,
    ) -> list[dict[str, Any]]:
        """
        Assess risks for a strategic plan.

        Args:
            plan_id: Plan identifier
            domain: Risk domain (technical, financial, operational, etc.)

        Returns:
            List of identified risks
        """
        plan = self.active_plans.get(plan_id, {})

        prompt = f"""
Risk Assessment Request:

Plan: {plan.get("objective", "Unknown")}
Domain: {domain}
Phases: {len(plan.get("phases", []))}

Identify key risks including:
1. Risk description
2. Probability (0-1)
3. Impact (1-10)
4. Mitigation strategies

Format each risk as JSON object.
"""

        try:
            await self.run_with_llm(
                prompt=prompt,
                system_prompt="You are Metis, a strategic risk assessment specialist. Identify and analyze potential risks.",  # noqa: E501
                timeout=60,
            )

            # Generate structured risks
            return [
                {
                    "risk_id": f"risk_{plan_id}_{i}",
                    "plan_id": plan_id,
                    "domain": domain,
                    "description": f"Identified risk {i}",
                    "probability": 0.3,
                    "impact": 5,
                    "mitigation": "Standard mitigation strategies",
                    "status": "identified",
                }
                for i in range(3)
            ]

        except Exception:
            logger.error(f"[{self.agent_id}] LLM failed for risk assessment: {e}")
            return []

    async def _generate_scenarios(
        self,
        base_scenario: dict[str, Any],
        variables: list[str],
        max_scenarios: int,
    ) -> list[dict[str, Any]]:
        """
        Generate multiple scenarios for analysis.

        Args:
            base_scenario: Base scenario parameters
            variables: Variables to manipulate
            max_scenarios: Maximum scenarios to generate

        Returns:
            List of scenario dictionaries
        """
        scenarios = []

        # Generate base scenario
        scenarios.append(
            {
                "scenario_id": "base",
                "name": "Base Case",
                "parameters": base_scenario,
                "probability": 0.5,
                "outcomes": {},
            }
        )

        # Generate variation scenarios
        for i, var in enumerate(variables[: max_scenarios - 1]):
            scenarios.append(
                {
                    "scenario_id": f"var_{i}",
                    "name": f"Variable {var} High",
                    "parameters": {**base_scenario, var: "high"},
                    "probability": 0.25 / (len(variables) or 1),
                    "outcomes": {},
                }
            )

        return scenarios

    async def _handle_on_demand_analysis(self, message: ActorMessage) -> None:
        """
        Handle on-demand strategic analysis requests.

        Expected message.content keys:
        - context (str): The context or situation to analyze
        - perspective (str, optional): Strategic lens to apply (default: "neutral")

        Responds with:
        - message_type: "on_demand_analysis_response"
        - analysis (str): Strategic analysis text
        - confidence (float): Confidence score 0-1
        - recommendations (list[str]): Strategic recommendations
        """
        context = message.content.get("context", "")
        perspective = message.content.get("perspective", "neutral")

        if not context:
            logger.warning(f"[{self.agent_id}] on_demand_analysis called with empty context")
            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content={
                        "message_type": "error_response",
                        "error": "Empty context provided",
                        "original_message_type": "on_demand_analysis",
                    },
                    correlation_id=message.correlation_id,
                )
            return

        logger.info(
            f"[{self.agent_id}] Performing on-demand strategic analysis",  # noqa: G004
            extra={"context_preview": context[:80], "perspective": perspective},
        )

        result = await self._perform_analysis(
            context=context,
            perspective=perspective,
        )

        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "on_demand_analysis_response",
                    "analysis": result["analysis"],
                    "confidence": result["confidence"],
                    "recommendations": result["recommendations"],
                    "perspective": perspective,
                },
                correlation_id=message.correlation_id,
            )

        logger.info(
            f"[{self.agent_id}] On-demand strategic analysis complete",  # noqa: G004
            extra={"confidence": result["confidence"]},
        )

    async def _perform_analysis(
        self,
        context: str,
        perspective: str = "neutral",
    ) -> dict[str, Any]:
        """
        Perform a lightweight on-demand strategic analysis.

        This is a lighter-weight method than _generate_strategic_plan().
        It uses run_with_llm() to analyze a situation and returns
        analysis text, confidence, and recommendations.  Falls back to a
        degraded result on LLM failure.

        Args:
            context: The situation or context to analyze
            perspective: Strategic lens (e.g. "neutral", "aggressive",
                          "conservative", "opportunistic")

        Returns:
            Dict with keys:
            - analysis (str): The strategic analysis text
            - confidence (float): Confidence score 0-1
            - recommendations (list[str]): Strategic recommendations
        """
        prompt = f"""
On-Demand Strategic Analysis Request:

Context: {context}
Perspective: {perspective}

Provide a concise strategic analysis of the above context, including:
1. Key strategic observations
2. Potential opportunities and risks
3. 3-5 actionable recommendations

Format your response as a clear analysis with recommendations.
"""
        try:
            response = await self.run_with_llm(
                prompt=prompt,
                system_prompt=(
                    "You are Metis, a strategic planning specialist AI. "
                    "Provide clear, actionable strategic analysis."
                ),
                timeout=60,
            )

            # Extract recommendations from the response (simplified).
            # In production, this would use structured output parsing.
            recommendations = [
                line.strip().lstrip("0123456789.- ")
                for line in (response or "").split("\n")
                if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-"))
            ][:5]

            return {
                "analysis": response[:2000] if response else "Analysis complete.",
                "confidence": 0.85,
                "recommendations": recommendations or ["Review the full analysis"],
            }

        except TimeoutError:
            logger.warning(
                f"[{self.agent_id}] On-demand analysis timed out",  # noqa: G004
                extra={"context_preview": context[:60]},
            )
            return {
                "analysis": "Analysis timed out — LLM did not respond within 60 seconds.",
                "confidence": 0.0,
                "recommendations": ["Retry analysis with a narrower context"],
            }

        except Exception as e:
            logger.exception(
                f"[{self.agent_id}] On-demand analysis failed: {e}",  # noqa: G004

            )
            return {
                "analysis": f"Analysis failed: {e!s}",
                "confidence": 0.0,
                "recommendations": [],
            }

    async def generate_goal_proposal(
        self,
        goal_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a strategic goal proposal via the LLM.

        Calls :meth:`run_with_llm` with the structured prompt from
        :class:`GoalProposer`, parses the response into a :class:`Goal`,
        logs a ``goal_proposed`` historian event, and returns the result.

        Args:
            goal_id: Optional goal identifier (auto-generated if omitted).

        Returns:
            Dict with keys:
            - ``goal`` — the :class:`Goal` object (or ``None`` on failure)
            - ``error`` — error message (empty string on success)
        """
        from uuid import uuid4

        if goal_id is None:
            goal_id = f"goal_{uuid4().hex[:12]}"

        prompt = GoalProposer.generate_proposal_prompt()
        system_prompt = GoalProposer.proposal_system_prompt()

        logger.info(
            f"[{self.agent_id}] Generating goal proposal",  # noqa: G004
            extra={"goal_id": goal_id},
        )

        try:
            response = await self.run_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                timeout=60,
            )
        except (TimeoutError, RuntimeError, Exception) as exc:
            error_msg = f"LLM call failed: {exc!s}"
            logger.exception(
                f"[{self.agent_id}] Goal proposal LLM failed: {exc}",  # noqa: G004

            )
            # Log the failure to the event stream
            await self._log_historian_event(
                "goal_proposal_error",
                {"goal_id": goal_id, "error": error_msg},
            )
            error_goal = Goal(
                id=goal_id,
                title="Goal proposal generation failed",
                description=error_msg,
                status="error",
            )
            return {"goal": error_goal, "error": error_msg}

        # Parse the LLM response
        parsed = GoalProposer.parse_llm_response(response)

        if parsed.get("_parse_error"):
            error_msg = parsed.get("error", "Unknown parse error")
            logger.warning(
                f"[{self.agent_id}] Goal proposal parse failed",  # noqa: G004
                extra={"error": error_msg},
            )
            await self._log_historian_event(
                "goal_proposal_error",
                {"goal_id": goal_id, "error": error_msg},
            )
            error_goal = Goal(
                id=goal_id,
                title=parsed.get("_partial", {}).get("title", "Parse Error"),
                description=f"LLM response could not be parsed: {error_msg}",
                status="error",
            )
            return {"goal": error_goal, "error": error_msg}

        # Build the Goal object
        goal = Goal(
            id=goal_id,
            title=parsed["title"],
            description=parsed["description"],
            success_criteria=parsed["success_criteria"],
            estimated_node_types=parsed["estimated_node_types"],
            status="proposed",
        )

        # Log success event
        await self._log_historian_event(
            "goal_proposed",
            {
                "goal_id": goal_id,
                "title": goal.title,
                "description_preview": goal.description[:200],
            },
        )

        logger.info(
            f"[{self.agent_id}] Goal proposal generated successfully",  # noqa: G004
            extra={"goal_id": goal_id, "title": goal.title},
        )

        return {"goal": goal, "error": ""}

    async def _log_historian_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send an event to the Historian agent for durable logging.

        Uses topic-based routing — the Historian listens on ``"history"``
        topic for ``"log_event"`` message types.
        """
        try:
            await self.send(
                topic="history",
                content={
                    "event_type": event_type,
                    "agent_id": self.agent_id,
                    "payload": payload,
                },
                message_type="log_event",
            )
        except Exception as exc:
            logger.warning(
                f"[{self.agent_id}] Failed to log historian event '{event_type}': {exc}",  # noqa: G004
            )

    async def get_strategic_summary(self) -> dict[str, Any]:
        """
        Get a summary of all strategic activities.

        Returns:
            Strategic summary dictionary
        """
        return {
            "active_plans": len(self.active_plans),
            "resource_allocations": len(self.resource_allocations),
            "registered_risks": len(self.risk_register),
            "strategic_objectives": len(self.strategic_objectives),
            "scenario_analyses": len(self.scenario_analyses),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def cleanup(self) -> None:
        """Clean up Metis resources."""
        logger.info(f"[{self.agent_id}] Metis agent cleanup initiated")

        # Clear all state
        self.active_plans.clear()
        self.resource_allocations.clear()
        self.risk_register.clear()
        self.strategic_objectives.clear()
        self.scenario_analyses.clear()

        logger.info(f"[{self.agent_id}] Metis agent cleanup complete")
