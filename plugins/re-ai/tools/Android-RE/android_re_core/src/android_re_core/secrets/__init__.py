"""Secrets-scanning helpers.

Phase 2 ships:

- :mod:`android_re_core.secrets.rules` — pure-Python regex engine for
  high-precision secret detection. No external dependency.
- :mod:`android_re_core.secrets.apkleaks_runner` — optional wrapper
  around the ``apkleaks`` CLI (vendored separately). Phase 2 ships the
  wrapper but the tool itself is downloaded by ``bin/pull-tools.sh``.
"""

from __future__ import annotations

from .rules import SECRET_RULES, SecretFinding, SecretRule, scan_text

__all__ = [
    "SECRET_RULES",
    "SecretFinding",
    "SecretRule",
    "apkleaks_runner",
    "scan_text",
]
