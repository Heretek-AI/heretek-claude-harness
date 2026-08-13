"""Shared API schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthComponent(BaseModel):
    status: Literal["ok", "degraded", "down", "not_probed"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    components: dict[str, HealthComponent]


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: dict | None = None


class NewDeliberationRequest(BaseModel):
    problem: str = Field(min_length=1, max_length=5000)


class NewDeliberationResponse(BaseModel):
    id: str
    status: Literal["started"] = "started"


class InterjectRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class DeliberationSummary(BaseModel):
    id: str
    problem: str
    status: str
    created_at: float


class DeliberationListResponse(BaseModel):
    items: list[DeliberationSummary]
