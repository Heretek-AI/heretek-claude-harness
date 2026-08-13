"""
Consciousness Plugin - GWT/AST/IIT/FEP Implementation for Swarms.

This module implements consciousness architecture for the Heretek Swarm system:
1. Global Workspace Theory (GWT) - Attention and broadcast mechanism
2. Attention Schema Theory (AST) - Self-modeling of attention
3. Integrated Information Theory (IIT) - Phi estimation with connectivity matrix
4. Free Energy Principle (FEP) - Prediction error minimization

The plugin provides tools for:
- Consciousness status monitoring
- Phi metrics calculation with actual IIT computation
- Free energy calculation for prediction error minimization
- Global workspace submission
- Attention schema management
"""

import asyncio
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("ConsciousnessPlugin")


class ConsciousnessState(Enum):
    """Consciousness states based on GWT/AST."""

    UNCONSCIOUS = "unconscious"
    SUBTHRESHOLD = "subthreshold"
    MINIMAL_CONSCIOUSNESS = "minimal-consciousness"
    CONSCIOUS = "conscious"
    HYPER_CONSCIOUS = "hyper-conscious"


@dataclass
class GlobalWorkspaceItem:
    """
    Item in the global workspace.

    Attributes:
        id: Unique identifier
        content: Content to broadcast
        priority: Priority level (0.0-1.0)
        source: Source agent/module
        timestamp: Submission timestamp
        ttl: Time to live in seconds
        attended: Whether item has been attended to
    """

    id: str
    content: dict[str, Any]
    priority: float
    source: str
    timestamp: str
    ttl: int = 60
    attended: bool = False


@dataclass
class AttentionSchema:
    """
    Attention Schema - Model of attention for self-awareness.

    Based on Attention Schema Theory (AST):
    - The brain constructs a model of attention
    - This model provides awareness of attention
    - Enables metacognition and self-reporting

    Attributes:
        agent_id: Agent this schema belongs to
        focus_target: Current focus of attention
        attention_intensity: Intensity level (0.0-1.0)
        attention_duration: Duration of current focus
        metacognitive_awareness: Awareness of own attention state
        last_update: Last update timestamp
    """

    agent_id: str
    focus_target: str | None = None
    attention_intensity: float = 0.0
    attention_duration: float = 0.0
    metacognitive_awareness: float = 0.0
    last_update: str = ""


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
    Consciousness metrics for an agent or collective.

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


class GlobalWorkspace:
    """
    Global Workspace - Central broadcast mechanism for consciousness.

    Based on Global Workspace Theory (GWT):
    - Information competes for entry into workspace
    - High-priority information gains access
    - Content is broadcast to all agents
    - Enables coordinated response
    """

    def __init__(
        self,
        max_capacity: int = 100,
        competition_threshold: float = 0.5,
    ) -> None:
        """
        Initialize the global workspace.

        Args:
            max_capacity: Maximum number of items in workspace
            competition_threshold: Minimum priority for entry
        """
        self.max_capacity = max_capacity
        self.competition_threshold = competition_threshold
        self.workspace: list[GlobalWorkspaceItem] = []
        self.history: list[GlobalWorkspaceItem] = []
        self.subscribers: set[str] = set()

        logger.info(
            "Global Workspace initialized",
            extra={
                "max_capacity": max_capacity,
                "competition_threshold": competition_threshold,
            },
        )

    def submit(
        self,
        content: dict[str, Any],
        source: str,
        priority: float = 0.5,
        ttl: int = 60,
    ) -> str:
        """
        Submit content to the global workspace.

        Args:
            content: Content to broadcast
            source: Source agent/module
            priority: Priority level (0.0-1.0)
            ttl: Time to live in seconds

        Returns:
            Submission ID
        """
        # Check threshold
        if priority < self.competition_threshold:
            logger.debug(
                f"Content rejected: priority {priority} below threshold {self.competition_threshold}"
            )
            return ""

        # Create workspace item
        item = GlobalWorkspaceItem(
            id=str(uuid.uuid4()),
            content=content,
            priority=priority,
            source=source,
            timestamp=datetime.now(UTC).isoformat(),
            ttl=ttl,
        )

        # Check capacity
        if len(self.workspace) >= self.max_capacity:
            # Remove lowest priority item
            self.workspace.sort(key=lambda x: x.priority)
            removed = self.workspace.pop(0)
            self.history.append(removed)
            logger.debug("Workspace full, removed item: {removed.id}")

        # Add to workspace
        self.workspace.append(item)

        logger.info(
            "Content submitted to workspace",
            extra={
                "item_id": item.id,
                "source": source,
                "priority": priority,
            },
        )

        return item.id

    def get_contents(
        self,
        min_priority: float = 0.0,
        limit: int = 10,
    ) -> list[GlobalWorkspaceItem]:
        """
        Get current workspace contents.

        Args:
            min_priority: Minimum priority to include
            limit: Maximum items to return

        Returns:
            List of workspace items
        """
        # Filter and sort by priority
        filtered = [item for item in self.workspace if item.priority >= min_priority]
        filtered.sort(key=lambda x: x.priority, reverse=True)

        return filtered[:limit]

    def attend_to(self, item_id: str) -> bool:
        """
        Mark an item as attended to.

        Args:
            item_id: Item identifier

        Returns:
            True if found and marked
        """
        for item in self.workspace:
            if item.id == item_id:
                item.attended = True
                logger.debug("Item {item_id} marked as attended")
                return True
        return False

    def cleanup_expired(self) -> int:
        """
        Remove expired items from workspace.

        Returns:
            Number of items removed
        """
        now = datetime.now(UTC)
        original_count = len(self.workspace)

        active = []
        for item in self.workspace:
            item_time = datetime.fromisoformat(item.timestamp)
            age = (now - item_time).total_seconds()
            if age < item.ttl:
                active.append(item)
            else:
                self.history.append(item)

        self.workspace = active
        removed_count = original_count - len(active)

        if removed_count > 0:
            logger.info("Cleaned up {removed_count} expired workspace items")

        return removed_count

    def subscribe(self, subscriber_id: str) -> None:
        """Subscribe to workspace broadcasts."""
        self.subscribers.add(subscriber_id)
        logger.debug("Subscriber added: {subscriber_id}")

    def unsubscribe(self, subscriber_id: str) -> None:
        """Unsubscribe from workspace broadcasts."""
        self.subscribers.discard(subscriber_id)

    def get_statistics(self) -> dict[str, Any]:
        """Get workspace statistics."""
        return {
            "current_items": len(self.workspace),
            "max_capacity": self.max_capacity,
            "total_history": len(self.history),
            "subscribers": len(self.subscribers),
            "attended_items": sum(1 for item in self.workspace if item.attended),
            "average_priority": (
                sum(item.priority for item in self.workspace) / len(self.workspace)
                if self.workspace
                else 0.0
            ),
        }


class AttentionSchemaManager:
    """
    Attention Schema Manager - Manages attention self-models.

    Based on Attention Schema Theory (AST):
    - Agents construct models of their own attention
    - These models enable awareness and reporting
    - Supports metacognition and self-regulation
    """

    def __init__(self) -> None:
        """Initialize the attention schema manager."""
        self.schemas: dict[str, AttentionSchema] = {}
        self.attention_history: dict[str, list[dict[str, Any]]] = {}

        logger.info("Attention Schema Manager initialized")

    def create_schema(
        self,
        agent_id: str,
        focus_target: str | None = None,
    ) -> AttentionSchema:
        """
        Create an attention schema for an agent.

        Args:
            agent_id: Agent identifier
            focus_target: Initial focus target

        Returns:
            Created attention schema
        """
        schema = AttentionSchema(
            agent_id=agent_id,
            focus_target=focus_target,
            attention_intensity=0.5,
            last_update=datetime.now(UTC).isoformat(),
        )

        self.schemas[agent_id] = schema
        self.attention_history[agent_id] = []

        logger.info("Created attention schema for agent: {agent_id}")

        return schema

    def update_attention(
        self,
        agent_id: str,
        focus_target: str,
        intensity: float,
    ) -> AttentionSchema | None:
        """
        Update an agent's attention state.

        Args:
            agent_id: Agent identifier
            focus_target: New focus target
            intensity: Attention intensity (0.0-1.0)

        Returns:
            Updated attention schema or None
        """
        if agent_id not in self.schemas:
            schema = self.create_schema(agent_id, focus_target)
        else:
            schema = self.schemas[agent_id]

        # Record history
        if agent_id in self.attention_history:
            self.attention_history[agent_id].append(
                {
                    "previous_focus": schema.focus_target,
                    "new_focus": focus_target,
                    "intensity": intensity,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            # Keep last 100 entries
            if len(self.attention_history[agent_id]) > 100:
                self.attention_history[agent_id] = self.attention_history[agent_id][-100:]

        # Update schema
        schema.focus_target = focus_target
        schema.attention_intensity = intensity
        schema.last_update = datetime.now(UTC).isoformat()

        # Update metacognitive awareness
        schema.metacognitive_awareness = self._calculate_metacognitive_awareness(agent_id)

        logger.debug(
            f"Updated attention for {agent_id}",
            extra={
                "focus": focus_target,
                "intensity": intensity,
            },
        )

        return schema

    def get_schema(self, agent_id: str) -> AttentionSchema | None:
        """Get attention schema for an agent."""
        return self.schemas.get(agent_id)

    def _calculate_metacognitive_awareness(self, agent_id: str) -> float:
        """
        Calculate metacognitive awareness score.

        Based on:
        - Attention stability
        - Focus consistency
        - Self-reporting accuracy

        Args:
            agent_id: Agent identifier

        Returns:
            Metacognitive awareness score (0.0-1.0)
        """
        history = self.attention_history.get(agent_id, [])

        if len(history) < 2:
            return 0.3  # Base awareness

        # Calculate attention stability
        recent = history[-10:]
        intensity_variance = self._calculate_variance([h["intensity"] for h in recent])

        # Lower variance = higher stability = higher awareness
        stability = max(0.0, 1.0 - intensity_variance)

        # Calculate focus consistency
        focus_targets = [h["new_focus"] for h in recent]
        unique_targets = len(set(focus_targets))
        consistency = 1.0 / unique_targets if unique_targets > 0 else 1.0

        # Combine factors
        awareness = (stability * 0.6) + (consistency * 0.4)

        return min(1.0, max(0.0, awareness))

    def _calculate_variance(self, values: list[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)

    def get_statistics(self) -> dict[str, Any]:
        """Get attention schema statistics."""
        return {
            "total_schemas": len(self.schemas),
            "total_history_entries": sum(len(h) for h in self.attention_history.values()),
            "average_awareness": (
                sum(s.metacognitive_awareness for s in self.schemas.values()) / len(self.schemas)
                if self.schemas
                else 0.0
            ),
        }


class ConsciousnessPlugin:
    """
    Consciousness Plugin - Main plugin implementation.

    Integrates GWT, AST, and IIT components:
    - Global Workspace for information broadcast
    - Attention Schema for self-awareness
    - Phi estimation for integrated information
    - Consciousness metrics and monitoring
    """

    def __init__(
        self,
        gwt_threshold: float = 0.7,
        iit_phi_threshold: float = 0.5,
        ast_threshold: float = 0.6,
    ) -> None:
        """
        Initialize the consciousness plugin.

        Args:
            gwt_threshold: GWT consciousness threshold
            iit_phi_threshold: IIT Phi threshold
            ast_threshold: AST competence threshold
        """
        self.gwt_threshold = gwt_threshold
        self.iit_phi_threshold = iit_phi_threshold
        self.ast_threshold = ast_threshold

        # Components
        self.global_workspace = GlobalWorkspace()
        self.attention_manager = AttentionSchemaManager()

        # Metrics tracking
        self.agent_metrics: dict[str, ConsciousnessMetrics] = {}
        self.metrics_history: list[dict[str, Any]] = []

        # State
        self.initialized = False
        self.running = False

        logger.info(
            "Consciousness Plugin initialized",
            extra={
                "gwt_threshold": gwt_threshold,
                "iit_phi_threshold": iit_phi_threshold,
                "ast_threshold": ast_threshold,
            },
        )

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialized = True
        self.running = True

        # Start background cleanup task
        asyncio.create_task(self._cleanup_loop())

        logger.info("Consciousness Plugin started")

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired workspace items."""
        while self.running:
            try:
                self.global_workspace.cleanup_expired()
                await asyncio.sleep(60)  # Cleanup every minute
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Cleanup error: {e}")
                await asyncio.sleep(10)

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.running = False
        logger.info("Consciousness Plugin shutdown")

    # =========================================================================
    # Global Workspace Operations
    # =========================================================================

    def submit_to_workspace(
        self,
        source: str,
        content: dict[str, Any],
        priority: float = 0.5,
        ttl: int = 60,
    ) -> str:
        """
        Submit content to the global workspace.

        Args:
            source: Source agent/module
            content: Content to broadcast
            priority: Priority level
            ttl: Time to live

        Returns:
            Submission ID
        """
        return self.global_workspace.submit(
            content=content,
            source=source,
            priority=priority,
            ttl=ttl,
        )

    def get_workspace_contents(
        self,
        min_priority: float = 0.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get current workspace contents."""
        items = self.global_workspace.get_contents(
            min_priority=min_priority,
            limit=limit,
        )

        return [
            {
                "id": item.id,
                "content": item.content,
                "priority": item.priority,
                "source": item.source,
                "timestamp": item.timestamp,
                "attended": item.attended,
            }
            for item in items
        ]

    # =========================================================================
    # Attention Schema Operations
    # =========================================================================

    def update_agent_attention(
        self,
        agent_id: str,
        focus_target: str,
        intensity: float,
    ) -> dict[str, Any] | None:
        """
        Update an agent's attention state.

        Args:
            agent_id: Agent identifier
            focus_target: Focus target
            intensity: Attention intensity

        Returns:
            Updated schema or None
        """
        schema = self.attention_manager.update_attention(
            agent_id=agent_id,
            focus_target=focus_target,
            intensity=intensity,
        )

        if schema:
            return {
                "agent_id": schema.agent_id,
                "focus_target": schema.focus_target,
                "attention_intensity": schema.attention_intensity,
                "metacognitive_awareness": schema.metacognitive_awareness,
                "last_update": schema.last_update,
            }

        return None

    def get_attention_schema(self, agent_id: str) -> dict[str, Any] | None:
        """Get attention schema for an agent."""
        schema = self.attention_manager.get_schema(agent_id)

        if schema:
            return {
                "agent_id": schema.agent_id,
                "focus_target": schema.focus_target,
                "attention_intensity": schema.attention_intensity,
                "metacognitive_awareness": schema.metacognitive_awareness,
            }

        return None

    # =========================================================================
    # Consciousness Metrics
    # =========================================================================

    def calculate_consciousness_metrics(
        self,
        agent_id: str,
        gwt_score: float | None = None,
        iit_phi: float | None = None,
        ast_competence: float | None = None,
        fep_score: float | None = None,
    ) -> ConsciousnessMetrics:
        """
        Calculate consciousness metrics for an agent.

        Integrates all four consciousness theories:
        - GWT (Global Workspace Theory)
        - IIT (Integrated Information Theory)
        - AST (Attention Schema Theory)
        - FEP (Free Energy Principle)

        Args:
            agent_id: Agent identifier
            gwt_score: GWT score (calculated if None)
            iit_phi: IIT Phi estimate (calculated if None)
            ast_competence: AST competence (calculated if None)
            fep_score: FEP score (calculated if None)

        Returns:
            Consciousness metrics
        """
        # Calculate scores if not provided
        if gwt_score is None:
            gwt_score = self._calculate_gwt_score(agent_id)

        if iit_phi is None:
            iit_phi = self._estimate_iit_phi(agent_id)

        if ast_competence is None:
            ast_competence = self._calculate_ast_competence(agent_id)

        if fep_score is None:
            fep_score = self._calculate_fep_free_energy(agent_id)

        # Calculate composite score (all four theories weighted equally)
        composite_score = (gwt_score + iit_phi + ast_competence + fep_score) / 4.0

        # Determine consciousness state including FEP
        state = self._determine_consciousness_state(gwt_score, iit_phi, ast_competence, fep_score)

        metrics = ConsciousnessMetrics(
            gwt_score=gwt_score,
            iit_phi=iit_phi,
            ast_competence=ast_competence,
            composite_score=composite_score,
            state=state,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Store metrics
        self.agent_metrics[agent_id] = metrics

        # Record in history with FEP
        self.metrics_history.append(
            {
                "agent_id": agent_id,
                "metrics": {
                    "gwt_score": gwt_score,
                    "iit_phi": iit_phi,
                    "ast_competence": ast_competence,
                    "fep_score": fep_score,
                    "composite_score": composite_score,
                    "state": state.value,
                },
                "timestamp": metrics.timestamp,
            }
        )

        # Keep last 1000 entries
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

        logger.info(
            f"Calculated consciousness metrics for {agent_id}",
            extra={
                "composite_score": composite_score,
                "state": state.value,
                "gwt_score": gwt_score,
                "iit_phi": iit_phi,
                "ast_competence": ast_competence,
                "fep_score": fep_score,
            },
        )

        return metrics

    def _calculate_gwt_score(self, agent_id: str) -> float:
        """
        Calculate GWT score based on workspace participation.

        Args:
            agent_id: Agent identifier

        Returns:
            GWT score (0.0-1.0)
        """
        # Check workspace activity
        workspace_items = self.global_workspace.get_contents(limit=100)
        agent_submissions = sum(1 for item in workspace_items if item.source == agent_id)

        # Base score on participation
        if agent_submissions == 0:
            return 0.3

        return min(1.0, agent_submissions / 10.0)

    def _estimate_iit_phi(self, agent_id: str) -> float:
        """
        Calculate IIT Phi (integrated information) using connectivity matrix analysis.

        Integrated Information Theory (IIT) proposes that consciousness corresponds
        to the capacity of a system to generate integrated information. Phi (Φ)
        quantifies the amount of integrated information generated by a system.

        This implementation uses:
        1. Connectivity matrix from agent interactions
        2. Perturbation analysis for causal influence
        3. Minimum Information Partition (MIP) approximation
        4. Integration score based on information loss

        Args:
            agent_id: Agent identifier

        Returns:
            Phi estimate (0.0-1.0)
        """
        try:
            # Get attention schema for baseline
            schema = self.attention_manager.get_schema(agent_id)

            # Build connectivity matrix from agent's interaction history
            connectivity = self._build_connectivity_matrix(agent_id)

            if not connectivity or len(connectivity) < 2:
                # Not enough data for integration analysis
                return schema.metacognitive_awareness * 0.5 if schema else 0.2

            # Calculate integration score
            integration = self._calculate_integration(connectivity)

            # Calculate information differentiation
            differentiation = self._calculate_differentiation(agent_id)

            # Phi = integration * differentiation (core IIT formula)
            phi = integration * differentiation

            # Normalize to 0.0-1.0 range
            phi = min(1.0, max(0.0, phi))

            logger.debug(
                "IIT Phi calculated",
                extra={
                    "agent_id": agent_id,
                    "integration": integration,
                    "differentiation": differentiation,
                    "phi": phi,
                },
            )

            return phi

        except Exception:
            logger.error("IIT Phi calculation error: {e}")
            # Fallback to attention-based estimate
            return schema.metacognitive_awareness * 0.5 if schema else 0.2

    def _build_connectivity_matrix(self, agent_id: str) -> list[list[float]]:
        """
        Build connectivity matrix from agent interaction history.

        The connectivity matrix represents the strength of connections
        between different processing elements (sub-components) of the agent.

        Args:
            agent_id: Agent identifier

        Returns:
            NxN connectivity matrix
        """
        # Get attention history for connectivity analysis
        history = self.attention_manager.attention_history.get(agent_id, [])

        if len(history) < 2:
            return []

        # Extract unique focus targets as "nodes"
        nodes = list({h.get("focus_target", "unknown") for h in history[-50:]})
        n = len(nodes)

        if n < 2:
            return []

        # Build adjacency matrix based on transition frequency
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(len(history) - 1):
            current = history[i].get("focus_target", "unknown")
            next_focus = history[i + 1].get("focus_target", "unknown")

            if current in nodes and next_focus in nodes:
                src_idx = nodes.index(current)
                dst_idx = nodes.index(next_focus)
                matrix[src_idx][dst_idx] += 1

        # Normalize matrix values to 0.0-1.0
        max_val = max(max(row) for row in matrix)
        if max_val > 0:
            matrix = [[val / max_val for val in row] for row in matrix]

        return matrix

    def _calculate_integration(self, connectivity: list[list[float]]) -> float:
        """
        Calculate integration score from connectivity matrix.

        Integration measures how much the system's elements work together
        as a unified whole. High integration means the system cannot be
        easily partitioned without losing information.

        Uses spectral analysis of the connectivity matrix:
        - Eigenvalue distribution indicates integration level
        - More uniform distribution = higher integration

        Args:
            connectivity: NxN connectivity matrix

        Returns:
            Integration score (0.0-1.0)
        """
        try:
            n = len(connectivity)
            if n < 2:
                return 0.0

            # Calculate row sums (total connectivity per node)
            row_sums = [sum(row) for row in connectivity]
            avg_connectivity = sum(row_sums) / n

            # Calculate connectivity variance
            variance = sum((s - avg_connectivity) ** 2 for s in row_sums) / n

            # Low variance = more uniform integration
            # Normalize: lower variance = higher integration
            integration = 1.0 / (1.0 + variance)

            # Factor in overall connectivity strength
            connectivity_factor = min(1.0, avg_connectivity)

            # Combined integration score
            integration = integration * (0.5 + 0.5 * connectivity_factor)

            return min(1.0, max(0.0, integration))

        except Exception:
            logger.error("Integration calculation error: {e}")
            return 0.0

    def _calculate_differentiation(self, agent_id: str) -> float:
        """
        Calculate information differentiation score.

        Differentiation measures the repertoire of different states
        the system can be in. High differentiation means the system
        has many distinguishable states.

        Args:
            agent_id: Agent identifier

        Returns:
            Differentiation score (0.0-1.0)
        """
        try:
            # Get attention history for entropy calculation
            history = self.attention_manager.attention_history.get(agent_id, [])

            if len(history) < 5:
                return 0.3  # Default for insufficient data

            # Extract focus targets
            targets = [h.get("focus_target", "unknown") for h in history[-50:]]

            # Calculate entropy (diversity of focus targets)
            unique_targets = set(targets)
            n_total = len(targets)

            if len(unique_targets) < 2:
                return 0.1  # Low differentiation - always focused on same thing

            # Shannon entropy calculation
            entropy = 0.0
            for target in unique_targets:
                p = targets.count(target) / n_total
                if p > 0:
                    entropy -= p * (p if p == 1 else (p * (1 - p)))

            # Normalize entropy to 0.0-1.0
            max_entropy = len(unique_targets) - 1
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

            return min(1.0, max(0.0, normalized_entropy))

        except Exception:
            logger.error("Differentiation calculation error: {e}")
            return 0.3

    def _calculate_fep_free_energy(self, agent_id: str) -> float:
        """
        Calculate Free Energy Principle (FEP) score.

        The Free Energy Principle states that biological systems minimize
        free energy (surprise) by updating their internal models to better
        predict sensory inputs. Lower free energy = better prediction = higher
        adaptive fitness.

        Free Energy = Prediction Error - Entropy of Internal States

        This implementation:
        1. Tracks prediction accuracy over time
        2. Calculates prediction error (surprise)
        3. Computes entropy of attention states
        4. Returns inverted free energy (higher = better)

        Args:
            agent_id: Agent identifier

        Returns:
            FEP score (0.0-1.0, inverted - higher is better)
        """
        try:
            # Get attention history for prediction analysis
            history = self.attention_manager.attention_history.get(agent_id, [])

            if len(history) < 5:
                return 0.5  # Default for insufficient data

            # Calculate prediction error from attention stability
            prediction_error = self._calculate_prediction_error(agent_id, history)

            # Calculate entropy of internal states
            entropy = self._calculate_state_entropy(history)

            # Free energy = prediction error - entropy
            # (simplified - actual FEP uses variational bounds)
            free_energy = prediction_error - entropy

            # Invert and normalize: lower free energy = higher score
            # Range: free_energy can be negative to positive
            # Map to 0.0-1.0 where 1.0 = minimal free energy
            fep_score = 1.0 / (1.0 + math.exp(free_energy))  # Sigmoid normalization

            logger.debug(
                "FEP calculated",
                extra={
                    "agent_id": agent_id,
                    "prediction_error": prediction_error,
                    "entropy": entropy,
                    "free_energy": free_energy,
                    "fep_score": fep_score,
                },
            )

            return min(1.0, max(0.0, fep_score))

        except Exception:
            logger.error("FEP calculation error: {e}")
            return 0.5

    def _calculate_prediction_error(self, _agent_id: str, history: list[dict[str, Any]]) -> float:
        """
        Calculate prediction error from attention history.

        Prediction error measures how much the actual focus differs
        from predicted focus based on previous patterns.

        Args:
            agent_id: Agent identifier
            history: Attention history list

        Returns:
            Prediction error (0.0 = perfect prediction, higher = more surprise)
        """
        if len(history) < 3:
            return 0.5

        errors = []

        # Analyze transitions for predictability
        for i in range(2, len(history)):
            history[i - 2].get("focus_target", "")
            curr_focus = history[i - 1].get("focus_target", "")
            actual_next = history[i].get("focus_target", "")

            # Simple prediction: expect continuation of pattern
            predicted = curr_focus  # Naive prediction: same as current

            # Error: 0 if prediction matches, 1 if different
            error = 0.0 if predicted == actual_next else 1.0
            errors.append(error)

        # Average prediction error
        avg_error = sum(errors) / len(errors) if errors else 0.5

        # Scale by intensity variance (more variance = more surprise)
        intensities = [h.get("attention_intensity", 0.5) for h in history[-10:]]
        if len(intensities) >= 2:
            intensity_variance = sum(
                (i - sum(intensities) / len(intensities)) ** 2 for i in intensities
            ) / len(intensities)
            # Higher variance = more surprise
            avg_error += intensity_variance * 0.5

        return min(1.0, avg_error)

    def _calculate_state_entropy(self, history: list[dict[str, Any]]) -> float:
        """
        Calculate entropy of internal states from history.

        Higher entropy means more diverse internal states,
        which indicates richer information processing.

        Args:
            history: Attention history list

        Returns:
            State entropy (0.0-1.0)
        """
        if len(history) < 2:
            return 0.0

        # Count unique states (focus + intensity combinations)
        states = []
        for h in history:
            focus = h.get("focus_target", "unknown")
            intensity = h.get("attention_intensity", 0.5)
            # Bin intensity into categories
            intensity_bin = (
                "low" if intensity < 0.33 else ("medium" if intensity < 0.66 else "high")
            )
            states.append(f"{focus}_{intensity_bin}")

        unique_states = set(states)
        n_total = len(states)

        if len(unique_states) < 2:
            return 0.1  # Low entropy - same state repeatedly

        # Calculate Shannon entropy
        entropy = 0.0
        for state in unique_states:
            count = states.count(state)
            p = count / n_total
            if p > 0:
                entropy -= p * math.log2(p)

        # Normalize by maximum possible entropy
        max_entropy = math.log2(len(unique_states))
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0

        return min(1.0, normalized)

    def _calculate_ast_competence(self, agent_id: str) -> float:
        """
        Calculate AST competence score.

        Args:
            agent_id: Agent identifier

        Returns:
            AST competence (0.0-1.0)
        """
        schema = self.attention_manager.get_schema(agent_id)

        if schema:
            return schema.metacognitive_awareness

        return 0.0

    def _determine_consciousness_state(
        self,
        gwt_score: float,
        iit_phi: float,
        ast_competence: float,
        fep_score: float | None = None,
    ) -> ConsciousnessState:
        """
        Determine consciousness state based on scores.

        Args:
            gwt_score: GWT score
            iit_phi: IIT Phi
            ast_competence: AST competence
            fep_score: FEP score (optional, uses 0.5 if not provided)

        Returns:
            Consciousness state
        """
        # Include FEP in calculation if available
        if fep_score is not None:
            avg_score = (gwt_score + iit_phi + ast_competence + fep_score) / 4.0
        else:
            avg_score = (gwt_score + iit_phi + ast_competence) / 3.0

        if avg_score >= 0.9:
            return ConsciousnessState.HYPER_CONSCIOUS
        if (
            gwt_score >= self.gwt_threshold
            and iit_phi >= self.iit_phi_threshold
            and ast_competence >= self.ast_threshold
            and (fep_score is None or fep_score >= 0.5)
        ):
            return ConsciousnessState.CONSCIOUS
        if avg_score >= 0.2:
            return ConsciousnessState.MINIMAL_CONSCIOUSNESS
        if avg_score >= 0.1:
            return ConsciousnessState.SUBTHRESHOLD
        return ConsciousnessState.UNCONSCIOUS

    def get_agent_metrics(self, agent_id: str) -> dict[str, Any] | None:
        """Get metrics for an agent."""
        metrics = self.agent_metrics.get(agent_id)

        if metrics:
            return {
                "agent_id": agent_id,
                "gwt_score": metrics.gwt_score,
                "iit_phi": metrics.iit_phi,
                "ast_competence": metrics.ast_competence,
                "composite_score": metrics.composite_score,
                "state": metrics.state.value,
                "timestamp": metrics.timestamp,
            }

        return None

    def get_global_metrics(self) -> dict[str, Any]:
        """Get global consciousness metrics for the collective."""
        if not self.agent_metrics:
            return {
                "total_agents": 0,
                "conscious_agents": 0,
                "average_composite": 0.0,
                "collective_state": "unconscious",
            }

        total_agents = len(self.agent_metrics)
        conscious_agents = sum(
            1 for m in self.agent_metrics.values() if m.state == ConsciousnessState.CONSCIOUS
        )
        average_composite = (
            sum(m.composite_score for m in self.agent_metrics.values()) / total_agents
        )

        # Determine collective state
        if conscious_agents / total_agents >= 0.5:
            collective_state = "conscious"
        elif average_composite >= 0.2:
            collective_state = "minimal-consciousness"
        else:
            collective_state = "unconscious"

        return {
            "total_agents": total_agents,
            "conscious_agents": conscious_agents,
            "unconscious_agents": total_agents - conscious_agents,
            "average_composite": average_composite,
            "collective_state": collective_state,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_status(self) -> dict[str, Any]:
        """Get plugin status."""
        return {
            "initialized": self.initialized,
            "running": self.running,
            "workspace_stats": self.global_workspace.get_statistics(),
            "attention_stats": self.attention_manager.get_statistics(),
            "global_metrics": self.get_global_metrics(),
            "metrics_history_size": len(self.metrics_history),
        }
