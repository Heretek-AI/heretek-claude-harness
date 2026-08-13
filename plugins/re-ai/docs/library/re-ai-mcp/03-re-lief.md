---
title: "re-lief (RE-AI MCP server)"
category: "re-ai-mcp"
platforms: ["linux", "windows", "macos"]
difficulty: "intermediate"
tags: ["lief", "binary-parsing", "pe", "elf", "macho", "dex", "section-table", "string-categorization", "protection-classification"]
summary: "MCP server wrapping the LIEF (Library to Instrument Executable Formats) Python library for cross-format binary parsing: PE, ELF, MachO, COFF, DEX, ART, OAT in a single normalized API. 19 tools (was 18; v2.9.0 added `get_debug_directory` for IMAGE_DEBUG_TYPE_POGO + Pattern A-DW detection). The canonical first-pass binary parser; the `categorize_strings` output is the input to the drm-indicators.yaml catalog."
updated: "2026-06-07"
related: ["re-ai-mcp/01-re-ai-plugin", "native/02-pe-section-layout", "android/01-apk-structure", "anti-analysis/02-vm-bytecode-interpreter"]
---

## Summary

`re-lief` is the RE-AI MCP server that wraps
[LIEF](https://lief-project.github.io/) (Library
to Instrument Executable Formats). LIEF is a
cross-format binary parser that handles PE, ELF,
MachO, COFF, DEX, ART, and OAT in a single
normalized Python API. The server exposes 19
tools (the v2.9.0 cycle added `get_debug_directory`
for IMAGE_DEBUG_TYPE_POGO + Pattern A-DW
detection).

## Why this matters

`re-lief` is the **canonical first-pass binary
parser** in the RE-AI plugin. Every triage skill
starts with `parse_binary` + `get_sections`; the
`categorize_strings` output is the input to the
catalog's pattern detection; the `get_imphash` +
`get_overlay` + `get_authenticode` + `get_debug_
directory` form the full structural characterization.

The v2.9.0 cycle's new tool, `get_debug_directory`,
returns the PE debug directory entries including
IMAGE_DEBUG_TYPE_POGO (type 10). A POGO entry in
a UE5 binary is the canonical ANTI-TAMPER-TAXONOMY
Pattern A-DW signal (the Denuvo-wrapped encrypted-
VM bytecode interpreter). The P3R per-target
analysis in the v2.9.0 stress test subdir 4
empirically validated the new tool.

## Mechanics

The server requires `lief` (`pip install lief`).
The `check_lief()` tool reports the installed
version + the supported formats.

The 19 tools (v2.9.0):

| Tool | Purpose |
|---|---|
| `check_lief` | Health check |
| `parse_binary` | Format auto-detect + header (PE / ELF / MachO / DEX) |
| `get_sections` | Section list (name + VA + size + entropy + flags) |
| `get_imports_exports` | Import + export tables |
| `get_imphash` | PE import hash (MD5 of normalized import table) |
| `get_overlay` | Appended data after the last section (PE overlay) |
| `get_authenticode` | PE Authenticode signature details |
| `get_debug_directory` | PE debug directory entries (incl. IMAGE_DEBUG_TYPE_POGO) — **added v2.9.0** |
| `list_dex_classes` | Android DEX class enumeration |
| `list_dex_methods` | Android DEX method enumeration per class |
| `list_oat_art` | Android OAT/ART runtime method list |
| `categorize_strings` | String-table bucketing (anti_debug / hwid / crypto / network / etc.) — the input to the drm-indicators catalog |
| `classify_native_protection` | Native PE protection class (UPX / VM / encrypted-VM / IL2CPP) |
| `scan_anti_analysis_primitives` | Cross-section anti-analysis scanner |
| `extract_strings` | String extraction (ASCII / UTF-16LE) |
| `disasm_capstone` | Capstone-based disasm fallback |
| `normalize_for_diff` | Structural snapshot for binary diffing |
| `list_oat_art` | (dup; see above) |
| `parse_with_format` (etc.) | — (sub-set of the underlying LIEF API exposed) |

The `categorize_strings` output's `by_category` map
is the input to `ANTI-TAMPER-TAXONOMY.md` Pattern A
+ Pattern A-DW + Pattern B detection rules. The
`min_evidence: N` gates in the catalog suppress
single-keyword false positives.

## Approach

Typical first-pass triage:

1. `parse_binary(path)` — confirm format, arch,
   hashes (SHA-256, MD5, SHA-1), imphash, signing.
2. `get_sections(path)` — section table; look for
   Pattern A (Unity-IL2CPP) or Pattern A-DW
   (Denuvo-wrapped UE5) section sets.
3. `categorize_strings(path, min_length=5,
   max_per_category=200)` — bucketed string view;
   the `by_category` block is the catalog input.
4. `get_debug_directory(path)` (v2.9.0) — for PE,
   return the debug directory; a POGO entry is
   the Pattern A-DW signal.
5. `classify_native_protection(path)` — the
   protection-class label (UPX / VM / encrypted-VM
   / IL2CPP / plain-PE).

## Common pitfalls

- **Categorizer false positives.** The
  `min_evidence: N` gate is what suppresses
  single-keyword false positives. A bucket with
  `count > 0` but `meets_threshold: false` is
  surfaced in `samples[]` for the LLM's context
  but does not contribute to the score.
- **The 400 MB entropy walk is slow.** The
  `categorize_strings` tool walks the file
  linearly; the v2.9.0 stress test noted the
  `skip_sections` parameter (e.g. `.xtls`,
  `.xpdata`, `.udata`) for large binaries.
- **The `get_overlay` reads the trailing data
  after the last section.** The LIR per-target
  walk in the v2.9.0 stress test subdir 3 found
  a 7,024-byte overlay at offset 656,384 — the
  managed-launcher overlay archive (the B3
  catalog entry's signature).

## Tooling pointers

- The `categorize_strings` output's `by_category`
  map is the input to `ANTI-TAMPER-TAXONOMY.md`
  Pattern A + Pattern A-DW + Pattern B detection
  rules
- `re-android-dynamic` is the Android-specific
  runtime-analysis sibling; `re-lief` handles
  the static APK triage
- The DEX + ART + OAT tools are the Android
  bridge to `re-apktool` + `re-android-dynamic`

## References

- [LIEF](https://lief-project.github.io/) — the
  upstream project
- `native/02-pe-section-layout.md` — the section
  table reference
- `android/01-apk-structure.md` — the Android
  APK / DEX / OAT reference
- `anti-analysis/02-vm-bytecode-interpreter.md` —
  Pattern A (Unity-IL2CPP)
- `ANTI-TAMPER-TAXONOMY.md` Pattern A-DW — the
  Denuvo-wrapped variant (the v2.9.0 addition
  that uses `get_debug_directory`)
- `Output/v2.9.0-stress-test/denuvo-analysis/
  per-target/p3r/stage1-section-triage.md` — the
  P3R per-target section table
- `Output/v2.9.0-stress-test/origin-stub-drop/
  per-target/lir/rationale.md` — the LIR
  per-target overlay (the B3 signature)
