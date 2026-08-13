"""Robust JSON extraction from LLM output.

LLMs sometimes wrap JSON in markdown fences or prefix with prose. This
parser handles those cases without raising on minor formatting issues.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from tier1.deliberation.state import AgentName, AgentVerdict
from tier1.llm.errors import LLMMalformed


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(agent: AgentName, raw_text: str) -> AgentVerdict:
    """Extract a JSON object from raw LLM output and validate as AgentVerdict."""
    text = raw_text.strip()

    # Try fenced ```json ... ``` first
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    # Then try to find the first {...} block
    obj_match = _OBJECT_RE.search(text)
    if obj_match:
        text = obj_match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMMalformed(f"could not parse JSON from LLM output: {exc}") from exc

    if not isinstance(data, dict):
        raise LLMMalformed(f"expected JSON object, got {type(data).__name__}")

    try:
        return AgentVerdict(agent=agent, **data)
    except ValidationError as exc:
        raise LLMMalformed(f"verdict validation failed: {exc}") from exc
