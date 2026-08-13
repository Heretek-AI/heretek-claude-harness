# OWASP MASTG CrackMe Level 1 walkthrough

A minimal worked example for the OWASP MASTG CrackMe Level 1
Android challenge. CrackMes are intentionally-protected apps
designed for learning reverse engineering; the goal is to find
a hidden secret.

## Setup

1. Fetch the CrackMe APK:
   ```bash
   bin/pull-crackme.sh
   ```
   (This script lands in a follow-up; for now, download from
   https://github.com/OWASP/mastg/tree/master/Crackmes/Android)
2. Drop the APK at `tests/fixtures/owasp-mastg-crackme-level1.apk`.

## Walkthrough

### Static approach

```text
> /android-re-decompile
> Decompile the MainActivity of the CrackMe and show me the
> secret-check logic.
```

The CrackMe's secret check is in
`sg.vantagepoint.a.MainActivity`. After jadx decompile, you'll
see something like:

```java
public void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    setContentView(C0254R.layout.activity_main);
    if (getSecret().equals("hidden_value")) {
        // success
    }
}
```

The `getSecret()` is a simple string concat in
`sg.vantagepoint.a.a` (or similar). The `android-re-decompile`
skill returns the source.

### Dynamic approach

```text
> /android-re-dynamic-hook
> Hook the success check on the running CrackMe and print the
> secret.
```

Spawn the app, hook the equality check, dump the secret.

### Native approach

The string might also be in `lib/arm64-v8a/libnative.so` if the
CrackMe is built with a native method. Use
`android-re-native-triage` to read the strings.

## Files produced

None — this is a learning exercise. The deliverable is
understanding the workflow.

## Notes

- Real-world reverse engineering rarely requires *finding* a
  secret; more often the goal is to find a *vulnerability*
  (e.g. an exposed content provider). The CrackMe is a
  simplified target.
- For a more advanced challenge, see the OWASP MASTG
  CrackMe Level 2.
