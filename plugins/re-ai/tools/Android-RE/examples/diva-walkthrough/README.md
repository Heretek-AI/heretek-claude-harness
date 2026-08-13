# DIVA (Damn Insecure and Vulnerable App) walkthrough

A worked example showing how to use Android-RE to triage a
known-vulnerable Android app. **DIVA** is an intentionally
vulnerable app maintained by Dinesh Shetty
(https://github.com/payatu/diva-android). Use it to validate
that the skills and tools produce the expected findings.

## Setup

1. Install DIVA on a rooted device or emulator:
   ```bash
   adb install diva-beta.apk
   ```
2. Install the DIVA APK as a fixture:
   ```bash
   cp diva-beta.apk tests/fixtures/
   ```

## Walkthrough

### Step 1: Static triage

```text
> /android-re-static-triage
> Triage tests/fixtures/diva-beta.apk.
```

The triage surfaces:
- The `com.jeeva..diva.DivaActivity` is exported and
  reachable from any app.
- `usesCleartextTraffic=true` is set, allowing plain HTTP.
- The `IS_LOGGED_IN` SharedPreferences key contains hard-coded
  flag values.

### Step 2: Native triage

```text
> /android-re-native-triage
> Triage tests/fixtures/diva-beta.apk.
```

DIVA ships an `armeabi/libdiva.so` with hard-coded URL paths.
The native triage reports:
- Format: ELF, armv7
- NX: enabled, PIE: enabled, RELRO: partial
- Strings containing `http://payatu.com`

### Step 3: MASVS report

```text
> /android-re-masvs-report
> Produce a MASVS report for tests/fixtures/diva-beta.apk.
```

Expected findings:
- **MASVS-PLATFORM-1: FAIL** — `DivaActivity` exported with no
  permission gate.
- **MASVS-NETWORK-1: FAIL** — cleartext traffic permitted.
- **MASVS-STORAGE-2: FAIL** (after dynamic decompile) — `notes`
  SharedPreferences written in plaintext.
- **MASVS-CODE-1: PASS** (with v1 signing detected).

### Step 4: Dynamic hook

```text
> /android-re-dynamic-hook
> Hook Lcom/jeeva/diva/AccessActivity;.onCreate on com.jeeva.diva.
> Show me the Intent extras.
```

The DIVA "Access Control" issues (Issue 1-3) each launch a
component by name. Hooking the activity's `onCreate` and
printing the intent extras demonstrates that any app can
launch `DivaActivity` with arbitrary data.

### Step 5: SSL pinning bypass + MITM

```text
> /android-re-network-intercept
> Set up mitmproxy at 10.0.2.2:8080 and capture com.jeeva.diva.
```

DIVA does not pin certificates, so the bypass script is
redundant — the captures work without it. Real apps with
pinning will require both the bypass and the cert install.

## Expected timeline

| Step | Time |
|------|------|
| Static triage | 30-60 s |
| Native triage | 5-10 s |
| MASVS report | 1-2 s |
| Dynamic hook | 30-60 s (spawn + load + first call) |
| MITM setup | 1-2 min (cert install + reboot) |

## Files produced

After the walkthrough, your `./.triage/` directory contains:

- `triage-<id>.md` — the MASVS-aligned report
- `triage-<id>.sarif` — the SARIF document
- `network-<id>/` — captures (if MITM was run)

## Adapting for your own APK

The same workflow applies to any APK:

1. Drop the APK at `tests/fixtures/your-app.apk`.
2. Run each skill in order.
3. Compare the findings against your threat model.
4. Hand the report to the dev team (or the vendor, for
   vulnerability disclosure).

## Notes

- DIVA is intentionally vulnerable; the findings are
  expected. Use this walkthrough to *validate* the toolchain,
  not to discover novel issues.
- For a real audit, use the **DIVA classics** (also
  available on GitHub) — a less-known variant with more
  categories of vulnerabilities.
