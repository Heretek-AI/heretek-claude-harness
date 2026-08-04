---
name: audit-checklist
description: Pre-deploy security audit checklist. Run before merging security-sensitive changes.
---

Checklist (run all that apply):

**Authentication & Authorization:**
- [ ] All endpoints require authentication
- [ ] Authorization checks are per-resource, not per-route
- [ ] Sessions expire; tokens are short-lived
- [ ] Password / key handling follows NIST guidelines

**Input handling:**
- [ ] All input is validated against a strict schema
- [ ] SQL/NoSQL queries use parameterized statements
- [ ] HTML output is escaped (or uses a templating engine that escapes by default)
- [ ] File paths are canonicalized and checked against an allow-list

**Cryptography:**
- [ ] TLS 1.2+ everywhere; cleartext only for localhost
- [ ] No MD5/SHA1 for security purposes
- [ ] Random number generation uses a CSPRNG
- [ ] Secrets are not committed; use a vault

**Logging & monitoring:**
- [ ] Auth events are logged
- [ ] Logs do not contain secrets or PII
- [ ] Anomalies trigger alerts

Skip categories that don't apply to the change.
