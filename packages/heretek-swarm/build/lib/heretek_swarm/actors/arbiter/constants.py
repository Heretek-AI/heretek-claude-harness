"""
Arbiter Constants

Contains magic numbers and tuning parameters for the Arbiter agent.
"""

# Conflict resolution thresholds
MAX_CONFLICTS = 1000  # Maximum conflicts to track in history

# Relationship decay
RELATIONSHIP_DECAY = 0.01  # Health score decay per interaction

# Cooperation bonuses (positive interaction)
COOPERATION_BONUS = 0.05  # Health score increase on cooperative interaction
COOPERATION_TRUST_BONUS = 0.01  # Trust level increase on cooperative interaction

# Conflict penalties (negative interaction)
CONFLICT_PENALTY = 0.1  # Health score decrease on conflict
CONFLICT_TRUST_PENALTY = 0.05  # Trust level decrease on conflict

# Resolution recovery bonuses
RESOLUTION_HEALTH_BONUS = 0.1  # Health score increase when conflict resolved
RESOLUTION_TRUST_BONUS = 0.05  # Trust level increase when conflict resolved

# Mediation bonuses
MEDIATION_HEALTH_BONUS = 0.1  # Health score increase from successful mediation

# Default initial values
DEFAULT_HEALTH_SCORE = 0.7  # Starting health for new relationships
DEFAULT_TRUST_LEVEL = 0.5  # Starting trust for new relationships
DEFAULT_NEUTRAL_HEALTH = 0.5  # Default for missing relationships

# Relationship attention threshold
RELATIONSHIP_ATTENTION_THRESHOLD = 0.5  # Below this triggers attention recommendation
UNHEALTHY_RELATIONSHIP_THRESHOLD = 0.3  # Below this needs immediate attention

# Pattern confidence thresholds
PATTERN_MIN_CONFIDENCE = 0.5  # Minimum confidence for recommendations
HIGH_CONFIDENCE_THRESHOLD = 0.7  # Threshold for high-confidence patterns

# Memory optimization thresholds
FROZEN_MEMORY_RATIO_THRESHOLD = 0.5  # Alert when frozen count exceeds this ratio

# Statistics thresholds
HIGH_CONFLICT_VOLUME = 50  # Threshold for high conflict volume warning
FAILED_RESOLUTION_THRESHOLD = 10  # Threshold for multiple failed resolutions warning
