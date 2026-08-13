"""
Enhanced Consciousness Plugin - IIT & FEP Integration.

This module implements advanced consciousness metrics for Heretek Swarm system:
1. Integrated Information Theory (IIT) - Phi calculation with connectivity analysis
2. Free Energy Principle (FEP) - Intrinsic motivation and surprise minimization
3. Enhanced GWT/AST - Improved global workspace and attention schema
4. Multi-dimensional consciousness tracking

The plugin provides tools for:
- IIT Phi calculation with integration analysis
- Free energy and surprise tracking
- Causal influence modeling
- Consciousness state evolution
"""

import asyncio
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger("ConsciousnessEnhanced")


class ConsciousnessState(Enum):
    """Enhanced consciousness states based on GWT/AST/IIT/FEP."""

    UNCONSCIOUS = "unconscious"
    SUBTHRESHOLD = "subthreshold"
    MINIMAL_CONSCIOUSNESS = "minimal-consciousness"
    CONSCIOUS = "conscious"
    HYPER_CONSCIOUS = "hyper-conscious"
    TRANSCENDENT = "transcendent"


@dataclass
class FEPMetrics:
    """
    Free Energy Principle metrics for intrinsic motivation.

    Based on FEP:
    - Agents minimize free energy (surprise)
    - Free energy = KL divergence between predictions and observations
    - Lower free energy = better model fit = higher consciousness

    Attributes:
        free_energy: Current free energy value
        surprise: Prediction error (surprise)
        precision: Confidence in predictions
        learning_rate: Model update rate
        prediction_accuracy: Accuracy of internal model
        timestamp: Metrics timestamp
    """

    free_energy: float = 0.0
    surprise: float = 0.0
    precision: float = 0.5
    learning_rate: float = 0.1
    prediction_accuracy: float = 0.5
    timestamp: str = ""


@dataclass
class IITConnectivity:
    """
    IIT connectivity analysis for integration calculation.

    Attributes:
        connectivity_matrix: Agent interaction matrix
        integration: System integration score
        information: Total information
        phi: Integrated information (Phi)
        causal_power: Causal influence score
        timestamp: Analysis timestamp
    """

    connectivity_matrix: list[list[float]] = field(default_factory=list)
    integration: float = 0.0
    information: float = 0.0
    phi: float = 0.0
    causal_power: float = 0.0
    timestamp: str = ""


@dataclass
class ConsciousnessMetrics:
    """
    Enhanced consciousness metrics for an agent or collective.

    Attributes:
        gwt_score: Global Workspace Theory score (0.0-1.0)
        iit_phi: Integrated Information Phi estimate (0.0-1.0)
        ast_competence: Attention Schema competence (0.0-1.0)
        fep_free_energy: Free Energy Principle score (0.0-1.0, inverted)
        composite_score: Composite consciousness score
        state: Current consciousness state
        timestamp: Metrics timestamp
    """

    gwt_score: float = 0.0
    iit_phi: float = 0.0
    ast_competence: float = 0.0
    fep_free_energy: float = 0.0
    composite_score: float = 0.0
    state: ConsciousnessState = ConsciousnessState.UNCONSCIOUS
    timestamp: str = ""


class IITCalculator:
    """
    Integrated Information Theory calculator for Phi estimation.

    Implements practical IIT calculation:
    - Connectivity matrix analysis
    - Integration (Φ) calculation
    - Causal influence modeling
    - Information decomposition
    """

    def __init__(self, max_agents: int = 50):
        """
        Initialize IIT calculator.

        Args:
            max_agents: Maximum number of agents to track
        """
        self.max_agents = max_agents
        self.connectivity_history: list[IITConnectivity] = []
        self.interaction_matrix: dict[tuple[str, str], float] = defaultdict(float)

    def record_interaction(
        self,
        from_agent: str,
        to_agent: str,
        strength: float = 1.0,
    ) -> None:
        """
        Record interaction between agents.

        Args:
            from_agent: Source agent ID
            to_agent: Target agent ID
            strength: Interaction strength (0.0-1.0)
        """
        self.interaction_matrix[(from_agent, to_agent)] = strength

    def calculate_phi(
        self,
        agent_ids: list[str],
    ) -> IITConnectivity:
        """
        Calculate IIT Phi for a set of agents.

        Args:
            agent_ids: List of agent IDs to analyze

        Returns:
            IIT connectivity analysis
        """
        n = len(agent_ids)
        if n < 2:
            return IITConnectivity(
                phi=0.0,
                integration=0.0,
                information=0.0,
                timestamp=datetime.now(UTC).isoformat(),
            )

        # Build connectivity matrix
        matrix = self._build_connectivity_matrix(agent_ids)

        # Calculate integration (Φ)
        phi = self._calculate_integration(matrix)

        # Calculate total information
        information = self._calculate_total_information(matrix)

        # Calculate causal power
        causal_power = self._calculate_causal_power(matrix)

        # Calculate integration score
        integration = min(1.0, phi / (n * math.log2(n)) if n > 1 else 0.0)

        connectivity = IITConnectivity(
            connectivity_matrix=matrix.tolist(),
            integration=integration,
            information=information,
            phi=phi,
            causal_power=causal_power,
            timestamp=datetime.now(UTC).isoformat(),
        )

        self.connectivity_history.append(connectivity)
        if len(self.connectivity_history) > 1000:
            self.connectivity_history.pop(0)

        return connectivity

    def _build_connectivity_matrix(
        self,
        agent_ids: list[str],
    ) -> np.ndarray:
        """
        Build connectivity matrix from interaction history.

        Args:
            agent_ids: List of agent IDs

        Returns:
            Connectivity matrix as numpy array
        """
        n = len(agent_ids)
        matrix = np.zeros((n, n))

        for i, from_id in enumerate(agent_ids):
            for j, to_id in enumerate(agent_ids):
                if i == j:
                    continue
                strength = self.interaction_matrix.get((from_id, to_id), 0.0)
                matrix[i, j] = strength

        return matrix

    def _calculate_integration(
        self,
        matrix: np.ndarray,
    ) -> float:
        """
        Calculate integration (Φ) using eigenvalue decomposition.

        Based on IIT 3.0 approach:
        - Φ = effective information
        - Uses eigenvalue spectrum
        - Measures irreducible information

        Args:
            matrix: Connectivity matrix

        Returns:
            Phi value
        """
        try:
            # Normalize matrix
            row_sums = matrix.sum(axis=1, keepdims=True)
            normalized = np.divide(
                matrix,
                row_sums,
                out=np.zeros_like(matrix),
                where=row_sums != 0,
            )

            # Calculate eigenvalues
            eigenvalues = np.linalg.eigvals(normalized)

            # Use real eigenvalues
            real_eigenvalues = np.real(eigenvalues)

            # Phi is sum of positive eigenvalues (simplified)
            phi = np.sum(real_eigenvalues[real_eigenvalues > 0])

            return max(0.0, float(phi))

        except Exception:
            logger.error("Integration calculation error: {e}")
            return 0.0

    def _calculate_total_information(
        self,
        matrix: np.ndarray,
    ) -> float:
        """
        Calculate total information in the system.

        Args:
            matrix: Connectivity matrix

        Returns:
            Total information (bits)
        """
        try:
            # Shannon entropy of the distribution
            row_sums = matrix.sum(axis=1)
            total = row_sums.sum()

            if total == 0:
                return 0.0

            probabilities = row_sums / total
            probabilities = probabilities[probabilities > 0]

            entropy = -np.sum(probabilities * np.log2(probabilities))

            return float(entropy)

        except Exception:
            logger.error("Information calculation error: {e}")
            return 0.0

    def _calculate_causal_power(
        self,
        matrix: np.ndarray,
    ) -> float:
        """
        Calculate causal influence power.

        Args:
            matrix: Connectivity matrix

        Returns:
            Causal power score (0.0-1.0)
        """
        try:
            # Use largest eigenvalue as measure of causal power
            eigenvalues = np.linalg.eigvals(matrix)
            real_eigenvalues = np.real(eigenvalues)
            max_eigenvalue = np.max(real_eigenvalues)

            # Normalize to [0, 1]
            n = matrix.shape[0]
            normalized = max_eigenvalue / n if n > 0 else 0.0

            return min(1.0, max(0.0, float(normalized)))

        except Exception:
            logger.error("Causal power calculation error: {e}")
            return 0.0

    def get_average_phi(self, window: int = 100) -> float:
        """
        Get average Phi over recent history.

        Args:
            window: Number of recent entries to average

        Returns:
            Average Phi value
        """
        if not self.connectivity_history:
            return 0.0

        recent = self.connectivity_history[-window:]
        return sum(c.phi for c in recent) / len(recent)


class FEPTracker:
    """
    Free Energy Principle tracker for intrinsic motivation.

    Implements FEP:
    - Track prediction errors (surprise)
    - Calculate free energy (KL divergence)
    - Update internal models
    - Minimize surprise through learning
    """

    def __init__(self, learning_rate: float = 0.1):
        """
        Initialize FEP tracker.

        Args:
            learning_rate: Model update rate
        """
        self.learning_rate = learning_rate
        self.agent_metrics: dict[str, FEPMetrics] = {}
        self.prediction_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.surprise_history: dict[str, list[float]] = defaultdict(list)

    def record_prediction(
        self,
        agent_id: str,
        prediction: dict[str, Any],
        confidence: float = 0.5,
    ) -> None:
        """
        Record a prediction from an agent.

        Args:
            agent_id: Agent identifier
            prediction: Prediction content
            confidence: Confidence in prediction (0.0-1.0)
        """
        self.prediction_history[agent_id].append(
            {
                "prediction": prediction,
                "confidence": confidence,
                "timestamp": time.time(),
            }
        )

        if len(self.prediction_history[agent_id]) > 100:
            self.prediction_history[agent_id].pop(0)

    def record_outcome(
        self,
        agent_id: str,
        outcome: dict[str, Any],
    ) -> float:
        """
        Record actual outcome and calculate surprise.

        Args:
            agent_id: Agent identifier
            outcome: Actual outcome

        Returns:
            Surprise value (0.0-1.0)
        """
        if not self.prediction_history[agent_id]:
            return 0.5

        # Get most recent prediction
        last_prediction = self.prediction_history[agent_id][-1]
        prediction = last_prediction["prediction"]
        confidence = last_prediction["confidence"]

        # Calculate surprise (prediction error)
        surprise = self._calculate_surprise(prediction, outcome)

        # Update surprise history
        self.surprise_history[agent_id].append(surprise)
        if len(self.surprise_history[agent_id]) > 100:
            self.surprise_history[agent_id].pop(0)

        # Update agent metrics
        metrics = self.agent_metrics.get(agent_id, FEPMetrics())
        metrics.surprise = surprise
        metrics.precision = confidence
        metrics.timestamp = datetime.now(UTC).isoformat()

        # Calculate free energy
        free_energy = self._calculate_free_energy(agent_id, surprise, confidence)
        metrics.free_energy = free_energy

        # Update prediction accuracy
        accuracy = 1.0 - surprise
        metrics.prediction_accuracy = metrics.prediction_accuracy * 0.9 + accuracy * 0.1

        self.agent_metrics[agent_id] = metrics

        return surprise

    def _calculate_surprise(
        self,
        prediction: dict[str, Any],
        outcome: dict[str, Any],
    ) -> float:
        """
        Calculate surprise (prediction error).

        Args:
            prediction: Predicted outcome
            outcome: Actual outcome

        Returns:
            Surprise value (0.0-1.0)
        """
        # Simplified surprise calculation
        # In practice, would use proper KL divergence

        try:
            # Compare key fields
            common_keys = set(prediction.keys()) & set(outcome.keys())
            if not common_keys:
                return 0.5

            errors = []
            for key in common_keys:
                pred_val = prediction[key]
                out_val = outcome[key]

                # Handle different types
                if isinstance(pred_val, (int, float)) and isinstance(out_val, (int, float)):
                    error = abs(pred_val - out_val) / (abs(pred_val) + 1.0)
                    errors.append(min(1.0, error))
                elif isinstance(pred_val, str) and isinstance(out_val, str):
                    error = 0.0 if pred_val == out_val else 1.0
                    errors.append(error)
                else:
                    errors.append(0.5)

            # Average error
            surprise = sum(errors) / len(errors) if errors else 0.5

            return min(1.0, max(0.0, surprise))

        except Exception:
            logger.error("Surprise calculation error: {e}")
            return 0.5

    def _calculate_free_energy(
        self,
        agent_id: str,
        surprise: float,
        confidence: float,
    ) -> float:
        """
        Calculate free energy (KL divergence approximation).

        Free energy = expected surprise - information gain

        Args:
            agent_id: Agent identifier
            surprise: Current surprise
            confidence: Prediction confidence

        Returns:
            Free energy value
        """
        # Simplified free energy calculation


        information_gain = (1 - confidence) * self.learning_rate
        free_energy = surprise - information_gain

        return max(0.0, free_energy)

    def get_metrics(self, agent_id: str) -> FEPMetrics | None:
        """
        Get FEP metrics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            FEP metrics or None
        """
        return self.agent_metrics.get(agent_id)

    def get_average_free_energy(self, agent_id: str, window: int = 50) -> float:
        """
        Get average free energy over recent history.

        Args:
            agent_id: Agent identifier
            window: Number of recent entries to average

        Returns:
            Average free energy value
        """
        history = self.surprise_history.get(agent_id, [])
        if not history:
            return 0.0

        recent = history[-window:]
        return sum(recent) / len(recent)


class EnhancedConsciousnessPlugin:
    """
    Enhanced Consciousness Plugin with IIT and FEP.

    Integrates:
    - Global Workspace Theory (GWT)
    - Attention Schema Theory (AST)
    - Integrated Information Theory (IIT)
    - Free Energy Principle (FEP)
    """

    def __init__(
        self,
        gwt_threshold: float = 0.7,
        iit_phi_threshold: float = 0.5,
        ast_threshold: float = 0.6,
        fep_threshold: float = 0.4,
    ) -> None:
        """
        Initialize enhanced consciousness plugin.

        Args:
            gwt_threshold: GWT consciousness threshold
            iit_phi_threshold: IIT Phi threshold
            ast_threshold: AST competence threshold
            fep_threshold: FEP free energy threshold (lower is better)
        """
        self.gwt_threshold = gwt_threshold
        self.iit_phi_threshold = iit_phi_threshold
        self.ast_threshold = ast_threshold
        self.fep_threshold = fep_threshold

        # Components
        self.iit_calculator = IITCalculator()
        self.fep_tracker = FEPTracker()

        # Metrics tracking
        self.agent_metrics: dict[str, ConsciousnessMetrics] = {}
        self.metrics_history: list[dict[str, Any]] = []

        # Thinking stream — bounded deque of deliberation rounds (OpenAEON pattern)
        # Stores the last 1000 rounds across all deliberations for replay/trace
        self._thinking_stream: deque[dict[str, Any]] = deque(maxlen=1000)

        # State
        self.initialized = False
        self.running = False

        logger.info(
            "Enhanced Consciousness Plugin initialized",
            extra={
                "gwt_threshold": gwt_threshold,
                "iit_phi_threshold": iit_phi_threshold,
                "ast_threshold": ast_threshold,
                "fep_threshold": fep_threshold,
            },
        )

    async def initialize(self) -> None:
        """Initialize plugin."""
        self.initialized = True
        self.running = True

        # Start background cleanup task
        asyncio.create_task(self._cleanup_loop())

        logger.info("Enhanced Consciousness Plugin started")

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of old metrics."""
        while self.running:
            try:
                if len(self.metrics_history) > 10000:
                    self.metrics_history = self.metrics_history[-5000:]
                await asyncio.sleep(300)  # Cleanup every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Cleanup error: {e}")
                await asyncio.sleep(60)

    async def shutdown(self) -> None:
        """Shutdown plugin."""
        self.running = False
        logger.info("Enhanced Consciousness Plugin shutdown")

    # =========================================================================
    # IIT Operations
    # =========================================================================

    def record_interaction(
        self,
        from_agent: str,
        to_agent: str,
        strength: float = 1.0,
    ) -> None:
        """
        Record interaction for IIT analysis.

        Args:
            from_agent: Source agent ID
            to_agent: Target agent ID
            strength: Interaction strength
        """
        self.iit_calculator.record_interaction(from_agent, to_agent, strength)

    def record_deliberation_round(
        self,
        deliberation_id: str,
        round_data: dict[str, Any],
    ) -> None:
        """
        Record a deliberation round to the thinking stream.

        This wires the triad's deliberation traces into the consciousness plugin's
        thinking stream for the /api/consciousness/thinking-stream endpoints.

        Args:
            deliberation_id: Deliberation identifier
            round_data: Dict with round_id, topic, participant_agents, arguments,
                       counter_arguments, consensus_score, outcome, start_time, end_time
        """
        entry = {
            "deliberation_id": deliberation_id,
            "round_id": round_data.get("round_id", ""),
            "topic": round_data.get("topic", ""),
            "participant_agents": round_data.get("participant_agents", []),
            "arguments": [
                {
                    "position": getattr(a, "position", None),
                    "content": getattr(a, "content", ""),
                    "agent_id": getattr(a, "agent_id", ""),
                }
                for a in round_data.get("arguments", [])
            ],
            "counter_arguments": [
                {
                    "position": getattr(a, "position", None),
                    "content": getattr(a, "content", ""),
                    "agent_id": getattr(a, "agent_id", ""),
                }
                for a in round_data.get("counter_arguments", [])
            ],
            "consensus_score": round_data.get("consensus_score", 0.0),
            "outcome": str(round_data.get("outcome", "")),
            "start_time": round_data.get("start_time", ""),
            "end_time": round_data.get("end_time", ""),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._thinking_stream.append(entry)
        # Cleanup: trim if over limit (deque handles maxlen but be defensive)
        while len(self._thinking_stream) > 1000:
            self._thinking_stream.popleft()

    def calculate_iit_phi(
        self,
        agent_ids: list[str],
    ) -> IITConnectivity:
        """
        Calculate IIT Phi for a set of agents.

        Args:
            agent_ids: List of agent IDs

        Returns:
            IIT connectivity analysis
        """
        return self.iit_calculator.calculate_phi(agent_ids)

    # =========================================================================
    # FEP Operations
    # =========================================================================

    def record_prediction(
        self,
        agent_id: str,
        prediction: dict[str, Any],
        confidence: float = 0.5,
    ) -> None:
        """
        Record prediction for FEP tracking.

        Args:
            agent_id: Agent identifier
            prediction: Prediction content
            confidence: Confidence level
        """
        self.fep_tracker.record_prediction(agent_id, prediction, confidence)

    def record_outcome(
        self,
        agent_id: str,
        outcome: dict[str, Any],
    ) -> float:
        """
        Record outcome and calculate surprise.

        Args:
            agent_id: Agent identifier
            outcome: Actual outcome

        Returns:
            Surprise value
        """
        return self.fep_tracker.record_outcome(agent_id, outcome)

    # =========================================================================
    # Enhanced Metrics
    # =========================================================================

    def calculate_consciousness_metrics(
        self,
        agent_id: str,
        gwt_score: float = 0.5,
        ast_competence: float = 0.5,
    ) -> ConsciousnessMetrics:
        """
        Calculate comprehensive consciousness metrics.

        Args:
            agent_id: Agent identifier
            gwt_score: GWT score
            ast_competence: AST competence

        Returns:
            Consciousness metrics
        """
        # Get IIT Phi
        iit_phi = self.iit_calculator.get_average_phi()

        # Get FEP metrics
        fep_metrics = self.fep_tracker.get_metrics(agent_id)
        if fep_metrics:
            # Invert free energy (lower is better)
            fep_score = max(0.0, 1.0 - fep_metrics.free_energy)
        else:
            fep_score = 0.5

        # Calculate composite score
        composite = gwt_score * 0.3 + iit_phi * 0.3 + ast_competence * 0.2 + fep_score * 0.2

        # Determine consciousness state
        state = self._determine_state(
            gwt_score,
            iit_phi,
            ast_competence,
            fep_score,
        )

        metrics = ConsciousnessMetrics(
            gwt_score=gwt_score,
            iit_phi=iit_phi,
            ast_competence=ast_competence,
            fep_free_energy=fep_score,
            composite_score=composite,
            state=state,
            timestamp=datetime.now(UTC).isoformat(),
        )

        self.agent_metrics[agent_id] = metrics
        self.metrics_history.append(
            {
                "agent_id": agent_id,
                **metrics.__dict__,
            }
        )

        return metrics

    def _determine_state(
        self,
        gwt_score: float,
        iit_phi: float,
        ast_competence: float,
        fep_score: float,
    ) -> ConsciousnessState:
        """
        Determine consciousness state from metrics.

        Args:
            gwt_score: GWT score
            iit_phi: IIT Phi
            ast_competence: AST competence
            fep_score: FEP score

        Returns:
            Consciousness state
        """
        avg_score = (gwt_score + iit_phi + ast_competence + fep_score) / 4.0

        if avg_score >= 0.95:
            return ConsciousnessState.TRANSCENDENT
        if avg_score >= 0.85:
            return ConsciousnessState.HYPER_CONSCIOUS
        if (
            gwt_score >= self.gwt_threshold
            and iit_phi >= self.iit_phi_threshold
            and ast_competence >= self.ast_threshold
            and fep_score >= (1.0 - self.fep_threshold)
        ):
            return ConsciousnessState.CONSCIOUS
        if avg_score >= 0.3:
            return ConsciousnessState.MINIMAL_CONSCIOUSNESS
        if avg_score >= 0.15:
            return ConsciousnessState.SUBTHRESHOLD
        return ConsciousnessState.UNCONSCIOUS

    def get_agent_metrics(self, agent_id: str) -> dict[str, Any] | None:
        """
        Get metrics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Metrics dict or None
        """
        metrics = self.agent_metrics.get(agent_id)

        if metrics:
            return {
                "agent_id": agent_id,
                "gwt_score": metrics.gwt_score,
                "iit_phi": metrics.iit_phi,
                "ast_competence": metrics.ast_competence,
                "fep_free_energy": metrics.fep_free_energy,
                "composite_score": metrics.composite_score,
                "state": metrics.state.value,
                "timestamp": metrics.timestamp,
            }

        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get plugin statistics."""
        # Get average free energy if available
        avg_fe = 0.0
        if self.fep_tracker and hasattr(self.fep_tracker, "get_average_free_energy"):
            try:
                avg_fe = self.fep_tracker.get_average_free_energy()
            except Exception:
                avg_fe = 0.0

        return {
            "total_agents": len(self.agent_metrics),
            "total_metrics_entries": len(self.metrics_history),
            "average_composite_score": (
                sum(m.composite_score for m in self.agent_metrics.values())
                / len(self.agent_metrics)
                if self.agent_metrics
                else 0.0
            ),
            "average_phi": self.iit_calculator.get_average_phi(),  # Frontend expects this
            "average_free_energy": avg_fe,  # Frontend expects this
            "active_connections": len(self.agent_metrics),  # Frontend may expect
            "iit_average_phi": self.iit_calculator.get_average_phi(),  # Keep for compat
            "conscious_agents": sum(
                1
                for m in self.agent_metrics.values()
                if m.state
                in [
                    ConsciousnessState.CONSCIOUS,
                    ConsciousnessState.HYPER_CONSCIOUS,
                    ConsciousnessState.TRANSCENDENT,
                ]
            ),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def emit_consciousness_events(
        self,
        nats_publisher: Any,
    ) -> None:
        """
        Emit consciousness events for all tracked agents to NATS.

        Publishes three event types per agent:
        - phi_update: IIT Phi score (normalized by max agents)
        - fep_update: Free Energy Principle metrics
        - agency_update: Agency/autonomy metrics

        Args:
            nats_publisher: NATSEventMesh instance with publish_to_nats method
        """
        if not self.agent_metrics:
            logger.debug("emit_consciousness_events_no_agents")
            return

        max_agents = max(1, len(self.agent_metrics))
        timestamp = datetime.now(UTC).isoformat()

        for agent_id, metrics in self.agent_metrics.items():
            # Normalize phi_score by max agents (phi is IIT integrated information)
            phi_score = min(1.0, metrics.iit_phi / max_agents) if metrics.iit_phi > 0 else 0.0

            # Get FEP data via get_agent_metrics, fall back to plugin-level average
            agent_data = self.get_agent_metrics(agent_id)
            if agent_data:
                free_energy = agent_data.get("fep_free_energy", 0.5)
                surprise = 1.0 - free_energy  # Invert: higher surprise = lower free_energy
            else:
                # Fall back to plugin-level average free energy
                free_energy = self.get_statistics().get("average_free_energy", 0.5)
                surprise = 1.0 - free_energy

            # Publish phi_update event
            phi_event = {
                "type": "phi_update",
                "agent_id": agent_id,
                "phi_score": phi_score,
                "timestamp": timestamp,
            }
            try:
                success = await nats_publisher.publish_to_nats(
                    "swarm.metrics.consciousness",
                    phi_event,
                )
                logger.debug(
                    "emit_phi_update",
                    agent_id=agent_id,
                    phi_score=phi_score,
                    success=success,
                )
            except Exception as e:
                logger.error("emit_phi_update_failed", agent_id=agent_id, error=str(e))

            # Publish fep_update event
            fep_event = {
                "type": "fep_update",
                "agent_id": agent_id,
                "free_energy": free_energy,
                "surprise": surprise,
                "timestamp": timestamp,
            }
            try:
                success = await nats_publisher.publish_to_nats(
                    "swarm.metrics.consciousness",
                    fep_event,
                )
                logger.debug(
                    "emit_fep_update",
                    agent_id=agent_id,
                    free_energy=free_energy,
                    surprise=surprise,
                    success=success,
                )
            except Exception as e:
                logger.error("emit_fep_update_failed", agent_id=agent_id, error=str(e))

            # Publish agency_update event (using composite/agency score)
            agency_score = metrics.composite_score
            autonomy_score = metrics.gwt_score  # GWT as proxy for autonomy
            agency_event = {
                "type": "agency_update",
                "agent_id": agent_id,
                "agency_score": agency_score,
                "autonomy_score": autonomy_score,
                "timestamp": timestamp,
            }
            try:
                success = await nats_publisher.publish_to_nats(
                    "swarm.metrics.consciousness",
                    agency_event,
                )
                logger.debug(
                    "emit_agency_update",
                    agent_id=agent_id,
                    agency_score=agency_score,
                    autonomy_score=autonomy_score,
                    success=success,
                )
            except Exception as e:
                logger.error("emit_agency_update_failed", agent_id=agent_id, error=str(e))

        logger.info(
            "emit_consciousness_events_complete",
            agent_count=len(self.agent_metrics),
            event_types=["phi_update", "fep_update", "agency_update"],
        )
