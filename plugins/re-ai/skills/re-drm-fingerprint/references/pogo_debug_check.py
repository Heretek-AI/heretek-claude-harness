"""pogo_debug_check.py — extract the PE debug directory from a binary
and surface IMAGE_DEBUG_TYPE_POGO (type 10) entries.

Standalone helper for the re-drm-fingerprint skill. The POGO
entry is the third-party-ATD layer's trigger-arming metadata
(per the ANTI-TAMPER-TAXONOMY.md Pattern A-DW detection rule;
the empirical evidence base is the v2.9.0 stress test's
section-triage artifact in
See the RE-AI output directory.).

The MCP-surface replacement is the v2.9.0+
`mcp__re-lief__get_debug_directory` tool (preferred path
when the new MCP tool is installed). This skill-side
helper is the v2.9.0 ship path — the v2.8.0 cycle
documented the POGO workaround as "would be a v2.9.1+
addition"; v2.9.0 ships both the MCP tool and this
fallback.

Usage:
    python3 pogo_debug_check.py <path-to-pe-binary>

Vendor-neutral: emits only category names + structural
facts (entry types, timestamps, sizes). No vendor-
attribution prose in the output.
"""

from __future__ import annotations

import argparse
import sys

try:
    import lief
except ImportError as exc:
    sys.stderr.write(
        "error: lief is required for pogo_debug_check.py\n"
        "  install with: pip install 'lief>=0.16,<0.18'\n"
        f"  ({exc})\n"
    )
    sys.exit(2)


# PE debug directory entry types. The subset documented
# in `Output/.../drm-catalog-analysis/per-target/<ue5-target>/stage5-pogo-debug-check.md`:
#   IMAGE_DEBUG_TYPE_CODEVIEW = 2   (PDB pointer)
#   IMAGE_DEBUG_TYPE_POGO     = 10  (profile-guided optimization)
# The full enum is exported by Microsoft's PE/COFF
# specification; we only need the canonical names.
_DEBUG_TYPE_NAMES = {
    0: "UNKNOWN",
    1: "COFF",
    2: "CODEVIEW",       # PDB pointer
    3: "FPO",
    4: "MISC",
    5: "EXCEPTION",
    6: "FIXUP",
    7: "BORLAND_MAP",
    9: "CLSID",
    10: "POGO",          # profile-guided optimization
    11: "ILTCG",
    12: "MPX",
    13: "REPRO",
    14: "EX_DLLCHARACTERISTICS",
    16: "RESERVED10",
    20: "VC_FEATURE",
    21: "POGO_INLINES",
    22: "ILTCG_INSTRUMENTATION",
}


def _kind_for_type(t: int) -> str:
    """Return the canonical name for a debug-directory type code."""
    return _DEBUG_TYPE_NAMES.get(t, f"TYPE_{t}")


def debug_directory_summary(path: str) -> dict:
    """Return a structured summary of the PE debug directory.

    Args:
        path: absolute or relative path to a PE (.dll / .exe).

    Returns:
        {
          "path": str,
          "debug_entries": int,
          "has_pogo_entry": bool,
          "has_codeview_entry": bool,
          "pogo_indices": list[int],
          "codeview_indices": list[int],
          "entries": [
            {"index": int, "type": int, "kind": str,
             "timestamp": int, "version": int,
             "sizeof_data": int, "addressof_rawdata": int},
            ...
          ],
        }
    """
    pe = lief.PE.parse(path)
    if pe is None:
        raise ValueError(f"failed to parse {path} as a PE")
    dbg = pe.debug_directory
    entries: list[dict] = []
    pogo_indices: list[int] = []
    codeview_indices: list[int] = []
    for i, entry in enumerate(dbg):
        kind = _kind_for_type(entry.type)
        if entry.type == 10:
            pogo_indices.append(i)
        if entry.type == 2:
            codeview_indices.append(i)
        entries.append({
            "index": i,
            "type": entry.type,
            "kind": kind,
            "timestamp": entry.timestamp,
            "version": entry.version,
            "sizeof_data": entry.sizeof_data,
            "addressof_rawdata": entry.addressof_rawdata,
        })
    return {
        "path": path,
        "debug_entries": len(entries),
        "has_pogo_entry": bool(pogo_indices),
        "has_codeview_entry": bool(codeview_indices),
        "pogo_indices": pogo_indices,
        "codeview_indices": codeview_indices,
        "entries": entries,
    }


def _print_human(result: dict) -> None:
    """Print the summary in a human-readable form."""
    print(f"path: {result['path']}")
    print(f"debug_entries: {result['debug_entries']}")
    print(f"has_pogo_entry: {result['has_pogo_entry']}")
    print(f"has_codeview_entry: {result['has_codeview_entry']}")
    if result["pogo_indices"]:
        print(f"pogo_indices: {result['pogo_indices']}")
    if result["codeview_indices"]:
        print(f"codeview_indices: {result['codeview_indices']}")
    for e in result["entries"]:
        print(
            f"  [{e['index']}] type={e['type']} "
            f"kind={e['kind']} "
            f"timestamp={e['timestamp']} "
            f"version=0x{e['version']:08x} "
            f"sizeof_data={e['sizeof_data']} "
            f"addressof_rawdata=0x{e['addressof_rawdata']:x}"
        )


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", help="Path to a PE binary")
    ap.add_argument(
        "--json", action="store_true",
        help="Emit the structured dict as JSON instead of human-readable text",
    )
    args = ap.parse_args()
    try:
        result = debug_directory_summary(args.path)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        import json
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
