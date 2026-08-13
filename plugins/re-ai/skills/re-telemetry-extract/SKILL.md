---
name: re-telemetry-extract
description: Extract publisher telemetry endpoints from a binary AND actively verify each one is live. Use when the user says "find all endpoints this binary calls and confirm which ones are live", "verify the Sentry DSN / Confluence URL is actually reachable", "is this leaked endpoint still up". Calls re-leak-scan.find_secrets + re-leak-scan.verify_sentry_dsn + re-leak-scan.verify_confluence_url and produces a verified-leaks report. Pairs with re-leak-scan (which is the static-only counterpart).
---

# Telemetry Endpoint Verification

## When to use

Use this skill when the analyst wants to know **which leaked
endpoints are actually live** (vs. revoked, redirected, or
unreachable). The static `re-leak-scan` finds the matches; this
skill adds an active verification pass.

**Distinct from `re-leak-scan`:**

- `re-leak-scan` — static pass; finds Sentry DSNs, Logstash URLs,
  Confluence links, etc. in the string table. No network.
- `re-telemetry-extract` — calls `re-leak-scan.find_secrets` first
  to find the matches, then **probes each one** with HTTP
  (Sentry `/api/0/projects/.../`, Confluence page load). Returns
  a per-endpoint `verified: bool` + `http_status` + `reason`.

**What this skill returns** (a Markdown report):

1. **Header** — file path, candidates found, verified count
2. **Per-endpoint table** — category, matched string, parsed
   components, HTTP status, anon-accessible, reason
3. **HIGH-risk verified endpoints** — these are the live leaks
   the analyst should prioritize

## What this skill does NOT do

- **Does not submit forged crash reports.** The Sentry probe only
  checks whether `<host>/api/0/projects/<key>/<project>/` is
  reachable; it does not POST a fake event. The leaked public
  key is the credential the analyst needs to *be aware of*; the
  probe does not use it to write data.
- **Does not authenticate.** The Confluence probe only checks
  the unauthenticated page load (200 vs 401/403). It does not
  try to log in.
- **Does not scan the binary.** Call `re-leak-scan.find_secrets`
  first; this skill consumes its output and adds the verification
  layer.

## Workflow

**Step 1 — Run the static scan**

```
result = re-leak-scan.find_secrets(path, detector_set="sentry-dsn,logstash-url,confluence-url,google-drive-url")
```

The `result["by_category"]` dict has the matches per category. Each
match has a `string`, `offset`, `encoding`, and `groups` (named
regex group captures).

**Step 2 — Probe each Sentry DSN**

For each match in `result["by_category"]["sentry-dsn"]`, call
`re-leak-scan.verify_sentry_dsn(match["string"])`. The verifier
parses the DSN and probes `<host>/api/0/projects/<key>/<id>/`.

A 200/401/403/404 means the endpoint is reachable (the specific
status tells you whether the leaked key has project access). A
connection error means the host is unreachable from the
analyst's network.

**Step 3 — Probe each Confluence URL**

For each match in `result["by_category"]["confluence-url"]`, call
`re-leak-scan.verify_confluence_url(match["string"])`. The verifier
follows redirects and reports the final HTTP status.

A 200 means the page is **publicly readable** (anon-accessible).
A 401/403 means it's behind auth (still reachable, but the
analyst would need credentials to read). A redirect to a login
page is reported as "behind auth".

**Step 4 — Logstash + Google Drive URLs**

These two are not actively verified — the Sentry and Confluence
probes are the highest-value ones (they confirm a credential leak
vs. an anonymous link). For Logstash / Google Drive, the static
match is the report.

**Step 5 — Build the verified-leaks report**

The output is a per-endpoint table. The analyst reads the table
top-down — the HIGH-risk Sentry verified-endpoints are the
priority; the MEDIUM-risk Confluence verified-endpoints are
secondary; the unverified (Logstash / Google Drive) are listed
at the bottom.

## Output report format

```markdown
# Telemetry Endpoint Verification — <path>

## Summary
- Candidates: N
- Verified live: N
- Reachable but auth-walled: N
- Unreachable from analyst network: N

## Sentry DSNs (verified)

| DSN | Host | Project ID | HTTP Status | Reason |
|---|---|---|---|---|
| https://abc...@sentry.example.com/42 | sentry.example.com | 42 | 200 | endpoint reachable |
| https://def...@sentry.example.com/43 | sentry.example.com | 43 | 403 | key has no project access |
| https://ghi...@sentry.old.com/1 | sentry.old.com | 1 | connection refused | unreachable |

## Confluence URLs (verified)

| URL | HTTP Status | Anon-accessible | Reason |
|---|---|---|---|
| https://acme.atlassian.net/wiki/spaces/ENG/pages/123 | 200 | true | publicly readable |
| https://acme.atlassian.net/wiki/spaces/SECRET/pages/456 | 401 | false | behind auth |

## Logstash URLs (static-only)
- ...

## Google Drive URLs (static-only)
- ...

## Limitations
- The probes are passive — they confirm reachability, not data
  exfiltration. Run re-dynamic-analysis + re-mitm2swagger for the
  dynamic network trace.
- `verify_sentry_dsn` does not POST a fake event. The leaked
  public key is reported, not used to write data.
```

## Pairing with other skills

- `re-leak-scan` — the static-only counterpart. Call first to
  get the candidate list; this skill adds the verification layer.
- `re-dynamic-analysis` — for the dynamic network trace (process
  start → HTTP requests). Complementary to the static pass.
- `re-mitm2swagger` — for live-traffic capture during a dynamic
  analysis run. The two together give "what endpoints does the
  binary hard-code" + "what endpoints does it actually call at
  runtime".
