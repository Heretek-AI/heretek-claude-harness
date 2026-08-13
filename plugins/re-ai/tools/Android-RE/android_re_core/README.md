# android-re-core

Shared Python library for Android reverse engineering. This is the internal
core that every Python MCP server (`android-re-static`, `android-re-native`,
`android-re-dynamic`, `android-re-triage`) imports from.

## What it provides

| Module                       | Purpose                                                       |
|------------------------------|----------------------------------------------------------------|
| `android_re_core.project`    | Central `Project` state object; the `ProjectStore` registry.  |
| `android_re_core.apk`        | androguard 4.1.4 wrapper with zip-bomb guards.                 |
| `android_re_core.manifest`   | Decoded manifest view, intent filters, exported components.    |
| `android_re_core.dex`        | DEX class / method / xref queries.                              |
| `android_re_core.certs`      | Signing-scheme + certificate chain extraction.                  |
| `android_re_core.errors`     | Typed exception hierarchy.                                      |
| `android_re_core.paths`      | Locates vendored tools (jadx, apktool, …).                     |
| `android_re_core.native`     | LIEF-based native binary analysis (Phase 2).                    |
| `android_re_core.smali`      | apktool-based smali decode/build (Phase 2).                     |
| `android_re_core.sources`    | jadx-based Java decompilation (Phase 2).                        |
| `android_re_core.frida`      | frida session lifecycle, RPC, script loading (Phase 3).         |
| `android_re_core.device`     | ADB + emulator helpers (Phase 3).                               |
| `android_re_core.reporting`  | MASVS v2 mapping, SARIF emission (Phase 2).                     |
| `android_re_core.secrets`    | apkleaks and rules engine (Phase 2).                            |
| `android_re_core.store`      | SQLite triage state store (Phase 4).                            |

## Pinned versions

| Dependency        | Version     | Why pinned                          |
|-------------------|-------------|-------------------------------------|
| `androguard`      | 4.1.4       | API churn in 4.x vs 3.x             |
| `lief`            | 0.17.6      | ELF API changes between minor ver.  |
| `frida`           | 17.10.1     | Server/client version match         |
| `cryptography`    | >=44.0      | Modern API for cert validation      |

## Versioning

This package follows semver and is versioned **independently** from the
monorepo top-level tag (which mirrors it in v0.1.x for simplicity).
Breaking changes are flagged with a minor bump (0.x → 0.(x+1).0).

## License

Apache-2.0. See `LICENSE` in the monorepo root.
