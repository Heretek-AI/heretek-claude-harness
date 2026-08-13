---
title: "RE-AI Plugin"
category: "re-ai-mcp"
platforms: ["linux", "windows", "macos"]
difficulty: "intermediate"
tags: ["claude-code", "mcp", "plugin", "skill-orchestration", "reverse-engineering"]
summary: "Claude Code plugin that ships 28 skills + 31 MCP servers for reverse engineering and decompilation. The plugin is the orchestration layer; the skills are prompt-instruction markdown; the MCP servers are JSON-RPC tool providers that wrap real RE backends (LIEF, rizin, capa, Triton, GDB, VTIL, angr, Speakeasy, Frida, mitmproxy, kaitai, winedbg, and the .NET / IL2CPP metadata readers)."
updated: "2026-06-07"
related: ["tools/01-ghidra", "tools/02-ida", "tools/03-binary-ninja", "native/01-elf-format", "anti-analysis/02-vm-bytecode-interpreter"]
---

## Summary

The RE-AI plugin turns Claude Code into a reverse-engineering
workstation. It does not replace Claude — it gives Claude 28
**skills** (prompt-instruction markdown that auto-activates on
user prompts) and 31 **MCP servers** (standalone JSON-RPC tool
providers that wrap real RE backends).

## Why this matters

Most reverse-engineering sessions need a 5-20 tool chain
(headers → strings → section table → disasm → decompile →
symbol trace → leak scan → report). The RE-AI plugin's
contribution is the **skill layer** — the 28 skills encode
the workflow, the MCP servers provide the tool primitives,
and Claude Code is the agent that decides which skill to
activate for which user prompt. The skill's `description:`
frontmatter field is the activation prompt; Claude Code uses
it to decide whether to apply the skill.

The plugin is **vendor-neutral** at the data layer
(`data/drm-indicators.yaml` describes *categories* of
anti-tamper, not specific commercial products). The
NEEDLES test (`tests/test_no_vendor_leakage.py`) enforces
the vendor neutrality — 49 parametrized tests scan every
shipped source file for vendor-name substrings.

## Mechanics

The plugin's three layers:

```
Claude Code (the agent — owns the conversation)
    ├── Skills (28 SKILL.md files in skills/)
    │   └── Each skill: YAML frontmatter (name, description)
    │       + a Markdown body (when to use, workflow,
    │       output format, what NOT to do, references)
    │
    └── MCP servers (31 processes in servers/)
        └── Each server: a Python module exposing
            @mcp.tool()-decorated functions; the server
            runs as a stdio subprocess of Claude Code
            and returns JSON-serializable dicts
```

When the user asks "is this DRM-protected", Claude
activates `re-drm-fingerprint`, which calls the
`re-lief` + `re-anti-analysis` + `re-rizin` MCP
servers. Each tool call returns a structured dict;
the skill's SKILL.md instructs Claude how to
synthesize the dicts into a confidence score.

The plugin also ships:

- `data/drm-indicators.yaml` — the central
  anti-tamper catalog (anti-debug + HWID + section +
  pattern indicators). The B3 catalog entry
  `managed launcher store-gate` is the canonical
  category label for the EA App / Origin
  entitlement on Mono launchers.
- `ANTI-TAMPER-TAXONOMY.md` — the inference chain
  for the catalog (Pattern A = Unity-IL2CPP
  encrypted-VM bytecode interpreter; Pattern A-DW
  = the Denuvo-wrapped UE5 variant; Pattern B =
  hardware-fingerprinting routine + anti-debug).
- `tests/test_no_vendor_leakage.py` — the 49-NEEDLE
  parametrized test that enforces the vendor-
  neutrality contract.
- `Output/v2.9.0-stress-test/` — the v2.9.0
  stress-test artifacts (the empirical evidence
  base for the v2.9.0 cycle's closed gaps).

## Approach

To use the plugin:

1. **Install** via `install.sh` (or `install.bat` on
   Windows). The script publishes the v2.8.1 `re-dotnet-cli`
   + the v2.9.0 `patcher-cli` + the optional vtil-cli
   helper, and clones the `data/capa-rules/` ruleset.
2. **Verify** via `bash verify.sh` (or `verify.bat`).
   Reports 31 servers / 28 skills and a 49/49
   vendor-leakage pass.
3. **Start Claude Code** with the plugin loaded
   (Claude Code reads `.claude-plugin/plugin.json`
   for the metadata; the `.mcp.json` file lists
   the 31 servers).
4. **Ask Claude** about a binary. The plugin's
   skills auto-activate based on the prompt;
   Claude invokes the MCP tools as needed.

## Common pitfalls

- **Stale MCP server caches.** The plugin's MCP
  servers run in subprocess; if you change a
  server's source, restart Claude Code to pick
  up the new module.
- **Skill activation requires an active `description:`.**
  The plugin enforces a 40-character minimum and
  a 200-character cap on `description:` (the
  v2.9.0 trim pass); the body of the SKILL.md
  still has the full details.
- **Vendor-leakage test failure is a hard
  fail.** `tests/test_no_vendor_leakage.py` has
  49 parametrized tests; any one failure means
  a vendor-name substring leaked into shipped
  source. The test is the gate; passing the test
  is required for merge.
- **The DRM catalog is intentional.** The B3
  entry `managed launcher store-gate` is the
  renamed, vendor-neutral form of the EA App /
  Origin entitlement. The vendor-name
  re-attribution is the user's job, not the
  plugin's.

## Tooling pointers

The 6 most-used MCP servers are documented as
per-server entries in this category:

- `re-ai-mcp/02-re-rizin.md` — the rizin / rz-bin
  CLI wrapper (the canonical disasm + string
  extraction server)
- `re-ai-mcp/03-re-lief.md` — the LIEF library
  wrapper (the canonical cross-format binary
  parser; 19 tools after the v2.9.0
  `get_debug_directory` addition)
- `re-ai-mcp/04-re-capa.md` — the capa
  (Mandiant) wrapper (the canonical capability
  detector)
- `re-ai-mcp/05-re-triton.md` — the Triton
  symbolic-execution library wrapper
  (the canonical solver for "what input
  reaches branch X")
- `re-ai-mcp/06-re-winedbg.md` — the Wine +
  winedbg + gdb wrapper (the canonical
  Windows .exe debugging surface from
  Linux/macOS)
- `re-ai-mcp/07-re-dotnet.md` — the .NET 10
  CLI + ilspycmd wrapper (the canonical C#
  class graph + decompile server; the v2.8.1
  C8 backend for the Mono.Cecil IL patching
  is in `servers/re-dotnet-patch/`)

The 28 skills (listed for the catalog; cross-
referenced from per-server entries) are:

`re-android-dynamic`, `re-anti-analysis-scan`,
`re-api-reverse`, `re-archive-author`,
`re-decompile`, `re-dotnet-analysis`,
`re-drm-fingerprint`, `re-dynamic-analysis`,
`re-eos-bypass`, `re-encrypted-vm-tamper`,
`re-format-decode`, `re-fuzz-replay`,
`re-game-ac-bypass`, `re-hypervisor-detect`,
`re-il2cpp-decompile`, `re-il2cpp-static-triage`,
`re-leak-scan`, `re-malware-triage`,
`re-mba-deobfuscate`, `re-origin-stub-drop`,
`re-pcap-correlate`, `re-report`,
`re-static-triage`, `re-steam-stub-unwrap`,
`re-symbolic-exec`, `re-telemetry-extract`,
`re-vm-reverse`, `re-vuln-research`,
`re-yara-author`.

## References

- `tools/01-ghidra.md` — the per-tool entry
  template (single tool per entry; this
  category's per-server entries follow the
  same shape)
- `tools/02-ida.md` — the IDA Pro entry
  (the canonical commercial RE IDE)
- `tools/03-binary-ninja.md` — the Binary
  Ninja entry
- `anti-analysis/02-vm-bytecode-interpreter.md` —
  the Unity-IL2CPP Pattern A entry (the
  encrypted-VM bytecode interpreter pattern
  that the plugin's re-vm-reverse + re-encrypted-
  vm-tamper skills characterize)
- `ANTI-TAMPER-TAXONOMY.md` in the RE-AI repo —
  Pattern A-DW (the Denuvo-wrapped variant;
  added v2.9.0)
- `data/drm-indicators.yaml::pattern_indicators
  .mappings` in the RE-AI repo — the catalog
  the skills read
- GitHub: <https://github.com/Heretek-AI/RE-AI>
- v2.9.0 stress test: <https://github.com/Heretek-RE/RE-AI/tree/main/Output/v2.9.0-stress-test>
