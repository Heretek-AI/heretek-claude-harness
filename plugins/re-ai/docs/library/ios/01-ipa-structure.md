---
title: "IPA Structure"
category: "ios"
platforms: ["ios", "macos"]
difficulty: "beginner"
tags: ["fundamentals", "static-analysis", "packaging"]
summary: "How an iOS App Package is laid out on disk: the ZIP container, Info.plist, embedded mobile provision, the Mach-O binary, and the bundles and frameworks it ships with."
updated: "2026-06-04"
related: ["ios/02-objc-runtime", "ios/03-swift-demangling", "ios/05-frida-ios"]
---

## Summary

An IPA is a ZIP archive with a well-defined internal layout. Knowing the shape of an IPA — and the metadata the App Store / device use to decide whether to launch it — is the prerequisite for almost every other iOS RE task.

## Why this matters

Every tool you'll use — `unzip`, `otool`, `class-dump`, Hopper, Ghidra, frida-ios-dump, objection — reads the same on-disk structure. The moment you can navigate an IPA by hand, you can validate what tools are telling you.

## Mechanics

The high-level layout of an IPA:

```
MyApp.ipa                (a ZIP file; conventionally named .ipa)
└── Payload/
    └── MyApp.app/       (a "bundle" directory; name matches the executable)
        ├── MyApp                   # the Mach-O executable
        ├── Info.plist              # text plist; metadata, supported devices
        ├── PkgInfo                 # 8-byte APPL???? stub (legacy)
        ├── embedded.mobileprovision # dev certs + entitlements + UDIDs
        ├── _CodeSignature/
        │   └── CodeResources       # v1 signing manifest
        ├── Frameworks/             # embedded private frameworks
        ├── PlugIns/                # app extensions (.appex)
        ├── en.lproj/ …             # localised resources
        ├── Assets.car              # compiled asset catalog
        └── *.dylib, *.nib, images, … # arbitrary resource files
```

A few details that surprise people the first time:

- `Info.plist` is a text plist (XML or binary; `plutil -convert xml1` makes it readable). The most important keys for RE: `CFBundleExecutable` (the binary to load), `CFBundleIdentifier`, `MinimumOSVersion`, and `LSRequiresIPhoneOS`.
- `embedded.mobileprovision` is a CMS-signed plist listing the team, entitlements, and (for development) allowed device UDIDs. `security cms -D -i embedded.mobileprovision` decodes it.
- The Mach-O binary is at the bundle root, **not** in a `Contents/MacOS/` subdirectory (which is the macOS .app convention — iOS uses a flat bundle).
- The binary's load commands are critical: `LC_LOAD_DYLIB` entries tell you which system frameworks and embedded private frameworks the app links against, and `LC_CODE_SIGNATURE` points to the signature blob appended after the load commands.
- iOS apps ship **embedded private frameworks** under `Frameworks/` (e.g. `MyApp.framework/MyApp` plus `MyApp.framework/Info.plist`). These are themselves bundles-with-a-binary, and the binary is just another Mach-O you can `otool -L` on.
- App extensions are sibling `.appex` bundles under `PlugIns/`. They run in a separate process; calls into the host app go through `NSExtensionContext`.

## Approach

For a first pass on an unknown IPA:

1. `unzip -l target.ipa` to see the layout. Look for `Frameworks/` (private frameworks are a rich target), `PlugIns/`, and `Assets.car` (compiled assets — `Asset Catalog Tinkerer` can unpack them).
2. `plutil -convert xml1 -o - Payload/MyApp.app/Info.plist` to read the bundle metadata.
3. `security cms -D -i Payload/MyApp.app/embedded.mobileprovision` to see the entitlements and signing chain.
4. `otool -L Payload/MyApp.app/MyApp` to see what the binary links against. System frameworks start with `/System/Library/...` or `/usr/lib/...`; embedded frameworks start with `@rpath/`.
5. `otool -l Payload/MyApp.app/MyApp | grep -A 5 LC_CODE_SIGNATURE` to find the signature blob.
6. For decompiled ObjC: `class-dump` the binary, or open it in Hopper / Ghidra (the latter has a Mach-O loader and an ObjC class reconstruction pass).
7. For Swift: combine `class-dump` (limited Swift coverage) with Swift demangling (`swift demangle` from the Swift toolchain, or Ghidra's Swift plugin).

## Common pitfalls

- **Treating class-dump output as authoritative.** The class-dump is reconstructed from the ObjC metadata section; it's not the original header. Some methods will be missing (especially those that the compiler eliminated).
- **Hoping for the Swift type info to be useful.** Swift strips a lot of metadata into the binary's Mach-O `__swift5_*` sections, but private types and inlined generics can be heavily mangled. Plan to read the disassembly for high-stakes claims.
- **Missing embedded frameworks.** A malicious-looking or interesting function in the *main* binary may actually be calling into an embedded framework that you haven't pulled apart yet.
- **Assuming the .ipa extension is required.** It's a ZIP; the App Store, Xcode, and `ios-deploy` all use the same on-disk layout. Renaming to `.zip` lets you `unzip` it on Linux.
- **Running on the wrong OS.** Mach-O is also the macOS executable format; many of the same tools (otool, class-dump, Hopper) work on macOS binaries. The differences are in load commands and dyld semantics, not the basic layout.

## Tooling pointers

- `otool` and `class-dump` — first-pass binary inspection (both ship with Xcode's command-line tools, and there are Linux ports).
- Hopper, Ghidra, Binary Ninja — full disassembly + ObjC class reconstruction.
- `plutil`, `security` — reading plist and CMS blobs from the command line.
- frida-ios-dump / objection — for runtime introspection once the app is on a device.

## References

- [Apple: Bundle Structure](https://developer.apple.com/documentation/bundleresources/bundle-structures)
- [Apple: Mach-O Programming Topics](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/MachORuntime/)
- [class-dump](https://github.com/nomad-software/class-dump)
