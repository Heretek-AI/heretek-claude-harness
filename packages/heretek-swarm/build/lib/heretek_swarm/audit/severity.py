"""Severity taxonomy for audit findings."""

from enum import Enum, auto


class Severity(Enum):
    """Severity levels for audit findings.

    CRITICAL: Immediate quality issues that break functionality or indicate
        placeholder code in production paths.
        Examples: hardcoded mock data, pass-only handlers, NotImplementedError
        modules, demo loops in production, empty returns where data expected.

    WARNING: Code that may work but violates design conventions or hides
        potential bugs.
        Examples: `create_sample_*` functions, <5 line bodies, silent exception
        swallowing, never-true conditionals.

    INFO: Code style concerns, maintainability hints, or documentation gaps.
        Examples: duplicate definitions, to-do comments, complexity concerns.
    """

    CRITICAL = auto()
    WARNING = auto()
    INFO = auto()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_critical(severity: Severity | str) -> bool:
    """Return True if severity is CRITICAL."""
    if isinstance(severity, str):
        return severity.upper() == "CRITICAL"
    return severity == Severity.CRITICAL


def is_warning(severity: Severity | str) -> bool:
    """Return True if severity is WARNING."""
    if isinstance(severity, str):
        return severity.upper() == "WARNING"
    return severity == Severity.WARNING


def is_info(severity: Severity | str) -> bool:
    """Return True if severity is INFO."""
    if isinstance(severity, str):
        return severity.upper() == "INFO"
    return severity == Severity.INFO
