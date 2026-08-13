"""Actor mixins for reusable functionality.

These mixins extract common patterns from actor files to reduce duplication.
"""

from .audit import AuditMixin
from .deliberation import DeliberationMixin
from .health_reporting import HealthReportingMixin
from .learning import LearningMixin
from .memory import MemoryMixin
from .memory_access import MemoryAccessMixin
from .pattern import PatternMixin
from .pattern_consumer import PatternConsumerMixin
from .tribunal import TribunalMixin
from .validation import ValidationMixin

__all__ = [
    "AuditMixin",
    "DeliberationMixin",
    "HealthReportingMixin",
    "LearningMixin",
    "MemoryAccessMixin",
    "MemoryMixin",
    "PatternConsumerMixin",
    "PatternMixin",
    "TribunalMixin",
    "ValidationMixin",
]
