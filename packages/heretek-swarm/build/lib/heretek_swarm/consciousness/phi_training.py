"""
Phi Training Environment - IIT Phi Optimization for Agent Training.

This module implements training environments for optimizing Phi (Integrated Information)
in agent swarms, based on DeepMind OpenSpiel multi-agent training patterns.

Features:
- Create training scenarios for Phi optimization
- Implement Phi calculation as reward signal
- Track Phi changes over training episodes
- Export training metrics to Prometheus
- Support both online (live) and offline (replay) training

Training Scenarios:
- Communication efficiency: Maximize information integration between agents
- Decision coherence: Align agent decisions for higher collective Phi
- Task collaboration: Optimize collaborative task execution for Phi gain
- Consensus formation: Train agents to reach consensus while maintaining Phi

Author: Heretek Swarm Collective
Date: 2026-04-07
Version: 1.0.0
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from .iit_phi import PhiCalculator

logger = structlog.get_logger("PhiTrainingEnvironment")


class TrainingMode(StrEnum):
    """Training execution modes."""

    ONLINE = "online"  # Live training with real agents
    OFFLINE = "offline"  # Replay training from recorded data
    SIMULATION = "simulation"  # Simulated agent training


class ScenarioType(StrEnum):
    """Types of training scenarios."""

    COMMUNICATION = "communication"
    DECISION_COHERENCE = "decision_coherence"
    TASK_COLLABORATION = "task_collaboration"
    CONSENSUS_FORMATION = "consensus_formation"
    INFORMATION_INTEGRATION = "information_integration"


@dataclass
class TrainingEpisode:
    """
    Represents a single training episode.

    Attributes:
        episode_id: Unique episode identifier
        scenario_type: Type of scenario trained
        start_phi: Phi value at episode start
        end_phi: Phi value at episode end
        phi_delta: Change in Phi (reward signal)
        steps: Number of steps in episode
        duration_seconds: Episode duration
        metadata: Additional episode data
        timestamp: Episode creation time
    """

    episode_id: str
    scenario_type: ScenarioType
    start_phi: float
    end_phi: float
    phi_delta: float
    steps: int
    duration_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "episode_id": self.episode_id,
            "scenario_type": self.scenario_type.value,
            "start_phi": self.start_phi,
            "end_phi": self.end_phi,
            "phi_delta": self.phi_delta,
            "steps": self.steps,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class TrainingScenario:
    """
    Defines a training scenario for Phi optimization.

    Attributes:
        scenario_id: Unique scenario identifier
        scenario_type: Type of scenario
        description: Scenario description
        agent_count: Number of agents in scenario
        initial_state: Initial system state
        objectives: Training objectives
        max_steps: Maximum steps per episode
        phi_target: Target Phi value (optional)
    """

    scenario_id: str
    scenario_type: ScenarioType
    description: str
    agent_count: int
    initial_state: dict[str, Any]
    objectives: list[str]
    max_steps: int = 100
    phi_target: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type.value,
            "description": self.description,
            "agent_count": self.agent_count,
            "initial_state": self.initial_state,
            "objectives": self.objectives,
            "max_steps": self.max_steps,
            "phi_target": self.phi_target,
        }


@dataclass
class TrainingResult:
    """
    Result from a training episode.

    Attributes:
        episode: Episode data
        total_reward: Cumulative reward
        avg_phi: Average Phi during episode
        max_phi: Maximum Phi achieved
        convergence_step: Step where Phi converged (if applicable)
        success: Whether training was successful
        metrics: Additional training metrics
    """

    episode: TrainingEpisode
    total_reward: float
    avg_phi: float
    max_phi: float
    convergence_step: int | None
    success: bool
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "episode": self.episode.to_dict(),
            "total_reward": self.total_reward,
            "avg_phi": self.avg_phi,
            "max_phi": self.max_phi,
            "convergence_step": self.convergence_step,
            "success": self.success,
            "metrics": self.metrics,
        }


class AgentActor:
    """
    Abstract agent actor for training.

    Represents an agent that can participate in Phi training scenarios.
    """

    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state: dict[str, Any] = {}
        self.message_history: list[dict[str, Any]] = []

    async def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        """
        Take an action based on observation using active inference.

        Args:
            observation: Current environment observation

        Returns:
            Action dictionary with phi optimization
        """
        # Active inference: select action that minimizes expected free energy
        current_phi = self.state.get("current_phi", 0.0)
        available_actions = observation.get("available_actions", ["observe", "adapt", "broadcast"])

        # Select action that maximizes phi (integrated information)
        best_action = "observe"
        best_phi = current_phi

        for action in available_actions:
            # Simulate phi gain for each action
            simulated_phi = self._simulate_phi_gain(action, observation)
            if simulated_phi > best_phi:
                best_phi = simulated_phi
                best_action = action

        # Update state with selected action
        self.state["last_action"] = best_action
        self.state["current_phi"] = best_phi

        return {
            "action": best_action,
            "phi_gain": best_phi - current_phi,
            "reasoning": f"Selected {best_action} for phi optimization",
        }

    def _simulate_phi_gain(self, action: str, observation: dict[str, Any]) -> float:
        """Simulate expected phi gain from an action."""
        base_phi = self.state.get("current_phi", 0.0)

        # Action-specific phi contributions
        phi_gains = {
            "observe": 0.05,  # Information gathering
            "adapt": 0.10,  # System adaptation increases integration
            "broadcast": 0.08,  # Sharing increases collective phi
            "deliberate": 0.12,  # Consensus building
            "learn": 0.07,  # Pattern learning
        }

        gain = phi_gains.get(action, 0.02)

        # Factor in observation quality
        observation_quality = observation.get("novelty", 0.5)
        return base_phi + (gain * observation_quality)

    def get_state(self) -> dict[str, Any]:
        """Get current agent state."""
        return self.state.copy()

    def reset(self) -> None:
        """Reset agent state for new episode."""
        self.state = {}
        self.message_history = []


class PhiTrainingEnvironment:
    """
    Training environment for Phi optimization.

    This class provides the infrastructure for training agents to maximize
    integrated information (Phi) in swarm systems. It implements multiple
    training scenarios and provides reward signals based on Phi changes.

    Example:
        ```python
        # Create training environment
        env = PhiTrainingEnvironment()

        # Define agents
        agents = [AgentActor(f"agent_{i}", "default") for i in range(5)]

        # Create scenario
        scenario = TrainingScenario(
            scenario_id="comm_train_001",
            scenario_type=ScenarioType.COMMUNICATION,
            description="Communication efficiency training",
            agent_count=5,
            initial_state={},
            objectives=["maximize_phi", "minimize_messages"],
        )

        # Run training episode
        result = await env.run_episode(agents, scenario)
        logger.info("phi_training_episode_delta", phi_delta=result.episode.phi_delta)
        ```
    """

    def __init__(
        self,
        phi_calculator: PhiCalculator | None = None,
        training_mode: TrainingMode = TrainingMode.SIMULATION,
    ):
        """
        Initialize the training environment.

        Args:
            phi_calculator: Optional pre-configured Phi calculator
            training_mode: Mode of training (online, offline, simulation)
        """
        self.phi_calculator = phi_calculator or PhiCalculator()
        self.training_mode = training_mode

        # Episode tracking
        self.episode_history: list[TrainingEpisode] = []
        self.current_episode: TrainingEpisode | None = None

        # Training metrics
        self.metrics = {
            "total_episodes": 0,
            "successful_episodes": 0,
            "total_phi_improvement": 0.0,
            "avg_phi_improvement": 0.0,
            "best_phi_achieved": 0.0,
            "avg_episode_duration": 0.0,
        }

        # Rate limiting
        self._episode_cooldown_seconds = 1.0
        self._last_episode_time: float = 0.0
        self._episodes_in_window: list[float] = []
        self._max_episodes_per_minute = 30

        logger.info(
            "PhiTrainingEnvironment initialized",
            extra={
                "training_mode": training_mode.value,
            },
        )

    async def run_episode(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,
    ) -> TrainingResult:
        """
        Run a single training episode.

        Args:
            agents: List of agent actors
            scenario: Training scenario definition

        Returns:
            TrainingResult with episode data and metrics
        """
        # Rate limiting check
        self._check_rate_limit()

        episode_id = f"ep_{uuid.uuid4()}"
        start_time = time.time()

        # Calculate initial Phi
        initial_state = self._build_system_state(agents, scenario.initial_state)
        initial_phi_result = self.phi_calculator.calculate_phi(initial_state)
        start_phi = initial_phi_result.phi

        logger.info(
            "episode_started",
            episode_id=episode_id,
            scenario=scenario.scenario_type.value,
            start_phi=start_phi,
        )

        # Track Phi values during episode
        phi_values: list[float] = [start_phi]
        rewards: list[float] = []
        convergence_step: int | None = None

        # Run episode steps
        for step in range(scenario.max_steps):
            # Execute scenario-specific step
            step_result = await self._execute_step(agents, scenario, step)

            # Calculate Phi after step
            current_state = self._build_system_state(agents, step_result.get("state", {}))
            phi_result = self.phi_calculator.calculate_phi(current_state)
            current_phi = phi_result.phi
            phi_values.append(current_phi)

            # Calculate reward
            reward = self.calculate_phi_reward(phi_values[-2], current_phi)
            rewards.append(reward)

            # Check for convergence
            if convergence_step is None and len(phi_values) >= 5:
                recent_variance = self._calculate_variance(phi_values[-5:])
                if recent_variance < 0.001:
                    convergence_step = step

            # Check for early termination
            if scenario.phi_target and current_phi >= scenario.phi_target:
                logger.info(
                    "phi_target_reached",
                    episode_id=episode_id,
                    phi=current_phi,
                    target=scenario.phi_target,
                )
                break

        # Calculate final Phi
        final_state = self._build_system_state(agents, {})
        final_phi_result = self.phi_calculator.calculate_phi(final_state)
        end_phi = final_phi_result.phi

        # Create episode record
        duration = time.time() - start_time
        episode = TrainingEpisode(
            episode_id=episode_id,
            scenario_type=scenario.scenario_type,
            start_phi=start_phi,
            end_phi=end_phi,
            phi_delta=end_phi - start_phi,
            steps=len(phi_values),
            duration_seconds=duration,
            metadata={
                "scenario_id": scenario.scenario_id,
                "agent_count": len(agents),
                "convergence_step": convergence_step,
            },
        )

        # Calculate result metrics
        total_reward = sum(rewards)
        avg_phi = sum(phi_values) / len(phi_values)
        max_phi = max(phi_values)
        success = end_phi > start_phi

        result = TrainingResult(
            episode=episode,
            total_reward=total_reward,
            avg_phi=avg_phi,
            max_phi=max_phi,
            convergence_step=convergence_step,
            success=success,
            metrics={
                "phi_values": phi_values,
                "rewards": rewards,
                "final_phi_result": final_phi_result.to_dict(),
            },
        )

        # Store episode
        self.episode_history.append(episode)
        self._update_metrics(result)

        logger.info(
            "episode_completed",
            episode_id=episode_id,
            phi_delta=episode.phi_delta,
            success=success,
        )

        return result

    def calculate_phi_reward(self, before: float, after: float) -> float:
        """
        Calculate reward based on Phi change.

        Reward is designed to encourage Phi improvement while penalizing
        large negative changes.

        Args:
            before: Phi value before action
            after: Phi value after action

        Returns:
            Reward value
        """
        delta = after - before

        # Base reward is the Phi delta
        reward = delta

        # Bonus for positive changes
        if delta > 0:
            reward += delta * 0.5  # 50% bonus

        # Penalty for large negative changes
        if delta < -0.1:
            reward -= abs(delta) * 0.5  # Additional penalty

        return reward

    def export_metrics(self) -> dict[str, float]:
        """
        Export training metrics for Prometheus.

        Returns:
            Dictionary of metrics
        """
        return self.metrics.copy()

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = [
            "# HELP heretek_phi_training_episodes_total Total training episodes",
            "# TYPE heretek_phi_training_episodes_total counter",
            f"heretek_phi_training_episodes_total {self.metrics['total_episodes']}",
            "",
            "# HELP heretek_phi_training_success_total Successful training episodes",
            "# TYPE heretek_phi_training_success_total counter",
            f"heretek_phi_training_success_total {self.metrics['successful_episodes']}",
            "",
            "# HELP heretek_phi_training_avg_improvement Average Phi improvement per episode",
            "# TYPE heretek_phi_training_avg_improvement gauge",
            f"heretek_phi_training_avg_improvement {self.metrics['avg_phi_improvement']}",
            "",
            "# HELP heretek_phi_training_best_phi Best Phi achieved in training",
            "# TYPE heretek_phi_training_best_phi gauge",
            f"heretek_phi_training_best_phi {self.metrics['best_phi_achieved']}",
            "",
            "# HELP heretek_phi_training_avg_duration Average episode duration in seconds",
            "# TYPE heretek_phi_training_avg_duration gauge",
            f"heretek_phi_training_avg_duration {self.metrics['avg_episode_duration']}",
            "",
        ]

        return "\n".join(lines)

    def get_episode_history(self, limit: int = 100) -> list[TrainingEpisode]:
        """
        Get recent episode history.

        Args:
            limit: Maximum episodes to return

        Returns:
            List of TrainingEpisode objects
        """
        return self.episode_history[-limit:]

    def get_training_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive training statistics.

        Returns:
            Dictionary of statistics
        """
        if not self.episode_history:
            return {"episodes": 0}

        phi_deltas = [ep.phi_delta for ep in self.episode_history]

        return {
            "total_episodes": len(self.episode_history),
            "successful_episodes": self.metrics["successful_episodes"],
            "success_rate": self.metrics["successful_episodes"] / max(len(self.episode_history), 1),
            "phi_improvement": {
                "total": self.metrics["total_phi_improvement"],
                "average": self.metrics["avg_phi_improvement"],
                "best": max(phi_deltas) if phi_deltas else 0,
                "worst": min(phi_deltas) if phi_deltas else 0,
            },
            "best_phi_achieved": self.metrics["best_phi_achieved"],
            "avg_duration_seconds": self.metrics["avg_episode_duration"],
        }

    def _build_system_state(
        self,
        agents: list[AgentActor],
        additional_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build system state for Phi calculation.

        Args:
            agents: List of agent actors
            additional_state: Additional state data

        Returns:
            System state dictionary
        """
        elements = [agent.agent_id for agent in agents]

        # Build connectivity based on agent communication
        connectivity: dict[str, dict[str, float]] = {}
        for agent in agents:
            connectivity[agent.agent_id] = {}
            for other in agents:
                if other.agent_id != agent.agent_id:
                    # Connection strength based on message history
                    connection_strength = self._calculate_connection_strength(agent, other)
                    connectivity[agent.agent_id][other.agent_id] = connection_strength

        # Build current state from agent states
        current_state = {}
        for agent in agents:
            agent_state = agent.get_state()
            current_state[agent.agent_id] = agent_state.get("activation", 0.5)

        # Add additional state
        current_state.update(additional_state)

        return {
            "system_id": f"training_{uuid.uuid4()}",
            "elements": elements,
            "connectivity": connectivity,
            "current_state": current_state,
        }

    def _calculate_connection_strength(
        self,
        agent1: AgentActor,
        agent2: AgentActor,
    ) -> float:
        """
        Calculate connection strength between two agents.

        Args:
            agent1: First agent
            agent2: Second agent

        Returns:
            Connection strength (0.0-1.0)
        """
        # Base strength on message exchange frequency
        messages_between = sum(
            1 for msg in agent1.message_history if msg.get("recipient") == agent2.agent_id
        )

        # Normalize to 0.0-1.0
        strength = min(1.0, messages_between / 10.0)

        # Ensure minimum connectivity for training
        return max(0.1, strength)

    async def _execute_step(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,
        step: int,
    ) -> dict[str, Any]:
        """
        Execute a single training step.

        Args:
            agents: List of agent actors
            scenario: Training scenario
            step: Current step number

        Returns:
            Step result dictionary
        """
        # Scenario-specific execution
        if scenario.scenario_type == ScenarioType.COMMUNICATION:
            return await self._execute_communication_step(agents, scenario, step)
        if scenario.scenario_type == ScenarioType.DECISION_COHERENCE:
            return await self._execute_decision_coherence_step(agents, scenario, step)
        if scenario.scenario_type == ScenarioType.TASK_COLLABORATION:
            return await self._execute_task_collaboration_step(agents, scenario, step)
        if scenario.scenario_type == ScenarioType.CONSENSUS_FORMATION:
            return await self._execute_consensus_formation_step(agents, scenario, step)
        return await self._execute_generic_step(agents, scenario, step)

    async def _execute_communication_step(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,  # noqa: ARG002
        step: int,
    ) -> dict[str, Any]:
        """Execute communication efficiency training step."""
        # Simulate message passing between agents
        for agent in agents:
            observation = {"step": step, "agents": len(agents)}
            action = await agent.act(observation)

            # Record message in history
            if "message" in action:
                for other in agents:
                    if other.agent_id != agent.agent_id:
                        agent.message_history.append(
                            {
                                "sender": agent.agent_id,
                                "recipient": other.agent_id,
                                "content": action["message"],
                                "step": step,
                            }
                        )

        return {"state": {}}

    async def _execute_decision_coherence_step(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,
        step: int,
    ) -> dict[str, Any]:
        """Execute decision coherence training step."""
        decisions = []
        for agent in agents:
            observation = {"step": step, "scenario": scenario.scenario_type.value}
            action = await agent.act(observation)
            if "decision" in action:
                decisions.append(action["decision"])

        # Calculate coherence
        coherence = len(set(decisions)) / len(decisions) if decisions else 0

        return {"state": {"coherence": coherence}}

    async def _execute_task_collaboration_step(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,  # noqa: ARG002
        step: int,
    ) -> dict[str, Any]:
        """Execute task collaboration training step."""
        task_progress = 0.0
        for agent in agents:
            observation = {"step": step, "task_progress": task_progress}
            action = await agent.act(observation)
            task_progress += action.get("contribution", 0.1)

        return {"state": {"task_progress": min(1.0, task_progress)}}

    async def _execute_consensus_formation_step(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,  # noqa: ARG002
        step: int,
    ) -> dict[str, Any]:
        """Execute consensus formation training step."""
        positions = []
        for agent in agents:
            observation = {"step": step}
            action = await agent.act(observation)
            positions.append(action.get("position", 0.5))

        # Calculate consensus (inverse of variance)
        avg_position = sum(positions) / len(positions)
        variance = sum((p - avg_position) ** 2 for p in positions) / len(positions)
        consensus = 1.0 - min(1.0, variance * 4)

        return {"state": {"consensus": consensus}}

    async def _execute_generic_step(
        self,
        agents: list[AgentActor],
        scenario: TrainingScenario,  # noqa: ARG002
        step: int,
    ) -> dict[str, Any]:
        """Execute generic training step."""
        for agent in agents:
            observation = {"step": step}
            await agent.act(observation)

        return {"state": {}}

    def _calculate_variance(self, values: list[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

    def _check_rate_limit(self) -> None:
        """Check rate limiting for episode execution."""
        current_time = time.time()

        # Clean old episodes from window
        window_start = current_time - 60.0
        self._episodes_in_window = [t for t in self._episodes_in_window if t > window_start]

        # Check limit
        if len(self._episodes_in_window) >= self._max_episodes_per_minute:
            raise RuntimeError(
                f"Rate limit exceeded: {self._max_episodes_per_minute} episodes per minute"
            )

        # Record this episode
        self._episodes_in_window.append(current_time)
        self._last_episode_time = current_time

    def _update_metrics(self, result: TrainingResult) -> None:
        """Update training metrics after episode."""
        self.metrics["total_episodes"] += 1

        if result.success:
            self.metrics["successful_episodes"] += 1

        self.metrics["total_phi_improvement"] += result.episode.phi_delta
        self.metrics["avg_phi_improvement"] = (
            self.metrics["total_phi_improvement"] / self.metrics["total_episodes"]
        )

        if result.max_phi > self.metrics["best_phi_achieved"]:
            self.metrics["best_phi_achieved"] = result.max_phi

        # Update average duration
        total_duration = self.metrics["avg_episode_duration"] * (self.metrics["total_episodes"] - 1)
        total_duration += result.episode.duration_seconds
        self.metrics["avg_episode_duration"] = total_duration / self.metrics["total_episodes"]


class CommunicationTrainingScenario(TrainingScenario):
    """Specialized scenario for communication efficiency training."""

    def __init__(self, agent_count: int = 5):
        super().__init__(
            scenario_id=f"comm_{uuid.uuid4()}",
            scenario_type=ScenarioType.COMMUNICATION,
            description="Communication efficiency training for Phi optimization",
            agent_count=agent_count,
            initial_state={"message_budget": agent_count * 3},
            objectives=[
                "maximize_phi",
                "minimize_messages",
                "maintain_connectivity",
            ],
            max_steps=50,
            phi_target=0.7,
        )


class DecisionCoherenceTrainingScenario(TrainingScenario):
    """Specialized scenario for decision coherence training."""

    def __init__(self, agent_count: int = 5):
        super().__init__(
            scenario_id=f"decision_{uuid.uuid4()}",
            scenario_type=ScenarioType.DECISION_COHERENCE,
            description="Decision coherence training for aligned Phi",
            agent_count=agent_count,
            initial_state={"decision_rounds": 0},
            objectives=[
                "maximize_phi",
                "achieve_consensus",
                "minimize_disagreement",
            ],
            max_steps=30,
            phi_target=0.8,
        )


class ConsensusTrainingScenario(TrainingScenario):
    """Specialized scenario for consensus formation training."""

    def __init__(self, agent_count: int = 5):
        super().__init__(
            scenario_id=f"consensus_{uuid.uuid4()}",
            scenario_type=ScenarioType.CONSENSUS_FORMATION,
            description="Consensus formation training for collective Phi",
            agent_count=agent_count,
            initial_state={"proposal": "", "positions": {}},
            objectives=[
                "maximize_phi",
                "reach_consensus",
                "maintain_diversity",
            ],
            max_steps=40,
            phi_target=0.75,
        )
