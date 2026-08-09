"""CLI driver for the harness self-audit toolkit.

Subcommands
-----------
emit-prompts  Write one <letter>.txt prompt per cluster to --out-dir.
synthesize    Run synthesis pass (validate + dedupe + report + JSON).
build-issues  Read synthesis JSON, write GitHub-MCP-ready payload file.

The driver does NOT call GitHub MCP directly -- payload creation is the
safe, testable part; the actual mcp__github__github-issue_write calls
happen in the operator's session when MCP is available.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit import findings as findings_mod
from audit import issues as issues_mod
from audit import prompts as prompts_mod
from audit import synthesis as synthesis_mod


# ---------------------------------------------------------------------------
# Subcommand: emit-prompts
# ---------------------------------------------------------------------------


def _cmd_emit_prompts(args: argparse.Namespace) -> int:
    """Write one ``<letter>.txt`` per cluster to *out_dir*."""
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for letter in sorted(prompts_mod.CLUSTERS):
        text = prompts_mod.render_prompt(letter, args.repo_root, args.commit_sha)
        (out_dir / f"{letter}.txt").write_text(text)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: synthesize
# ---------------------------------------------------------------------------


def _cmd_synthesize(args: argparse.Namespace) -> int:
    """Run synthesis; write report + JSON to *output_dir*."""
    sonar_exclusions: set[str] | None = None
    if args.sonar_exclusions_file:
        raw = Path(args.sonar_exclusions_file).read_text()
        sonar_exclusions = {line.strip() for line in raw.splitlines() if line.strip()}
    result = synthesis_mod.synthesize(
        cluster_results_dir=args.cluster_results,
        output_dir=args.output_dir,
        commit_sha=args.commit_sha,
        sonar_exclusions=sonar_exclusions,
    )
    print(
        f"Synthesis complete: {len(result.findings)} findings, "
        f"{result.duplicate_count} duplicates removed"
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: build-issues
# ---------------------------------------------------------------------------


def _cmd_build_issues(args: argparse.Namespace) -> int:
    """Read synthesis JSON, write GitHub-MCP-ready payload file."""
    loaded = findings_mod.load_findings(args.findings_json)
    payloads = issues_mod.build_issue_payloads(loaded)
    # If --report-link provided, append to each body
    if args.report_link:
        for p in payloads:
            p.body += f"\n\n---\n*Audit report: {args.report_link}*"
    out_path: Path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            [{"title": p.title, "body": p.body, "labels": p.labels} for p in payloads],
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"Wrote {len(payloads)} issue payloads to {out_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse *argv* (or ``sys.argv[1:]``) and dispatch to a subcommand."""
    parser = argparse.ArgumentParser(
        prog="harness_self",
        description="CLI driver for the heretek harness self-audit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- emit-prompts -------------------------------------------------------
    ep = sub.add_parser("emit-prompts", help="Write one prompt file per cluster.")
    ep.add_argument("--repo-root", type=Path, required=True)
    ep.add_argument("--commit-sha", required=True)
    ep.add_argument("--out-dir", type=Path, required=True)

    # -- synthesize ---------------------------------------------------------
    sp = sub.add_parser("synthesize", help="Run synthesis pass.")
    sp.add_argument("--cluster-results", type=Path, required=True)
    sp.add_argument("--output-dir", type=Path, required=True)
    sp.add_argument("--commit-sha", required=True)
    sp.add_argument("--sonar-exclusions-file", type=Path, default=None)

    # -- build-issues -------------------------------------------------------
    bp = sub.add_parser("build-issues", help="Build GitHub-MCP-ready payload.")
    bp.add_argument("--findings-json", type=Path, required=True)
    bp.add_argument("--output", type=Path, required=True)
    bp.add_argument("--report-link", default=None)

    args = parser.parse_args(argv)
    dispatch = {
        "emit-prompts": _cmd_emit_prompts,
        "synthesize": _cmd_synthesize,
        "build-issues": _cmd_build_issues,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
