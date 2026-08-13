"""handler_frequency_analyzer.py — the ONE new helper for the
v2.9.0 stress test vm-unpack subdir.

The user explicitly authorized this ~100-line helper in the
plan. It wraps `mcp__re-winedbg.gef_trace_breakpoint` in 10
batches of 1000 hits (to overcome the v2.4 max_hits=1000
cap), aggregates the per-handler-index hit counts into a
single frequency table, and exports as JSON.

Pure stdlib + JSON; the script does not invoke any MCP
tool itself. The caller (a Claude session running the
vm-unpack PoC) drives the `re-winedbg.gef_trace_breakpoint`
MCP call 10 times and feeds the results into this script.

Usage:
    python3 handler_frequency_analyzer.py \\
        --batch-json batch-1.json batch-2.json ... \\
        --output handler-frequency-table.json

Each batch JSON is the response from one
`re-winedbg.gef_trace_breakpoint` call:
{
  "hits": [
    {"register": "$rcx", "value": 42, "format": "idx=%d\\n"},
    ...
  ],
  "truncated": bool
}

The helper aggregates all `value` fields across all
batches and emits a frequency table:
{
  "target": "<binary path>",
  "dispatcher_rva": "<hex address>",
  "register": "$rcx",
  "total_hits": 10000,
  "unique_handlers": <count>,
  "top_5": [
    {"handler_index": 42, "hit_count": 1234},
    ...
  ],
  "frequency_table": {
    "42": 1234,
    "43": 987,
    ...
  }
}

The helper also prints the top-5 to stdout for the
Stage 5 handler lift.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def _load_batch(path: str) -> list[dict]:
    """Load one batch JSON and return the hits array."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: failed to load {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict) or "hits" not in data:
        print(f"error: {path} is not a valid batch JSON", file=sys.stderr)
        sys.exit(2)
    return data["hits"]


def aggregate(
    batches: list[list[dict]],
    target: str,
    dispatcher_rva: str,
    register: str,
) -> dict:
    """Aggregate per-handler-index hit counts across all batches."""
    counter: Counter[int] = Counter()
    for batch in batches:
        for hit in batch:
            value = hit.get("value")
            if value is None:
                continue
            counter[int(value)] += 1
    total = sum(counter.values())
    top5 = [
        {"handler_index": idx, "hit_count": cnt}
        for idx, cnt in counter.most_common(5)
    ]
    return {
        "target": target,
        "dispatcher_rva": dispatcher_rva,
        "register": register,
        "total_hits": total,
        "unique_handlers": len(counter),
        "top_5": top5,
        "frequency_table": {str(k): v for k, v in counter.items()},
    }


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--batch-json", nargs="+", required=True,
        help="Paths to batch JSON files (one per 1000-hit batch)",
    )
    ap.add_argument(
        "--output", required=True,
        help="Path to write the frequency-table JSON",
    )
    ap.add_argument(
        "--target", default="<unknown>",
        help="Path to the target binary (recorded in the output)",
    )
    ap.add_argument(
        "--dispatcher-rva", default="<unknown>",
        help="Dispatcher entry RVA (recorded in the output)",
    )
    ap.add_argument(
        "--register", default="$rcx",
        help="The register holding the handler index (default: $rcx)",
    )
    args = ap.parse_args()
    batches = [_load_batch(p) for p in args.batch_json]
    result = aggregate(
        batches,
        target=args.target,
        dispatcher_rva=args.dispatcher_rva,
        register=args.register,
    )
    Path(args.output).write_text(json.dumps(result, indent=2))
    sys.stdout.write(f"wrote {args.output}\n")
    sys.stdout.write(f"total_hits: {result['total_hits']}\n")
    sys.stdout.write(f"unique_handlers: {result['unique_handlers']}\n")
    sys.stdout.write("top_5:\n")
    for entry in result["top_5"]:
        sys.stdout.write(
            f"  handler_index={entry['handler_index']} "
            f"hit_count={entry['hit_count']}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
