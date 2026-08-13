# MASVS Controls referenced by android-re-static-triage

The static triage skill is intentionally lightweight — it does not run a
full MASVS audit. It does, however, surface findings that map to specific
MASVS v2 controls so the user can decide whether to escalate to
`android-re-masvs-report` (Phase 4).

## Mapped controls (Phase 1)

| MASVS control                | What the static triage surfaces                                            |
|------------------------------|-----------------------------------------------------------------------------|
| **MASVS-CODE-2** (no obvious backdoors) | Self-signed cert on a non-debug build, missing v2/v3 schemes, exported activities with no permission gate |
| **MASVS-STORAGE-1** (no sensitive data in plaintext) | (Not in Phase 1 — requires source review; covered by `android-re-decompile`) |
| **MASVS-PLATFORM-1** (exported component hardening) | Components with `exported=true` and no `permission` attribute; deep links handling untrusted data |
| **MASVS-PLATFORM-2** (intent filters on exported components) | Components with `exported=true` AND `<intent-filter>`; the canonical deep-link surface |
| **MASVS-RESILIENCE-1** (root/tamper detection) | (Not in Phase 1 — runtime check; covered by `android-re-dynamic-hook` in Phase 3) |
| **MASVS-NETWORK-1** (TLS everywhere) | `application@usesCleartextTraffic="true"`, missing `networkSecurityConfig` |
| **MASVS-NETWORK-2** (cert pinning) | (Static heuristics; full coverage in Phase 2 with `apk-mitm`/Frida) |

## When to escalate

If the triage surfaces any of the following, suggest the user escalate
to `android-re-masvs-report` (Phase 4 orchestrator):

- More than 5 exported components with intent filters
- `targetSdkVersion < 30` (Android 11+ scoped storage requirements)
- `application@debuggable="true"` on a release build
- `application@usesCleartextTraffic="true"`
- Self-signed or expired signing certificate
- Custom permissions declared by the app (often a sign of multi-process IPC)

## When NOT to escalate

If the user is just exploring ("what is this APK?") and has not
indicated they want a formal audit, the static triage report is
sufficient. Don't over-pitch MASVS — it's a meaningful commitment.
