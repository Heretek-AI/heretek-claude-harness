"""
SQLAlchemy ORM Models for Configuration Database Tables

These models map to the PostgreSQL tables created by migration 009.
They are separate from Pydantic models (models.py) which handle validation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class UserConfiguration(Base):
    """User-defined system configuration - maps to user_configurations table."""
    __tablename__ = "user_configurations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    config_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    config_value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_user_configurations_key", "config_key"),
        Index("idx_user_configurations_category", "category"),
    )


class LLMProvider(Base):
    """LLM Provider configuration - maps to llm_providers table."""
    __tablename__ = "llm_providers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_models: Mapped[list] = mapped_column(JSON, default=list)
    model_aliases: Mapped[dict] = mapped_column(JSON, default=dict)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_function_calling: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_requests_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_tokens_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(50), default="unknown")
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_check_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    extra_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_llm_providers_type", "provider_type"),
        Index("idx_llm_providers_enabled", "is_enabled"),
        Index("idx_llm_providers_default", "is_default"),
        Index("idx_llm_providers_priority", "priority"),
    )

    # Relationships
    agent_configs: Mapped[list[AgentConfig]] = relationship(back_populates="llm_provider")


class EmbeddingProvider(Base):
    """Embedding Provider configuration - maps to embedding_providers table."""
    __tablename__ = "embedding_providers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_models: Mapped[list] = mapped_column(JSON, default=list)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supported_input_formats: Mapped[list] = mapped_column(JSON, default=["text"])
    max_batch_size: Mapped[int] = mapped_column(Integer, default=32)
    max_tokens_per_batch: Mapped[int] = mapped_column(Integer, default=8192)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(50), default="unknown")
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_check_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    extra_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_embedding_providers_type", "provider_type"),
        Index("idx_embedding_providers_enabled", "is_enabled"),
        Index("idx_embedding_providers_default", "is_default"),
    )

    # Relationships
    agent_configs: Mapped[list[AgentConfig]] = relationship(back_populates="embedding_provider")


class AgentConfig(Base):
    """Agent configuration - maps to agent_configs table."""
    __tablename__ = "agent_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    llm_provider_id: Mapped[UUID | None] = mapped_column(ForeignKey("llm_providers.id"), nullable=True)
    embedding_provider_id: Mapped[UUID | None] = mapped_column(ForeignKey("embedding_providers.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default_for_type: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_agent_configs_type", "agent_type"),
        Index("idx_agent_configs_agent_id", "agent_id"),
        Index("idx_agent_configs_active", "is_active"),
        Index("idx_agent_configs_default", "is_default_for_type"),
    )

    # Relationships
    llm_provider: Mapped[LLMProvider | None] = relationship(back_populates="agent_configs")
    embedding_provider: Mapped[EmbeddingProvider | None] = relationship(back_populates="agent_configs")


class ConfigAuditLog(Base):
    """Configuration audit log - maps to config_audit_log table."""
    __tablename__ = "config_audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        Index("idx_config_audit_entity", "entity_type", "entity_id"),
        Index("idx_config_audit_action", "action"),
        Index("idx_config_audit_changed_at", "changed_at"),
    )


class ConfigCache(Base):
    """Configuration cache - maps to config_cache table."""
    __tablename__ = "config_cache"

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    cache_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        Index("idx_config_cache_expires", "expires_at"),
    )


class InfrastructureConfig(Base):
    """Infrastructure service configuration - maps to infrastructure_config table."""
    __tablename__ = "infrastructure_config"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str] = mapped_column(String(255), default="localhost")
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    connection_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(50), default="unknown")
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_check_latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    health_check_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_infrastructure_config_service", "service"),
        Index("idx_infrastructure_config_enabled", "is_enabled"),
    )
