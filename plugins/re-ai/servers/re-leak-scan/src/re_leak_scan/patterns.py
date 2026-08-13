"""Vendor-neutral regex catalog for publisher telemetry pipeline leaks.

Each pattern category covers a *category* of leak endpoint
(Sentry error tracking, Logstash ingestion, Confluence wiki link,
Google Drive document, Kafka topic, generic secret). The patterns
are derived from the URL schemes / hostnames of the public
infrastructure — they describe observable string content without
naming any specific publisher.

Adding a new pattern: append a new entry to ``PATTERNS`` and
(optionally) a new verifier. The pattern name is used as the
``category`` field in the scan output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


# ── Pattern entries ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Pattern:
    """A single leak-detection rule.

    ``name`` is the vendor-neutral category label. ``regex`` must
    use ``re.VERBOSE``-friendly syntax. ``description`` is a one-line
    analyst hint shown in scan summaries. ``risk`` is HIGH / MEDIUM
    / LOW — used to sort the scan output.
    """

    name: str
    regex: str
    description: str
    risk: str  # "HIGH" | "MEDIUM" | "LOW"
    # Optional: a callable to actively verify a single match.
    # Receives the matched string; returns a dict of verification
    # metadata. Returning ``None`` means "no live check available"
    # — the match is still reported, just not verified.
    verifier: Callable[[str], dict] | None = None


# ── Patterns ───────────────────────────────────────────────────────────


# Sentry DSN: https://<key>@<host>/<int_id>
# Example format: https://abc123def456@sentry.io/42
SENTRY_DSN = Pattern(
    name="sentry-dsn",
    regex=r"https?://[a-f0-9]{20,}@[a-z0-9.\-]+/(?P<project_id>\d+)",
    description="Sentry DSN with embedded public auth (enables forged crash submission)",
    risk="HIGH",
)


# Logstash ingestion URL. Endpoints typically end in /_bulk, /_ingest,
# or /<topic>.  Hostname hints: logstash, ingest, logs.
LOGSTASH_URL = Pattern(
    name="logstash-url",
    regex=r"https?://[a-z0-9.\-]*(?:logstash|ingest|logs)[a-z0-9.\-]*\.[a-z]{2,}(?::\d+)?/[a-zA-Z0-9_\-/]+",
    description="Logstash / log-ingestion URL (internal observability infrastructure)",
    risk="MEDIUM",
)


# Confluence wiki page. Format: https://<host>/wiki/spaces/<space>/pages/<id>/<title>
# Or the newer /wiki/x/<id> form.
CONFLUENCE_URL = Pattern(
    name="confluence-url",
    regex=r"https?://[a-z0-9.\-]*(?:atlassian|confluence|wiki)[a-z0-9.\-]*\.[a-z]{2,}/wiki/(?:spaces/[A-Z0-9_]+/pages/\d+|x/[A-Za-z0-9]+)",
    description="Confluence internal wiki page (often engineering-only docs / secrets)",
    risk="MEDIUM",
)


# Google Drive document URL. Format: https://docs.google.com/document/d/<id>/
# Or presentation, spreadsheet, etc.
GOOGLE_DRIVE_URL = Pattern(
    name="google-drive-url",
    regex=r"https?://docs\.google\.com/(?:document|spreadsheets|presentation|forms|drawings)/d/[a-zA-Z0-9_\-]{20,}",
    description="Google Drive document URL (may be a leaked publisher-internal document)",
    risk="MEDIUM",
)


# AWS access key ID — pattern matches the public-prefix + 16 base32 chars.
AWS_ACCESS_KEY = Pattern(
    name="aws-access-key",
    regex=r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    description="AWS access key ID (long-lived credential, rotate immediately on leak)",
    risk="HIGH",
)


# Slack token — xox[bpars]-…
SLACK_TOKEN = Pattern(
    name="slack-token",
    regex=r"\bxox[bpaeors\-]{1,3}[A-Za-z0-9\-]{10,}\b",
    description="Slack token (long-lived API credential, rotate immediately on leak)",
    risk="HIGH",
)


# Generic high-entropy hex string ≥ 32 chars (likely a secret or key).
# Excludes strings that look like GUIDs by requiring the string to be
# a continuous run in the binary.
GENERIC_HEX_SECRET = Pattern(
    name="generic-hex-secret",
    regex=r"\b[a-f0-9]{32,64}\b",
    description="Continuous high-entropy hex string (possible key / secret / token)",
    risk="LOW",
)


# Cycle 2 fix (L1, 2026-06-06): internal-diagnostic-relay hostname.
# Discovered in target-B's `MonoLauncher::PASystemInfoScanner.SenderInfomation`
# (a .NET WPF class). The class does a DNS lookup of a publisher-internal
# `.io` TLD hostname, compares the resolved IP against RFC1918
# `10.0.0.0/8` to detect the corporate environment, and conditionally
# sends the un-hashed machine fingerprint only when the host is on
# the internal network. The hostname itself is a real leak — it
# indicates the binary was built against an internal corporate
# resolver and shipped without scrubbing.
#
# The pattern matches an internal-TLD anchor + a diagnostic-product
# stem (jenkins, jira, grafana, prometheus, etc.) to keep the false-
# positive rate low (the public `jenkins.io` would otherwise match).
# A18 fix (v2.8.0): widen the TLD set to include `.io` / `.dev` /
# `.app` / `.tech` / `.cloud` (per gap-analysis Cat A18; r01 found a
# `.io` TLD hit in MonoLauncher that this v4 regex no longer matched).
# The diagnostic-product stem keeps the false-positive rate low —
# `jenkins.io` would only match if it ALSO carries a diagnostic-product
# anchor in the hostname, which the public Jenkins website doesn't.
PUBLISHER_INTERNAL_DIAGNOSTIC_HOSTNAME = Pattern(
    name="publisher-internal-diagnostic-hostname",
    regex=(
        r"\b(?:[a-z0-9\-]+\.)*"
        r"(?:jenkins|jira|grafana|prometheus|kibana|splunk|sentry|"
        r"bitbucket|gerrit|artifactory|nexus|sonarqube|vault|consul|"
        r"etcd|datadog|newrelic|pagerduty)"
        r"(?:\.[a-z0-9\-]+)*"
        r"\.(?:internal|corp|lan|local|intra|private|home\.arpa|"
        r"io|dev|app|tech|cloud)"
        r"\b"
    ),
    description=(
        "Internal diagnostic / observability hostname — suggests "
        "the binary was built against an internal corporate "
        "resolver and shipped without scrubbing. Pairs with the "
        "telemetry_leak catalog category in drm-indicators.yaml."
    ),
    risk="HIGH",
)


PATTERNS: list[Pattern] = [
    SENTRY_DSN,
    LOGSTASH_URL,
    CONFLUENCE_URL,
    GOOGLE_DRIVE_URL,
    AWS_ACCESS_KEY,
    SLACK_TOKEN,
    GENERIC_HEX_SECRET,
    PUBLISHER_INTERNAL_DIAGNOSTIC_HOSTNAME,
]


# ── Catalog summary (for get_patterns()) ──────────────────────────────


def get_pattern_names() -> list[str]:
    return [p.name for p in PATTERNS]


def get_pattern(name: str) -> Pattern | None:
    for p in PATTERNS:
        if p.name == name:
            return p
    return None


def get_patterns_by_risk() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for p in PATTERNS:
        out.setdefault(p.risk, []).append(p.name)
    return out
