---
name: re-report
description: Generate a final RE report. Use when the user says "write up the findings", "give me a report", "summarize the analysis", "I need a doc". Aggregates all prior tool outputs into a structured Markdown report (executive summary, IOCs, ATT&CK, decompiled snippets, mitigations).
---

# Final RE Report

## When to use

Use this skill at the **end** of an analysis session, after `re-static-triage`, `re-decompile`, `re-dynamic-analysis`, `re-symbolic-exec`, `re-malware-triage`, or `re-vuln-research` have produced their findings. The skill aggregates all that output into a single Markdown report.

Common prompts:

- "Write up the findings"
- "Generate a report"
- "I need to send this to a colleague"
- "Summarize the analysis"

## Workflow

**Step 1 — Gather context**

The skill expects the prior skill outputs to be available in the conversation. If they are not, ask the user to provide them, or re-run the relevant tool calls.

**Step 2 — Pick the report template**

There are three templates:

- **Binary triage** (after `re-static-triage`): sample info, structure, imports, strings, capabilities, indicators.
- **Malware analysis** (after `re-malware-triage`): capabilities, ATT&CK, MBC, IOCs, severity, recommendations.
- **Vulnerability** (after `re-vuln-research`): affected function, vulnerability type, reproduction, severity, mitigation.

If the user has done multiple analyses (e.g. triage + vuln research), use a combined template.

**Step 3 — Generate the report**

Use the template below. Fill in every section from the prior outputs. If a section is empty (e.g. no IOCs found), say so explicitly — don't skip it.

**Step 4 — Save the report**

Default output path: `REPORT-<sha256[:8]>-<YYYY-MM-DD>.md` in the current directory.

**Step 5 — Confirm**

Show the user the path and the executive summary. Ask if they want to add anything.

## Templates

### Template 1: Binary Triage

```markdown
# Binary Triage Report

**Sample:** <filename>
**SHA256:** <hash>
**MD5:** <hash>
**Imphash:** <hash> (PE only)
**Analysis date:** YYYY-MM-DD
**Analyst:** Claude Code (RE-AI v2 plugin)

## Executive summary
<1-2 paragraphs: what is this binary, what does it do, is it suspicious>

## File info
- Format: <PE / ELF / MachO / DEX>
- Architecture: <x86_64 / i386 / arm64 / arm>
- Type: <EXE / DLL / SYS / lib / kernel module>
- Size: <bytes>
- Entry point: <hex>
- Signed: <yes/no, by whom>

## Structure
- Sections: <n> total
- Notable: <list unusual sections, W^X, packed indicators>

## Imports (top by category)
- Network: <list>
- Process: <list>
- Persistence: <list>
- Crypto: <list>
- Anti-analysis: <list>

## Capabilities (capa)
- <capa findings>

## Strings of interest
- <URLs / IPs / paths / mutexes / registry keys>

## Indicator triage
| Finding | Severity | Notes |
|---|---|---|

## Recommendation
- <deeper analysis / dynamic / symbolic / malware-triage / report>
```

### Template 2: Malware Analysis

```markdown
# Malware Analysis Report

**Sample:** <filename>
**SHA256:** <hash>
**MD5:** <hash>
**Imphash:** <hash>
**Analysis date:** YYYY-MM-DD
**Analyst:** Claude Code (RE-AI v2 plugin)

## Executive summary
<1-2 paragraphs: what is this sample, what does it do, severity>

## Sample info
<as in Template 1>

## Capabilities (ATT&CK)
| Technique | Description |
|---|---|
| T1055 | Process Injection |
| ... | ... |

## Capabilities (MBC)
| Objective | Behavior |
|---|---|
| E0001 | Host Communication |
| ... | ... |

## Suspicious indicators
<table as in Template 1>

## IOCs
- Hashes: ...
- IPs: ...
- URLs: ...
- Mutexes: ...
- Registry keys: ...
- File paths: ...

## Severity
**HIGH** — <justification>

## Recommendations
- <block at network, add to threat intel, etc.>
```

### Template 3: Vulnerability

```markdown
# Vulnerability Report

**Target:** <filename> or library
**Affected version:** <if known>
**Analysis date:** YYYY-MM-DD
**Analyst:** Claude Code (RE-AI v2 plugin)

## Executive summary
<1 paragraph: what's the bug, severity, exploitability>

## Affected function
- Name: <function>
- Address: 0x...
- Decompiled code

## Vulnerability
- Type: <buffer overflow / UAF / format string / etc.>
- CWE: <CWE-XXX>
- Severity: <Critical / High / Medium / Low>
- CVSS: <score> (if calculable)

## Reproduction
1. <step 1>
2. <step 2>
3. Crash at: <RIP value>
4. Offset: <pattern offset>

## Exploitation
- NX: <enabled/disabled>
- PIE: <enabled/disabled>
- Stack canary: <enabled/disabled>
- CFG: <enabled/disabled>
- Exploitable: <yes / no / with primitives>

## Mitigation
- <fix suggestion>
- <long-term hardening>

## References
- <CVE / NVD / vendor advisory links>
```

## Output

The report file is saved as Markdown. To convert to other formats:

```bash
# To HTML
pandoc REPORT.md -o REPORT.html

# To PDF
pandoc REPORT.md -o REPORT.pdf

# To Word
pandoc REPORT.md -o REPORT.docx
```

## Multi-run stress-summary template (v2.9.0)

For stress-test runs that probe M subdirs × N targets
(e.g. the v2.9.0 stress test's 5 workstream subdirs
× 8 Input/ targets = 60 artifacts), the canonical
output shape is:

```
<run-root>/
├── override-scope.md           (parent; authorizes the subdirs)
├── stress-summary.md           (roll-up; per-workstream gap closure +
│                                per-gap disposition + v2.9.1+ priorities)
├── SHA256SUMS                  (union of all subdirs' SHA256SUMS)
├── <subdir-1>/                 (READ-ONLY probes)
│   ├── plan.md
│   ├── override-scope.md       (inherits + narrows the parent)
│   ├── SHA256SUMS
│   ├── coverage.md             (per-(tool, target) matrix)
│   ├── gap-analysis.md
│   ├── per-server/<server>.md
│   └── per-binary/<target>/<binary>.<tool>.json
├── <subdir-2>/                 (e.g. steam-stub-unwrap)
│   ├── plan.md
│   ├── override-scope.md
│   ├── summary.md
│   ├── per-target/<target>/
│   │   ├── <target>-classify.json
│   │   ├── rationale.md
│   │   └── side-file          (e.g. steam_appid.txt)
└── ...
```

The canonical reference is
`See the RE-AI output directory.`
+ the 5 subdirs' `summary.md` files. The
`stress-summary.md` has 4 tables: per-workstream
gap closure, per-gap disposition, v2.9.1+ work
priorities, 6/8 unsafe-repos recommendation.

## What this skill does NOT do

- It does not produce graphics (function call graphs, CFG diagrams). Use `re-rizin.get_cfg_graph` for that and embed as a mermaid block.
- It does not generate YARA rules. v2 candidate.
- It does not run on multiple samples at once. For bulk analysis, loop the triage skill and append reports.
