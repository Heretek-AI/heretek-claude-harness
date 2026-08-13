#!/usr/bin/env python3
"""Bandit severity gate — exits non-zero only when findings at or above a configurable severity threshold exist.

Bandit CLI's -l/-ll flags control display output only, not exit codes. This script parses
the JSON report and conditionally fails so CI can block on HIGH severity while keeping
LOW/MEDIUM findings as informational.

Usage:
    python3 scripts/check-bandit-severity.py --input bandit-report.json
    python3 scripts/check-bandit-severity.py --input bandit-report.json --severity MEDIUM
    python3 scripts/check-bandit-severity.py --input bandit-report.json --severity HIGH --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SEVERITY_ORDER: dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate CI on Bandit severity — exit 1 only when findings at/above threshold exist.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the Bandit JSON report (produced by -f json -o <file>).",
    )
    parser.add_argument(
        "--severity",
        default="HIGH",
        choices=["LOW", "MEDIUM", "HIGH"],
        help="Minimum severity that triggers a failure exit.  Default: HIGH.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-finding details even when not failing.",
    )
    return parser.parse_args(argv)


def load_report(path: Path) -> dict[str, Any]:
    """Load and validate the Bandit JSON report file.

    Raises:
        SystemExit: On missing file or malformed JSON.
    """
    if not path.is_file():
        print(f"❌ Input file not found: {path}", file=sys.stderr)
        sys.exit(2)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ Malformed JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(data, dict):
        print(f"❌ Expected a JSON object, got {type(data).__name__}", file=sys.stderr)
        sys.exit(2)

    return data


def severity_at_or_above(severity: str, threshold: str) -> bool:
    """Return True when *severity* is at least as severe as *threshold*."""
    return SEVERITY_ORDER.get(severity.upper(), 0) >= SEVERITY_ORDER.get(threshold.upper(), 2)


def run(args: argparse.Namespace) -> int:
    """Core gate logic.

    Returns:
        0 when no findings at/above threshold exist (informational pass).
        1 when one or more findings at/above threshold exist (blocking fail).
    """
    data = load_report(args.input)
    results: list[dict[str, Any]] = data.get("results", [])

    if not results:
        print("✅ No Bandit findings — report is clean.")
        return 0

    threshold = args.severity.upper()
    threshold_order = SEVERITY_ORDER[threshold]

    # --- classify every finding ---------------------------------------------------
    findings_at_or_above: list[dict[str, Any]] = []
    findings_below: list[dict[str, Any]] = []

    for r in results:
        sev = r.get("issue_severity", "LOW").upper()
        if SEVERITY_ORDER.get(sev, 0) >= threshold_order:
            findings_at_or_above.append(r)
        else:
            findings_below.append(r)

    # --- summary ------------------------------------------------------------------
    total = len(results)
    blocking = len(findings_at_or_above)
    informational = len(findings_below)
    # Count by severity for the summary table
    counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in results:
        s = r.get("issue_severity", "LOW").upper()
        if s in counts:
            counts[s] += 1

    print(f"Bandit severity gate (threshold: {threshold})")
    print(f"  Total findings:   {total}")
    print(f"  HIGH:             {counts['HIGH']}")
    print(f"  MEDIUM:           {counts['MEDIUM']}")
    print(f"  LOW:              {counts['LOW']}")
    print(f"  Blocking (≥{threshold}):  {blocking}")
    print(f"  Informational:    {informational}")

    # --- blocking findings detail -------------------------------------------------
    if blocking > 0:
        print(f"\n❌ BLOCKED — {blocking} finding(s) at severity ≥ {threshold}:")
        for i, r in enumerate(findings_at_or_above, 1):
            fname = r.get("filename", "?")
            line = r.get("line_number", r.get("line_range", ["?"])[0] if isinstance(r.get("line_range"), list) else "?")
            test_id = r.get("test_id", "?")
            issue_text = r.get("issue_text", "?").replace("\n", " ")
            sev = r.get("issue_severity", "?").upper()
            print(f"  {i}. {fname}:{line}  [{sev}] {test_id} — {issue_text}")

        # Also print informational findings when verbose requested
        if args.verbose and findings_below:
            print(f"\n{len(findings_below)} informational finding(s) below threshold:")
            for r in findings_below:
                fname = r.get("filename", "?")
                line = r.get("line_number", "?")
                sev = r.get("issue_severity", "?").upper()
                test_id = r.get("test_id", "?")
                print(f"    {fname}:{line}  [{sev}] {test_id}")

        return 1

    # --- clean pass ---------------------------------------------------------------
    print(f"\n✅ PASS — no findings at severity ≥ {threshold}.")
    if findings_below:
        print(f"   {len(findings_below)} finding(s) below threshold (informational only).")
        if args.verbose:
            for r in findings_below:
                fname = r.get("filename", "?")
                line = r.get("line_number", "?")
                sev = r.get("issue_severity", "?").upper()
                test_id = r.get("test_id", "?")
                print(f"    {fname}:{line}  [{sev}] {test_id}")

    return 0


def main() -> None:
    args = parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
