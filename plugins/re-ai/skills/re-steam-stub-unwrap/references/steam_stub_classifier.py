"""steam_stub_classifier.py — classify a sibling steam_api64.dll by
Steamworks SDK version (v1.51 vs v1.60+) from its export list.

Standalone helper for the re-steam-stub-unwrap skill. The classifier
runs on the export list (typically obtained via
`mcp__re-rizin__list_imports_exports(path=<steam_api64.dll>)`), so
this script does not invoke any MCP tool itself.

Usage:
    python3 steam_stub_classifier.py <path-to-steam_api64.dll>
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


# Marker exports that distinguish Steamworks SDK versions. Names are
# part of the SDK's documented public surface (Steamworks SDK release
# notes); not vendor secrets.
_V160_PLUS_EXCLUSIVE = frozenset({
    "SteamAPI_InitSafe",
    "SteamAPI_InitAnonymousUser",
    "SteamAPI_InitFlat",
})

_V151_REQUIRED = frozenset({
    "SteamAPI_Init",
    "SteamAPI_RestartAppIfNecessary",
    "SteamAPI_Shutdown",
})


def classify(exports: list[str]) -> dict:
    """Classify a steam_api64.dll by exported function names."""
    export_set = set(exports)
    steam_exports = [e for e in exports if e.startswith("SteamAPI_")]
    v160_present = sorted(export_set & _V160_PLUS_EXCLUSIVE)
    v151_present = sorted(export_set & _V151_REQUIRED)
    evidence: list[str] = []
    if v160_present:
        evidence.append(
            f"Found {len(v160_present)} v1.60+ exclusive exports: "
            + ", ".join(v160_present)
        )
        version_band, confidence = "v1.60+", "High"
    elif len(v151_present) == len(_V151_REQUIRED):
        evidence.append("All 3 v1.51-required exports present + 0 v1.60+ markers")
        version_band, confidence = "v1.51", "High"
    elif v151_present:
        evidence.append(
            f"Found {len(v151_present)}/3 v1.51 markers; non-canonical DLL"
        )
        version_band, confidence = "unknown", "Low"
    else:
        evidence.append("No Steamworks-SDK markers in the export list")
        version_band, confidence = "unknown", "Low"
    return {
        "version_band": version_band,
        "confidence": confidence,
        "evidence": evidence,
        "export_count": len(exports),
        "steam_export_count": len(steam_exports),
        "v160_plus_markers_present": v160_present,
        "v151_markers_present": v151_present,
    }


def _list_pe_exports(path: str) -> list[str]:
    """Pull export names from a PE without pefile/lief deps."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    if len(data) < 0x40 or data[:2] != b"MZ":
        return []
    try:
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    except struct.error:
        return []
    if pe_off + 24 > len(data) or data[pe_off:pe_off + 4] != b"PE\x00\x00":
        return []
    try:
        opt_hdr_size = struct.unpack_from("<H", data, pe_off + 20)[0]
        num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    except struct.error:
        return []
    opt_hdr_off = pe_off + 24
    if opt_hdr_off + opt_hdr_size > len(data):
        return []
    magic = struct.unpack_from("<H", data, opt_hdr_off)[0]
    dd_off = opt_hdr_off + (96 if magic == 0x10b else 112)
    if dd_off + 8 > len(data):
        return []
    export_rva, export_size = struct.unpack_from("<II", data, dd_off)
    if export_rva == 0 or export_size == 0:
        return []
    sec_off = pe_off + 24 + opt_hdr_size

    def rva_to_offset(rva: int) -> int | None:
        for i in range(num_sections):
            sb = sec_off + i * 40
            v_addr = struct.unpack_from("<I", data, sb + 12)[0]
            v_size = struct.unpack_from("<I", data, sb + 8)[0]
            f_off = struct.unpack_from("<I", data, sb + 20)[0]
            if v_addr <= rva < v_addr + max(v_size, 1):
                return f_off + (rva - v_addr)
        return None

    edata = rva_to_offset(export_rva)
    if edata is None:
        return []
    try:
        num_names = struct.unpack_from("<I", data, edata + 24)[0]
        names_rva = struct.unpack_from("<I", data, edata + 32)[0]
    except struct.error:
        return []
    names_off = rva_to_offset(names_rva)
    if names_off is None:
        return []
    exports: list[str] = []
    for i in range(num_names):
        name_ptr_off = names_off + i * 4
        if name_ptr_off + 4 > len(data):
            break
        name_rva = struct.unpack_from("<I", data, name_ptr_off)[0]
        name_off = rva_to_offset(name_rva)
        if name_off is None:
            continue
        end = data.find(b"\x00", name_off)
        if end < 0:
            continue
        try:
            exports.append(data[name_off:end].decode("ascii"))
        except UnicodeDecodeError:
            continue
    return exports


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", help="Path to a steam_api64.dll")
    args = ap.parse_args()
    exports = _list_pe_exports(args.path)
    if not exports:
        print(f"error: failed to read exports from {args.path}", file=sys.stderr)
        return 2
    json.dump(classify(exports), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
