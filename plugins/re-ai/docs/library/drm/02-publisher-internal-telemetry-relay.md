---
title: "Publisher-Internal Diagnostic-Relay Hostnames"
category: "drm"
platforms: ["linux", "windows", "macos", "android", "ios"]
difficulty: "advanced"
tags: ["telemetry", "fingerprinting", "leak", "diagnostic", "publisher-network", "detection"]
summary: "A new category of telemetry leak — binaries that ship with the hostname of a publisher-internal diagnostic / observability server (jenkins.internal, grafana.corp, sentry.io.internal) and conditionally send the un-hashed machine fingerprint only when the host is on RFC1918 corporate network space. The hostname is the leak; the public variant (jenkins.io) does not fire."
updated: "2026-06-06"
related: ["drm/01-cdm-architecture", "anti-analysis/05-launcher-activation-fingerprinting", "anti-analysis/02-vm-bytecode-interpreter"]
---

## Summary

A publisher-internal diagnostic-relay hostname is a DNS name that resolves only inside the publisher's corporate network (`.internal`, `.corp`, `.lan`, `.local`, `.intra`, `.private`, `.home.arpa` TLDs) and is *paired* with a diagnostic product stem (`jenkins`, `jira`, `grafana`, `prometheus`, `kibana`, `splunk`, `sentry`, `bitbucket`, `gerrit`, `artifactory`, `nexus`, `sonarqube`, `vault`, `consul`, `etcd`, `datadog`, `newrelic`, `pagerduty`). The hostname alone is a *leak*: it tells the reader the binary was built against an internal corporate resolver and shipped without scrubbing.

The new danger surface is the *conditional upload*: many of these binaries check whether the host is on RFC1918 corporate network space (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) and, only if so, send the **un-hashed** machine fingerprint to the internal hostname. Off the corporate network, the binary looks inert (the hostname doesn't resolve, the upload is skipped). The fingerprint is the second leak.

## Why this matters

This category is *not* in the standard telemetry-leak catalogs (Sentry DSN, Logstash, Confluence wiki page, Google Drive document, AWS access key, Slack token). Those are public infrastructure. The diagnostic-relay hostname is a *publisher-private* endpoint — a build artifact that survived the dev-to-prod pipeline and shipped in the release binary. The pattern is:

> A string in the binary references a diagnostic product (grafana, sentry, jenkins) at a TLD that doesn't exist on the public internet (`.internal`, `.corp`).

The reader's first hint is *why* the string is in the binary at all — the binary is either (a) a tool the publisher built for their own developers and never stripped, or (b) shipped a build of an upstream library that embeds a developer-environment config. Both are leaks.

## Mechanics

### The hostname pattern

A typical example is `jenkins.internal` (the build server at a publisher that hosts Jenkins internally on a `.internal` TLD) or `grafana.corp` (the metrics dashboard). The full regex is a diagnostic-product stem + a private TLD:

```
(?P<diagnostic_product>jenkins|jira|grafana|prometheus|kibana|splunk|sentry|...)
(?P<tld>\.internal|\.corp|\.lan|\.local|\.intra|\.private|\.home\.arpa)
```

The diagnostic-product stem is a closed list (not free-form) because the leak is specifically a *product* name (a server product the publisher deploys), not a generic host. The TLD list is the standard private-network TLD set; the public internet doesn't use these.

A real example is a publisher's .NET WPF companion binary with a `PASystemInfoScanner.SenderInfomation` class that does a DNS lookup of a `*.io.internal` hostname, checks the resolved IP against RFC1918, and conditionally sends the un-hashed machine fingerprint. The hostname in the binary is the leak; the conditional upload is the second leak.

### Why the public variant does *not* fire

A *public* `jenkins.io` is the website of the Jenkins project. A `grafana.com` is a SaaS vendor. These are *not* leaks — they're public web properties that the binary legitimately links to for documentation, status pages, or update checks. The pattern requires a *private TLD* to be diagnostic.

```python
# A live example with the test string
import re
P = re.compile(
    r"\b(?:[a-z0-9\-]+\.)*"
    r"(?:jenkins|jira|grafana|prometheus|kibana|splunk|sentry|"
    r"bitbucket|gerrit|artifactory|nexus|sonarqube|vault|consul|"
    r"etcd|datadog|newrelic|pagerduty)"
    r"(?:\.[a-z0-9\-]+)*"
    r"\.(?:internal|corp|lan|local|intra|private|home\.arpa)"
    r"\b",
    re.IGNORECASE,
)

# These fire (the leak):
P.search("jenkins.internal")          # match
P.search("grafana.corp")              # match
P.search("sentry.io.internal")        # match
P.search("splunk.lan")                # match
P.search("artifactory.intra.example") # match

# These do NOT fire (public, not a leak):
P.search("jenkins.io")                # no match
P.search("github.com")                # no match
P.search("grafana.com")               # no match
```

The match is **case-insensitive** — `Asian-Internal.corp` would also match (because `asian` is in the diagnostic-product stem list? actually no — the stems are specific products, not generic words). The `\.home\.arpa` TLD is the special-case for mDNS (RFC 8375) — modern Unix systems register their hostname under `.home.arpa` and a publisher's internal hostnames may use it too.

### The conditional upload

The leak usually doesn't end at the hostname. The same binary often has a code path that:

1. Resolves the hostname via the system resolver.
2. Checks whether the resolved IP is in RFC1918 space (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) — the "are we on the corporate LAN?" probe.
3. If on the corporate LAN, sends the *un-hashed* machine fingerprint to the internal hostname.
4. If not on the corporate LAN, the upload is skipped (the hostname doesn't resolve, the request would fail).

The off-corporate-network case looks inert (no network traffic, no upload), which is why this category is hard to catch with a "run the binary and watch the network" workflow. The static-string signal is the only reliable one.

```python
# A typical conditional-upload pattern (pseudocode)
hostname = "fingerprint-relay.internal"
ip = dns_resolve(hostname)
if is_rfc1918(ip):
    fingerprint = read_machine_fingerprint()  # no hashing
    http_post(f"https://{hostname}/v1/fingerprint", json=fingerprint)
```

The un-hashed fingerprint is the *second* leak — even if the network is corporate-only, the publisher's diagnostic server is now logging the un-hashed machine identifier. If the diagnostic server is later compromised, every machine that ever ran the binary is at risk.

## Approach

The triage workflow:

1. **Grep for the diagnostic-product stems** in the binary's strings — `jenkins`, `grafana`, `sentry`, `prometheus`, etc. The result is a *candidate list*; not all hits are leaks (e.g. a binary that links a public Grafana plugin is fine).
2. **Filter to the private-TLD anchors** — only hostnames with `.internal`, `.corp`, `.lan`, `.local`, `.intra`, `.private`, `.home.arpa` are diagnostic. The regex above does this in one step.
3. **Cross-reference the public variant** — if the same hostname (sans the private TLD) is a public website, the leak is weaker (the binary may legitimately link to a public status page). If the hostname is *only* in the private-TLD form, the leak is conclusive.
4. **Check the conditional-upload code path** — find the DNS-resolution + RFC1918 + upload code (the binary's strings dump usually surfaces the relevant substrings: `10.0.0.0`, `192.168.`, `home.arpa`, etc.). Document the upload for the publisher's security team.
5. **Do not run the binary on a corporate network** — the upload path may fire and send the un-hashed fingerprint to a server you can't audit. The static analysis is enough; the dynamic analysis is the threat surface.

## Common pitfalls

- **Assuming the binary is "off-corporate" so the leak is harmless.** The binary may be installed on an analyst's workstation that is *VPN'd into* the publisher's corporate network. The conditional upload fires. The static string is the only signal you have.
- **Mistaking a public diagnostic product (grafana.com, sentry.io) for a leak.** The pattern is the *private TLD* — `grafana.com` is the vendor's SaaS; `grafana.corp` is the publisher's internal instance. The regex enforces this.
- **Treating the un-hashed fingerprint upload as "just a feature".** The fingerprint goes to a server the publisher can't audit (and may be a misconfigured bucket). The un-hashed form is the danger: even an internal upload creates a high-value target.
- **Missing the diagnostic-product stems in non-English binaries.** A CJK-market binary may have the same diagnostic infrastructure with `internal` → `内部` or `.corp` → `.集团`. The English regex won't fire. Build a localized stem list per market.

## Tooling pointers

- [`drm/01-cdm-architecture`](../drm/01-cdm-architecture.md) — the broader "publisher network architecture" topic. The diagnostic-relay hostname is a sibling concern: both are about "what the binary talks to that you didn't know about".
- [`anti-analysis/05-launcher-activation-fingerprinting`](../anti-analysis/05-launcher-activation-fingerprinting.md) — the activation library that often co-locates the diagnostic-relay code in the same launch flow.
- `re-leak-scan.scan` (via [RE-AI](https://github.com/Heretek-AI/RE-AI)) — the leak catalog includes a `publisher-internal-diagnostic-hostname` detector. The 8 patterns in the catalog (Sentry DSN, Logstash URL, Confluence wiki, Google Drive, AWS access key, Slack token, generic hex secret) cover the public-infrastructure leaks; the diagnostic-relay pattern covers the publisher-private one.
- `re-lief.categorize_strings` (via [RE-AI](https://github.com/Heretek-AI/RE-AI)) — the `telemetry_leak` category surfaces candidates; the `license-activation` category catches the activation-library context. Cycle 2 of the categorizer added `exclude_keywords` to suppress Unicode UCD constant false positives (e.g. `East_Asian_Width` was matching the `width` keyword).
- `httpx` (or `curl -I`) for verifying the *public* variants of the diagnostic-product names (so you can exclude them as leaks). The reachability of the *private* variants cannot be verified from outside the publisher's network.

## References

- [RFC 1918 — Address Allocation for Private Internets](https://datatracker.ietf.org/doc/html/rfc1918) — the `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` private network ranges.
- [RFC 8375 — Special-Use Domain `home.arpa`](https://datatracker.ietf.org/doc/html/rfc8375) — the `.home.arpa` TLD for residential networking.
- [RE-AI: data/drm-indicators.yaml](https://github.com/Heretek-AI/RE-AI/blob/main/data/drm-indicators.yaml) — the `hwid_apis` and `telemetry_leak` categories that informed this entry.
- [RE-AI: servers/re-leak-scan/src/re_leak_scan/patterns.py](https://github.com/Heretek-AI/RE-AI/blob/main/servers/re-leak-scan/src/re_leak_scan/patterns.py) — the `publisher-internal-diagnostic-hostname` pattern definition.
