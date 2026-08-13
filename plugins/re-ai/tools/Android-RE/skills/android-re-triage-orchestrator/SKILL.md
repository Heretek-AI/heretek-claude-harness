---
name: android-re-triage-orchestrator
description: |
  Use when the user wants the full triage workflow: drop in an APK,
  run a MASVS-aligned multi-step analysis, and produce a report.
  This is the master skill that composes every other Android-RE
  skill and tool. Triggers: "triage this APK end-to-end", "give me
  a full security report on <path>", "run the orchestrator",
  "comprehensive triage", "MASVS audit of <app>". Do NOT use this
  for narrow, single-purpose tasks (use android-re-static-triage,
  -native-triage, -decompile, -dynamic-hook, etc. directly).
effect:
  filesystem:
    - read APK
    - write decoded workdir to /tmp/android-re/
    - write triage artifacts to ./.triage/
  network: depends on dynamic / MITM steps (only if user opts in)
  device:
    - dynamic steps require a rooted device with frida-server
    - all device operations require explicit confirm
requires:
  mcp:
    - android-re-static
    - android-re-native
    - android-re-dynamic
    - android-re-triage
---

# End-to-end triage orchestrator

Drop in an APK → get a MASVS-aligned report. Composes the
`android-re-triage` MCP server with the static / native / dynamic
servers, runs a multi-step plan, correlates findings across
sources, and produces the final markdown / SARIF / JSON report.

## When to use

The user wants the full picture, not a single question answered.
Typical triggers:

- "Run a full triage on `app.apk`."
- "Generate a MASVS audit."
- "What does this app do, and is it secure?"

If the user has a narrow question, route to the focused skill
(static-triage, native-triage, dynamic-hook, etc.) instead.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `apk_path` | yes | Path to the `.apk` |
| `goals` | no | One of: `masvs` (default), `full`, `static_only`, `dynamic_only`, `native_only` |
| `device_serial` | no | If running dynamic steps, the Frida device id |
| `mitm` | no | If true, set up MITM during dynamic steps |

## Workflow

1. **Open the static project.**
   `mcp__android-re-static__open_project` with `apk_path`.
   Capture `project_id` and the SHA-256.

2. **Start the triage.**
   `mcp__android-re-triage__start_triage` with `apk_path`,
   `apk_sha256`, and `goals`. Returns `triage_id` and a multi-step
   plan.

3. **Run the static plan.**
   Execute every tool listed in the static steps. For each
   interesting result, call
   `mcp__android-re-triage__add_finding` to record it. Use the
   `mcp__android-re-static__get_masvs_coverage` output to
   populate `masvs_control`.

4. **Run the native plan (if applicable).**
   `mcp__android-re-native__list_binaries` →
   `parse_binary` → `get_security_features` for each lib. Add
   findings for missing NX/RELRO/PIE/canary, suspicious packer
   matches, weak crypto imports.

5. **Run the dynamic plan (if a device is available).**
   - `mcp__android-re-dynamic__frida_spawn` (or
     `frida_attach`) to start a session.
   - `frida_load_script` with a focused hook (e.g. log the
     login flow, trace OkHttp calls).
   - `build_session_report` to retrieve the runtime data.
   - `add_finding` for each runtime observation.

6. **MITM (if requested and user has a proxy).**
   - `setup_mitm` with the proxy host/port.
   - Tell the user to use the app; watch the proxy.

7. **Correlate.**
   `mcp__android-re-triage__correlate_findings` to link
   static claims with dynamic observations.

8. **Propose tests (optional).**
   `mcp__android-re-triage__propose_dynamic_tests` to suggest
   the next set of Frida hooks based on the static findings.

9. **Finalize.**
   `mcp__android-re-triage__finalize_triage` with `format=markdown`
   (or `sarif` / `json` / `html`). Returns the report path.

10. **Hand off.**
    Show the user the report path and a one-paragraph summary
    of the top 3 findings.

## Output

A markdown report at `~/.triage/triage-<id>.md` (or as
`./.triage/triage-<id>.md`) plus a JSON / SARIF copy on request.

## Examples

### Example 1: full MASVS audit

> User: Run a full MASVS audit on `app.apk`.

Steps: 1-10 above with `goals=["masvs"]`. Static + MASVS coverage
+ correlate + finalize.

### Example 2: dynamic-only with MITM

> User: Set up MITM and observe the network traffic from
> `com.example` for the next 60 seconds.

Steps: spawn + MITM setup + a focused OkHttp/URLConnection hook;
finalize as `dynamic_only`.

## Background reading (peer MCP)

While running this skill, the agent can consult the RE-Library peer
MCP for generic patterns. Triggers: "what does the literature say
about <observed pattern>". The peer is read-only; it never
overwrites a verified observation on the target.

- `mcp__re-library__list_categories()` — enumerate the 8 categories.
- `mcp__re-library__search_re(query="<category> <pattern>", max_results=3)` — up to 3 hits with snippet + score.
- `mcp__re-library__get_entry(slug="<category>/<NN>-<slug>")` — full body of one entry.

Pair with the cross-source findings; cite the entry in
`mcp__android-re-triage__add_finding`'s `related` field.

The peer is registered in `.mcp.json`; install it once with
`just install-re-library` (opt-in).

## Output convention

The orchestrator writes to:

```
Output/<apk-basename>-<short-sha>/<triage_id>/triage-<id>.md
Output/<apk-basename>-<short-sha>/<triage_id>/triage-<id>.json
Output/<apk-basename>-<short-sha>/<triage_id>/triage-<id>.sarif
```

Pass `output_dir` to `start_triage` to override the per-triage
subdir; pass `output_path` to `finalize_triage` to override the report
file. For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md) and
`android_re_core.paths.output_dir_for`.

The first call opens a static project, so pass `max_size=<apk_bytes * 2>`
on `open_project` for any APK over the 500 MB default cap.

## Notes

- The orchestrator's state lives in SQLite at
  `~/.android-re/triage.db`. Each triage can be resumed.
- For very large APKs (> 100 MB), the static step takes
  noticeably longer. Tell the user the expected wait.
- Dynamic steps require the user to plug in / start an
  emulator. If no device is available, the orchestrator falls
  back to static-only and notes the gap in the report.
- The final report is the only deliverable that lands on the
  host filesystem; everything else is in SQLite / on the device.
- **Size limit.** The MCP `open_project` tool caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
