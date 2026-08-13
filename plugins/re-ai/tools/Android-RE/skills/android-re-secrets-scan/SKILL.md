---
name: android-re-secrets-scan
description: |
  Use when the user wants to find hard-coded secrets in an APK: API
  keys, AWS / GCP / Azure credentials, JWTs, private keys, hard-
  coded URLs, IP addresses, or any other sensitive data embedded in
  the decompiled source. Triggers: "scan for secrets", "find API
  keys", "find AWS credentials", "check for hard-coded secrets",
  "scan the APK for sensitive data", "find URLs in the source". Do
  NOT use for runtime data leak detection (Phase 3) or for network
  interception (use android-re-network-intercept).
effect:
  filesystem: read APK in current directory or absolute path
  network: none
  device: none
requires:
  mcp: android-re-static
---

# Secrets scan of an APK

Walks the decompiled Java source of the APK looking for hard-coded
secrets. Pure static — no device, no Frida, no runtime.

## When to use

The user has an APK and wants to know whether sensitive credentials
or endpoints are embedded in the code. Typical cases:

- Pre-release audit ("did we ship a key?")
- Malware triage ("does this app talk to a C2?")
- Bug bounty ("find the AWS access key")

If the user wants runtime secrets leak detection (e.g. keys logged
or transmitted), use `android-re-dynamic-hook` (Phase 3+).

## Inputs

| Field       | Required | Description                                       |
|-------------|----------|---------------------------------------------------|
| `apk_path`  | yes      | Path to the `.apk`                                |
| `rules`     | no       | `default` (medium+) or `strict` (low+)            |

## Workflow

1. **Open the project.**
   `mcp__android-re-static__open_project` → `project_id`.

2. **Scan for secrets.**
   `mcp__android-re-static__scan_secrets` with the project_id and
   rule set. The first call triggers a jadx decompile (cached on
   disk) and then runs the rule engine.

3. **Group findings by severity.**
   The result includes per-finding severity and rule. Group
   CRITICAL first, then HIGH, MEDIUM, LOW, INFO.

4. **Surface the highest-impact hits.**
   - `aws-access-key-id` + nearby `aws-secret-access-key` is a
     confirmed AWS credential pair.
   - `private-key-pem` is a leaked private key.
   - `github-token` / `slack-token` are leaked service tokens.

5. **Optional cross-checks.**
   For each high-severity hit, fetch the surrounding ~10 lines
   using `get_smali` (Phase 2) or `decompile_class` to confirm
   the secret is actually used in code (vs. a comment).

6. **Close the project.**
   `mcp__android-re-static__close_project`.

## Output

A markdown report with sections by severity:

```markdown
# Secrets Scan Report — <package>

## CRITICAL (<n>)
- **F-001**: aws-access-key-id in `com/example/AWS.java:42`
  - Match: `AKIA****************`
  - File: sources/com/example/AWS.java

## HIGH (<n>)
- **F-002**: github-token in `com/example/CI.java:17`
  - Match: `ghp_…`
  - File: sources/com/example/CI.java

## MEDIUM (<n>)
- <list>

## LOW (<n>)
- <list>
```

## Examples

### Example 1: full scan

> User: Scan this APK for secrets.

Steps:

1. Open project.
2. `scan_secrets` with `rules="default"`. Returns up to 500
   findings across all severities ≥ MEDIUM.
3. Group and emit report.

### Example 2: strict (catch IP / URL / email too)

> User: Run a strict secrets scan, including URLs and IPs.

Steps: same as Example 1, but `rules="strict"`. Findings include
`http-url` and `ip-address` matches.

## Background reading (peer MCP)

While running this skill, the agent can consult the RE-Library peer
MCP for generic patterns. Triggers: "what does the literature say
about <observed pattern>". The peer is read-only; it never
overwrites a verified observation on the target.

- `mcp__re-library__list_categories()` — enumerate the 8 categories.
- `mcp__re-library__search_re(query="<category> <pattern>", max_results=3)` — up to 3 hits with snippet + score.
- `mcp__re-library__get_entry(slug="<category>/<NN>-<slug>")` — full body of one entry.

Pair with the regex-hit class (AWS key, GCP key, JWT, private key,
etc.) from this skill; the `tools` and `android` categories are
the right lookups for "what is the canonical form of <secret
type>" before promoting a finding to HIGH.

The peer is registered in `.mcp.json`; install it once with
`just install-re-library` (opt-in).

## Output convention

All three scanners (`scan_secrets`, `scan_with_quark`, `run_androwarn`)
write to:

```
Output/<apk-basename>-<short-sha>/secrets/secrets-findings.json
Output/<apk-basename>-<short-sha>/secrets/quark/            # quark output dir
Output/<apk-basename>-<short-sha>/secrets/androwarn.json
```

(For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).) Override
with the `output_path` / `output_dir` parameter on each tool.

## Notes

- The scanner is **regex-based**, so false positives are expected
  (e.g. base64 strings that look like JWTs). For high-confidence
  results, always confirm the context.
- It does not run **apkleaks**, **quark**, or **androwarn** by
  default (those are separate tools; see the workflow below).
- The first call is slow (jadx decompile); subsequent calls are
  fast (cached on disk under ``/tmp/android-re/<project_id>-jadx/``).
- **Size limit.** The MCP `open_project` tool caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
