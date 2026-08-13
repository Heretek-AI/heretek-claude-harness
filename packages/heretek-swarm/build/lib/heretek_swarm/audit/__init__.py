"""Audit package for detecting stub code and quality anti-patterns.

Test discovery: pytest tests/audit/
"""

from heretek_swarm.audit.report import AuditFinding, generate_report, group_by_severity
from heretek_swarm.audit.severity import Severity
from heretek_swarm.audit.stub_patterns import scan_directory, scan_file

__all__ = [
    "AuditFinding",
    "Severity",
    "generate_report",
    "group_by_severity",
    "scan_directory",
    "scan_file",
]
