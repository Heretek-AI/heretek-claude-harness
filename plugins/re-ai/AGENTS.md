# RE-AI Agent Guide

This document describes how AI agents compose the 31 per-MCP servers into workflows using the 29 skill definitions.

## Architecture

RE-AI is an **agent-space**: it doesn't run servers itself. It orchestrates per-MCP repos that are cloned at pinned versions. An agent interacting with RE-AI sees:

1. **31 MCP servers** registered in `.mcp.json` — each is a standalone tool surface
2. **29 skills** in `skills/` — each is a multi-step workflow that calls multiple servers
3. **5 catalogs** in `data/` — shared reference data consumed by servers and skills

## The per-MCP server pattern

Each server follows the same pattern:

```
re-<name>/
  pyproject.toml          # declares mcp[cli] + tool-specific deps
  src/re_<name>/
    __init__.py
    __main__.py           # entry: from server import main; main()
    server.py             # FastMCP app with @mcp.tool() functions
  README.md
  LICENSE
```

Server registration in `.mcp.json`:
```json
{
  "re-<name>": {
    "command": "uv",
    "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}/servers/re-<name>", "run", "re-<name>"]
  }
}
```

## Skill structure

Each skill is a directory under `skills/` containing a `SKILL.md` with YAML frontmatter:

```yaml
---
name: re-static-triage
description: Triage a fresh binary against the technique catalog
tools: [re-catalog-match, re-triage, re-rizin, re-lief]
effect_envelope: read-only
test_cases:
  - input: /path/to/sample.exe
    expected: catalog match count > 0
---
```

### Skill categories

| Category | Skills | What they do |
|---|---|---|
| **Triage** | re-static-triage, re-dynamic-analysis, re-malware-triage, re-il2cpp-static-triage | Fast assessment of unknown binaries |
| **Analysis** | re-decompile, re-dotnet-analysis, re-vm-reverse, re-vuln-research, re-symbolic-exec | Deep reverse engineering |
| **Data** | re-format-decode, re-leak-scan, re-telemetry-extract, re-pcap-correlate | Data extraction and correlation |
| **Catalog** | re-yara-author, re-archive-author, re-report, re-drm-fingerprint | Tool authorship and reporting |
| **Bypass** | re-game-ac-bypass, re-eos-bypass, re-steam-stub-unwrap, re-origin-stub-drop | Protection analysis (detection, not circumvention) |

## Catalog data

The `data/` catalogs are shared across servers:

- `drm-indicators.yaml` — DRM / anti-tamper indicator mappings (pattern families, section shapes, string signatures)
- `anti-analysis-catalog.json` — anti-debug / anti-VM / anti-sandbox technique catalog
- `compiler-fingerprints.json` — compiler identification from binary heuristics
- `apkid-signatures.json` — APKiD packer / compiler signatures
- `ollvm-pass-catalog.json` — OLLVM obfuscation pass identification

## Composing workflows

A typical triage workflow:

1. Agent calls `re-triage.triage_target(path)` — runs RE-AI's static analysis primitives end-to-end
2. Agent calls `re-catalog-match.run_matcher(triage_json)` — matches triage against the catalog
3. Agent calls `re-report.write_report(matches, triage)` — generates a structured report

A typical decompile workflow:

1. Agent calls `re-rizin.disassemble_binary(path)` — gets disassembly
2. Agent calls `re-lief.parse_binary(path)` — gets PE/ELF structure
3. Agent calls `re-llm-decompile.decompile_function(address)` — LLM-assisted decompilation

## Version management

Servers are pinned in `versions.lock`. To update:

1. Edit `versions.lock`: bump the tag for the server you want
2. Run `./install.sh --update` to re-clone at the new tag
3. Run integration tests: `pytest tests/integration/`
4. If tests pass, the update is safe
