"""Reporting modules: SARIF and MASVS.

- :mod:`android_re_core.reporting.sarif` — SARIF 2.1.0 emission.
- :mod:`android_re_core.reporting.masvs` — MASVS v2 control mapping.

Phase 2 ships both. The Triage orchestrator (Phase 4) consumes their
output to produce a unified report.
"""

from __future__ import annotations

__all__ = ["masvs", "sarif"]
