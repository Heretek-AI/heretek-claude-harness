"""Tests for the :mod:`android_re_core.secrets` modules."""

from __future__ import annotations

from android_re_core.secrets.rules import (
    SECRET_RULES,
    SecretFinding,
    SecretSeverity,
    scan_text,
)


def test_secret_rules_nonempty():
    """The default rules are populated."""
    assert len(SECRET_RULES) > 0
    assert all(r.severity for r in SECRET_RULES)


def test_scan_text_aws_access_key_id():
    """AWS access key id pattern matches AKIA / ASIA prefixes."""
    text = "config.set('aws_key', 'AKIAIOSFODNN7EXAMPLE')"
    findings = scan_text(text)
    rules_hit = {f.rule for f in findings}
    assert "aws-access-key-id" in rules_hit


def test_scan_text_github_token():
    """GitHub personal access token pattern matches ghp_ prefix."""
    text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    findings = scan_text(text)
    rules_hit = {f.rule for f in findings}
    assert "github-token" in rules_hit


def test_scan_text_private_key_pem():
    """A PEM private key header is detected as CRITICAL."""
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAA..."
    findings = scan_text(text)
    rules_hit = {f.rule for f in findings}
    assert "private-key-pem" in rules_hit
    critical = [f for f in findings if f.severity == SecretSeverity.CRITICAL]
    assert len(critical) >= 1


def test_scan_text_jwt():
    """A JWT token is detected."""
    text = "auth = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'"
    findings = scan_text(text)
    rules_hit = {f.rule for f in findings}
    assert "jwt" in rules_hit


def test_scan_text_url():
    """An HTTP URL is detected at the LOW severity by default."""
    text = "endpoint = 'https://api.example.com/v1/users'"
    findings = scan_text(text, min_severity=SecretSeverity.LOW)
    rules_hit = {f.rule for f in findings}
    assert "http-url" in rules_hit


def test_scan_text_filters_by_severity():
    """min_severity drops lower-severity matches."""
    text = "https://api.example.com"
    low = scan_text(text, min_severity=SecretSeverity.LOW)
    high_only = scan_text(text, min_severity=SecretSeverity.HIGH)
    # LOW includes URL/email; HIGH drops them
    assert len(low) >= len(high_only)


def test_scan_text_empty():
    """Empty input returns an empty list."""
    assert scan_text("") == []


def test_scan_text_line_column_tracking():
    """Findings include accurate line and column numbers."""
    text = "line 1\nline 2 with AKIAIOSFODNN7EXAMPLE\nline 3"
    findings = scan_text(text)
    aws = [f for f in findings if f.rule == "aws-access-key-id"]
    assert len(aws) == 1
    assert aws[0].line == 2
    assert aws[0].column >= 1


def test_secret_finding_to_dict():
    """SecretFinding.to_dict serializes all fields."""
    f = SecretFinding(
        rule="aws-access-key-id",
        severity=SecretSeverity.CRITICAL,
        line=10,
        column=5,
        match="AKIA***",
        description="AWS access key id",
    )
    d = f.to_dict()
    assert d["rule"] == "aws-access-key-id"
    assert d["severity"] == "critical"
    assert d["line"] == 10
    assert d["column"] == 5
    assert d["match"] == "AKIA***"
    assert d["description"] == "AWS access key id"
