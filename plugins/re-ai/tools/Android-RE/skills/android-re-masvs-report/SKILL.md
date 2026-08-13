---
name: android-re-masvs-report
description: |
  Use when the user asks for a MASVS-aligned report, an OWASP MASTG
  audit, or a formal "is this app secure" assessment. Triggers: "MASVS
  report", "MASTG audit", "OWASP compliance check", "security audit of
  <path>". Phase 1 ships a stub; the real implementation lands in
  Phase 4 with the android-re-triage orchestrator MCP server.
effect:
  filesystem: read APK in current directory or absolute path
  network: none
  device: none
requires:
  mcp: android-re-static
status: phase1-stub
---

# MASVS-aligned security report

**Phase 1 stub.** The Phase 1 implementation produces a lightweight
report that maps the static triage findings to the relevant MASVS v2
control groups. A full MASVS audit requires the dynamic, native, and
orchestrator MCP servers and lands in Phase 4.

## When to use

The user wants a security assessment, not just an overview. Typical
triggers:

- "Give me a MASVS report on this APK."
- "Is this app OWASP-compliant?"
- "Run an OWASP MASTG audit on `~/Downloads/app.apk`."

If the user has not installed Phase 4 components yet, fall back to a
Phase 1 report and clearly state its scope.

## Phase 1 scope

This stub produces a markdown table mapping each static finding to the
MASVS v2 control group it touches, plus a "Phase 4 will cover" section
listing the controls that require dynamic analysis.

### What Phase 1 covers

| MASVS group       | Phase 1 coverage                                                |
|-------------------|------------------------------------------------------------------|
| MASVS-CODE        | self-signed cert, missing v2/v3, debuggable in release            |
| MASVS-PLATFORM    | exported components, intent filters, targetSdkVersion checks      |
| MASVS-NETWORK     | `usesCleartextTraffic`, missing `networkSecurityConfig`            |
| MASVS-STORAGE     | (Phase 2: source review for hard-coded keys)                      |
| MASVS-AUTH        | (Phase 2: decompile + dynamic)                                    |
| MASVS-CRYPTO      | (Phase 2: source review)                                          |
| MASVS-RESILIENCE  | (Phase 3: dynamic root/tamper detection)                          |
| MASVS-PRIVACY     | (Phase 2: data-flow review)                                       |

## Workflow (Phase 1)

1. **Run `android-re-static-triage` first.** The triage output feeds
   this skill.

2. **Map findings to MASVS controls.** Use the table in
   [`references/masvs-v2.md`](references/masvs-v2.md) to assign each
   finding to one or more MASVS controls.

3. **Emit the report.** Use the template in
   [`templates/report.md.j2`](templates/report.md.j2).

4. **Note the gaps.** Add a "What Phase 4 will add" section that lists
   the control groups the user should re-audit when dynamic + native +
   triage orchestrator are available.

## Output

```markdown
# MASVS Security Report — <package>

## Summary
- **Status**: Phase 1 (static only)
- **Findings**: <n> total
- **Highest severity**: <severity>

## MASVS Coverage

| MASVS Control   | Status   | Evidence                              |
|-----------------|----------|----------------------------------------|
| MASVS-CODE-2    | FAIL     | debuggable=true on release build       |
| MASVS-PLATFORM-1| REVIEW   | 3 exported activities, no permissions   |
| MASVS-NETWORK-1 | FAIL     | usesCleartextTraffic="true"             |
| ...             |          |                                        |

## Findings

### F-001: <title>
- **MASVS**: <control id>
- **Severity**: <severity>
- **Evidence**: <code reference, manifest snippet, etc.>
- **Remediation**: <one-paragraph fix>

## What Phase 4 will add

- MASVS-AUTH-* — dynamic authentication flow analysis
- MASVS-RESILIENCE-* — runtime root/hook/tamper detection
- MASVS-STORAGE-* — encrypted shared prefs, key store usage review
- MASVS-CRYPTO-* — algorithm choice and key strength review
```

## Examples

### Example 1: static-only MASVS

> User: Run a MASVS audit on this APK.

Steps:

1. Run `android-re-static-triage` (or invoke it as a sub-skill).
2. Map findings to MASVS controls.
3. Emit the Phase 1 report.
4. Tell the user: "Phase 1 covers static findings only. Re-run after
   Phase 4 ships for full dynamic coverage."

## Background reading (peer MCP)

While running this skill, the agent can consult the RE-Library peer
MCP for generic patterns. Triggers: "what does the literature say
about <observed pattern>". The peer is read-only; it never
overwrites a verified observation on the target.

- `mcp__re-library__list_categories()` — enumerate the 8 categories.
- `mcp__re-library__search_re(query="<category> <pattern>", max_results=3)` — up to 3 hits with snippet + score.
- `mcp__re-library__get_entry(slug="<category>/<NN>-<slug>")` — full body of one entry.

Pair with the MASVS control being mapped; cite the entry in the
report's `References` section. The `anti-analysis` category is the
right lookup for MASVS-RESILIENCE-* work; the `network` /
`android` categories overlap with MASVS-NETWORK-* and
MASVS-PLATFORM-*.

The peer is registered in `.mcp.json`; install it once with
`just install-re-library` (opt-in).

## Output convention

`get_masvs_coverage` and `build_sarif_report` write a JSON / SARIF copy
to:

```
Output/<apk-basename>-<short-sha>/masvs/coverage.json
Output/<apk-basename>-<short-sha>/masvs/report.sarif
```

(For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).) Override
with the `output_path` parameter on each tool.

## Notes

- Do not falsely claim full MASVS coverage in Phase 1.
- The output is intentionally honest about its scope.
- Severity ratings follow the MASTG convention (Critical / High /
  Medium / Low / Info).
- **Size limit.** The MCP `open_project` tool (used by the
  `android-re-static-triage` sub-skill) caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
