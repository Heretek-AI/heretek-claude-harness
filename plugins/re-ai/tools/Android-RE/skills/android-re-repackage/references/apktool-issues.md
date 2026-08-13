# apktool issues & workarounds

apktool round-tripping is generally reliable but has known edge cases.
This document lists the issues that the `android-re-repackage` skill
is most likely to surface, and how to handle them.

## "Manifest is corrupt" after rebuild

Some APKs use a binary AXML form that apktool's decoder doesn't
fully understand. Symptoms:

- `apktool b` exits 0, but the rebuilt APK fails to install with
  `INSTALL_PARSE_FAILED_MANIFEST_MALFORMED`.
- `apktool.yml` shows an unknown `unknown-files` entry.

Workaround:

- Use the `--use-aapt2` flag (apktool 2.9.0+). This re-encodes the
  manifest with Google's aapt2 instead of apktool's homegrown
  encoder. Phase 2 does not yet expose this flag; Phase 3 will.
- Alternatively, run aapt2 directly:

  ```bash
  aapt2 link -o unsigned.apk -I android.jar --manifest AndroidManifest.xml
  ```

## Resources missing in the rebuilt APK

If the APK was signed with v2/v3 schemes and apktool didn't decode
the signing block, the rebuilt APK loses its signature. This is
expected. Re-sign with apksigner or uber-apk-signer.

```bash
apksigner sign --ks debug.keystore --ks-pass pass:android unsigned.apk
```

## Smali syntax errors after a manual edit

Common pitfalls when hand-editing smali:

- Forgetting a `.method` or `.end method` directive.
- Using a class name without the leading `L` or trailing `;`.
- Mismatched register widths (`p0` vs `p0, p0`).

Always run `apktool b` after each edit; the error messages are
informative.

## Method-too-large errors

If the rebuilt DEX has a method that exceeds the 64 KB limit (rare
on modern Android, common on large smali-patched methods), apktool
will fail with `Method ... not in range`. Phase 3 will add a
workaround using `dx --no-files` to split the method.

## The "framework" tag

Some OEM APKs declare a framework reference that apktool cannot
resolve:

```text
<application android:name="com.example.android.app.somecomponent"/>
```

This is usually safe; the rebuild succeeds. The `unknown-files` list
will include the framework JAR. To silence the warning, install the
OEM framework JAR with `apktool if framework.jar`.

## Debugger-detection of the repackaged APK

If the original APK has anti-tamper / anti-RE checks, the repackage
itself may break the app. The rebuilt APK's signature differs from
the original, and many apps embed the signing certificate hash
somewhere as a tamper check.

If the app refuses to start after repackaging, see the
`android-re-secrets-scan` skill output for embedded cert fingerprints
and compare to the new signature.
