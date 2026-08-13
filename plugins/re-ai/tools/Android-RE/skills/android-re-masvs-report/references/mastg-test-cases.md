# MASTG test cases reference

A condensed reference for the OWASP Mobile Application Security
Testing Guide (MASTG) test IDs. The
`android-re-masvs-report` skill cross-references these to
produce a structured report.

## MASTG v1.x → MASVS v2 mapping (selected)

The MASTG organizes tests by the same categories as MASVS. The
test IDs are:

- **MASTG-TEST-XXXX** — atomic test case
- **MASTG-TECH-XXXX** — reusable technique
- **MASTG-DEMO-XXXX** — runnable demo

The full list is in the OWASP MASTG repository
(https://github.com/OWASP/mastg). Below is a Phase-4-relevant
subset that the static / dynamic / native servers can verify.

## Storage (MASVS-STORAGE)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0001 | No sensitive data written to app-specific external storage |
| MASTG-TEST-0002 | No sensitive data in SharedPreferences (Phase 4: covered by dynamic decompile) |
| MASTG-TEST-0003 | No sensitive data in logs (Phase 4: logcat) |
| MASTG-TEST-0006 | No sensitive data in WebView caches |
| MASTG-TEST-0012 | Sensitive data removed on `onPause` |

## Crypto (MASVS-CRYPTO)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0013 | No usage of MD5 / SHA-1 / DES / RC4 |
| MASTG-TEST-0014 | Symmetric key length ≥ 128 bits |
| MASTG-TEST-0015 | Asymmetric key length ≥ 2048 (RSA) / ≥ 256 (ECC) |
| MASTG-TEST-0017 | Sufficient PBKDF2 iteration count (≥ 10,000) |
| MASTG-TEST-0061 | SecureRandom used for sensitive values |
| MASTG-TEST-0062 | No hard-coded IVs for symmetric crypto |

## Auth (MASVS-AUTH)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0018 | Biometric prompt not bypassable |
| MASTG-TEST-0019 | Server-side auth, not just client |
| MASTG-TEST-0020 | Strong password policy |
| MASTG-TEST-0021 | 2FA for sensitive operations |
| MASTG-TEST-0023 | Session timeout enforced |
| MASTG-TEST-0024 | Auth tokens cleared on logout |

## Network (MASVS-NETWORK)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0026 | TLS for all network traffic |
| MASTG-TEST-0027 | Cert validation enabled |
| MASTG-TEST-0028 | Cert pinning for sensitive connections |
| MASTG-TEST-0029 | No cleartext traffic (release builds) |
| MASTG-TEST-0060 | HSTS / equivalent where applicable |

## Platform (MASVS-PLATFORM)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0030 | Exported components have permission gates |
| MASTG-TEST-0031 | Intent filters validate caller |
| MASTG-TEST-0032 | Pending Intents are explicit |
| MASTG-TEST-0033 | WebView JavaScript interface is restricted |
| MASTG-TEST-0034 | WebView file access disabled |
| MASTG-TEST-0039 | Content provider URIs are enforced |
| MASTG-TEST-0040 | Content provider permissions declared |

## Code (MASVS-CODE)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0041 | App is signed with non-debug key |
| MASTG-TEST-0042 | `debuggable=false` on release builds |
| MASTG-TEST-0043 | Third-party libs are up-to-date (Phase 4: SCA via apk-mitm or quark) |
| MASTG-TEST-0044 | PIE / stack canary / RELRO on native libs |
| MASTG-TEST-0081 | Native libs not loaded from world-writable paths |

## Resilience (MASVS-RESILIENCE)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0045 | Anti-tamper / signature check |
| MASTG-TEST-0046 | Anti-debug (ptrace / TracerPid) |
| MASTG-TEST-0047 | Root / emulator detection |
| MASTG-TEST-0048 | Frida detection (libfrida-agent / port 27042) |
| MASTG-TEST-0049 | Hooking framework detection (Xposed / Substrate) |
| MASTG-TEST-0050 | Obfuscation present (R8 / ProGuard) |
| MASTG-TEST-0051 | Device attestation (an integrity-attestation API) |
| MASTG-TEST-0052 | Runtime integrity checks (memory / stack) |
| MASTG-TEST-0053 | No sensitive data in logs (cross-ref Storage) |

## Privacy (MASVS-PRIVACY)

| MASTG test | What it asserts |
|------------|-----------------|
| MASTG-TEST-0054 | Minimal data collection (no over-asking) |
| MASTG-TEST-0055 | User consent for tracking |
| MASTG-TEST-0056 | No third-party SDKs that exfiltrate data |
| MASTG-TEST-0057 | Opt-out for analytics |
| MASTG-TEST-0058 | No device fingerprinting |

## Techniques (cross-cutting)

- **MASTG-TECH-0005** — Static analysis (use
  `android-re-static-triage` + `android-re-native-triage`)
- **MASTG-TECH-0006** — Dynamic analysis (use
  `android-re-dynamic-hook`)
- **MASTG-TECH-0007** — Network interception (use
  `android-re-network-intercept`)

## Cross-walking in the report

When the report says "MASVS-PLATFORM-1: FAIL", add the
corresponding MASTG test IDs:

```markdown
| MASVS Control | Status | MASTG tests | Evidence |
|---------------|--------|-------------|----------|
| MASVS-PLATFORM-1 | FAIL | MASTG-TEST-0030 | com.example/.SecretActivity exported=true |
```

The full MASTG is at https://github.com/OWASP/mastg. Update the
control ID → test ID mapping when new tests land.
