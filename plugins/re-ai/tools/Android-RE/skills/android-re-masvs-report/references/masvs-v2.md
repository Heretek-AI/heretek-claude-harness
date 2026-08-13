# MASVS v2 Control Reference

The OWASP MASVS v2 controls relevant to Phase 1 of Android-RE. The
`android-re-masvs-report` skill maps static-triage findings to these
controls.

## MASVS-STORAGE — Secure storage of sensitive data

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-STORAGE-1         | The app does not store sensitive data unless strictly necessary |
| MASVS-STORAGE-2         | The app does not store sensitive data in plaintext          |
| MASVS-STORAGE-3         | The app removes sensitive data from views when backgrounded |

Phase 1 surfaces MASVS-STORAGE-2 only via `<meta-data>` and
`sharedUserId` checks; full coverage requires source review (Phase 2).

## MASVS-CRYPTO — Cryptographic functionality

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-CRYPTO-1         | The app does not use insecure crypto algorithms            |
| MASVS-CRYPTO-2         | The app performs key derivation with proper parameters    |
| MASVS-CRYPTO-3         | The app uses strong random number generation              |
| MASVS-CRYPTO-4         | The app does not reuse keys across distinct purposes      |

Not covered by Phase 1. Requires source review (Phase 2).

## MASVS-AUTH — Authentication and authorization

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-AUTH-1           | The app uses secure authentication mechanisms             |
| MASVS-AUTH-2           | The app uses secure authorization mechanisms              |
| MASVS-AUTH-3           | The app uses secure session management                    |
| MASVS-AUTH-4           | The app implements biometric authentication securely      |
| MASVS-AUTH-5           | The app does not rely on insecure communication channels for authentication |
| MASVS-AUTH-6           | The app does not use SMS as the sole factor for authentication |
| MASVS-AUTH-7           | The app does not use push notifications as the sole factor for authentication |
| MASVS-AUTH-8           | The app uses an attestation mechanism to detect compromised devices |
| MASVS-AUTH-9           | The app uses certificate pinning for authentication       |
| MASVS-AUTH-10          | The app uses proper account management                    |
| MASVS-AUTH-11          | The app enforces session timeout                          |

Not covered by Phase 1. Requires dynamic analysis (Phase 3+).

## MASVS-NETWORK — Secure network communication

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-NETWORK-1         | The app uses TLS for all network communication             |
| MASVS-NETWORK-2         | The app performs certificate validation                    |
| MASVS-NETWORK-3         | The app uses strong cryptographic algorithms               |

Phase 1 surfaces MASVS-NETWORK-1 via `usesCleartextTraffic` and
`networkSecurityConfig` analysis.

## MASVS-PLATFORM — Secure interaction with the platform

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-PLATFORM-1         | The app uses IPC mechanisms safely                        |
| MASVS-PLATFORM-2         | The app uses WebViews safely                              |
| MASVS-PLATFORM-3         | The app uses the user interface safely                     |

Phase 1 surfaces MASVS-PLATFORM-1 via exported-component and
intent-filter analysis.

## MASVS-CODE — Code quality and build

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-CODE-1            | The app is signed and the signature is valid              |
| MASVS-CODE-2            | The app is built in release mode with appropriate compiler flags |
| MASVS-CODE-3            | The app uses memory-safe languages                        |
| MASVS-CODE-4            | The app uses free security features (PIE, ARC, etc.)      |

Phase 1 surfaces MASVS-CODE-1 (signature verification) and
MASVS-CODE-2 (`debuggable` attribute).

## MASVS-RESILIENCE — Resilience to reverse engineering

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-RESILIENCE-1       | The app detects rooted devices                            |
| MASVS-RESILIENCE-2       | The app detects emulators                                 |
| MASVS-RESILIENCE-3       | The app detects tampering                                |
| MASVS-RESILIENCE-4       | The app detects debugging                                |
| MASVS-RESILIENCE-5       | The app detects reverse engineering tools                 |
| MASVS-RESILIENCE-6       | The app implements anti-tampering                        |
| MASVS-RESILIENCE-7      | The app implements obfuscation                           |
| MASVS-RESILIENCE-8      | The app uses device attestation                          |
| MASVS-RESILIENCE-9      | The app uses runtime integrity checks                    |
| MASVS-RESILIENCE-10     | The app does not log sensitive data                       |
| MASVS-RESILIENCE-11     | The app does not have known vulnerabilities              |
| MASVS-RESILIENCE-12     | The app uses a tested cryptographic library               |
| MASVS-RESILIENCE-13     | The app uses unique keys and certificates                 |

Not covered by Phase 1. Requires dynamic analysis (Phase 3) and the
native MCP server (Phase 2).

## MASVS-PRIVACY — Privacy controls

| Control                 | What it asserts                                           |
|-------------------------|------------------------------------------------------------|
| MASVS-PRIVACY-1         | The app minimizes access to sensitive data                |
| MASVS-PRIVACY-2         | The app does not share user data with third parties without consent |
| MASVS-PRIVACY-3         | The app does not log sensitive data                       |
| MASVS-PRIVACY-4         | The app uses privacy-respecting analytics                 |

Phase 1 surfaces MASVS-PRIVACY-1 partially via dangerous-permission
enumeration.

## Severity rating convention

Findings are rated using the MASTG convention:

- **Critical** — Direct, exploitable vulnerability with severe impact.
- **High** — Vulnerability with significant impact under realistic conditions.
- **Medium** — Vulnerability with notable impact, exploitation is constrained.
- **Low** — Vulnerability with limited impact or requires unusual conditions.
- **Info** — Best-practice violation; not directly exploitable.
