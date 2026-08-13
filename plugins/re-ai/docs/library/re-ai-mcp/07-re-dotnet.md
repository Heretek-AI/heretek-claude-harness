---
title: "re-dotnet (RE-AI MCP server)"
category: "re-ai-mcp"
platforms: ["linux", "windows", "macos"]
difficulty: "intermediate"
tags: [".net", "mono", "ilspycmd", "system-reflection-metadata", "il-decompile", "il-patching", "managed-launcher"]
summary: "MCP server wrapping a .NET 10 CLI (System.Reflection.Metadata) + ilspycmd for C# decompilation. 11 tools covering parse_assembly, get_methods, get_fields, get_properties, get_events, list_strings (field-default + ldstr modes), classify_dotnet_protection, detect_managed_anti_debug, decompile_type/method, run_il_simplification, get_entry_point. The canonical .NET-style launcher / mod loader server; pairs with the v2.8.1 C8 `re-dotnet-patch` backend for IL patching."
updated: "2026-06-07"
related: ["re-ai-mcp/01-re-ai-plugin", "re-ai-mcp/06-re-winedbg", "re-ai-mcp/03-re-lief", "anti-analysis/05-launcher-activation-fingerprinting"]
---

## Summary

`re-dotnet` is the RE-AI MCP server that wraps
a .NET 10 CLI built on `System.Reflection.Metadata`
+ `ilspycmd` for C# decompilation. The server
exposes 11 tools covering assembly parsing,
typed method/field discovery, string-table
extraction (field-default + ldstr modes),
protection classification, anti-debug detection,
and per-type / per-method decompilation.

## Why this matters

`re-dotnet` is the **canonical .NET-style
launcher / mod loader server** in the RE-AI
plugin. The CD `pers.exe` (the 3.9 MB Mono
launcher for Crimson Desert) is the canonical
target; the v2.9.0 stress test confirmed the
server's `parse_assembly` + `get_methods` +
`get_fields` tools correctly handle the
Mono-variant PE.

The v2.8.1 cycle closed:

- **A10** — `classify_dotnet_protection` now
  detects Mono PE files via a heuristic check
  (`mscoree.dll` import, `_CorExeMain` export,
  `BSJB` signature). The CD `pers.exe` analysis
  in the v2.8.0 slimmer confirmed the fix.
- **A11** — `list_strings(mode="ldstr")` walks
  every method body's IL stream and captures
  every `ldstr` operand (opcode 0x72 + 4-byte
  user-string token). Replaces the v2.8.0
  stub that returned only the field-default
  strings.
- **A12** — `get_methods` + `get_fields` MCP
  tools added (the Mono path; the v2.8.0
  cycle's tooling only handled the IL2CPP
  path).

The companion server `re-dotnet-patch` (the
v2.8.1 C8 deliverable) wraps Mono.Cecil 0.11.5
for IL patching (`nop_method`,
`replace_method_body`, `replace_string_ldstr`,
`patch_assembly`). The CD-3 round-trip
empirically validated the C8 backend.

## Mechanics

The server requires .NET 10 SDK + the vendored
`re-dotnet-cli` binary at
`servers/re-dotnet/bin/re-dotnet-cli`. The
`check_dotnet()` tool reports the .NET 10
runtime version + the ilspycmd version + the
CLI binary path.

The 11 tools:

| Tool | Purpose |
|---|---|
| `check_dotnet` | Health check (.NET runtime + ilspycmd + CLI path) |
| `parse_assembly` | TypeDef table walk (assembly name + version + target framework + entry point + per-type summary) |
| `get_methods` | Methods of one type (per Mono / .NET assembly) |
| `get_fields` | Fields of one type |
| `classify_dotnet_protection` | Protection class (type-name-renaming / control-flow-flattening / string-encryption / etc.) + the v2.8.1 Mono branch (`is_mono: true` + remediation hint) |
| `detect_managed_anti_debug` | IL method-body scan for managed anti-debug primitives (`IsDebuggerPresent`, `Debugger.IsAttached`, `Debug.Assert`, `Debugger.Break`, and the indirect-check set) |
| `list_strings` | String extraction; two modes: `field-default` (default) or `ldstr` (v2.8.1 added) |
| `decompile_type` | Decompile a single class to C# via ilspycmd |
| `decompile_method` | Decompile a single method to C# via ilspycmd |
| `run_il_simplification` | Run a d810-ng-style IL simplification pass set on one method (constant_fold / dead_branch_elim / opaque_predicate_eval / string_decrypt) |
| `get_entry_point` | The managed entry point (`<Module>::.cctor` or `Main`) |

## Approach

Typical managed-launcher walk:

1. `parse_assembly(path)` — confirm a Mono /
   .NET PE; the `entry_point` field is the
   managed entry.
2. `get_methods(path, fqn="<MainWindow fqn>")` —
   discover the launcher class's methods; look
   for `GetStoreRegistryKey` +
   `GetLauncherType` (the B3 catalog entry's
   signature).
3. `get_fields(path, fqn="<MainWindow fqn>")` —
   discover the launcher class's fields; look
   for `_isSteam` / `_isStore` / `_isLauncher`
   (the B3 catalog entry's signature).
4. `classify_dotnet_protection(path)` — the
   v2.8.1 Mono branch returns `is_mono: true`
   + the remediation hint pointing at
   `parse_assembly` / `decompile_type`.
5. `decompile_type(path, fqn=<MainWindow fqn>)` —
   the ilspycmd output.
6. For IL patching: `re-dotnet-patch.nop_method(
   path=<copy>, method_fqn="<MainWindow>::
   GetStoreRegistryKey", dst=<output>,
   confirm_legal=...)` — the C8 backend.

## Common pitfalls

- **The Mono launcher's `pers.exe` may be a
  separate sibling DLL.** The CD install
  tree has `CrimsonDesert.exe` (the game)
  + `pers.exe` (the Mono launcher); the gate
  is in `pers.exe`, not the game binary. The
  C8 round-trip proves the type-graph
  preservation regardless of the target.
- **The C8 backend writes to `<dst>`**; the
  source is never modified. The round-trip
  returns the pre/post SHA-256 + the
  type/method/field/property/event counts.
- **The Mono branch on `classify_dotnet_protection`**
  returns a remediation hint when the strict
  CLI-header walker returns None but the
  binary IS Mono (per the v2.8.1 A10 fix).

## Tooling pointers

- The `re-dotnet-patch` companion server is
  the IL-patch backend (the v2.8.1 C8
  deliverable)
- The `run_il_simplification` tool is the
  d810-ng pass set (constant_fold /
  dead_branch_elim / opaque_predicate_eval
  / string_decrypt)
- The `decompile_type` output is the input
  to `re-llm-decompile.decompile_function`
  (for the high-fidelity decompile pass)

## References

- [ilspycmd](https://github.com/icsharpcode/
  ILSpy) — the ILSpy CLI for C# decompilation
- [Mono.Cecil](https://github.com/jbevain/
  cecil) — the IL-patching library that
  powers `re-dotnet-patch`
- `Output/v2.9.0-r04-slim/cd/cd-3-report.md` —
  the v2.8.1 C8 round-trip proof (the
  CD-3 closure; the canonical empirical
  evidence for the C8 backend)
- `Output/v2.9.0-stress-test/origin-stub-
  drop/per-target/lir/entitlement-classify
  .json` — the LIR per-target Mono launcher
  walk (uses the same v2.8.1 C8 backend)
- `Output/v2.9.0-stress-test/eos-stub-
  drop/per-target/<football-manager-target>/
  rationale.md` — the FM26 per-target
  entitlement walk
