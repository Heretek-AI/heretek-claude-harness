"""Weekly scorecard generator + regression detector.

Consumes result.json from each artifact bundle, emits scorecard-YYYY-WW.md.
Compares against previous week; reports regressions > threshold.

Entry: scripts/scorecard.py <bundles-dir> --week 2026-W32 [--prev prev.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def generate_scorecard(bundles_dir: Path, *, week: tuple[int, int]) -> str:
    """Render a markdown scorecard for the given ISO week (year, week_num)."""
    rows = []
    for bundle in sorted(bundles_dir.glob("harness-*")):
        result_path = bundle / "result.json"
        if not result_path.exists():
            continue
        result = json.loads(result_path.read_text())
        fixture = result.get("fixture", bundle.name)
        verdict = result.get("verdict", "unknown")
        rows.append(f"| {fixture} | {verdict} |")

    year, wk = week
    header = f"# Harness Scorecard — {year}-W{wk:02d}\n\n"
    if not rows:
        body = "_No result.json files found in this directory._\n"
    else:
        body = "| Fixture | Verdict |\n|---|---|\n" + "\n".join(rows) + "\n"
    return header + body


def detect_regressions(
    prev: dict[str, float], curr: dict[str, float], *, threshold: float = 0.05
) -> list[str]:
    """Return fixtures whose score dropped by more than threshold vs prev."""
    return [f for f in prev if f in curr and (prev[f] - curr[f]) > threshold]


def main() -> int:
    p = argparse.ArgumentParser(description="Weekly scorecard generator")
    p.add_argument("bundles_dir", type=Path)
    p.add_argument("--week", required=True, help="ISO week like 2026-W32")
    p.add_argument("--prev", type=Path, help="Previous scorecard JSON for regression detection")
    args = p.parse_args()

    year_str, wk_str = args.week.split("-W")
    week_tuple = (int(year_str), int(wk_str))
    scorecard = generate_scorecard(args.bundles_dir, week=week_tuple)
    out = args.bundles_dir / f"scorecard-{args.week}.md"
    out.write_text(scorecard)

    if args.prev:
        prev_data = json.loads(args.prev.read_text())
        curr_data: dict[str, float] = {}
        for bundle in sorted(args.bundles_dir.glob("harness-*")):
            result_path = bundle / "result.json"
            if not result_path.exists():
                continue
            result = json.loads(result_path.read_text())
            fixture = result.get("fixture", bundle.name)
            verdict = result.get("verdict", "unknown")
            curr_data[fixture] = 1.0 if verdict == "pass" else 0.0
        regressions = detect_regressions(prev_data, curr_data)
        if regressions:
            print(f"regressions: {regressions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
