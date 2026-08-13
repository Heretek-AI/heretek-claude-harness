"""
Agent tier catalog for the configuration wizard.

Extracted from ``api/wizard.py`` as part of Phase 2.4 of PLAN.md
(§1.4 "Configuration service masquerading as a router"). The
``AGENT_TIERS`` dict defines the four pre-canned deployment
shapes (minimal / standard / enhanced / maximal) the wizard
offers. Moving it to :mod:`heretek_swarm.config` keeps the
wizard router thin and lets the deployment CLI, the wizard UI,
and the configuration service all draw from the same source.

Backwards compatibility: ``from heretek_swarm.api.wizard
import AGENT_TIERS`` keeps working — the wizard module
re-exports the constant from this file.
"""

from __future__ import annotations


AGENT_TIERS: dict[str, dict[str, object]] = {
    "minimal": {
        "id": "minimal",
        "name": "Minimal",
        "description": "Single agent for basic tasks",
        "agent_count": 1,
        "agents": ["coordinator"],
        "memory_enabled": False,
        "consciousness_enabled": False,
    },
    "standard": {
        "id": "standard",
        "name": "Standard",
        "description": "Multi-agent swarm for collaborative work",
        "agent_count": 5,
        "agents": [
            "coordinator",
            "coder",
            "examiner",
            "historian",
            "catalyst",
        ],
        "memory_enabled": True,
        "consciousness_enabled": False,
    },
    "enhanced": {
        "id": "enhanced",
        "name": "Enhanced",
        "description": "Full swarm with memory and coordination",
        "agent_count": 11,
        "agents": [
            "coordinator",
            "coder",
            "examiner",
            "historian",
            "catalyst",
            "explorer",
            "dreamer",
            "echo",
            "metis",
            "nexus",
            "arbiter",
        ],
        "memory_enabled": True,
        "consciousness_enabled": True,
    },
    "maximal": {
        "id": "maximal",
        "name": "Maximal",
        "description": "Complete 23-agent collective with full capabilities",
        "agent_count": 23,
        "agents": [
            "alpha",
            "beta",
            "charlie",
            "coordinator",
            "coder",
            "examiner",
            "historian",
            "catalyst",
            "explorer",
            "dreamer",
            "echo",
            "metis",
            "nexus",
            "arbiter",
            "prism",
            "perceiver",
            "perceiver_plus",
            "steward",
            "sentinel",
            "sentinel_prime",
            "triad",
            "handoff",
            "validation",
        ],
        "memory_enabled": True,
        "consciousness_enabled": True,
    },
}


__all__ = ["AGENT_TIERS"]
