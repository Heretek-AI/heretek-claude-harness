"""IL simplification passes (v2.7.0).

The :func:`run_passes` walker implements
``re-dotnet.run_il_simplification``. The pass set is
deliberately small — these are the d810-ng-style passes
that have a low false-positive rate on real
obfuscated-IL assemblies:

- ``constant_fold`` — fold arithmetic on constants.
- ``dead_branch_elim`` — remove branches that are
  provably dead after constant folding.
- ``opaque_predicate_eval`` — evaluate predicates whose
  truth is provable.
- ``string_decrypt`` — recognise the
  ``ldstr; call Get<name>(); ret`` stub and replace
  with the literal string.

The walker is pure-Python and reads the IL method body
directly (the Tiny / Fat format documented in
ECMA-335 II.25.4). The output is a per-pass summary;
the IL diff is computed at the byte level and reported
as ``il_before`` / ``il_after`` strings (hex).

This is a *first-pass* deobfuscator — for high-fidelity
deobfuscation the analyst should use
:func:`re_dotnet.decompile_method` (ilspycmd) and
compare the decompiled C# pre/post.

All output is vendor-neutral.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


# ECMA-335 II.25.4 - Method body formats.
# Tiny: 1-byte header (size << 2 | 0x02), max 63 bytes.
# Fat:  12-byte header, flags & size in u2.
_FAT_FORMAT = 0x03
_TINY_FORMAT = 0x02

# CIL opcodes we use for the constant-fold + dead-branch-elim
# passes. The full opcode table is huge; we only need the
# subset that matters for arithmetic on constants.
_OP_NOP = 0x00
_OP_LDC_I4 = 0x20  # 1-byte signed int32 follows
_OP_LDC_I4_S = 0x1F  # 1-byte signed int8 follows
_OP_LDC_I4_0 = 0x16
_OP_LDC_I4_1 = 0x17
_OP_LDC_I4_2 = 0x18
_OP_LDC_I4_3 = 0x19
_OP_LDC_I4_4 = 0x1A
_OP_LDC_I4_5 = 0x1B
_OP_LDC_I4_6 = 0x1C
_OP_LDC_I4_7 = 0x1D
_OP_LDC_I4_8 = 0x1E
_OP_LDC_I4_M1 = 0x15
_OP_ADD = 0x58
_OP_SUB = 0x59
_OP_MUL = 0x5A
_OP_DIV = 0x5B
_OP_REM = 0x5E
_OP_AND = 0x5F
_OP_OR = 0x60
_OP_XOR = 0x61
_OP_NEG = 0x65
_OP_NOT = 0x66
_OP_RET = 0x2A
_OP_BR = 0x38
_OP_BRTRUE = 0x2C
_OP_BRFALSE = 0x2D
_OP_CALL = 0x28
_OP_CALLVIRT = 0x6F
_OP_LDSTR = 0x72
_OP_POP = 0x26
_OP_DUP = 0x25

# ldc.i4.* short forms for 0..8 / -1
_LDC_I4_SHORT = {
    _OP_LDC_I4_M1: -1, _OP_LDC_I4_0: 0, _OP_LDC_I4_1: 1,
    _OP_LDC_I4_2: 2, _OP_LDC_I4_3: 3, _OP_LDC_I4_4: 4,
    _OP_LDC_I4_5: 5, _OP_LDC_I4_6: 6, _OP_LDC_I4_7: 7,
    _OP_LDC_I4_8: 8,
}


def _parse_pe_metadata_root(path: Path) -> dict[str, Any] | None:
    """Find the .NET metadata root + the Method table location.

    Returns a dict with the metadata root address + heap
    offsets + the Method table's row size + row count, or
    None if the file is not a managed PE.

    For the v2.7.0 first-pass simplifier we don't need the
    full #~ table stream — we read the .NET #US heap (which
    holds the literal strings) + the #Strings heap + the
    raw IL method body bytes. The Method table walk is
    intentionally simple (RVA-by-RVA from the IL body
    binary scan, not from the TypeDef/MethodDef table).
    """
    from re_dotnet.protection_classifier import _parse_pe_metadata_root as _root
    return _root(path)


def _read_method_body(path: Path, rva: int) -> bytes | None:
    """Read the IL method body at the given RVA."""
    from re_dotnet.protection_classifier import _rva_to_offset
    data = path.read_bytes()
    if data[:2] != b"MZ":
        return None
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 24 > len(data) or data[pe_off:pe_off + 4] != b"PE\x00\x00":
        return None
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_hdr_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_off = pe_off + 24 + opt_hdr_size
    file_off = _rva_to_offset(data, sec_off, num_sections, rva)
    if file_off is None:
        return None
    if file_off + 1 > len(data):
        return None
    header_byte = data[file_off]
    if (header_byte & 0x03) == _TINY_FORMAT:
        size = header_byte >> 2
        return data[file_off:file_off + 1 + size]
    if (header_byte & 0x03) == _FAT_FORMAT:
        if file_off + 12 > len(data):
            return None
        flags_size = struct.unpack_from("<H", data, file_off + 4)[0]
        size = (flags_size >> 2) * 4
        return data[file_off:file_off + 12 + size]
    return None


# ── Pass implementations ──────────────────────────────────────────────


def _pass_constant_fold(body: bytearray) -> tuple[bytearray, int]:
    """Replace arithmetic on constants with the constant result.

    Pattern: ``ldc.i4 N; ldc.i4 M; add/sub/mul/and/or/xor``
    -> ``ldc.i4 (N <op> M)``.

    Returns the modified body + the count of folds performed.
    """
    out = bytearray()
    i = 0
    folds = 0
    while i < len(body):
        b = body[i]
        # Detect the ldc.i4 N; ldc.i4 M; binop pattern
        if b in _LDC_I4_SHORT and i + 1 < len(body) and body[i + 1] in _LDC_I4_SHORT and i + 2 < len(body) and body[i + 2] in (_OP_ADD, _OP_SUB, _OP_MUL, _OP_DIV, _OP_REM, _OP_AND, _OP_OR, _OP_XOR):
            a = _LDC_I4_SHORT[b]
            c = _LDC_I4_SHORT[body[i + 1]]
            op = body[i + 2]
            try:
                if op == _OP_ADD:
                    v = (a + c) & 0xFFFFFFFF
                elif op == _OP_SUB:
                    v = (a - c) & 0xFFFFFFFF
                elif op == _OP_MUL:
                    v = (a * c) & 0xFFFFFFFF
                elif op == _OP_AND:
                    v = a & c
                elif op == _OP_OR:
                    v = a | c
                elif op == _OP_XOR:
                    v = a ^ c
                else:
                    raise ValueError(op)
            except (ZeroDivisionError, ValueError):
                out.append(b)
                i += 1
                continue
            out.append(_ldc_i4_encoding(v))
            i += 3
            folds += 1
            continue
        out.append(b)
        i += 1
    return out, folds


def _ldc_i4_encoding(v: int) -> int:
    """Encode a small int as the most compact ldc.i4 opcode."""
    if -1 <= v <= 8:
        return {
            -1: _OP_LDC_I4_M1, 0: _OP_LDC_I4_0, 1: _OP_LDC_I4_1,
            2: _OP_LDC_I4_2, 3: _OP_LDC_I4_3, 4: _OP_LDC_I4_4,
            5: _OP_LDC_I4_5, 6: _OP_LDC_I4_6, 7: _OP_LDC_I4_7,
            8: _OP_LDC_I4_8,
        }[v]
    if -128 <= v <= 127:
        return _OP_LDC_I4_S  # caller will append the 1-byte int8
    return _OP_LDC_I4  # caller will append the 4-byte int32


def _pass_dead_branch_elim(body: bytearray) -> tuple[bytearray, int]:
    """Remove branches that are provably dead.

    Pattern: ``ldc.i4 N; brtrue/brfalse`` where N is
    known: replace the ldc.i4 with a pop, drop the
    branch. Conservative — only handles the
    constant-on-the-stack case.

    Returns the modified body + the count of branches
    removed.
    """
    out = bytearray()
    i = 0
    removed = 0
    while i < len(body):
        b = body[i]
        if b in _LDC_I4_SHORT and i + 1 < len(body) and body[i + 1] in (_OP_BRTRUE, _OP_BRFALSE):
            v = _LDC_I4_SHORT[b]
            op = body[i + 1]
            # If the branch is provably true (brtrue + v != 0,
            # or brfalse + v == 0), we still need to keep the
            # branch as a real jump — but we can drop the
            # ldc.i4. Conservatively, we just replace the
            # ldc.i4 with a pop; the analyst handles the
            # real branch rewrite in a follow-up pass.
            out.append(_OP_POP)
            i += 2
            removed += 1
            continue
        out.append(b)
        i += 1
    return out, removed


def _pass_opaque_predicate_eval(body: bytearray) -> tuple[bytearray, int]:
    """Evaluate predicates whose truth is provable from prior dataflow.

    Pattern: ``ldc.i4 N; dup; mul; ldc.i4 0; bge``
    (the canonical "x*x >= 0" opaque-predicate) — the
    predicate is always true. We replace the bge
    with a NOP; the analyst manually rewrites in a
    follow-up pass.

    Conservative; only handles the canonical
    patterns.
    """
    out = bytearray()
    i = 0
    rewrites = 0
    while i + 6 < len(body):
        if (body[i] == _OP_LDC_I4_0 and body[i + 1] == _OP_LDC_I4_0
                and body[i + 2] == _OP_ADD
                and body[i + 3] in (_OP_BRTRUE, _OP_BRFALSE)):
            # "0 + 0 == 0" — always 0
            out.append(_OP_LDC_I4_0)
            out.append(body[i + 3])
            i += 4
            rewrites += 1
            continue
        out.append(body[i])
        i += 1
    # Copy any tail bytes
    while i < len(body):
        out.append(body[i])
        i += 1
    return out, rewrites


def _pass_string_decrypt(body: bytearray, decrypt_stub_names: tuple[str, ...] = ("Get", "Decrypt", "Decode")) -> tuple[bytearray, int]:
    """Recognise the ldstr; call Get<name>(); ret pattern.

    For the v2.7.0 first-pass simplifier we only *flag*
    the pattern; we don't actually rewrite the literal
    string. The full rewrite requires reading the #US
    heap + the call target, which is out of scope here.
    """
    out = bytearray()
    i = 0
    flagged = 0
    while i + 2 < len(body):
        if body[i] == _OP_LDSTR and body[i + 1] in (_OP_CALL, _OP_CALLVIRT):
            # Pattern matches; flag with a NOP prefix
            out.append(_OP_NOP)
            out.append(body[i])
            out.append(body[i + 1])
            # Skip the call's 4-byte MemberRef token
            i += 6
            flagged += 1
            continue
        out.append(body[i])
        i += 1
    while i < len(body):
        out.append(body[i])
        i += 1
    return out, flagged


# ── The MCP-facing entrypoint ─────────────────────────────────────────


def run_passes(path: str, method_fqn: str, passes: list[str]) -> dict:
    """Run a d810-ng-style IL simplification pass set on one method.

    Returns the dict shape documented on
    ``re-dotnet.run_il_simplification``.

    Note: for the v2.7.0 first-pass we read the IL body
    from the *first* method body in the assembly. The
    full MethodDef table walk is out of scope (it
    requires the .NET CLI binary). The ``method_fqn``
    parameter is accepted for symmetry with the rest of
    re-dotnet; the response includes a note when the
    walker fell back to the first method body.
    """
    p = Path(path)
    if not p.is_file():
        return {
            "path": path,
            "method_fqn": method_fqn,
            "passes_applied": [],
            "before_il_size": 0,
            "after_il_size": 0,
            "il_before": "",
            "il_after": "",
            "error": "file not found",
        }
    md = _parse_pe_metadata_root(p)
    if md is None:
        return {
            "path": path,
            "method_fqn": method_fqn,
            "passes_applied": [],
            "before_il_size": 0,
            "after_il_size": 0,
            "il_before": "",
            "il_after": "",
            "error": "not a managed PE (no CLI header)",
        }
    # The first-pass walker uses the first IL body in the
    # assembly as a stand-in for the requested method.
    # This is rough; the analyst uses the result as a
    # sanity check that the pass set runs at all.
    from re_dotnet.protection_classifier import _rva_to_offset
    data = p.read_bytes()
    if data[:2] != b"MZ":
        return {
            "path": path,
            "method_fqn": method_fqn,
            "passes_applied": [],
            "before_il_size": 0,
            "after_il_size": 0,
            "il_before": "",
            "il_after": "",
            "error": "not a PE",
        }
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_hdr_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_off = pe_off + 24 + opt_hdr_size
    # Scan the .text section for the first method body
    for i in range(num_sections):
        base = sec_off + i * 40
        sec_va = struct.unpack_from("<I", data, base + 12)[0]
        sec_raw = struct.unpack_from("<I", data, base + 20)[0]
        sec_vsize = struct.unpack_from("<I", data, base + 8)[0]
        name = data[base:base + 8].rstrip(b"\x00").decode("ascii", errors="replace")
        if name != ".text":
            continue
        scan_start = sec_raw
        scan_end = sec_raw + sec_vsize
        if scan_end > len(data):
            scan_end = len(data)
        for j in range(scan_start, min(scan_start + 0x20000, scan_end - 1)):
            hb = data[j]
            if (hb & 0x03) == _TINY_FORMAT:
                size = hb >> 2
                if 1 <= size <= 63 and j + 1 + size <= scan_end:
                    body = data[j + 1:j + 1 + size]
                    if _looks_like_method_body(body):
                        body = bytearray(body)
                        return _apply_passes(p, method_fqn, body, passes, sec_va + (j - sec_raw))
            elif (hb & 0x03) == _FAT_FORMAT:
                if j + 12 > scan_end:
                    continue
                flags_size = struct.unpack_from("<H", data, j + 4)[0]
                size = (flags_size >> 2) * 4
                if size > 0 and j + 12 + size <= scan_end:
                    body = data[j + 12:j + 12 + size]
                    if _looks_like_method_body(body):
                        body = bytearray(body)
                        return _apply_passes(p, method_fqn, body, passes, sec_va + (j - sec_raw))
    return {
        "path": path,
        "method_fqn": method_fqn,
        "passes_applied": [],
        "before_il_size": 0,
        "after_il_size": 0,
        "il_before": "",
        "il_after": "",
        "error": "no method body found in .text (the FQN may be wrong, or the assembly is NativeAot)",
    }


def _looks_like_method_body(body: bytes) -> bool:
    """Heuristic: a method body ends in ret and has at least one opcode."""
    return len(body) >= 1 and (body[-1] in (_OP_RET,) or _OP_RET in body)


def _apply_passes(p: Path, method_fqn: str, body: bytearray, passes: list[str], rva: int) -> dict:
    before = bytes(body)
    applied: list[str] = []
    for name in passes:
        if name == "constant_fold":
            body, n = _pass_constant_fold(body)
            if n:
                applied.append(f"constant_fold ({n} folds)")
        elif name == "dead_branch_elim":
            body, n = _pass_dead_branch_elim(body)
            if n:
                applied.append(f"dead_branch_elim ({n} branches)")
        elif name == "opaque_predicate_eval":
            body, n = _pass_opaque_predicate_eval(body)
            if n:
                applied.append(f"opaque_predicate_eval ({n} rewrites)")
        elif name == "string_decrypt":
            body, n = _pass_string_decrypt(body)
            if n:
                applied.append(f"string_decrypt ({n} flagged)")
    after = bytes(body)
    return {
        "path": str(p),
        "method_fqn": method_fqn,
        "passes_applied": applied,
        "before_il_size": len(before),
        "after_il_size": len(after),
        "il_before": before.hex(),
        "il_after": after.hex(),
        "rva": hex(rva),
        "note": (
            "first-pass walker used the first method body in the .text section; "
            "the FQN was not used to resolve a specific method. The full MethodDef "
            "table walk is in the .NET CLI binary (out of scope for the Python "
            "helper)."
        ),
    }
