"""
TierCircuitBreaker - Per-tier sliding-window circuit breaker.

D003 mandates a tier-based circuit breaker to prevent cascading restart storms
when a shared dependency (LLM provider) fails.  The existing per-agent
max_restarts does not catch shared-dependency cascades - 23 agents x 3 retries
= 69 restart attempts.  A per-tier sliding-window gate stops the cascade at
the source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# Agent-id prefix → tier classification.
# Defaults to the agent_id itself when no prefix matches.
TIER_MAP: dict[str, str] = {
    # Tier 1 - Core Triad
    "alpha": "triad",
    "beta": "triad",
    "charlie": "triad",
    "steward": "triad",
    # Tier 2 - Support / Analysts
    "historian": "analyst",
    "metis": "analyst",
    "empath": "analyst",
    "perceiver": "perception",
    "echo": "perception",
    # Tier 3 - Exploration & Specialist
    "explorer": "exploration",
    "examiner": "exploration",
    "dreamer": "exploration",
    "coder": "specialist",
    "architect": "specialist",
    # Tier 4 - Safety & Security (core guardians)
    "sentinel": "core",
    "sentinel_prime": "core",
    "arbiter": "core",
    # Tier 5 - Coordination
    "coordinator": "coordination",
    "nexus": "coordination",
    "catalyst": "coordination",
    "chronos": "coordination",
    # Tier 6 - Enhancement
    "prism": "enhancement",
    "habit_forge": "enhancement",
    "perceiver_plus": "perception",
}


@dataclass
class TierCircuitBreaker:
    """Per-tier sliding-window circuit breaker.

    Tracks failure timestamps per tier in a sliding window.  When the
    failure count within the window exceeds *failure_threshold*, the
    circuit for that tier opens and remains open until explicitly reset
    or until the window slides clear of failures.

    Attributes:
        window_seconds: Sliding-window duration (default 60 s).
        failure_threshold: Failures per tier before opening (default 5).
    """

    window_seconds: int = 60
    failure_threshold: int = 5

    # Per-tier list of failure timestamps (seconds since epoch).
    _windows: dict[str, list[float]] = field(default_factory=dict)
    # Tiers whose circuit is currently open.
    _open_circuits: set[str] = field(default_factory=set)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def classify_tier(agent_id: str) -> str:
        """Derive a tier label from an agent_id prefix.

        Splits the *agent_id* on ``-`` or ``_`` and matches the first
        segment against :data:`TIER_MAP`.  Falls back to the raw
        *agent_id* if no known prefix is found.
        """
        # Normalise: try dash split first, then underscore.
        parts = agent_id.replace("_", "-").split("-")
        prefix = parts[0].lower() if parts else agent_id.lower()
        return TIER_MAP.get(prefix, agent_id)

    def record_failure(self, tier: str) -> bool:
        """Record a failure for *tier*.

        Returns ``True`` if the circuit *just opened* as a result of
        this failure (i.e. the failure pushed the count past the
        threshold).  Returns ``False`` otherwise.
        """
        now = time.monotonic()

        # Ensure the window list exists.
        if tier not in self._windows:
            self._windows[tier] = []

        # Evict expired timestamps before recording the new failure.
        self._windows[tier] = [
            ts for ts in self._windows[tier] if now - ts <= self.window_seconds
        ]

        # Record the new failure.
        self._windows[tier].append(now)

        # Check threshold.
        if len(self._windows[tier]) >= self.failure_threshold and tier not in self._open_circuits:
            self._open_circuits.add(tier)
            return True

        return False

    def is_open(self, tier: str) -> bool:
        """Return ``True`` if the circuit for *tier* is currently open.

        Also performs lazy eviction of expired failures - if all
        failures in the window have expired while the circuit was open,
        the circuit auto-closes.  If the circuit was set open but has
        no recorded failures (manual override), it stays open until
        explicitly :meth:`reset`.
        """
        if tier not in self._open_circuits:
            return False

        # If there are no failure records at all, stay open (manual override).
        window = self._windows.get(tier, [])
        if not window:
            return True

        # Lazy auto-close: if all failures have aged out, reset.
        now = time.monotonic()
        self._windows[tier] = [
            ts for ts in window if now - ts <= self.window_seconds
        ]

        if not self._windows[tier]:
            self._open_circuits.discard(tier)
            return False

        return True

    def reset(self, tier: str) -> None:
        """Manually reset (close) the circuit for *tier*.

        Clears the failure window and removes the tier from the
        open-circuits set.  Idempotent - safe to call on a tier that
        is not open.
        """
        self._windows.pop(tier, None)
        self._open_circuits.discard(tier)
