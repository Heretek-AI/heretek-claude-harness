"""
GoalProposer — structured prompt template for goal proposal generation.

MetisAgent calls :meth:`GoalProposer.generate_proposal_prompt` to build a
prompt that instructs the LLM to produce a strategic goal as parseable JSON,
then calls :meth:`GoalProposer.parse_llm_response` to convert the LLM's
raw string into a dict safe for constructing a :class:`Goal`.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

logger = structlog.get_logger("GoalProposer")

# ---------------------------------------------------------------------------
# Prompt template constants
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are Metis, the strategic planning specialist for the Heretek swarm — "
    "an autonomous multi-agent system. Your role is to propose strategic goals "
    "that advance the swarm's capabilities."
)

_GOAL_PROPOSAL_PROMPT = """\
Propose a strategic goal for the Heretek autonomous swarm.

The swarm consists of:
- Steward (orchestration) — the lead agent coordinating operations
- Arbiter (governance) — validates ethical boundaries and consensus
- Metis (strategy) — strategic planning and foresight
- Cronos (scheduling) — timeline and cadence management
- Historian (memory) — event persistence and retrieval
- Empath (sentiment) — emotional and tonal analysis
- Maester (devops) — infrastructure and tool management
- Harbinger (alerts) — notification routing
- Perceiver (input) — external signal ingestion
- Aether (comm layer) — inter-agent messaging

The goal should be achievable within a small number of implementation cycles
and should advance the swarm's autonomy or capability.

Return ONLY a JSON object (no markdown, no code fences, no commentary) with
these exact keys:

- "title": A short, descriptive title (1 line)
- "description": Full goal description with motivation and scope (2-4 sentences)
- "success_criteria": An array of measurable, verifiable criteria (3-5 items)
- "estimated_node_types": An array of 1-3 workflow node types needed, from:
  "llm", "agent", "decision", "parallel", "sequential", "transform", "io"

Example of expected output:
{"title": "Implement cross-agent knowledge sharing", "description": "Enable agents to query and contribute to a shared knowledge base...", "success_criteria": ["Agents can publish observations", "Queries return relevant results within 2s"], "estimated_node_types": ["llm", "agent", "io"]}  # noqa: E501
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}", re.DOTALL)


def _extract_json_from_text(text: str) -> str | None:
    """Extract the first JSON object from text that may contain commentary.

    Handles two common failure modes:
    1. The LLM wraps JSON in ``` ... ``` fences.
    2. The LLM adds pre/post-amble prose.

    Returns the raw JSON string, or *None* if nothing that looks like a
    JSON object can be found.
    """
    # Try JSON fences first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    # Try bare JSON object
    bare_match = _JSON_BLOCK_RE.search(text)
    if bare_match:
        return bare_match.group(0)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class GoalProposer:
    """Prompt template and response parser for goal proposal generation."""

    @staticmethod
    def generate_proposal_prompt() -> str:
        """Return the structured prompt that instructs the LLM to generate a
        strategic goal proposal.

        The returned string is a complete prompt suitable for passing to
        ``metis_agent.run_with_llm(prompt=..., system_prompt=...)``.
        """
        return _GOAL_PROPOSAL_PROMPT

    @staticmethod
    def proposal_system_prompt() -> str:
        """Return the system-prompt text that should accompany a goal
        proposal request."""
        return _SYSTEM_PROMPT

    @staticmethod
    def parse_llm_response(response: str) -> dict[str, Any]:
        """Parse the LLM's raw response string into a goal-creation dict.

        **Success** returns a dict with keys matching :class:`Goal` fields:
        ``title``, ``description``, ``success_criteria``,
        ``estimated_node_types``.  Callers are responsible for adding the
        ``id`` and setting the initial ``status``.

        **Failure** (malformed JSON, missing required keys, invalid types)
        returns ``{"_parse_error": True, "error": "<reason>", "raw": "..."}``
        so callers can construct a degraded Goal without crashing.
        """
        if not response or not response.strip():
            return {
                "_parse_error": True,
                "error": "Empty LLM response",
                "raw": response,
            }

        json_str = _extract_json_from_text(response)
        if json_str is None:
            return {
                "_parse_error": True,
                "error": "No JSON object found in LLM response",
                "raw": response[:500],
            }

        try:
            parsed: dict[str, Any] = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.warning(
                "goal_proposer_parse_failed",
                error=str(exc),
                raw_preview=json_str[:200],
            )
            return {
                "_parse_error": True,
                "error": f"JSON decode failed: {exc}",
                "raw": json_str[:500],
            }

        errors: list[str] = []

        # Validate required keys
        if not isinstance(parsed.get("title"), str) or not parsed["title"].strip():
            errors.append("Missing or invalid 'title' (must be non-empty string)")
        if not isinstance(parsed.get("description"), str) or not parsed["description"].strip():
            errors.append("Missing or invalid 'description' (must be non-empty string)")
        if not isinstance(parsed.get("success_criteria"), list):
            errors.append("Missing or invalid 'success_criteria' (must be array)")
        elif not all(isinstance(s, str) for s in parsed["success_criteria"]):
            errors.append("All 'success_criteria' items must be strings")
        if not isinstance(parsed.get("estimated_node_types"), list):
            errors.append("Missing or invalid 'estimated_node_types' (must be array)")

        if errors:
            logger.warning(
                "goal_proposer_validation_failed",
                errors=errors,
            )
            return {
                "_parse_error": True,
                "error": "; ".join(errors),
                "raw": json_str[:500],
                "_partial": parsed,
            }

        return {
            "title": parsed["title"].strip(),
            "description": parsed["description"].strip(),
            "success_criteria": [str(s).strip() for s in parsed["success_criteria"]],
            "estimated_node_types": [str(n).strip() for n in parsed["estimated_node_types"]],
        }
