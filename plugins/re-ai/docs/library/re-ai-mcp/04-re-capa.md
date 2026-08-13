---
title: "re-capa (RE-AI MCP server)"
category: "re-ai-mcp"
platforms: ["linux", "windows", "macos"]
difficulty: "intermediate"
tags: ["capa", "flare-capa", "capability-detection", "att&ck", "mbc", "rule-engine"]
summary: "MCP server wrapping Mandiant's capa (the canonical capability detector for PE / ELF / shellcode / .NET binaries). 4 tools (`check_capa`, `detect_capabilities`, `extract_mbc`, `find_interesting`) that surface ATT&CK + MBC mappings from the 1055-rule `data/capa-rules/` ruleset. The canonical second-pass capability detector; sits between the static-triage `categorize_strings` and the per-function `re-llm-decompile`."
updated: "2026-06-07"
related: ["re-ai-mcp/01-re-ai-plugin", "re-ai-mcp/03-re-lief", "re-ai-mcp/05-re-triton", "anti-analysis/05-launcher-activation-fingerprinting"]
---

## Summary

`re-capa` is the RE-AI MCP server that wraps
[Mandiant's capa](https://github.com/mandiant/capa) —
the canonical capability detector for compiled
binaries. The server exposes 4 tools that surface
ATT&CK (T-code) and Malware Behavior Catalog (MBC)
mappings from the 1055-rule `data/capa-rules/`
ruleset (cloned by `install.sh` at install time).

## Why this matters

`re-capa` is the **canonical second-pass capability
detector** in the RE-AI plugin. The static-triage
flow goes: `re-lief.parse_binary` + `get_sections`
(first-pass structural) → `re-lief.categorize_strings`
(string-bucket view) → **`re-capa.detect_capabilities`**
(capability rules) → `re-llm-decompile.decompile_function`
(per-function decompile).

The v2.8.1 cycle added the `check_capa_rules` probe
in `scripts/check_deps.py` (line 158+); the probe
confirms the `data/capa-rules/` tree cloned by
install.sh is present and non-empty. The
v2.8.1 cycle also closed the "re-capa reports
bundled rules only" gap by ensuring the ruleset
is current.

## Mechanics

The server requires `flare-capa` (`pip install
flare-capa`). The `check_capa()` tool reports
the installed version + the rules path.

The 4 tools:

| Tool | Purpose |
|---|---|
| `check_capa` | Health check (capa version + rules path) |
| `detect_capabilities` | The full capa run: returns ATT&CK + MBC + rule names + matched strings + per-rule confidence |
| `extract_mbc` | The MBC-only mapping (lightweight; for when ATT&CK is too noisy) |
| `find_interesting` | Filter capa's output to high-confidence / unique matches (the analyst's "what should I look at first" view) |

The `detect_capabilities` output shape:

```json
{
  "rules": [
    {
      "rule": "create remote thread in another process",
      "namespace": "host-interaction/process/inject",
      "tags": ["attack.t1055"],
      "meta": {"attack": ["T1055"], "mbc": ["B0021"]},
      "strings": ["CreateRemoteThread", "WriteProcessMemory"],
      "rule_length": 4
    },
    ...
  ],
  "rule_count": 12,
  "matches_count": 47
}
```

The `min_score` parameter on `find_interesting`
defaults to 3 (rules per namespace); a higher
threshold returns the high-confidence subset.

## Approach

Typical second-pass capability run:

1. `check_capa()` — confirm capa is installed +
   the ruleset is at the expected path.
2. `detect_capabilities(path)` — the full run;
   expect a few hundred rules + several thousand
   matches on a typical AAA game binary.
3. `find_interesting(path, min_score=5)` — the
   high-confidence subset; the analyst's "what
   should I look at first" view.
4. `extract_mbc(path)` — the MBC-only mapping
   (handy when ATT&CK is too noisy).

## Common pitfalls

- **The ruleset must be current.** The
  `check_capa_rules` probe in `scripts/check_deps.py`
  is the canonical gate; the v2.8.1 cycle
  closed the "re-capa reports bundled rules
  only" gap.
- **Capa is best on PE/ELF/shellcode/.NET.**
  The Android DEX coverage is partial; use
  `re-apktool` + `re-lief` for the static
  analysis + `re-android-dynamic` for the
  runtime hooks.
- **Encrypted bytecode body is opaque.**
  Capa runs on the .text / .data / .rdata
  sections; the encrypted-VM bytecode
  interpreter's encrypted body is unreadable
  at the capa level (use `re-vm-reverse` for
  the dynamic per-handler analysis).

## Tooling pointers

- The capa ruleset is the input to the
  `re-yara-author` skill (the v2.8.1 cycle
  added the yara-author integration; the
  author skill extracts distinctive features
  + ranks candidates + emits the rule)
- The MBC mapping is the input to
  `re-malware-triage` (the MBC bucket is the
  malware-behavior view; the ATT&CK mapping
  is the threat-intel view)

## References

- [Mandiant capa](https://github.com/mandiant/capa) —
  the upstream project
- [ATT&CK](https://attack.mitre.org/) — the
  ATT&CK T-code catalog
- [MBC](https://github.com/MBCProject/mbc-markdown) —
  the Malware Behavior Catalog
- `re-ai-mcp/03-re-lief.md` — the canonical
  first-pass binary parser
- `re-ai-mcp/05-re-triton.md` — the
  symbolic-execution bridge
- `Output/v2.9.0-stress-test/tool-stress/
  coverage.md` — the v2.9.0 stay-closed
  verification on the 8 Input/ targets
