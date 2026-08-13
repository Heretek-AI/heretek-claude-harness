---
name: re-leak-scan
description: Find publisher telemetry pipeline leaks in a binary's string table. Use when the user says "scan this binary for telemetry endpoints", "find Sentry DSNs / Logstash URLs / Confluence links / Google Drive docs in this binary", "look for embedded publisher credentials", or hands you a .exe / .dll / .so and asks for what an attacker would extract. Calls re-leak-scan.find_secrets + re-leak-scan.scan and produces a per-category leak report. Pairs with re-telemetry-extract for live endpoint verification.
---

# Telemetry Pipeline Leak Scan

## When to use

Use this skill when a binary is suspected of leaking its publisher's
**operational infrastructure** — telemetry endpoints, internal wiki
links, design documents, or long-lived credentials. The leak
detection runs as a regex pass over the binary's string table.

The user gives you a `.exe` / `.dll` / `.so` (or the path to a
GameAssembly.dll-style bundle) and asks for "what endpoints does
this call out to" or "does this binary contain Sentry DSNs / Google
Drive links / Confluence pages". The output is a per-category
report — no live network calls by default.

**What this skill returns** (a Markdown report):

1. **Header** — file path, strings scanned, total matches
2. **HIGH-risk findings** — Sentry DSNs, AWS access keys, Slack tokens
3. **MEDIUM-risk findings** — Logstash URLs, Confluence links, Google Drive URLs
4. **LOW-risk findings** — generic high-entropy hex strings (high false-positive rate)
5. **Per-category counts** — how many matches, what risk tier
6. **First-3 samples per category** — enough context for the analyst
   to confirm or reject
7. **Remediation suggestions** — rotate the Sentry project ID, move
   the Confluence page out of the binary, etc.

## What this skill does NOT do

- **Does not run the binary.** The scan is purely a static pass
  over the file's string table. For dynamic network analysis, use
  `re-mitm2swagger` and `re-dynamic-analysis` instead.
- **Does not exfiltrate the matched endpoints.** The output is the
  matched string + offset; the analyst chooses what to do with it.
- **Does not crack encrypted-VM bytecode protection.** Encrypted
  strings (XOR'd, AES'd, RC4'd) are invisible to a string-table
  scan. Run `re-encrypted-vm-tamper` + a dynamic trace to recover
  the runtime-decrypted strings; this skill works on what the
  binary leaves in plaintext.

## Workflow

**Step 1 — First-pass scan with all categories**

```
re-leak-scan.scan(path)
```

Note the totals and the per-category counts. The HIGH-risk
categories (Sentry, AWS, Slack) are the analyst's first concern;
the LOW-risk generic-hex-secret category is mostly noise.

**Step 2 — Targeted scan (if a specific leak type is suspected)**

```
re-leak-scan.find_secrets(path, detector_set="sentry-dsn,logstash-url")
```

Use this when the user names a specific category. Faster than a
full scan and produces less output for the analyst to read.

**Step 3 — Sample extraction (for first-3 review)**

For each category with matches, the top 3 sample strings give the
analyst enough context to confirm or reject. The pattern description
in the catalog (`"Sentry DSN with embedded public auth"`,
`"Logstash ingestion URL"`) is the analyst's hint for what to
look for.

**Step 4 — Live verification (optional)**

If the analyst wants to confirm that a leaked endpoint is
**actually reachable** (vs. an unused / revoked endpoint), pair
this skill with `re-telemetry-extract`. That skill calls
`re-leak-scan.verify_sentry_dsn` / `verify_confluence_url`
to make outbound HTTP requests.

**Step 5 — Vendor-neutral summary**

The output must be vendor-neutral. If a specific publisher /
product is named, replace it with the role: "Sentry DSN
(enables forged crash submission)" rather than
"publisher Sentry DSN". The catalog is already vendor-neutral;
the analyst's report should be too.

## Output report format

```markdown
# Telemetry Pipeline Leak Scan — <path>

## Summary
- Strings scanned: N
- Total matches: N
- HIGH-risk findings: N
- MEDIUM-risk findings: N
- LOW-risk findings: N (likely noise)

## HIGH-risk findings

### Sentry DSNs (N matches)
- offset 0x...: https://abc...@sentry.example.com/42
- offset 0x...: https://def...@sentry.example.com/43
- ... (up to 3 samples)

## MEDIUM-risk findings

### Logstash URLs (N matches)
- ...

## Remediation
1. Rotate the Sentry project ID — the leaked public key enables
   forged crash submission.
2. Move the Confluence wiki page URL out of the binary (or use
   a permission boundary that requires auth).
3. ...

## Limitations
- Encrypted-VM bytecode strings are not visible to this scan.
  For samples with runtime-decrypted strings, run
  `re-encrypted-vm-tamper` first.
```

## Pairing with other skills

- `re-telemetry-extract` — adds live endpoint verification
  (HTTP probe). Call after the static scan to confirm reachability.
- `re-drm-fingerprint` — for samples with encrypted-VM bytecode
  anti-tamper. The encrypted string regions are not visible to
  this scan.
- `re-vm-reverse` — when dynamic decryption is needed to recover
  the runtime string table before scanning.
- `re-static-triage` — for the broader binary triage (imports,
  sections, capabilities). Pairs with this skill for the
  telemetry-side complement.
