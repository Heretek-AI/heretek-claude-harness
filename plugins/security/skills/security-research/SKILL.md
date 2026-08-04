---
name: security-research
description: Walk through threat modeling, vulnerability enumeration, and exploit analysis. Use for security audit prep or incident triage.
---

A structured workflow for security research:

1. **Scope**: what's the asset, the threat actor, the goal?
2. **Threat model**: enumerate STRIDE categories (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege).
3. **Attack surface**: list inputs (network, file, IPC, env vars), trust boundaries.
4. **Vulnerabilities**: enumerate with CWE IDs where possible.
5. **Verification**: propose reproduction steps; never run them against production.
6. **Mitigation**: rank by exploitability + impact; propose remediations.

For incident triage, start at step 5 (verification) and work backwards to the root cause.
