"""
ExternalCallLog Pydantic Schemas

Provides validation and serialization for external call log data.
Includes create, response, and list response schemas with proper field types
and validation constraints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)


def extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    if not url:
        return ""
    # Simple extraction: remove protocol and path
    result = url
    # Remove protocol
    if "://" in result:
        result = result.split("://", 1)[1]
    # Remove path, query, fragment
    for sep in ("/", "?", "#"):
        if sep in result:
            result = result.split(sep, 1)[0]
    return result


class ExternalCallLogBase(BaseModel):
    """Base schema with common fields for external call logs."""

    agent_id: str = Field(..., min_length=1, max_length=255, description="Agent identifier")
    agent_type: str = Field(..., min_length=1, max_length=100, description="Type of agent")
    call_type: str = Field(..., min_length=1, max_length=50, description="Type of call")
    url: str = Field(..., min_length=1, max_length=2048, description="Full URL of the call")
    method: str = Field(..., min_length=1, max_length=10, description="HTTP method")
    status_code: int | None = Field(None, ge=100, le=599, description="HTTP status code")
    duration_ms: float | None = Field(None, ge=0, description="Call duration in milliseconds")
    tool_name: str | None = Field(None, max_length=255, description="Tool name if applicable")
    error_message: str | None = Field(None, description="Error message if call failed")


class ExternalCallLogCreate(ExternalCallLogBase):
    """Schema for creating a new external call log entry."""

    request_headers: dict[str, Any] | None = Field(
        None,
        description="Request headers (will be encrypted)",
    )
    request_body: str | None = Field(
        None,
        max_length=10240,  # 10KB max as per encryption config
        description="Request body (will be encrypted)",
    )
    response_body: str | None = Field(
        None,
        max_length=10240,  # 10KB max as per encryption config
        description="Response body (will be encrypted)",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class ExternalCallLogResponse(ExternalCallLogBase):
    """Schema for a single external call log response (expanded view).

    Includes decrypted and sanitized request/response bodies.
    """

    id: UUID
    url_domain: str = Field(..., description="Domain extracted from URL for display")
    url_full: str = Field(..., description="Full URL")
    request_headers: dict[str, Any] | None = Field(
        None,
        description="Decrypted and sanitized request headers",
    )
    request_body: str | None = Field(
        None,
        description="Decrypted and sanitized request body",
    )
    response_body: str | None = Field(
        None,
        description="Decrypted and sanitized response body",
    )
    created_at: datetime = Field(..., description="Timestamp when the call was recorded")

    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
    )

    @classmethod
    def from_orm_with_decryption(
        cls,
        orm_obj: Any,
        decrypted_headers: dict[str, Any] | None = None,
        decrypted_request_body: str | None = None,
        decrypted_response_body: str | None = None,
    ) -> ExternalCallLogResponse:
        """Create response from ORM object with decrypted data.

        Args:
            orm_obj: SQLAlchemy ORM object
            decrypted_headers: Decrypted request headers
            decrypted_request_body: Decrypted request body
            decrypted_response_body: Decrypted response body

        Returns:
            ExternalCallLogResponse instance
        """
        return cls(
            id=orm_obj.id,
            agent_id=orm_obj.agent_id,
            agent_type=orm_obj.agent_type,
            call_type=orm_obj.call_type,
            url=orm_obj.url,
            url_domain=extract_domain(orm_obj.url),
            url_full=orm_obj.url,
            method=orm_obj.method,
            status_code=orm_obj.status_code,
            duration_ms=orm_obj.duration_ms,
            request_headers=decrypted_headers,
            request_body=decrypted_request_body,
            response_body=decrypted_response_body,
            tool_name=orm_obj.tool_name,
            error_message=orm_obj.error_message,
            created_at=orm_obj.created_at,
        )


class ExternalCallLogListItem(ExternalCallLogBase):
    """Schema for external call log item in list view.

    Excludes request/response bodies for performance.
    """

    id: UUID
    url_domain: str = Field(..., description="Domain extracted from URL")
    url_full: str = Field(..., description="Full URL for expanded view")
    created_at: datetime = Field(..., description="Timestamp when the call was recorded")

    model_config = ConfigDict(
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
    )


class ExternalCallLogListResponse(BaseModel):
    """Paginated list response for external call logs."""

    items: list[ExternalCallLogListItem] = Field(
        default_factory=list,
        description="List of external call log items",
    )
    total: int = Field(..., ge=0, description="Total number of matching records")
    offset: int = Field(default=0, ge=0, description="Number of records skipped")
    limit: int = Field(default=50, ge=1, le=100, description="Page size")
    has_more: bool = Field(default=False, description="Whether more records exist")

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )
