"""Regex-based secret detection rules.

A pure-Python, dependency-free engine for finding URLs, API keys, JWT
tokens, AWS/GCP credentials, private keys, and similar secrets in
decompiled source or text. Intended for fast pre-filtering; the
:mod:`apkleaks_runner` module wraps the more comprehensive apkleaks
tool for high-recall scans.

Each :class:`SecretRule` has a name, a regex, and a severity. The
:func:`scan_text` function runs every rule against a string and
returns a list of :class:`SecretFinding` objects.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "SECRET_RULES",
    "SecretFinding",
    "SecretRule",
    "SecretSeverity",
    "scan_text",
]


class SecretSeverity(str, Enum):
    """How seriously to treat a rule's matches."""

    CRITICAL = "critical"  # private keys, master credentials
    HIGH = "high"  # cloud keys, JWTs
    MEDIUM = "medium"  # URLs, IPs
    LOW = "low"  # UUIDs, generic tokens
    INFO = "info"


@dataclass(frozen=True)
class SecretRule:
    """A single regex-based secret-detection rule."""

    name: str
    pattern: str
    severity: SecretSeverity
    description: str
    _compiled: re.Pattern[str] | None = None

    def compiled(self) -> re.Pattern[str]:
        """Lazily compile the regex."""
        if self._compiled is None:
            object.__setattr__(
                self, "_compiled", re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)
            )
        return self._compiled  # type: ignore[return-value]


@dataclass(frozen=True)
class SecretFinding:
    """A single match of a secret rule."""

    rule: str
    severity: SecretSeverity
    line: int
    column: int
    match: str
    description: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity.value,
            "line": self.line,
            "column": self.column,
            "match": self.match,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------

SECRET_RULES: tuple[SecretRule, ...] = (
    # --- Critical ---
    SecretRule(
        name="private-key-pem",
        pattern=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
        severity=SecretSeverity.CRITICAL,
        description="Embedded private key block",
    ),
    SecretRule(
        name="aws-access-key-id",
        pattern=r"\b(AKIA|ASIA)[0-9A-Z]{16}\b",
        severity=SecretSeverity.CRITICAL,
        description="AWS access key id",
    ),
    SecretRule(
        name="gcp-api-key",
        pattern=r"\bAIza[0-9A-Za-z\-_]{35}\b",
        severity=SecretSeverity.HIGH,
        description="Google API key",
    ),
    SecretRule(
        name="github-token",
        pattern=r"\bghp_[0-9A-Za-z]{36}\b",
        severity=SecretSeverity.CRITICAL,
        description="GitHub personal access token",
    ),
    SecretRule(
        name="github-fine-grained-token",
        pattern=r"\bgithub_pat_[0-9A-Za-z_]{82}\b",
        severity=SecretSeverity.CRITICAL,
        description="GitHub fine-grained access token",
    ),
    SecretRule(
        name="slack-token",
        pattern=r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b",
        severity=SecretSeverity.HIGH,
        description="Slack token",
    ),
    SecretRule(
        name="stripe-secret",
        pattern=r"\bsk_(?:live|test)_[0-9A-Za-z]{24,}\b",
        severity=SecretSeverity.CRITICAL,
        description="Stripe secret API key",
    ),
    # --- High ---
    SecretRule(
        name="jwt",
        pattern=r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        severity=SecretSeverity.HIGH,
        description="JSON Web Token",
    ),
    SecretRule(
        name="aws-secret-access-key",
        pattern=r"(?i)aws[_\-]?secret[_\-]?(?:access)?[_\-]?key[\"' :=]+[0-9A-Za-z/+=]{40}",
        severity=SecretSeverity.CRITICAL,
        description="AWS secret access key",
    ),
    SecretRule(
        name="firebase-url",
        pattern=r"\bhttps?://[a-z0-9\-]+\.firebaseio\.com\b",
        severity=SecretSeverity.MEDIUM,
        description="Firebase database URL",
    ),
    SecretRule(
        name="sendgrid-key",
        pattern=r"\bSG\.[0-9A-Za-z_\-]{22}\.[0-9A-Za-z_\-]{43}\b",
        severity=SecretSeverity.HIGH,
        description="SendGrid API key",
    ),
    SecretRule(
        name="twilio-account-sid",
        pattern=r"\bAC[0-9a-f]{32}\b",
        severity=SecretSeverity.MEDIUM,
        description="Twilio Account SID",
    ),
    # --- Medium ---
    SecretRule(
        name="http-url",
        pattern=r"\bhttps?://[^\s\"'<>]+",
        severity=SecretSeverity.LOW,
        description="HTTP(S) URL",
    ),
    SecretRule(
        name="ip-address",
        pattern=r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}\b",
        severity=SecretSeverity.LOW,
        description="IPv4 address",
    ),
    SecretRule(
        name="email",
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        severity=SecretSeverity.INFO,
        description="Email address",
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_text(
    text: str,
    *,
    rules: Iterable[SecretRule] = SECRET_RULES,
    min_severity: SecretSeverity = SecretSeverity.INFO,
) -> list[SecretFinding]:
    """Run every rule against ``text`` and return a list of findings.

    Args:
        text: The text to scan.
        rules: Iterable of :class:`SecretRule`. Defaults to
            :data:`SECRET_RULES`.
        min_severity: Drop findings below this severity.
    """
    sev_rank = {
        SecretSeverity.CRITICAL: 4,
        SecretSeverity.HIGH: 3,
        SecretSeverity.MEDIUM: 2,
        SecretSeverity.LOW: 1,
        SecretSeverity.INFO: 0,
    }
    threshold = sev_rank[min_severity]

    out: list[SecretFinding] = []
    # Pre-compute line offsets for fast line/column lookup.
    line_offsets = _line_offsets(text)
    for rule in rules:
        if sev_rank[rule.severity] < threshold:
            continue
        try:
            for m in rule.compiled().finditer(text):
                line, col = _locate(line_offsets, m.start())
                # Truncate long matches for display
                match_str = m.group(0)
                if len(match_str) > 200:
                    match_str = match_str[:200] + "…"
                out.append(
                    SecretFinding(
                        rule=rule.name,
                        severity=rule.severity,
                        line=line,
                        column=col,
                        match=match_str,
                        description=rule.description,
                    )
                )
        except re.error:
            continue
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _line_offsets(text: str) -> list[int]:
    """Return a list of character offsets where each line begins."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _locate(offsets: list[int], pos: int) -> tuple[int, int]:
    """Return (line, column) for an absolute character offset."""
    # Binary search would be faster; for our scale, linear is fine.
    line = 1
    for off in offsets:
        if off > pos:
            break
        line += 1
    line -= 1
    col = pos - offsets[line - 1] + 1
    return line, col
