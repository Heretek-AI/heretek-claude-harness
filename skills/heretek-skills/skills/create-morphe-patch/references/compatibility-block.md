# Compatibility block

`Compatibility` declares which app, which versions, and which signing certificates a patch targets. Without it, the patch is **universal** — runs against any package.

## Capturing the signature

The `signatures` set contains SHA-256 fingerprints of the APKs the patch accepts. Use the **delegated signer** (the certificate the Play Store uses to sign the APK), not the upload cert.

```bash
# Run from the skill's scripts/ directory:
bash scripts/compute-signature.sh path/to/base.apk
# Output: one line of hex.
```

Or manually:

```bash
apksigner verify --print-certs path/to/base.apk
# Look for "Signer #1 certificate DN" → "SHA-256 Digest: <hex>"
```

> ⚠️ For `.apkm`/`.xapk` archives, unzip and run on the inner `base.apk`. The SHA-256 must match the cert Play Store delegates.

## Defining Compatibility

```kotlin
val COMPATIBILITY_XYZ = Compatibility(
    packageName = "app.xyz.mobile",
    name = "XYZ App",
    description = "Optional user-facing description.",
    apkFileType = ApkFileType.APK_REQUIRED,   // or APK_OPTIONAL, APKM, etc.
    appIconColor = 0xFF3300,                  // ARGB int, only used for Manager UI.
    signatures = setOf("6e21a5f966a7252628cd8f5982d93086a0fcf76c09edb9d7731964bb1c842897"),
    targets = listOf(
        AppTarget(version = "2.0.0"),
        AppTarget(version = "1.0.42"),
    ),
)
```

## Fields

| Field | Type | Required | Purpose |
|---|---|---|---|
| `packageName` | `String` | Yes (unless universal) | Android application ID. |
| `name` | `String` | Yes (if `packageName`) | App name shown in the Manager UI. |
| `description` | `String?` | No | User-facing app description. |
| `apkFileType` | `ApkFileType` | No | `APK_REQUIRED`, `APK_OPTIONAL`, `APKM`, `APKM_REQUIRED`, etc. |
| `appIconColor` | `Int` (0xRRGGBB) | No | Background color for the app icon in the Manager UI. |
| `signatures` | `Set<String>` | No | SHA-256 allowed cert digests. |
| `targets` | `List<AppTarget>` | Yes | Versions supported. |

## Universal patch

If the patch is not app-specific, declare it without a `packageName`:

```kotlin
val universalPatch = bytecodePatch(name = "Generic patch") {
    // No compatibleWith → runs against any package.
}
```

## AppTarget

Each `AppTarget` declares a version. Newest first.

```kotlin
AppTarget(version = "2.0.0")                    // Any device with v2.0.0.
AppTarget(version = "1.0.42", minSdk = 32)     // v1.0.42 requires SDK 32+.
AppTarget(version = "1.0.42", versionCode = 12345)  // Specific release.
AppTarget(version = null)                      // Any version (default).
```

By default, `targets` is `listOf(AppTarget(version = null))` — meaning "any version of the package." Override with a list of explicit versions.

## ApkFileType

Specify whether the patch needs a `.apk` or accepts `.apkm`/`.xapk`/`.apks`:

- `APK_REQUIRED` — cannot process `.apkm` directly.
- `APK_OPTIONAL` — accepts `.apk`; `.apkm` may work but is not preferred.
- `APKM_REQUIRED`, `APKM` — `.apkm` (split APKs).
- `APKS_REQUIRED`, `APKS` — `.apks` (Google bundle).
- `XAPK_REQUIRED`, `XAPK` — `.xapk` (third-party split).

The `_REQUIRED` variants tell the Manager UI to refuse other types.

## Validation rules

The `Compatibility` constructor enforces these constraints:

- `packageName` must match the Android package name regex (if present).
- `appIconColor` must be `0xRRGGBB` (alpha = 0).
- `signatures` must be valid 64-hex SHA-256 strings.
- `targets` must not be empty.
- No duplicate `version` values in `targets`.
- A universal patch (null `packageName`) cannot declare any version targets.

## How to bump a version

When a new app release ships:

1. Update `targets` with the new `AppTarget(version = "X.Y.Z")`. Newest first.
2. If the signing cert rotated, update `signatures` with the new delegated signer SHA-256.
3. Rebuild. `./gradlew :patches:generatePatchesList` will reflect the change.

## Fingerprint compatibility

If your patch's `Fingerprint` matches the same method across multiple versions, you only need one patch. If the implementation differs per version, you typically need:

- One `AppTarget` per version with the same `compatibleWith`, OR
- Multiple patch entries each declared with its own `compatibleWith`.
