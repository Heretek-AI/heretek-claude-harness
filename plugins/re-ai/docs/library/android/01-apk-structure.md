---
title: "APK Structure"
category: "android"
platforms: ["android"]
difficulty: "beginner"
tags: ["fundamentals", "static-analysis", "packaging"]
summary: "How an Android Package is laid out on disk: the ZIP container, AndroidManifest, dex files, resources, and the native libraries that ship alongside."
updated: "2026-06-04"
related: ["android/02-smali-basics", "android/03-native-libs", "android/06-repackaging"]
---

## Summary

An APK is a ZIP archive with a well-defined internal layout. Knowing where every artifact lives is the prerequisite to almost every other Android RE task.

## Why this matters

Every tool you'll use — `apktool`, `jadx`, `unzip`, `aapt2`, frida, ghidra, IDA — reads the same on-disk structure. The moment you can navigate an APK by hand, you stop being dependent on tooling rendering it correctly.

## Mechanics

The high-level layout of an APK:

```
my-app.apk
├── AndroidManifest.xml      # binary XML; resources, components, permissions
├── classes.dex              # primary dex (Java/Kotlin compiled to dex)
├── classes2.dex ...         # multidex; older devices required classes2+
├── lib/                     # native libraries
│   ├── arm64-v8a/
│   ├── armeabi-v7a/
│   ├── x86/
│   └── x86_64/
├── assets/                  # arbitrary files; read via AssetManager
├── res/                     # compiled resources (resources.arsc + per-type)
├── resources.arsc           # the resource table; string pools, style refs
├── META-INF/                # signing artefacts (CERT.RSA, MANIFEST.MF, *.SF)
└── kotlin/                  # Kotlin metadata (if any)
```

A few details that surprise people the first time:

- `AndroidManifest.xml` is **binary XML** (AXML), not text. `apktool` decodes it; `aapt2 dump xmltree` works for spot-checks.
- `resources.arsc` is a separate index from the per-resource files in `res/`. Resource IDs (the `R.id.foo` ints you see in smali) are indices into this table.
- The dex format is little-endian and very compact; strings, types, methods, and fields are all pool-indexed. A `classes.dex` is effectively a serialized symbol table plus bytecode.
- Native libraries under `lib/<abi>/` are loaded by `System.loadLibrary("name")` from the `app`'s default classloader. Stripped or unstripped is a per-build-flag choice.
- `META-INF/CERT.RSA` and `MANIFEST.MF` are v1 signing artefacts; v2+ signatures live in a special block *between* ZIP entries and the central directory. Tools that don't understand v2/v3 (or that mangle them) will silently break signature verification.

## Approach

For a first pass on an unknown APK:

1. `unzip -l target.apk` to see the layout. Skim for `lib/`, `assets/`, anything unusual.
2. `aapt2 dump badging target.apk` (or `aapt dump badging` on older toolchains) to get the package name, version, target SDK, and permissions.
3. `apktool d target.apk -o out/` to decode everything to a directory tree of text XML, smali, and resource stubs. This is the canonical "I want to read the source" step.
4. For decompiled Java/Kotlin rather than smali: `jadx -d out-jadx target.apk`. jadx is a dex decompiler; it does best-effort reconstruction and falls back to smali for the parts it can't recover.
5. For native code: pull `lib/<abi>/*.so` out and load them in Ghidra / IDA / Binary Ninja directly. They are standard ELF.

## Common pitfalls

- **Treating the smali you see as canonical.** It's decompiled; the original may have had different control flow that the decompiler collapsed. Always check the dex for high-stakes claims.
- **Assuming `res/` is the source.** It's the *compiled* output. The actual XML sources live in the developer's build tree, not in the APK.
- **Multidex and `classes.dex` only.** Tools that walk "the dex file" will miss `classes2.dex`, `classes3.dex`, etc.
- **v2/v3 signature tampering.** Repackaging a signed APK will invalidate the v2+ block; you must re-sign with `apksigner` (or `jarsigner` for v1-only).
- **Resource ID collisions across packages.** Merged manifests and resource overlays can change IDs at build time; never hardcode resource IDs across builds.

## Tooling pointers

- [`apktool`](../tools/01-apktool.md) — decode and rebuild APKs.
- [`jadx`](../tools/02-jadx.md) — dex → Java decompiler.
- Ghidra / IDA / Binary Ninja — for the native libs.
- `aapt2` (Android SDK build-tools) — manifest and resource inspection from the CLI.

## References

- [Android docs: App Bundle / APK format](https://developer.android.com/build/building-an-app-bundle)
- [APK Signature Scheme v2 / v3](https://source.android.com/docs/security/features/apksigning)
- [DEX format (dalvik-bytecode)](https://source.android.com/devices/tech/dalvik/dex-format)
