"""
Translates strategic goals into executable workflows using the Metis agent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from heretek_swarm.actors.metis import MetisAgent
    from heretek_swarm.goals.models import Goal

logger = structlog.get_logger("GoalToWorkflowTranslator")


class GoalToWorkflowTranslator:
    """Translates Goal objects into JSON workflow definitions using Metis."""

    def __init__(self, metis_agent: MetisAgent):
        self.metis = metis_agent

    async def translate_goal(self, goal: Goal) -> dict[str, Any]:
        """
        Convert an accepted Goal into a workflow definition via LLM.

        Args:
            goal: The accepted Goal to translate.

        Returns:
            A workflow definition dict with `nodes` and `edges`. If LLM
            parsing fails, returns a minimal fallback single-node workflow.
        """
        prompt = f"""
Goal Translation Request:

Title: {goal.title}
Description: {goal.description}
Success Criteria: {", ".join(goal.success_criteria)}

Convert this goal into a valid JSON workflow definition for our execution engine.
The output MUST be a JSON object with two keys:
1. "nodes": A list of node objects. Each node must have "id" (string), "type" (string), and "config" (object).  # noqa: E501
2. "edges": A list of edge objects. Each edge must have "source" (string) and "target" (string).

Do NOT wrap the JSON in markdown code blocks. Output ONLY valid JSON.
"""
        try:
            response = await self.metis.run_with_llm(
                prompt=prompt,
                system_prompt=(
                    "You are Metis, generating executable JSON workflow "
                    "definitions from strategic goals."
                ),
                timeout=60,
            )

            # Clean up potential markdown formatting
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            workflow_def = json.loads(text)

            if "nodes" not in workflow_def or "edges" not in workflow_def:
                raise ValueError("Missing required keys 'nodes' or 'edges'")

            logger.info("goal_translated_successfully", goal_id=goal.id)
            return workflow_def

        except Exception as exc:
            logger.error("goal_translation_failed", goal_id=goal.id, error=str(exc))
            return self._fallback_workflow(goal)

    def _fallback_workflow(self, goal: Goal) -> dict[str, Any]:
        """Generate a minimal fallback workflow when LLM translation fails."""
        return {
            "nodes": [
                {
                    "id": "fallback_execution_node",
                    "type": "agent_task",
                    "config": {
                        "agent_id": "coder",
                        "instruction": f"Execute fallback plan for goal: {goal.title}",
                        "context": goal.description,
                    },
                }
            ],
            "edges": [],
        }
