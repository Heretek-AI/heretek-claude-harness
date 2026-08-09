"""heretek CLI — top-level cross-cutting commands for the heretek marketplace.

Subcommand groups:
- telemetry: local hook event log inspection (sub-spec 1 §2.3)
- (future) validate, generate, refresh-pins

Top-level entry: `python scripts/heretek_cli.py <group> <command> [args]`
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

TELEMETRY_ROOT = Path(
    os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry")
)
SCHEMA_PATH = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "telemetry_schema.json"
)


def _iter_session_files(root: Path) -> list[Path]:
    sessions_dir = root / "sessions"
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.glob("*/*.jsonl"))


def _read_events(files: list[Path]) -> list[dict]:
    events = []
    dropped = 0
    for f in files:
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                dropped += 1
                continue
    if dropped:
        print(f"warning: {dropped} malformed JSONL line(s) skipped", file=sys.stderr)
    return events


def cmd_telemetry_show(args: argparse.Namespace) -> int:
    files = _iter_session_files(TELEMETRY_ROOT)
    if args.session:
        files = [f for f in files if args.session in f.name]
    events = _read_events(files)
    if args.tool:
        events = [e for e in events if e.get("tool_name") == args.tool]
    if args.since:
        # naive: filter by ts prefix matching YYYY-MM-DD HH
        events = [e for e in events if e.get("ts", "") >= args.since]
    if not events:
        print("(no events)", file=sys.stderr)
        return 0
    for e in events:
        print(
            f"{e.get('ts', '?'):<27} {e.get('event_type', '?'):<11} {e.get('tool_name', '?'):<10} "
            f"{e.get('hook_decision', '?'):<5} {e.get('tool_input_path', '')}"
        )
    return 0


def cmd_telemetry_grep(args: argparse.Namespace) -> int:
    pattern = re.compile(args.pattern)
    files = _iter_session_files(TELEMETRY_ROOT)
    events = _read_events(files)
    matches = [e for e in events if pattern.search(json.dumps(e))]
    for e in matches:
        print(json.dumps(e))
    return 0


def cmd_telemetry_diff(args: argparse.Namespace) -> int:
    files = {f.stem: f for f in _iter_session_files(TELEMETRY_ROOT)}
    missing = [s for s in (args.session_a, args.session_b) if s not in files]
    if missing:
        for name in missing:
            print(f"session not found: {name}", file=sys.stderr)
        return 1
    events_a = _read_events([files[args.session_a]])
    events_b = _read_events([files[args.session_b]])
    counts_a = Counter(e.get("hook_decision") for e in events_a)
    counts_b = Counter(e.get("hook_decision") for e in events_b)
    print(f"{'decision':<10} {'A':>5} {'B':>5} {'delta':>7}")
    for key in sorted(set(counts_a) | set(counts_b)):
        a, b = counts_a.get(key, 0), counts_b.get(key, 0)
        print(f"{key:<10} {a:>5} {b:>5} {b - a:>+7}")
    return 0


def cmd_telemetry_export(args: argparse.Namespace) -> int:
    if not args.i_understand_pii_implications:
        print(
            "ERROR: --i-understand-pii-implications is required to export.\n"
            "Local telemetry may contain file paths and tool inputs. By exporting\n"
            "you confirm you have reviewed the data for PII before uploading.",
            file=sys.stderr,
        )
        return 2
    files = _iter_session_files(TELEMETRY_ROOT)
    out = Path(args.out) if args.out else TELEMETRY_ROOT / "exports" / "export.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    events = _read_events(files)
    with out.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    print(f"exported {len(events)} events to {out}")
    return 0


def cmd_telemetry_config(args: argparse.Namespace) -> int:
    """Read/write telemetry config.properties.

    Format: flat ``key: value`` lines (one per line).  Values are always
    strings — no nested keys, no quoting, no type coercion.  Lines
    starting with ``#`` are ignored.  Keys are sorted alphabetically
    on write.
    """
    config_path = TELEMETRY_ROOT / "config.properties"
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)
    if args.subcommand == "set":
        existing: dict[str, str] = {}
        if config_path.exists():
            for line in config_path.read_text().splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    existing[k.strip()] = v.strip()
        existing[args.key] = args.value
        config_path.write_text(
            "\n".join(f"{k}: {v}" for k, v in sorted(existing.items())) + "\n"
        )
        print(f"set {args.key}={args.value} in {config_path}")
    return 0


def cmd_telemetry_schema(args: argparse.Namespace) -> int:
    if not SCHEMA_PATH.exists():
        print(f"error: schema file not found: {SCHEMA_PATH}", file=sys.stderr)
        return 1
    schema = json.loads(SCHEMA_PATH.read_text())
    print(json.dumps(schema, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="heretek", description="heretek marketplace CLI"
    )
    sub = parser.add_subparsers(dest="group", required=True)
    tel = sub.add_parser("telemetry", help="local hook event log inspection")
    tel_sub = tel.add_subparsers(dest="command", required=True)

    show = tel_sub.add_parser("show", help="show events")
    show.add_argument(
        "--session",
        help="filter by session id (substring match; e.g., '2026-08-08' matches all sessions in that date folder)",
    )
    show.add_argument("--tool", help="filter by tool name")
    show.add_argument("--since", help="filter by timestamp prefix")
    show.set_defaults(func=cmd_telemetry_show)

    grep = tel_sub.add_parser("grep", help="regex search across all sessions")
    grep.add_argument("pattern")
    grep.set_defaults(func=cmd_telemetry_grep)

    diff = tel_sub.add_parser("diff", help="diff two sessions' hook-firing rates")
    diff.add_argument("session_a")
    diff.add_argument("session_b")
    diff.set_defaults(func=cmd_telemetry_diff)

    exp = tel_sub.add_parser("export", help="bundle for upload (opt-in)")
    exp.add_argument(
        "--out", help="output path (default: ~/.heretek/telemetry/exports/)"
    )
    exp.add_argument(
        "--i-understand-pii-implications",
        action="store_true",
        dest="i_understand_pii_implications",
        help="confirm PII review before exporting",
    )
    exp.set_defaults(func=cmd_telemetry_export)

    cfg = tel_sub.add_parser(
        "config", help="read/write ~/.heretek/telemetry/config.properties"
    )
    cfg_sub = cfg.add_subparsers(dest="subcommand", required=True)
    cfg_set = cfg_sub.add_parser("set", help="set a config key")
    cfg_set.add_argument("key")
    cfg_set.add_argument("value")
    cfg_set.set_defaults(func=cmd_telemetry_config)

    sch = tel_sub.add_parser("schema", help="print telemetry JSON Schema")
    sch.set_defaults(func=cmd_telemetry_schema)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
