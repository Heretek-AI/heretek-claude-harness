"""
ExternalCallLog SQLAlchemy ORM Model

Records external API calls made by agents with encrypted request/response bodies
using Fernet symmetric encryption.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class ExternalCallLog(Base):
    """
    External call log for tracking API calls made by agents.

    Records details of external API calls including URL, method, status code,
    duration, and encrypted request/response bodies. Uses Fernet symmetric
    encryption for sensitive data storage.

    Maps to the external_call_logs table.
    """

    __tablename__ = "external_call_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Integer, nullable=True)
    request_headers_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_body_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_body_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("idx_external_call_logs_agent_created", "agent_id", "created_at"),
        Index("idx_external_call_logs_call_type_created", "call_type", "created_at"),
        Index("idx_external_call_logs_status_code", "status_code"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExternalCallLog(id={self.id}, agent_id={self.agent_id}, "
            f"call_type={self.call_type}, url={self.url[:50]}...)>"
        )
