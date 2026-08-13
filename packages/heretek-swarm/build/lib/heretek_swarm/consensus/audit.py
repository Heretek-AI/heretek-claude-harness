"""
Decision Audit Trail - Facade module for consensus audit system.

This module provides backwards-compatible access to the split audit system.
All types and the main class are re-exported from the split modules:

- audit_models: All dataclass definitions (AuditEvent, DecisionRecord, etc.)
- audit_trail:  ConsensusAuditTrail (recording/writing methods)
- audit_query:   AuditQueryMixin (querying/reading methods, composed into main class)

For new code, import directly from the split modules:
    from heretek_swarm.consensus.audit_models import AuditEvent, DecisionOutcome
    from heretek_swarm.consensus.audit_trail import ConsensusAuditTrail

Example:
    from heretek_swarm.consensus.audit import ConsensusAuditTrail

    audit = ConsensusAuditTrail()
    audit.record_decision(decision_id="deploy-001", ...)
    results = audit.query_decisions(min_confidence=0.8)
    data = audit.export_audit_data()
"""

from .audit_models import (
    ArgumentRecord,
    AuditEvent,
    AuditEventType,
    DecisionAudit,
    DecisionOutcome,
    DecisionRecord,
    DeliberationRoundRecord,
    QueryResult,
    VoteRecord,
)
from .audit_query import AuditQueryMixin
from .audit_trail import ConsensusAuditTrail

# Backwards-compatible composition: ConsensusAuditTrail + AuditQueryMixin
# This makes all query methods available on the trail instance directly.
ConsensusAuditTrail.query_decisions = AuditQueryMixin.query_decisions
ConsensusAuditTrail.get_vote_breakdown = AuditQueryMixin.get_vote_breakdown
ConsensusAuditTrail.get_decision_timeline = AuditQueryMixin.get_decision_timeline
ConsensusAuditTrail.export_audit_data = AuditQueryMixin.export_audit_data
ConsensusAuditTrail.export_decision_audit = AuditQueryMixin.export_decision_audit
ConsensusAuditTrail.export_all_audits = AuditQueryMixin.export_all_audits

# Patch _get_trail so query methods delegate to self
ConsensusAuditTrail._get_trail = lambda self: self  # noqa: SLF001

__all__ = [
    "ArgumentRecord",
    # Re-exported from audit_models
    "AuditEvent",
    "AuditEventType",
    # Re-exported from audit_query
    "AuditQueryMixin",
    # Re-exported from audit_trail
    "ConsensusAuditTrail",
    "DecisionAudit",
    "DecisionOutcome",
    "DecisionRecord",
    "DeliberationRoundRecord",
    "QueryResult",
    "VoteRecord",
]
