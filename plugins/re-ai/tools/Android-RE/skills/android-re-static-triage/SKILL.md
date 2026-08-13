---
name: android-re-static-triage
description: |
  Use when the user wants to triage an APK, perform a 5-minute static
  overview, or get a high-level "what does this app do" summary without
  running it. Triggers: "triage this APK", "what does this app do",
  "static overview of <path>", "analyze <path>.apk", "give me a quick
  security summary of this APK". Do NOT use for dynamic analysis, Frida
  hooking, native binary inspection, or repackaging — those have their
  own skills.
effect:
  filesystem: read APK in current directory or absolute path
  network: none
  device: none
requires:
  mcp: android-re-static
---

# Static Triage of an Android APK

A 5-minute static overview of an APK. Produces a structured summary
covering package metadata, components, permissions, signing, and a list
of notable findings. No device, no Frida, no runtime analysis.

## When to use

The user has an APK and wants to know what it is, what it asks for, and
whether anything looks unusual. Use this as the **first step** in any
analysis workflow — even if the user later wants dynamic hooking, the
static triage findings inform which methods are worth hooking.

If the user wants dynamic analysis, jump to `android-re-dynamic-hook` or
`android-re-triage-orchestrator` instead.

## Inputs

| Field         | Required | Description                                                |
|---------------|----------|------------------------------------------------------------|
| `apk_path`    | yes      | Absolute or CWD-relative path to the `.apk` file            |

If the path is not obvious, ask one short clarifying question. Do not
guess.

## Workflow

1. **Confirm the path.** Resolve any `~` or relative segments; the MCP
   tool will error if the file does not exist.

2. **Open the project.** Call
   `mcp__android-re-static__open_project` with the resolved `apk_path`.
   Capture the returned `project_id`.

3. **Read the manifest.** Call
   `mcp__android-re-static__read_manifest` with `project_id` and
   `formatted=false` (structured). The result is a dict with `package`,
   `uses_sdk`, `uses_features`, `permissions`, `components`, and
   `application`.

4. **List exported components.** Call
   `mcp__android-re-static__list_components` with `exported_only=true`.
   Exported activities, services, receivers, and providers are the
   primary attack surface from outside the app.

5. **Get dangerous permissions.** Call
   `mcp__android-re-static__get_permissions` with
   `classification="dangerous"`. These warrant a follow-up check
   against the manifest and the source.

6. **Verify signature.** Call
   `mcp__android-re-static__verify_signature`. Note the signing schemes
   present and the number of signers.

7. **Cert details.** Call
   `mcp__android-re-static__get_certificate_info` with `signer_index=0`.
   Note `is_self_signed`, `is_expired`, key size, and fingerprint.

8. **Class fingerprint.** Call
   `mcp__android-re-static__find_classes` with `query="Lcom/"` and
   `limit=50`. This catches common app-namespace classes; adjust the
   query based on the package name from step 3.

9. **Native methods.** Call
   `mcp__android-re-static__find_methods` with
   `native_only=true` and `limit=200`. The presence of native methods
   may warrant a follow-up with `android-re-native-triage`.

10. **Close the project.** Call
    `mcp__android-re-static__close_project` with the `project_id`.

## Output

A markdown report with the following sections:

```markdown
# Static Triage Report — <package>

## Package
- **Name**: <package>
- **Version**: <version_name> (<version_code>)
- **min/target SDK**: <min_sdk> / <target_sdk>
- **SHA-256**: <sha256>
- **Size**: <size> bytes

## Signing
- **Signed**: yes/no
- **Schemes**: v1, v2, v3 (whichever present)
- **Signer**: <subject>
- **Self-signed**: yes/no
- **Expired**: yes/no
- **Key size**: <bits>
- **Fingerprint (SHA-256)**: <hex>

## Permissions (<n> total, <m> dangerous)
- <list of dangerous permissions>

## Exported Components (<n>)
- <list of exported activities/services/receivers/providers>

## Native Methods (<n>)
- <list of JNI methods, or "none found">

## Notable Findings
- <bullet list of anything unusual: e.g. "self-signed cert",
  "missing v2/v3 signature", "exported activity with no permission
  gate", "INTERNET + cleartext allowed", "uses_requestLegacyExternalStorage
  on API 30+", etc.>
```

## Examples

### Example 1: simple triage

> User: Triage `~/Downloads/suspicious.apk`.

Steps:

1. Resolve `~/Downloads/suspicious.apk`.
2. `open_project` → returns `apk-1a2b3c4d5e6f`.
3. `read_manifest` → structured view.
4. `list_components` (exported_only).
5. `get_permissions` (dangerous).
6. `verify_signature`.
7. `get_certificate_info` (signer 0).
8. `find_classes` (Lcom/).
9. `find_methods` (native_only).
10. `close_project`.

Produce the markdown report.

### Example 2: many components

If the app declares 50+ components, summarize counts and call out the
ones with intent filters that match well-known schemes (`http`, `https`,
`tel`, `sms`, `mailto`).

## Background reading (peer MCP)

While running this skill, the agent can consult the RE-Library peer
MCP for generic patterns. Triggers: "what does the literature say
about <observed pattern>". The peer is read-only; it never
overwrites a verified observation on the target.

- `mcp__re-library__list_categories()` — enumerate the 8 categories.
- `mcp__re-library__search_re(query="<category> <pattern>", max_results=3)` — up to 3 hits with snippet + score.
- `mcp__re-library__get_entry(slug="<category>/<NN>-<slug>")` — full body of one entry.

Pair with the manifest, component, and signature observations from
this skill; do not let a search hit override a verified observation
on the target.

The peer is registered in `.mcp.json`; install it once with
`just install-re-library` (opt-in).

## Output convention

The skill writes a markdown summary to:

```
Output/<apk-basename>-<short-sha>/static/static-triage.md
```

(For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md) and
`android_re_core.paths.output_dir_for`.) The first call also opens a
project, so pass `max_size=<apk_bytes * 2>` on `open_project` for any
APK over the 500 MB default cap.

## Notes

- This skill is read-only. Nothing is written to the device.
- The first call (manifest read) is the most expensive; the rest are
  cheap because they read the already-cached views.
- Always close the project. Leaving it open keeps a file handle on the
  APK and burns memory.
- **Size limit.** The MCP `open_project` tool caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
