"""Tests for scripts/audit/issues.py."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit.findings import Evidence, Finding  # noqa: E402
from audit.issues import (  # noqa: E402
    BASE_LABELS,
    build_issue_payloads,
)


def _f(
    severity: str,
    fid: str,
    cluster: str,
    principle: str = "test principle",
) -> Finding:
    """Minimal Finding helper for tests."""
    return Finding(
        finding_id=fid,
        cluster=cluster,
        principle=principle,
        severity=severity,
        adversarial_posture="violated",
        evidence=Evidence(
            code_refs=["scripts/x.py:1-10"],
            file="scripts/x.py",
            line_range=[1, 10],
            metric="x",
        ),
        failure_scenario="x",
        recommended_action="refactor",
        rationale="x",
        principle_reference="x",
    )


# --- 7 tests per brief ---


def test_skips_medium_low_info() -> None:
    """medium, low, info findings produce zero payloads."""
    fs = [
        _f("medium", "A-001", "Readability & quality bar"),
        _f("low", "A-002", "Readability & quality bar"),
        _f("info", "A-003", "Readability & quality bar"),
    ]
    assert build_issue_payloads(fs) == []


def test_emits_one_payload_per_critical_high() -> None:
    """Each critical and high finding gets its own IssuePayload."""
    fs = [
        _f("critical", "A-001", "Readability & quality bar"),
        _f("high", "A-002", "Readability & quality bar"),
    ]
    payloads = build_issue_payloads(fs)
    assert len(payloads) == 2
    ids = {p.labels[-1] for p in payloads}
    assert "P0" in ids
    assert "P1" in ids


def test_caps_at_five_per_cluster() -> None:
    """8 critical findings in cluster A yields 5 individual + 1 umbrella with overflow=3."""
    fs = [_f("critical", f"A-{i:03d}", "Readability & quality bar") for i in range(1, 9)]
    payloads = build_issue_payloads(fs)
    # 5 individual + 1 umbrella = 6
    assert len(payloads) == 6
    # Last one is the umbrella
    umbrella = payloads[-1]
    assert "3 additional findings" in umbrella.title


def test_umbrella_title_shows_overflow_count() -> None:
    """Umbrella issue title includes the correct overflow count."""
    fs = [_f("critical", f"A-{i:03d}", "Readability & quality bar") for i in range(1, 11)]
    payloads = build_issue_payloads(fs)
    umbrella = payloads[-1]
    assert "5 additional findings" in umbrella.title


def test_per_cluster_cap_not_global() -> None:
    """Cap is per-cluster: 5 in A + 5 in B each produce 5 issues, no umbrella."""
    fs_a = [_f("critical", f"A-{i:03d}", "Readability & quality bar") for i in range(1, 6)]
    fs_b = [_f("critical", f"B-{i:03d}", "Design & architecture") for i in range(1, 6)]
    payloads = build_issue_payloads(fs_a + fs_b)
    # Exactly 10 — no umbrella because neither cluster exceeds cap
    assert len(payloads) == 10
    assert not any("additional findings" in p.title for p in payloads)


def test_labels_include_p0_for_critical() -> None:
    """Critical finding gets P0 priority label."""
    fs = [_f("critical", "A-001", "Readability & quality bar")]
    payloads = build_issue_payloads(fs)
    assert len(payloads) == 1
    p = payloads[0]
    assert "P0" in p.labels
    assert "P1" not in p.labels
    for lbl in BASE_LABELS:
        assert lbl in p.labels


def test_labels_include_p1_for_high() -> None:
    """High finding gets P1 priority label."""
    fs = [_f("high", "A-001", "Readability & quality bar")]
    payloads = build_issue_payloads(fs)
    assert len(payloads) == 1
    p = payloads[0]
    assert "P1" in p.labels
    assert "P0" not in p.labels
    for lbl in BASE_LABELS:
        assert lbl in p.labels
