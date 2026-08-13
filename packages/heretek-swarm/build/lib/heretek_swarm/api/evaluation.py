"""
Evaluation API - Agent Quality Assessment
"""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.gateway.auth import verify_auth

try:
    from heretek_swarm.evaluation.evaluator import (
        EvaluationMetric,
        TestCase,
        get_evaluator,
    )

    EVALUATION_AVAILABLE = True
except ImportError:
    EVALUATION_AVAILABLE = False
    EvaluationMetric = None  # type: ignore[misc, assignment]
    TestCase = None  # type: ignore[misc, assignment]
    get_evaluator = None  # type: ignore[misc, assignment]

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


def _require_evaluator():
    if not EVALUATION_AVAILABLE or get_evaluator is None:
        raise HTTPException(status_code=503, detail="Evaluation module unavailable")
    return get_evaluator()


@router.post("/test-cases", status_code=201)
async def create_test_case(
    test_case: dict[str, Any], authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    evaluator = _require_evaluator()

    case = TestCase(
        id=test_case.get("id", f"test_{len(evaluator.test_cases)}"),
        name=test_case.get("name", "Unnamed Test"),
        description=test_case.get("description", ""),
        input_data=test_case.get("input_data", {}),
        expected_output=test_case.get("expected_output"),
        evaluation_criteria=[
            EvaluationMetric(m) for m in test_case.get("evaluation_criteria", [])
        ],
        metadata=test_case.get("metadata", {}),
    )

    evaluator.load_test_cases([case])
    logger.info("test_case_created", test_case_id=case.id)
    return {"id": case.id, "name": case.name, "description": case.description}


@router.post("/test-cases/batch", status_code=201)
async def create_test_cases_batch(
    test_cases: list[dict[str, Any]], authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    evaluator = _require_evaluator()

    cases = [
        TestCase(
            id=tc.get("id", f"test_{len(evaluator.test_cases) + i}"),
            name=tc.get("name", "Unnamed Test"),
            description=tc.get("description", ""),
            input_data=tc.get("input_data", {}),
            expected_output=tc.get("expected_output"),
            evaluation_criteria=[
                EvaluationMetric(m) for m in tc.get("evaluation_criteria", [])
            ],
            metadata=tc.get("metadata", {}),
        )
        for i, tc in enumerate(test_cases)
    ]

    evaluator.load_test_cases(cases)
    logger.info("test_cases_created_batch", count=len(cases))
    return {"count": len(cases), "test_case_ids": [case.id for case in cases]}


@router.get("/test-cases", status_code=200)
async def list_test_cases(authenticated: Annotated[str, Depends(verify_auth)]) -> dict[str, Any]:
    evaluator = _require_evaluator()
    return {
        "test_cases": [
            {
                "id": case.id,
                "name": case.name,
                "description": case.description,
                "evaluation_criteria": [m.value for m in case.evaluation_criteria],
            }
            for case in evaluator.test_cases.values()
        ]
    }


@router.post("/agents/{agent_id}/evaluate", status_code=201)
async def evaluate_agent(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
    test_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    evaluator = _require_evaluator()
    try:
        executions = await evaluator.evaluate_agent(agent_id, test_case_ids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    logger.info("agent_evaluated", agent_id=agent_id, tests_run=len(executions))
    return {
        "agent_id": agent_id,
        "executions": [execution.to_dict() for execution in executions],
    }


@router.get("/agents/{agent_id}/summary", status_code=200)
async def get_agent_evaluation_summary(
    agent_id: str, authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    evaluator = _require_evaluator()
    return evaluator.get_agent_summary(agent_id)


@router.get("/summaries", status_code=200)
async def get_all_evaluation_summaries(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    evaluator = _require_evaluator()
    return {"summaries": evaluator.get_all_summaries()}


@router.delete("/test-cases/{test_case_id}", status_code=204)
async def delete_test_case(
    test_case_id: str, authenticated: Annotated[str, Depends(verify_auth)]
) -> None:
    evaluator = _require_evaluator()
    if test_case_id not in evaluator.test_cases:
        raise HTTPException(status_code=404, detail="Test case not found")
    del evaluator.test_cases[test_case_id]
    logger.info("test_case_deleted", test_case_id=test_case_id)
