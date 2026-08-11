"""Issue-loop CLI primitives.

Each subcommand is a thin wrapper around a `Ledger` method or a read-only
helper. Subagent dispatch, GitHub PR ops, and gate polling happen in the
Claude orchestrator (OMC ralph mode), NOT here. This module is state + IO.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from .ledger import IssueRef, Ledger


DEFAULT_LEDGER_PATH = Path(".omc/state/issue-loop/ledger.json")
DEFAULT_LABELS: list[str] = []  # empty = all open issues (see ADR 2026-08-09 widening)
GH_TIMEOUT_S = 30

# Match ``path/to/file.ext:NNN`` references inside backticks or plain text.
_FILE_REF_RE = re.compile(r"`?([\w./\-]+\.[A-Za-z]+):(\d+)`?")


def _default_gh_runner(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("timeout", GH_TIMEOUT_S)
    kwargs.setdefault("check", False)
    return subprocess.run(args, **kwargs)  # type: ignore[arg-type]


def _extract_files(body: str) -> list[str]:
    """Pull ``path:line`` references from an issue body."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _FILE_REF_RE.finditer(body or ""):
        path = m.group(1)
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _list_candidates_via_gh(
    gh_runner: Callable,
    repo: str | None = None,
) -> list[IssueRef]:
    """Query GitHub for open issues matching the config labels.

    `gh_runner` is the (testable) subprocess replacement. Defaults to
    `subprocess.run`. Failures bubble up as RuntimeError so the caller
    can report non-zero exit.
    """
    args = [
        "gh",
        "issue",
        "list",
        "--json",
        "number,title,body",
        "--state",
        "open",
        "--limit",
        "200",
    ]
    for label in DEFAULT_LABELS:
        args.extend(["--label", label])
    if repo:
        args.extend(["--repo", repo])

    proc = gh_runner(args)
    if getattr(proc, "returncode", 0) != 0:
        raise RuntimeError(
            f"gh issue list failed (rc={getattr(proc, 'returncode', '?')}): "
            f"{getattr(proc, 'stderr', '')}"
        )

    raw = getattr(proc, "stdout", "") or "[]"
    items = json.loads(raw)
    return [
        IssueRef(
            number=int(it["number"]),
            title=str(it.get("title", "")),
            files=_extract_files(str(it.get("body", ""))),
        )
        for it in items
    ]


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _cmd_select_next(args: argparse.Namespace, ledger: Ledger) -> int:
    try:
        candidates = _list_candidates_via_gh(args.gh_runner, repo=args.repo)
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"select-next: {exc}", file=sys.stderr)
        return 1
    chosen = ledger.select_next(candidates)
    if chosen is None:
        print("{}")
        return 0
    print(
        json.dumps(
            {
                "number": chosen.number,
                "title": chosen.title,
                "files": chosen.files,
            }
        )
    )
    return 0


def _cmd_mark_attempt(args: argparse.Namespace, ledger: Ledger) -> int:
    ledger.mark_attempt(args.issue_number)
    return 0


def _cmd_mark_merged(args: argparse.Namespace, ledger: Ledger) -> int:
    ledger.mark_merged(args.issue_number, args.pr_url)
    return 0


def _cmd_mark_skipped(args: argparse.Namespace, ledger: Ledger) -> int:
    ledger.mark_skipped(args.issue_number, args.reason)
    return 0


def _cmd_mark_failed(args: argparse.Namespace, ledger: Ledger) -> int:
    ledger.mark_failed(args.issue_number, args.error)
    return 0


def _cmd_mark_investigated(args: argparse.Namespace, ledger: Ledger) -> int:
    ledger.mark_investigated(args.issue_number, args.findings_path)
    return 0


def _cmd_record_reject(args: argparse.Namespace, ledger: Ledger) -> int:
    print(ledger.record_verifier_reject())
    return 0


def _cmd_reset_rejects(args: argparse.Namespace, ledger: Ledger) -> int:
    ledger.reset_verifier_rejects()
    return 0


def _cmd_rejects_in_a_row(args: argparse.Namespace, ledger: Ledger) -> int:
    print(ledger.verifier_rejects_in_a_row())
    return 0


def _cmd_status(args: argparse.Namespace, ledger: Ledger) -> int:
    counts = {"merged": 0, "skipped": 0, "failed": 0, "pending": 0}
    for key, entry in ledger._entries.items():
        if key == "__root__":
            continue
        status = entry.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps(counts))
    return 0


def _cmd_log_event(args: argparse.Namespace, ledger: Ledger) -> int:
    from datetime import datetime, timezone

    entry = ledger._ensure(args.issue_number)
    entry.setdefault("events", []).append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": args.kind,
            "msg": args.message,
        }
    )
    ledger._save()
    return 0


def _cmd_register_sub_issue(args: argparse.Namespace, ledger: Ledger) -> int:
    entry = ledger._ensure(args.parent)
    entry.setdefault("sub_issues", []).append({"child": args.child, "relation": args.relation})
    ledger._save()
    return 0


def _cmd_classify(args: argparse.Namespace, ledger: Ledger) -> int:
    try:
        candidates = _list_candidates_via_gh(args.gh_runner, repo=args.repo)
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"classify: {exc}", file=sys.stderr)
        return 1
    match = next((c for c in candidates if c.number == args.issue_number), None)
    if match is None:
        print(
            f"classify: issue {args.issue_number} not found in candidates",
            file=sys.stderr,
        )
        return 1
    try:
        body_proc = args.gh_runner(
            [
                "gh",
                "issue",
                "view",
                str(args.issue_number),
                "--json",
                "body",
                "--jq",
                ".body",
            ]
        )
        body = getattr(body_proc, "stdout", "") or ""
    except Exception:
        body = ""
    from .classifier import classify

    path = classify(match, body=body)
    print(path)
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.issue_loop.cli",
        description="Issue-loop CLI: state mutators + read-only helpers.",
    )
    p.add_argument(
        "--ledger-path",
        type=Path,
        default=DEFAULT_LEDGER_PATH,
        help="Path to the ledger JSON file.",
    )
    p.add_argument(
        "--repo",
        default=None,
        help="GitHub repo (owner/name) for gh issue list. Default: gh's own detection.",
    )

    sub = p.add_subparsers(dest="subcommand", required=False)

    sub.add_parser("select-next", help="Print the next eligible IssueRef as JSON, or {} if empty.")

    pa = sub.add_parser("mark-attempt", help="Bump attempts for an issue.")
    pa.add_argument("issue_number", type=int)

    pm = sub.add_parser("mark-merged", help="Mark an issue merged.")
    pm.add_argument("issue_number", type=int)
    pm.add_argument("--pr-url", required=True)

    ps = sub.add_parser("mark-skipped", help="Mark an issue skipped; resets cross-issue rejects.")
    ps.add_argument("issue_number", type=int)
    ps.add_argument("--reason", required=True)

    pf = sub.add_parser("mark-failed", help="Mark an issue failed (non-terminal).")
    pf.add_argument("issue_number", type=int)
    pf.add_argument("--error", required=True)

    pi = sub.add_parser(
        "mark-investigated",
        help="Mark an issue investigated (terminal) and record the findings path.",
    )
    pi.add_argument("issue_number", type=int)
    pi.add_argument("--findings-path", required=True)

    sub.add_parser(
        "record-reject",
        help="Increment the cross-issue reject counter; print new value.",
    )
    sub.add_parser("reset-rejects", help="Zero the cross-issue reject counter.")
    sub.add_parser("rejects-in-a-row", help="Print the current reject count.")
    sub.add_parser("status", help="Print {merged, skipped, failed, pending} counts as JSON.")

    ple = sub.add_parser("log-event", help="Append an event log entry for an issue.")
    ple.add_argument("issue_number", type=int)
    ple.add_argument("--kind", choices=["info", "warn", "error"], required=True)
    ple.add_argument("--message", required=True)

    prs = sub.add_parser(
        "register-sub-issue", help="Record a parent->child sub-issue relationship."
    )
    prs.add_argument("parent", type=int)
    prs.add_argument("--child", type=int, required=True)
    prs.add_argument("--relation", choices=["blocks", "relates"], required=True)

    pc = sub.add_parser(
        "classify",
        help="Print the routing path for an issue (fix|investigate|spec|break-down|skip).",
    )
    pc.add_argument("issue_number", type=int)

    return p


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(
    argv: list[str] | None = None,
    *,
    gh_runner: Callable | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.gh_runner = gh_runner or _default_gh_runner

    ledger = Ledger(args.ledger_path)

    dispatch = {
        "select-next": _cmd_select_next,
        "mark-attempt": _cmd_mark_attempt,
        "mark-merged": _cmd_mark_merged,
        "mark-skipped": _cmd_mark_skipped,
        "mark-failed": _cmd_mark_failed,
        "mark-investigated": _cmd_mark_investigated,
        "record-reject": _cmd_record_reject,
        "reset-rejects": _cmd_reset_rejects,
        "rejects-in-a-row": _cmd_rejects_in_a_row,
        "status": _cmd_status,
        "log-event": _cmd_log_event,
        "register-sub-issue": _cmd_register_sub_issue,
        "classify": _cmd_classify,
    }
    handler = dispatch.get(args.subcommand)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args, ledger)


if __name__ == "__main__":
    sys.exit(main())
