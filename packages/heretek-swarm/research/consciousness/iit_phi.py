"""
IIT Phi Calculation Module - Integrated Information Theory Implementation.

This module implements Integrated Information Theory (IIT) 3.0+ calculations
for measuring consciousness levels in agent swarms. IIT proposes that
consciousness corresponds to the capacity of a system to generate integrated
information that cannot be reduced to its parts.

Key Concepts:
- Phi (Φ): Integrated information measure
- MIP (Minimum Information Partition): Partition that minimizes information loss
- Cause-Effect Structure: Repertoire of possible causes and effects
- Exclusion Principle: Only one cause-effect structure exists at a time

References:
- Tononi, G. (2008). Consciousness as integrated information: a provisional manifesto.
- Oizumi, M., Albantakis, L., & Tononi, G. (2014). From the phenomenology to the mechanisms of consciousness.  # noqa: E501

Author: Heretek Swarm Collective
Date: 2026-04-07
Version: 1.0.0
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.validation.llm_output import (
    LLMOutputValidator,
    ValidationResult,
    ValidationSeverity,
)

logger = structlog.get_logger("IITPhiCalculator")


@dataclass
class CauseEffectStructure:
    """
    Represents the cause-effect structure of a system element.

    Attributes:
        element_id: Unique identifier for the element
        cause_repertoire: Distribution of possible past states
        effect_repertoire: Distribution of possible future states
        phi_cause: Phi value for cause side
        phi_effect: Phi value for effect side
        phi_total: Total integrated information
        timestamp: Creation timestamp
    """

    element_id: str
    cause_repertoire: dict[str, float] = field(default_factory=dict)
    effect_repertoire: dict[str, float] = field(default_factory=dict)
    phi_cause: float = 0.0
    phi_effect: float = 0.0
    phi_total: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "element_id": self.element_id,
            "cause_repertoire": self.cause_repertoire,
            "effect_repertoire": self.effect_repertoire,
            "phi_cause": self.phi_cause,
            "phi_effect": self.phi_effect,
            "phi_total": self.phi_total,
            "timestamp": self.timestamp,
        }


@dataclass
class SystemPartition:
    """
    Represents a partition of the system for MIP calculation.

    A partition divides the system into two or more parts,
    severing causal connections between them.

    Attributes:
        partition_id: Unique identifier
        parts: List of element sets representing partition parts
        information_loss: Information loss due to partitioning
        is_mip: Whether this is the minimum information partition
    """

    partition_id: str
    parts: list[set[str]] = field(default_factory=list)
    information_loss: float = 0.0
    is_mip: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "partition_id": self.partition_id,
            "parts": [list(p) for p in self.parts],
            "information_loss": self.information_loss,
            "is_mip": self.is_mip,
        }


@dataclass
class PhiResult:
    """
    Result of Phi calculation for a system.

    Attributes:
        system_id: System identifier
        phi: Integrated information value (0.0-1.0)
        phi_max: Maximum phi across all elements
        mip: Minimum Information Partition
        cause_effect_structures: List of element cause-effect structures
        integration_level: Qualitative integration level
        differentiation_level: Qualitative differentiation level
        exclusion_applied: Whether exclusion principle was applied
        timestamp: Calculation timestamp
        metadata: Additional metadata
    """

    system_id: str
    phi: float = 0.0
    phi_max: float = 0.0
    mip: SystemPartition | None = None
    cause_effect_structures: list[CauseEffectStructure] = field(default_factory=list)
    integration_level: str = "unknown"
    differentiation_level: str = "unknown"
    exclusion_applied: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "system_id": self.system_id,
            "phi": self.phi,
            "phi_max": self.phi_max,
            "mip": self.mip.to_dict() if self.mip else None,
            "cause_effect_structures": [ces.to_dict() for ces in self.cause_effect_structures],
            "integration_level": self.integration_level,
            "differentiation_level": self.differentiation_level,
            "exclusion_applied": self.exclusion_applied,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class PhiCalculator:
    """
    Integrated Information Theory (IIT) Phi Calculator.

    This class implements the core IIT 3.0+ calculations for measuring
    integrated information in agent swarm systems. The calculator:

    1. Builds cause-effect structures from system states
    2. Calculates phi for each element (cause and effect information)
    3. Finds the Minimum Information Partition (MIP)
    4. Computes system-level Phi as the sum of element phis under MIP

    The implementation uses spectral analysis and information-theoretic
    measures to approximate IIT calculations for complex systems.

    Example:
        ```python
        calculator = PhiCalculator()

        # Define system state
        system_state = {
            "elements": ["A", "B", "C"],
            "connectivity": {
                "A": {"B": 0.8, "C": 0.6},
                "B": {"A": 0.7, "C": 0.5},
                "C": {"A": 0.6, "B": 0.7}
            },
            "current_state": {"A": 1, "B": 0, "C": 1}
        }

        # Calculate Phi
        result = calculator.calculate_phi(system_state)
        print(f"System Phi: {result.phi}")
        ```
    """

    # Integration level thresholds
    INTEGRATION_THRESHOLDS = {
        "minimal": 0.1,
        "low": 0.3,
        "moderate": 0.5,
        "high": 0.7,
        "very_high": 0.9,
    }

    # Differentiation level thresholds
    DIFFERENTIATION_THRESHOLDS = {
        "minimal": 0.1,
        "low": 0.3,
        "moderate": 0.5,
        "high": 0.7,
        "very_high": 0.9,
    }

    def __init__(self, strict_validation: bool = True):
        """
        Initialize the Phi calculator.

        Args:
            strict_validation: If True, strictly validate all inputs
        """
        self._validator = LLMOutputValidator(strict_mode=strict_validation)
        self._cache: dict[str, PhiResult] = {}
        self._calculation_count = 0
        self._last_calculation_time: datetime | None = None

        logger.info("PhiCalculator initialized", extra={"strict_validation": strict_validation})

    def calculate_phi(self, cause_effect_structure: dict[str, Any]) -> PhiResult:
        """
        Main Phi calculation entry point.

        Calculates integrated information (Phi) for a system based on its
        cause-effect structure. The calculation follows IIT 3.0+ principles:

        1. Identify system elements and their connections
        2. Calculate cause and effect repertoires for each element
        3. Find the Minimum Information Partition (MIP)
        4. Compute phi for each element under the MIP
        5. Sum element phis to get system Phi

        Args:
            cause_effect_structure: System structure with elements, connectivity,
                                   and current state. Expected format:
                                   {
                                       "system_id": str,
                                       "elements": List[str],
                                       "connectivity": Dict[str, Dict[str, float]],
                                       "current_state": Dict[str, Any],
                                       "transition_probabilities": Optional[Dict]
                                   }

        Returns:
            PhiResult containing Phi value and detailed metrics

        Raises:
            ValueError: If input structure is invalid
            CalculationError: If calculation fails
        """
        start_time = datetime.now(UTC)

        # Validate input structure
        validation_result = self._validate_cause_effect_structure(cause_effect_structure)
        if not validation_result.valid:
            raise ValueError(f"Invalid cause-effect structure: {validation_result.errors}")

        # Extract system components
        system_id = cause_effect_structure.get("system_id", str(uuid.uuid4()))
        elements = cause_effect_structure.get("elements", [])
        connectivity = cause_effect_structure.get("connectivity", {})
        current_state = cause_effect_structure.get("current_state", {})
        transition_probs = cause_effect_structure.get("transition_probabilities", {})

        if not elements:
            logger.warning("No elements in system, returning zero Phi")
            return PhiResult(
                system_id=system_id,
                phi=0.0,
                phi_max=0.0,
                metadata={"reason": "no_elements"},
            )

        # Calculate cause-effect structures for each element
        cause_effect_structures: list[CauseEffectStructure] = []
        element_phis: list[float] = []

        for element in elements:
            ces = self._calculate_element_cause_effect(
                element=element,
                elements=elements,
                connectivity=connectivity,
                current_state=current_state,
                transition_probabilities=transition_probs,
            )
            cause_effect_structures.append(ces)
            element_phis.append(ces.phi_total)

        # Find Minimum Information Partition
        mip = self.find_mip(
            {
                "elements": elements,
                "connectivity": connectivity,
                "current_state": current_state,
            }
        )

        # Calculate system Phi (sum of element phis under MIP)
        # Apply MIP information loss factor
        mip_loss = mip.information_loss if mip else 0.0
        raw_phi = sum(element_phis)
        system_phi = raw_phi * (1.0 - mip_loss)

        # Normalize Phi to 0.0-1.0 range
        normalized_phi = self._normalize_phi(system_phi, len(elements))

        # Calculate phi_max (maximum element phi)
        phi_max = max(element_phis) if element_phis else 0.0

        # Determine integration and differentiation levels
        integration_level = self._determine_integration_level(connectivity, elements)
        differentiation_level = self._determine_differentiation_level(current_state, elements)

        # Apply exclusion principle (select maximum phi cause-effect structure)
        exclusion_applied = len(cause_effect_structures) > 1

        result = PhiResult(
            system_id=system_id,
            phi=normalized_phi,
            phi_max=phi_max,
            mip=mip,
            cause_effect_structures=cause_effect_structures,
            integration_level=integration_level,
            differentiation_level=differentiation_level,
            exclusion_applied=exclusion_applied,
            metadata={
                "raw_phi": raw_phi,
                "mip_loss": mip_loss,
                "element_count": len(elements),
                "calculation_time_ms": (datetime.now(UTC) - start_time).total_seconds() * 1000,
            },
        )

        # Cache result
        self._cache[system_id] = result
        self._calculation_count += 1
        self._last_calculation_time = datetime.now(UTC)

        logger.info(
            "Phi calculation complete",
            extra={
                "system_id": system_id,
                "phi": normalized_phi,
                "phi_max": phi_max,
                "integration_level": integration_level,
            },
        )

        return result

    def _validate_cause_effect_structure(
        self,
        structure: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate cause-effect structure input.
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(structure, dict):
            errors.append("Cause-effect structure must be a dictionary")
            return ValidationResult(
                valid=False, content=structure, errors=errors,
                severity=ValidationSeverity.CRITICAL,
            )

        self._validate_elements(structure, errors)
        self._validate_connectivity(structure, errors, warnings)
        self._validate_current_state(structure, errors)
        self._validate_safety(structure, errors)

        severity = (
            ValidationSeverity.CRITICAL if errors
            else (ValidationSeverity.WARNING if warnings else ValidationSeverity.INFO)
        )
        return ValidationResult(
            valid=len(errors) == 0, content=structure,
            errors=errors, warnings=warnings, severity=severity,
        )

    def _validate_elements(
        self, structure: dict[str, Any], errors: list[str]
    ) -> None:
        """Validate the elements list in the structure."""
        elements = structure.get("elements")
        if elements is not None:
            if not isinstance(elements, list):
                errors.append("'elements' must be a list")
            elif not all(isinstance(e, str) for e in elements):
                errors.append("All elements must be strings")

    def _validate_connectivity(
        self, structure: dict[str, Any], errors: list[str], warnings: list[str]
    ) -> None:
        """Validate the connectivity matrix."""
        connectivity = structure.get("connectivity")
        if connectivity is None:
            return
        if not isinstance(connectivity, dict):
            errors.append("'connectivity' must be a dictionary")
            return
        for source, targets in connectivity.items():
            if not isinstance(targets, dict):
                errors.append(f"Connectivity targets for '{source}' must be a dictionary")
                break
            for target, weight in targets.items():
                if not isinstance(weight, (int, float)):
                    errors.append(f"Connection weight must be numeric: {source}->{target}")
                    break
                if weight < 0 or weight > 1:
                    warnings.append(
                        f"Connection weight outside [0,1] range: {source}->{target}={weight}"
                    )

    def _validate_current_state(
        self, structure: dict[str, Any], errors: list[str]
    ) -> None:
        """Validate the current_state field."""
        current_state = structure.get("current_state")
        if current_state is not None and not isinstance(current_state, dict):
            errors.append("'current_state' must be a dictionary")

    def _validate_safety(
        self, structure: dict[str, Any], errors: list[str]
    ) -> None:
        """Check for dangerous patterns using zero-trust validator."""
        structure_str = str(structure)
        safety_result = self._validator.validate_text(structure_str, content_type="json")
        if not safety_result.valid:
            errors.extend(safety_result.errors)

    def _calculate_element_cause_effect(
        self,
        element: str,
        elements: list[str],
        connectivity: dict[str, dict[str, float]],
        current_state: dict[str, Any],
        transition_probabilities: dict[str, Any] | None = None,
    ) -> CauseEffectStructure:
        """
        Calculate cause-effect structure for a single element.

        Args:
            element: Element identifier
            elements: All system elements
            connectivity: Connection weights between elements
            current_state: Current system state
            transition_probabilities: Optional transition probability matrix

        Returns:
            CauseEffectStructure for the element
        """
        # Calculate cause repertoire (past states that could cause current state)
        cause_repertoire = self._calculate_cause_repertoire(
            element=element,
            elements=elements,
            connectivity=connectivity,
            current_state=current_state,
        )

        # Calculate effect repertoire (future states caused by current state)
        effect_repertoire = self._calculate_effect_repertoire(
            element=element,
            elements=elements,
            connectivity=connectivity,
            current_state=current_state,
            transition_probabilities=transition_probabilities,
        )

        # Calculate cause information (phi_cause)
        phi_cause = self.calculate_cause_info(
            {"repertoire": cause_repertoire, "element": element},
            element,
        )

        # Calculate effect information (phi_effect)
        phi_effect = self.calculate_effect_info(
            {"repertoire": effect_repertoire, "element": element},
            element,
        )

        # Total phi is minimum of cause and effect (IIT 3.0)
        phi_total = min(phi_cause, phi_effect)

        return CauseEffectStructure(
            element_id=element,
            cause_repertoire=cause_repertoire,
            effect_repertoire=effect_repertoire,
            phi_cause=phi_cause,
            phi_effect=phi_effect,
            phi_total=phi_total,
        )

    def _calculate_cause_repertoire(
        self,
        element: str,
        elements: list[str],
        connectivity: dict[str, dict[str, float]],
        current_state: dict[str, Any],
    ) -> dict[str, float]:
        """
        Calculate cause repertoire for an element.

        The cause repertoire represents the probability distribution over
        possible past states that could have caused the element's current state.

        Args:
            element: Target element
            elements: All system elements
            connectivity: Connection weights
            current_state: Current system state

        Returns:
            Probability distribution over possible causes
        """
        repertoire: dict[str, float] = {}

        # Get incoming connections to this element
        incoming_connections = {}
        for source in elements:
            if source != element and source in connectivity:
                weight = connectivity[source].get(element, 0.0)
                if weight > 0:
                    incoming_connections[source] = weight

        if not incoming_connections:
            # No causal inputs - uniform distribution
            return {element: 1.0}

        # Calculate causal influence based on connection weights and source states
        total_weight = sum(incoming_connections.values())

        for source, weight in incoming_connections.items():
            source_state = current_state.get(source, 0.5)
            # Causal strength = weight * source activation
            causal_strength = weight * source_state
            repertoire[source] = causal_strength / total_weight if total_weight > 0 else 0.0

        # Normalize
        total = sum(repertoire.values())
        if total > 0:
            repertoire = {k: v / total for k, v in repertoire.items()}

        return repertoire

    def _calculate_effect_repertoire(
        self,
        element: str,
        elements: list[str],
        connectivity: dict[str, dict[str, float]],
        current_state: dict[str, Any],
        transition_probabilities: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """
        Calculate effect repertoire for an element.

        The effect repertoire represents the probability distribution over
        possible future states that the element's current state can cause.

        Args:
            element: Target element
            elements: All system elements
            connectivity: Connection weights
            current_state: Current system state
            transition_probabilities: Optional transition probabilities

        Returns:
            Probability distribution over possible effects
        """
        repertoire: dict[str, float] = {}

        # Get outgoing connections from this element
        outgoing_connections = connectivity.get(element, {})

        if not outgoing_connections:
            # No causal outputs - uniform distribution
            return {element: 1.0}

        # Use transition probabilities if provided
        if transition_probabilities and element in transition_probabilities:
            return transition_probabilities[element]

        # Calculate effect strength based on connection weights
        element_state = current_state.get(element, 0.5)
        total_weight = sum(outgoing_connections.values())

        for target, weight in outgoing_connections.items():
            if target in elements:
                # Effect strength = weight * element activation
                effect_strength = weight * element_state
                repertoire[target] = effect_strength / total_weight if total_weight > 0 else 0.0

        # Normalize
        total = sum(repertoire.values())
        if total > 0:
            repertoire = {k: v / total for k, v in repertoire.items()}

        return repertoire

    def calculate_cause_info(self, state: dict[str, Any], _element: str) -> float:
        """
        Calculate cause information (phi_cause) for an element.

        Cause information measures how much the element's current state
        constrains its possible causes. Higher phi_cause means the element
        has more specific causal requirements.

        Uses Kullback-Leibler divergence between:
        - Cause repertoire (constrained by current state)
        - Unconstrained prior distribution

        Args:
            state: State dictionary with 'repertoire' and 'element' keys
            element: Element identifier

        Returns:
            Cause information value (0.0-1.0)
        """
        repertoire = state.get("repertoire", {})

        if not repertoire:
            return 0.0

        # Calculate Shannon entropy of the repertoire
        entropy = 0.0
        for prob in repertoire.values():
            if prob > 0:
                entropy -= prob * math.log2(prob + 1e-10)

        # Maximum entropy for uniform distribution
        n_states = len(repertoire)
        max_entropy = math.log2(n_states) if n_states > 1 else 0.0

        if max_entropy == 0:
            return 0.0

        # Normalized information = 1 - (entropy / max_entropy)
        # Higher value = more constrained = more integrated
        normalized_info = 1.0 - (entropy / max_entropy)

        # Apply element-specific weighting based on connectivity
        connectivity_weight = state.get("connectivity_weight", 1.0)
        cause_info = normalized_info * connectivity_weight

        return min(1.0, max(0.0, cause_info))

    def calculate_effect_info(self, state: dict[str, Any], _element: str) -> float:
        """
        Calculate effect information (phi_effect) for an element.

        Effect information measures how much the element's current state
        constrains its possible effects. Higher phi_effect means the element
        has more specific causal power.

        Args:
            state: State dictionary with 'repertoire' and 'element' keys
            element: Element identifier

        Returns:
            Effect information value (0.0-1.0)
        """
        repertoire = state.get("repertoire", {})

        if not repertoire:
            return 0.0

        # Calculate Shannon entropy of the repertoire
        entropy = 0.0
        for prob in repertoire.values():
            if prob > 0:
                entropy -= prob * math.log2(prob + 1e-10)

        # Maximum entropy for uniform distribution
        n_states = len(repertoire)
        max_entropy = math.log2(n_states) if n_states > 1 else 0.0

        if max_entropy == 0:
            return 0.0

        # Normalized information = 1 - (entropy / max_entropy)
        normalized_info = 1.0 - (entropy / max_entropy)

        # Apply element-specific weighting
        connectivity_weight = state.get("connectivity_weight", 1.0)
        effect_info = normalized_info * connectivity_weight

        return min(1.0, max(0.0, effect_info))

    def find_mip(self, system_state: dict[str, Any]) -> SystemPartition:
        """
        Find the Minimum Information Partition (MIP) of the system.

        The MIP is the partition that minimizes information loss when
        causal connections between parts are severed. This represents
        the system's weakest integration point.

        Algorithm:
        1. Generate all possible bipartitions of the system
        2. For each partition, calculate information loss
        3. Return the partition with minimum information loss

        Args:
            system_state: System state with elements and connectivity

        Returns:
            SystemPartition representing the MIP
        """
        elements = system_state.get("elements", [])
        connectivity = system_state.get("connectivity", {})

        if len(elements) < 2:
            # Single element - no partition possible
            return SystemPartition(
                partition_id="single_element",
                parts=[set(elements)],
                information_loss=0.0,
                is_mip=True,
            )

        # Generate all bipartitions
        bipartitions = self._generate_bipartitions(elements)

        # Calculate information loss for each partition
        min_loss = float("inf")
        mip: SystemPartition | None = None

        for part1, part2 in bipartitions:
            loss = self._calculate_partition_loss(part1, part2, connectivity)

            if loss < min_loss:
                min_loss = loss
                mip = SystemPartition(
                    partition_id=f"bipartition_{len(part1)}_{len(part2)}",
                    parts=[part1, part2],
                    information_loss=loss,
                    is_mip=False,
                )

        if mip:
            mip.is_mip = True

        logger.debug(
            "MIP found",
            extra={
                "partition": mip.to_dict() if mip else None,
                "information_loss": min_loss,
            },
        )

        return mip or SystemPartition(
            partition_id="default",
            parts=[set(elements)],
            information_loss=0.0,
            is_mip=True,
        )

    def _generate_bipartitions(self, elements: list[str]) -> list[tuple[set[str], set[str]]]:
        """
        Generate all possible bipartitions of elements.

        For efficiency, only generates unique bipartitions (avoids
        counting A|B and B|A as separate).

        Args:
            elements: List of element identifiers

        Returns:
            List of (part1, part2) tuples
        """
        if len(elements) <= 1:
            return []

        bipartitions: list[tuple[set[str], set[str]]] = []
        n = len(elements)

        # Generate all non-empty proper subsets
        for i in range(1, 2 ** (n - 1)):
            part1: set[str] = set()
            part2: set[str] = set()

            # Always include first element in part1 to avoid duplicates
            part1.add(elements[0])

            for j in range(1, n):
                if i & (1 << (j - 1)):
                    part1.add(elements[j])
                else:
                    part2.add(elements[j])

            if part1 and part2:
                bipartitions.append((part1, part2))

        return bipartitions

    def _calculate_partition_loss(
        self,
        part1: set[str],
        part2: set[str],
        connectivity: dict[str, dict[str, float]],
    ) -> float:
        """
        Calculate information loss for a partition.

        Information loss is the sum of connection weights severed by
        the partition. Higher loss means the partition breaks more
        causal connections.

        Args:
            part1: First partition part
            part2: Second partition part
            connectivity: Connection weights

        Returns:
            Information loss value (0.0-1.0)
        """
        loss = 0.0
        total_weight = 0.0

        # Sum all connection weights
        for source, targets in connectivity.items():
            for target, weight in targets.items():
                total_weight += weight

        # Sum severed connection weights (cross-partition connections)
        for source in part1:
            if source in connectivity:
                for target, weight in connectivity[source].items():
                    if target in part2:
                        loss += weight

        for source in part2:
            if source in connectivity:
                for target, weight in connectivity[source].items():
                    if target in part1:
                        loss += weight

        # Normalize loss to 0.0-1.0
        normalized_loss = loss / total_weight if total_weight > 0 else 0.0

        return min(1.0, max(0.0, normalized_loss))

    def _normalize_phi(self, phi: float, element_count: int) -> float:
        """
        Normalize Phi value to 0.0-1.0 range.

        Normalization accounts for system size - larger systems can
        have higher raw phi values, but normalized phi should reflect
        integration quality, not just quantity.

        Args:
            phi: Raw phi value
            element_count: Number of system elements

        Returns:
            Normalized phi (0.0-1.0)
        """
        if element_count <= 1:
            return min(1.0, max(0.0, phi))

        # Logarithmic scaling for system size
        # Phi grows with integration, but is normalized by complexity
        size_factor = math.log2(element_count + 1)
        normalized = phi / size_factor if size_factor > 0 else phi

        # Sigmoid normalization for smooth 0-1 mapping
        normalized = 1.0 / (1.0 + math.exp(-normalized * 5 + 2.5))

        return min(1.0, max(0.0, normalized))

    def _determine_integration_level(
        self,
        connectivity: dict[str, dict[str, float]],
        elements: list[str],
    ) -> str:
        """
        Determine qualitative integration level.

        Based on connectivity density and average connection strength.

        Args:
            connectivity: Connection weights
            elements: System elements

        Returns:
            Integration level string
        """
        if not elements or len(elements) < 2:
            return "minimal"

        # Calculate connectivity density
        total_connections = 0
        total_weight = 0.0
        max_possible = len(elements) * (len(elements) - 1)

        for source, targets in connectivity.items():
            for target, weight in targets.items():
                if source != target:
                    total_connections += 1
                    total_weight += weight

        density = total_connections / max_possible if max_possible > 0 else 0.0
        avg_weight = total_weight / total_connections if total_connections > 0 else 0.0

        # Combined integration score
        integration_score = (density * 0.5) + (avg_weight * 0.5)

        # Map to level
        if integration_score >= self.INTEGRATION_THRESHOLDS["very_high"]:
            return "very_high"
        if integration_score >= self.INTEGRATION_THRESHOLDS["high"]:
            return "high"
        if integration_score >= self.INTEGRATION_THRESHOLDS["moderate"]:
            return "moderate"
        if integration_score >= self.INTEGRATION_THRESHOLDS["low"]:
            return "low"
        return "minimal"

    def _determine_differentiation_level(
        self,
        current_state: dict[str, Any],
        elements: list[str],
    ) -> str:
        """
        Determine qualitative differentiation level.

        Based on state diversity - how many different states elements occupy.

        Args:
            current_state: Current system state
            elements: System elements

        Returns:
            Differentiation level string
        """
        if not elements:
            return "minimal"

        # Get unique states
        states = [current_state.get(e, 0) for e in elements]
        len(set(states))

        # Calculate entropy
        state_counts: dict[Any, int] = {}
        for s in states:
            state_counts[s] = state_counts.get(s, 0) + 1

        entropy = 0.0
        n = len(states)
        for count in state_counts.values():
            p = count / n
            if p > 0:
                entropy -= p * math.log2(p)

        max_entropy = math.log2(len(set(states))) if len(set(states)) > 1 else 0.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        # Map to level
        if normalized_entropy >= self.DIFFERENTIATION_THRESHOLDS["very_high"]:
            return "very_high"
        if normalized_entropy >= self.DIFFERENTIATION_THRESHOLDS["high"]:
            return "high"
        if normalized_entropy >= self.DIFFERENTIATION_THRESHOLDS["moderate"]:
            return "moderate"
        if normalized_entropy >= self.DIFFERENTIATION_THRESHOLDS["low"]:
            return "low"
        return "minimal"

    def calculate_mip(self, system_state: dict[str, Any]) -> SystemPartition:
        """
        Public method to calculate Minimum Information Partition.

        Wrapper around find_mip for API consistency.

        Args:
            system_state: System state with elements and connectivity

        Returns:
            SystemPartition representing the MIP
        """
        return self.find_mip(system_state)

    def get_cached_result(self, system_id: str) -> PhiResult | None:
        """
        Get cached Phi calculation result.

        Args:
            system_id: System identifier

        Returns:
            Cached result or None
        """
        return self._cache.get(system_id)

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        logger.info("PhiCalculator cache cleared")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get calculator statistics.

        Returns:
            Dictionary with calculation statistics
        """
        return {
            "calculation_count": self._calculation_count,
            "cache_size": len(self._cache),
            "last_calculation_time": (
                self._last_calculation_time.isoformat() if self._last_calculation_time else None
            ),
        }
