"""Per-kind scanner wrappers for the security monitoring pipeline.

Each wrapper exposes:
    scan(path: Path, *, token: str | None = None) -> ScannerReport

The pipeline (`scripts/security_scan.py`) dispatches to a wrapper based
on the catalog item's `kind` field. See `base.py` for the contract.
"""
from __future__ import annotations
