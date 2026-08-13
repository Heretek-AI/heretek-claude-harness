"""Zero-Trust exception categories, rules, and helper functions."""

from typing import Any

EXCEPTION_CATEGORIES = {
    "internal_topics": [
        "system.health",
        "system.failover",
        "triad.>",
        "health.>",
        "heartbeat.>",
    ],
    "verified_inputs": [
        "localhost",
        "docker_internal",
        "bridge_network",
    ],
    "pre_validated": [
        "pre-validated-content-type",
        "pydantic-validated",
        "schema-validated",
    ],
    "infrastructure": [
        "postgres",
        "redis",
        "qdrant",
        "nats",
    ],
}


EXCEPTION_RULES = {
    "system.health": {
        "reason": "Heartbeat monitoring for system liveness detection",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "INFO",
    },
    "system.failover": {
        "reason": "Failover coordination between redundant components",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": True,
        "audit_level": "WARNING",
    },
    "triad.>": {
        "reason": "Internal triad communication (Steward/Alpha/Beta/Charlie)",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": True,
        "audit_level": "INFO",
        "note": "Pattern match for any triad topic",
    },
    "health.>": {
        "reason": "Health reporting and monitoring endpoints",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "INFO",
        "note": "Pattern match for any health topic",
    },
    "heartbeat.>": {
        "reason": "Agent heartbeat signals for liveness",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
        "note": "Pattern match for any heartbeat topic",
    },
    "localhost": {
        "reason": "Local processes communicating via loopback",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
    },
    "docker_internal": {
        "reason": "Docker container internal networking",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
    },
    "bridge_network": {
        "reason": "Docker bridge network for container-to-host",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
    },
    "pre-validated-content-type": {
        "reason": "Content already validated by Pydantic schema",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
    },
    "pydantic-validated": {
        "reason": "Data validated by Pydantic v2 with extra=forbid",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
    },
    "schema-validated": {
        "reason": "Data validated against strict schema",
        "risk": "LOW",
        "sanitization_bypass": True,
        "requires_tls": False,
        "audit_level": "DEBUG",
    },
}


def get_exception_rule(topic_or_source: str) -> dict[str, Any] | None:
    """Look up exception rule for a topic or source."""
    if topic_or_source in EXCEPTION_RULES:
        return EXCEPTION_RULES[topic_or_source]

    for pattern, rule in EXCEPTION_RULES.items():
        if pattern.endswith(".>"):
            prefix = pattern[:-2]
            if topic_or_source.startswith(prefix):
                return rule

    return None


def is_exception_topic(topic: str) -> bool:
    """Check if topic is in exception list."""
    return get_exception_rule(topic) is not None


def should_sanitize(topic: str) -> bool:
    """Determine if content should be sanitized based on topic."""
    rule = get_exception_rule(topic)
    if rule:
        return not rule.get("sanitization_bypass", False)
    return True
