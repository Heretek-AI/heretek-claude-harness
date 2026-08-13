# re-leak-scan

MCP server for detecting **publisher telemetry pipeline leaks** in binary artifacts. Scans the file's string table for:

- **Sentry DSNs** (with embedded public auth) — enables forged crash-report submission
- **Logstash / log-ingestion URLs** — internal observability infrastructure
- **Confluence wiki page links** — often engineering-only docs / secrets
- **Google Drive document URLs** — publisher-internal documents
- **AWS access key IDs** — long-lived credentials
- **Slack tokens** — long-lived API credentials
- **Generic high-entropy hex strings** — possible keys / secrets

The output is vendor-neutral: pattern categories describe observable string content, not specific publishers.

## Why

The 2026-06-05 stress test surfaced a new attack-surface class that the existing tools did not cover:

- **Sample A** (`GameAssembly.dll`): 16,236 Google Drive URL matches — the bulk are publisher-internal design documents.
- **Sample B** (`CrimsonDesert.exe`): a Sentry DSN with embedded auth, a Logstash ingestion URL, an internal dev server URL, and a Confluence wiki page link — all in plaintext, all unprotected by the encrypted-VM bytecode anti-tamper.

`re-leak-scan` fills that gap. It is **pure-Python** (no .NET, no system tools), works on any binary file, and is the .re-leak-scan / .re-telemetry-extract foundation for the `re-leak-scan` and `re-telemetry-extract` skills.

## Tools

| Tool | What it does |
|---|---|
| `check_leak_scan` | Health check — return pattern catalog + `httpx` availability |
| `extract_strings` | Walk the file, extract ASCII + UTF-16LE printable strings |
| `find_secrets` | Apply the regex catalog over a binary's string table |
| `scan` | Full pipeline: extract → apply all detectors → return findings |
| `verify_sentry_dsn` | Parse a Sentry DSN + probe `<host>/api/0/projects/.../` to confirm liveness |
| `verify_confluence_url` | Probe a Confluence URL to confirm reachability + anon-access |

## Install

Part of the RE-AI plugin; `./install.sh` installs the package. To install standalone:

```bash
pip install -e ./servers/re-leak-scan
# Optional: live verification (Sentry / Confluence HTTP probes)
pip install -e './servers/re-leak-scan[verify]'
```

## Run

```bash
re-leak-scan                          # stdio transport (default for MCP)
python -m re_leak_scan                # equivalent
```

## Pattern catalog

The 7 patterns are defined in `src/re_leak_scan/patterns.py`. Adding a new one is a 6-line dataclass entry. The patterns are all **vendor-neutral** — they match the URL schemes of public infrastructure (Sentry.io, Logstash, Atlassian Confluence, Google Docs) without naming any specific publisher.

## Active verification

`verify_sentry_dsn` and `verify_confluence_url` make outbound HTTP requests. By default, they are *passive* — they only check that the endpoint responds. They do **not** submit forged crash reports, do not authenticate, and do not exfiltrate the leaked data.

If you run these in an air-gapped environment, the verifier returns `verified: false, reason: "connection failed: ..."` — the leak detection itself is unaffected.
