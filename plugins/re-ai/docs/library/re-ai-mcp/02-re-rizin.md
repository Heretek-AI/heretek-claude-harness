---
title: "re-rizin (RE-AI MCP server)"
category: "re-ai-mcp"
platforms: ["linux", "windows", "macos"]
difficulty: "intermediate"
tags: ["rizin", "rz-bin", "disasm", "decompile", "string-scan", "byte-pattern-search"]
summary: "MCP server wrapping the rizin CLI (rz-bin, rz-asm, pdc) for cross-architecture disassembly, byte-pattern search, function analysis, and CFG extraction. The canonical RE-AI disasm + string-scan server; 13 tools covering the full rizin surface for the .text / .data / .rdata analysis pipeline."
updated: "2026-06-07"
related: ["re-ai-mcp/01-re-ai-plugin", "tools/01-ghidra", "native/02-pe-section-layout", "anti-analysis/02-vm-bytecode-interpreter"]
---

## Summary

`re-rizin` is the RE-AI MCP server that wraps the
[rizin](https://rizin.re/) reverse-engineering framework.
The server exposes 13 tools covering the canonical
disasm + string-scan + byte-pattern-search surface
that the `re-vm-reverse` and `re-static-triage` skills
consume end-to-end.

## Why this matters

`re-rizin` is the **canonical disasm + string-scan
server** in the RE-AI plugin. The v2.9.0 stress test
confirmed it as the go-to server for:

- The `search_bytes` byte-pattern search (the
  canonical Steamworks call-site, Denuvo ATD
  string, and VM dispatcher `FF E0` / `FF 20`
  opcode pattern searches are all rizin
  `search_bytes` calls)
- The `list_imports_exports` table walker
  (the canonical per-target .exe import walk
  that establishes whether Steamworks is
  directly imported or lives in a sibling
  `GameAssembly.dll`)
- The `analyze_function` + `disassemble_function`
  pair (the canonical per-function disassembly
  + decompile-via-pdc)

The v2.9.0 stress test surfaced a **memory wall on
>400 MB binaries** (Gap 19): `analyze_function`
returns 0 functions on TWW3 (226 MB — borderline),
007FL (340 MB — borderline), P3R (373 MB), and
CD (408 MB). The workaround is per-section
`search_bytes` + `disassemble_function(addr=...)`;
the v2.9.1+ fix is per-section `aa` mode in rizin
(skip the full-program auto-analysis).

## Mechanics

The server requires `rizin` (the C rewrite of
radare2) on PATH. The `check_rizin()` tool
reports the installed version + the binary
location.

The 13 tools:

| Tool | Purpose |
|---|---|
| `check_rizin` | Health check (version + binary path) |
| `get_file_info` | High-level file metadata (arch + format) |
| `list_imports_exports` | The import + export table walker |
| `list_strings` | String extraction (`ascii` / `utf16` / `all`) |
| `analyze_function` | Auto-analysis + function list (full-program) |
| `list_functions_with_metadata` | Function list with category hints (per `data/compiler-fingerprints.json`) |
| `disassemble_function` | Per-function disasm (capped at `max_insns`) |
| `decompile_function` | Per-function pseudo-C (via `pdc`) |
| `get_cfg_graph` | DOT-format CFG of a function |
| `find_crypto_constants` | Crypto-constant search (AES S-box, SHA-256 K, CRC32) |
| `get_xrefs` | Cross-references to/from a target |
| `search_bytes` | Hex byte-pattern search |
| `emulate_esil` | ESIL emulation of a function |

The `pdc` decompiler is the lowest-fidelity option
in RE-AI (much lower than IDA Hex-Rays or Ghidra);
for high-fidelity decompilation use
`re-llm-decompile.decompile_function` with
`disassemble_function` as input.

## Approach

Typical v2.9.0 stress test workflow:

1. `get_file_info(path)` — confirm the format +
   arch (PE32+ / x86_64 / etc.).
2. `list_imports_exports(path)` — walk the import
   table; look for `steam_api64.dll` /
   `EOSSDK-Win64-Shipping.dll` / `mscoree.dll`
   imports (the per-storefront stub-drop signal).
3. `search_bytes(path, pattern="<hex>")` — find
   the canonical SDK call sites (the
   `SteamAPI_RestartAppIfNecesary` string, the
   Denuvo `denuvo_atd` string, the VM `FF E0`
   dispatcher opcode).
4. `disassemble_function(path, function=<rva>,
   max_insns=500)` — lift the per-function disasm
   for the decompile input.
5. `decompile_function(path, function=<rva>)` —
   the pdc output (low fidelity; use re-llm-decompile
   for higher).

## Common pitfalls

- **The 400 MB memory wall** (Gap 19). `analyze_function`
  on a >400 MB binary is slow + memory-heavy;
  the per-section `search_bytes` workaround is
  the v2.9.0 canonical path. The v2.9.1+ fix is
  per-section `aa` mode.
- **`pdc` quality is low.** Don't use the
  `decompile_function` output as the final
  decompilation; use `re-llm-decompile` (Tier 1
  local LLM; Tier 1.5 agent-inline fallback per
  `re-decompile` SKILL.md) on the disasm
  output instead.
- **The `search_bytes` pattern is hex with
  spaces**, not ASCII. The Steamworks canonical
  pattern is `53 74 65 61 6d 41 50 49 5f 52 65 73
  74 61 72 74 41 70 70 49 66 4e 65 63 65 73 73
  61 72 79` (= "SteamAPI_RestartAppIfNecesary").

## Tooling pointers

- `re-rizin.search_bytes` is the canonical input
  to `re-llm-decompile.decompile_function`
  (the high-fidelity decompile path)
- The per-binary analysis is in
  `Output/v2.9.0-stress-test/steam-stub-
  unwrap/per-target/<target>/` (the per-target
  rationale + the canonical call-site RVA)
- The CFG output is DOT-format; render with
  Graphviz (`dot -Tpng file.dot -o file.png`)
  for the human-readable CFG

## References

- [rizin](https://rizin.re/) — the upstream
  project
- `tools/01-ghidra.md` — the Ghidra entry
  (the higher-fidelity decompiler alternative)
- `anti-analysis/02-vm-bytecode-interpreter.md` —
  the VM reverse-engineering pattern that uses
  `re-rizin` end-to-end
- `Output/v2.9.0-stress-test/vm-unpack/
  per-target/p3r/stage3-dispatcher-find.md` —
  the canonical VM dispatcher find using
  `search_bytes` for `FF E0` / `FF 20`
