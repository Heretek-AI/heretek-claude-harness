---
name: re-pcap-correlate
description: Analyze a packet capture and correlate its endpoints with the publisher telemetry leak catalog. Use when the user has a .pcap / .pcapng file in Input/ and asks for "what endpoints did this app call", "correlate the pcap with the leak scan", or "find the publisher-internal endpoints on the wire". Calls re-pcap.parse_pcap + extract_http_https + extract_dns_queries + correlate_endpoints to surface every HTTP host, DNS query, and publisher-internal endpoint. Pairs with re-leak-scan to confirm the matched endpoints are reachable; pairs with re-telemetry-extract for active HTTP verification.
---

# PCAP Endpoint Correlation

## When to use

Use this skill when the user has a packet capture
(`.pcap` / `.pcapng`) and wants to know what
endpoints the captured traffic talks to. The
skill wraps `re-pcap` + `re-leak-scan` to surface:

1. The HTTP hosts + paths seen on the wire.
2. The DNS query names.
3. The correlation between the captured
   endpoints and the publisher telemetry leak
   catalog (Sentry DSN hostnames, Logstash
   URLs, Confluence, Google Drive, AWS
   endpoints, Slack tokens).

## What this skill returns

1. **Per-flow summary** — HTTP method + host +
   path + status per captured flow.
2. **DNS query list** — per captured query
   name + qtype.
3. **Correlation matches** — the captured
   endpoints that match the leak-scan catalog.
4. **Vendor-neutral summary** — every label
   is a category, never a specific publisher.

## What this skill does NOT do

- **Does not decrypt TLS.** The walker
  extracts only the TLS metadata (host, SNI,
  cipher suite). The analyst pairs with
  `re-mitm2swagger` for the captured-cleartext
  side.
- **Does not run the binary.** The PCAP is a
  wire-side record; for userland hooks, pair
  with `re-frida` or `re-android-dynamic`.
- **Does not name specific publishers.** The
  correlation report uses category labels
  (sentry-dsn, logstash-url, confluence-url,
  etc.).

## Workflow

**Step 1 — Parse the PCAP (one call)**

```
re-pcap.parse_pcap(path=pcap_path, max_packets=10000)
```

Returns the packet summary + the flow list
(where parseable) + the DNS query list.

**Step 2 — Filter (optional, parallel-safe)**

```
re-pcap.filter_flows(
    path=pcap_path,
    method="POST",
    status=200,
    host_substring="sentry",
)
```

Returns the matching flows.

**Step 3 — HTTP/HTTPS extract (parallel-safe)**

```
re-pcap.extract_http_https(path=pcap_path, max_flows=1000)
```

Returns the HTTP request / response flows.

**Step 4 — DNS extract (parallel-safe)**

```
re-pcap.extract_dns_queries(path=pcap_path, max_queries=500)
```

Returns the DNS query list.

**Step 5 — Correlation (parallel-safe)**

```
re-pcap.correlate_endpoints(path=pcap_path)
```

Returns the correlation matches — the captured
endpoints that match the leak-scan catalog. The
analyst reviews the matched category + the
packet timestamp + the source / destination IP.

**Step 6 — Live verification (optional)**

For matched endpoints the analyst wants to
confirm are reachable:

```
re-leak-scan.verify_sentry_dsn(dsn=matched_sentry_dsn)
re-leak-scan.verify_confluence_url(url=matched_confluence_url)
```

The probes hit the endpoint; the response is
``{"verified": bool, "http_status": N}``.

## Output report format

```markdown
# PCAP Endpoint Correlation — <pcap_path>

## Flow summary
- HTTP flows: 412
- HTTPS flows: 187 (TLS-encrypted; only metadata)
- DNS queries: 47

## HTTP hosts (top 10)
- ac-vendor.example.com (47 flows)
- telemetry-vendor.example.com (23 flows)
- ad-network.example.com (12 flows)
- ...

## DNS queries (top 10)
- ac-vendor.example.com (8 queries)
- telemetry-vendor.example.com (4 queries)
- ...

## Correlation matches
- sentry-dsn: 3 (telemetry-vendor.example.com)
- logstash-url: 1 (logstash.internal.example.com)
- confluence-url: 0
- google-drive-url: 0
- aws-access-key: 0
- slack-token: 0

## Live verification (optional)
- sentry-dsn: verified=True, http_status=200
- (the rest are intentionally not verified here)
```

## Pairing with other skills

- `re-leak-scan` — for the static + live
  endpoint verification side. Use to confirm
  the matched endpoints are reachable.
- `re-telemetry-extract` — for the active
  HTTP probe of the matched endpoints.
- `re-mitm2swagger` — for the OpenAPI /
  Swagger generation from the captured
  HTTP flows.
- `re-frida` — for the userland hook side.
  Pair when the analyst wants to see the
  in-app view of the network call.
- `re-android-dynamic` — for the APK + Frida
  pairing that produces the PCAP.
