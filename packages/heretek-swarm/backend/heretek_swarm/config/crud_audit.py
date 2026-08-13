"""
Audit-log CRUD — extracted from ``config/crud.py`` as part of
Phase 2.6 of PLAN.md (§1.4 god-class extraction).

The audit-log surface is two methods:
  - ``_log_change`` — record a configuration change for
    audit purposes.
  - ``get_audit_log`` — retrieve audit log entries with
    optional entity_type / entity_id filters.

Both are expressed as free functions that take the service
instance as their first argument. The mixin class still
owns the public method surface; the methods now delegate
here.

Backwards compatibility: ``ConfigurationServiceCrud`` keeps
the same public method signatures.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heretek_swarm.config.models import ConfigAuditLog
    from heretek_swarm.config.service import ConfigurationService

logger = logging.getLogger("heretek_swarm.config.crud_audit")


def log_change(
    service: "ConfigurationService",
    action: str,
    entity_type: str,
    entity_id: str | None,
    changes: dict[str, Any] | None,
    user: str | None,
) -> None:
    """Log a configuration change for audit purposes."""
    logger.info(
        "config_change",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        changes=changes,
        user=user,
    )


async def get_audit_log(
    service: "ConfigurationService",
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
) -> list["ConfigAuditLog"]:
    """Get audit log entries.

    Args:
        entity_type: Optional entity type filter
        entity_id: Optional entity ID filter
        limit: Maximum number of entries to return

    Returns:
        List of audit log entries

    Note: the underlying audit-log persistence is not yet
    wired to a backing table; this function emits a
    'audit_log_requested' info line and returns an empty
    list. The full implementation will land when the
    ConfigAuditLog ORM model is added to db_models.py.
    """
    logger.info(
        "audit_log_requested",
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return []


__all__ = ["get_audit_log", "log_change"]
