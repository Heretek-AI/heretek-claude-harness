"""eos_stub_classifier.py — classify a sibling eossdk.dll by
EOS SDK version (SDK 1.0 vs SDK 1.5+) from its export
list.

Standalone helper for the re-eos-bypass skill. The
classifier runs on the export list (typically obtained
via `mcp__re-rizin__list_imports_exports(path=<sibling
eossdk.dll>)`), so this script does not invoke any MCP
tool itself.

Usage:
    python3 eos_stub_classifier.py <path-to-eossdk.dll>

Vendor-neutral: uses the catalog's category-only
descriptors and avoids any product-name literal that
would trip the vendor-leakage NEEDLES list.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


# Marker exports that distinguish EOS SDK generations.
# Names are part of the SDK's documented public surface;
# not vendor secrets.
_V15_PLUS_EXCLUSIVE = frozenset({
    "EOS_Platform_TryInitialize",
    "EOS_Platform_Create",
    "EOS_Platform_Release",
    "EOS_Platform_Tick",
})

_V10_REQUIRED = frozenset({
    "EOS_Initialize",
    "EOS_Shutdown",
})


def classify(exports: list[str]) -> dict:
    """Classify a sibling eossdk.dll by exported function names."""
    export_set = set(exports)
    sdk_exports = [e for e in exports if e.startswith("EOS_")]
    v15_present = sorted(export_set & _V15_PLUS_EXCLUSIVE)
    v10_present = sorted(export_set & _V10_REQUIRED)
    evidence: list[str] = []
    if v15_present:
        evidence.append(
            f"Found {len(v15_present)} v1.5+ exclusive exports: "
            + ", ".join(v15_present)
        )
        version_band, confidence = "v1.5+", "High"
    elif len(v10_present) == len(_V10_REQUIRED):
        evidence.append("All 2 v1.0-required exports present + 0 v1.5+ markers")
        version_band, confidence = "v1.0", "High"
    elif v10_present:
        evidence.append(
            f"Found {len(v10_present)}/2 v1.0 markers; non-canonical DLL"
        )
        version_band, confidence = "unknown", "Low"
    else:
        evidence.append("No EOS-SDK markers in the export list")
        version_band, confidence = "unknown", "Low"
    return {
        "version_band": version_band,
        "confidence": confidence,
        "evidence": evidence,
        "export_count": len(exports),
        "sdk_export_count": len(sdk_exports),
        "v15_plus_markers_present": v15_present,
        "v10_markers_present": v10_present,
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
    ap.add_argument("path", help="Path to an eossdk.dll")
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
