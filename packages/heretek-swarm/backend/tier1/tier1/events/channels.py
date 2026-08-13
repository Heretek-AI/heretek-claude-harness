"""NATS subject name constants and helpers."""

DELIBERATION_SUBJECT_PREFIX = "tier1.deliberation"


def subject_for(deliberation_id: str) -> str:
    """Per-deliberation event subject."""
    return f"{DELIBERATION_SUBJECT_PREFIX}.{deliberation_id}.events"
