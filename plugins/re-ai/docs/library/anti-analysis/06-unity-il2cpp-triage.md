---
title: "Unity IL2CPP Game Triage Workflow"
category: "anti-analysis"
platforms: ["windows", "linux", "macos"]
difficulty: "intermediate"
tags: ["unity", "il2cpp", "triage", "static-analysis", "metadata", "global-metadata"]
summary: "A first-pass workflow for triaging an unknown Unity IL2CPP game — confirm the IL2CPP runtime, recover the publisher's class graph from the unprotected global-metadata.dat, identify the protection layers, and decide which category-level entries apply."
updated: "2026-06-05"
related: ["anti-analysis/01-anti-debug", "anti-analysis/02-vm-bytecode-interpreter", "anti-analysis/05-launcher-activation-fingerprinting", "tools/01-ghidra"]
---

## Summary

Unity ships two managed runtimes: Mono (C# → CIL → JIT) and IL2CPP (C# → C++ → AOT). Most commercial Unity games use IL2CPP for performance and to make dynamic code-analysis tooling less effective. Triaging a Unity IL2CPP game means *first* recovering the publisher's class graph (which the runtime leaves unprotected), *then* identifying the protection layers around the AOT-compiled C++ binary.

## Why this matters

`global-metadata.dat` is **unprotected**. The magic at offset 0x00 is `0xFAB11BAF`. The version at offset 0x04 is 24-29 in modern Unity. The file is 10-20 MB. It contains 400,000+ string entries covering the publisher's full class graph — every Assembly-CSharp class, every method name, every field name, every type namespace.

The publisher's class graph is recoverable *without* defeating any protection layer. The AOT binary is encrypted-VM-wrapped, stripped, or otherwise hostile to static analysis; the metadata is sitting in plain text in a sibling file.

A common analyst mistake is to spend hours reverse-engineering `GameAssembly.dll` function prologues when the same information is sitting in the metadata file. Recover the class graph first; use it as a map for the AOT binary analysis.

## Mechanics

### The Unity IL2CPP install layout

A typical Unity IL2CPP install on Windows:

```
<install_dir>/
├── GameAssembly.dll           # AOT-compiled C++ (50-500 MB; size is a signal)
├── UnityPlayer.dll            # The Unity engine (28 MB on this version)
├── baselib.dll                # Unity's low-level OS shims (~500 KB)
├── dbdata.dll                 # Unity Burst helper (~1 MB)
├── UnityCrashHandler64.exe     # Unity's crash reporter
├── Game.exe        # The launcher (5 imports; small forwarder)
├── Core/
│   ├── Activation64.dll       # The launcher activation library (3 MB; ordinal-only exports)
│   └── Activation.dll         # 32-bit sibling of Activation64.dll
└── Game_Data/
    ├── app.info               # 26 bytes, build id
    ├── boot.config            # 120 bytes, gfx/GC settings
    ├── globalgamemanagers     # ~340 KB
    ├── globalgamemanagers.assets
    ├── globalgamemanagers.assets.resS
    ├── il2cpp_data/
    │   └── Metadata/
    │       └── global-metadata.dat    # 10-20 MB; THE unprotected class graph
    ├── level0..levelN          # Unity level bundles
    ├── resources.assets
    └── sharedassets*.assets
```

The same layout works on Linux (`.so` for `GameAssembly`, `GameAssembly.so`) and macOS (`.dylib`). The protection composition is identical across platforms.

### The AOT binary size is a signal

A normal Unity IL2CPP game is 30-80 MB. An encrypted-VM bytecode-wrapped one is 200+ MB. The size delta is the encrypted bytecode region in the W^X `.idata` (or the equivalent in the platform-specific section name set). Anything over 100 MB on Windows is a *signal* to check the section list for the 7-observable composition in the encrypted-VM bytecode interpreter entry.

### The metadata header

```
offset  field                  meaning
------  -----                  -------
0x00    sanity                 0xFAB11BAF (little-endian) — the unprotected magic
0x04    version                24..29 in modern Unity; 24=Unity 2019, 27=2020, 29=2021+
0x08    stringLiteralDataOffset
0x0C    stringLiteralDataCount
0x10    stringOffset
0x14    stringCount            typically 400,000+
```

If the magic is `0xFAB11BAF`, the metadata is unprotected. There is no encryption / no obfuscation to defeat.

### The class graph table

The metadata's `typeDefinitions` table is the publisher's class graph. Walk it with `re-il2cpp.get_type_definitions` to enumerate every type. The publisher's `Assembly-CSharp` is one image; standard Unity / Asset-Store libraries (`UnityEngine.*`, `Unity.Mathematics.*`, `Rewired.*`, `Cinemachine`, `Aura2_Core`, etc.) are other images. Knowing which is which is the triage result.

A typical publisher namespace:

```
<Publisher>.Core              (the primary class library)
<Publisher>.Hierarchy          (scene-graph helpers)
<Publisher>.Performance        (profiling / optimization)
<Publisher>.Editor             (editor-only utilities; stripped from builds)
```

Namespaces that are publisher-specific (not standard Unity / Asset-Store) are the *publisher's* code. Filter out the rest.

### Sibling files that signal protection layers

- `Core/Activation*.dll` — the launcher activation fingerprinting library (3 MB; ordinal-only exports). See the launcher activation entry.
- `__Installer/Cleanup.exe` and `__Installer/Touchup.exe` — installer clean-up utilities. Not protection; just installer scaffolding.
- `Support/` — localized EULA and help docs. Not protection; not part of the triage.

### The protection-layer map

Once you've found the metadata, walked the class graph, and checked the AOT binary size, you have a *protection-layer map*:

| Observation | Implied layer | Follow-up entry |
|---|---|---|
| 4+ of the 7 encrypted-VM section names; 8+ HWID APIs in the AOT binary; `WaitForActivation`-style export tail | Encrypted-VM bytecode interpreter | `anti-analysis/02-vm-bytecode-interpreter` |
| `Core/Activation*.dll` present; 1-3 MB; ordinal-only exports; 8+ HWID APIs in the activation DLL | Launcher activation fingerprinting | `anti-analysis/05-launcher-activation-fingerprinting` |
| Both | Layered — both categories are firing | Both entries |
| Neither | Plain Unity IL2CPP, no protection layer | Triage complete; static analysis is straightforward |

## Approach

1. **Find the metadata** — `find . -name 'global-metadata.dat'`. Read the magic at offset 0 and the version at offset 4. If the magic is `0xFAB11BAF`, the metadata is unprotected.
2. **Recover the class graph** — `re-il2cpp.list_namespaces`, `re-il2cpp.get_type_definitions`, `re-il2cpp.get_assembly_types`. The publisher's `Assembly-CSharp` is the surface; the standard Unity / Asset-Store libraries are noise to filter out.
3. **Check the AOT binary size** — anything over 100 MB on Windows is a *signal*; check the section list for the 7-observable composition.
4. **Check for sibling activation libraries** — `find . -name '*.dll' -size -5M -size +500k` is a rough heuristic. Anything matching is the launcher activation fingerprinting library.
5. **Run `re-lief.categorize_strings`** on every DLL in the install. The combined `by_category` output is the protection-layer map.
6. **Defer decompilation of the AOT binary** until you know which protection layer(s) you're looking at. Decompiling a 500 MB VM-wrapped binary without first identifying the VM dispatcher is the analysis trap.

## Common pitfalls

- **Skipping the metadata** because the binary is 500 MB and the analysis queue is long. The metadata is *the cheapest signal you'll get*.
- **Treating the AOT binary as a normal PE/ELF/Mach-O.** The section names, characteristics, and import patterns may be shaped by the protection layer, not by the Unity runtime.
- **Conflating "Unity game" with "no protection".** Most commercial Unity games ship with at least one anti-tamper layer; the question is which one(s), not whether.
- **Forgetting cross-platform builds.** A Windows-`GameAssembly.dll` is the same protection composition as a Linux-`GameAssembly.so`; if the analyst has both, diffing the two is a structural characterization of the protection layer.
- **Walking the typeDefinitions table for a 530 MB binary directly.** `re-il2cpp.get_type_definitions` reads the metadata, not the AOT binary — the typeDefs table is in the unprotected metadata file. Don't try to extract types from the AOT binary; extract them from the metadata.

## Tooling pointers

- [`re-il2cpp.check_il2cpp`](https://github.com/Heretek-AI/RE-AI) — confirm the magic and version.
- [`re-il2cpp.list_namespaces`](https://github.com/Heretek-AI/RE-AI) — enumerate the namespace surface.
- [`re-il2cpp.get_type_definitions`](https://github.com/Heretek-AI/RE-AI) — walk the publisher's class graph.
- [`re-lief.get_sections`](https://github.com/Heretek-AI/RE-AI) — AOT binary section table.
- [`re-lief.categorize_strings`](https://github.com/Heretek-AI/RE-AI) — keyword-bucketed strings dump.
- [`ghidra`](../tools/01-ghidra.md) — AOT decompilation when the protection layer is known.
- [`anti-analysis/02-vm-bytecode-interpreter`](../anti-analysis/02-vm-bytecode-interpreter.md) and [`anti-analysis/05-launcher-activation-fingerprinting`](../anti-analysis/05-launcher-activation-fingerprinting.md) — for the protection-layer follow-up.

## References

- [RE-AI: ANTI-TAMPER-TAXONOMY.md](https://github.com/Heretek-AI/RE-AI/blob/main/ANTI-TAMPER-TAXONOMY.md) — for the category vocabulary.
- [Unity Manual: IL2CPP](https://docs.unity3d.com/Manual/IL2CPP.html) — for the official IL2CPP overview.
- [Il2CppDumper](https://github.com/Perfare/Il2CppDumper) — a community tool for IL2CPP metadata / binary parsing; useful as a third-party reference for the metadata format.
- [Perfare/Il2CppDumper metadata format](https://github.com/Perfare/Il2CppDumper/blob/master/Il2CppDumper/Metadata.cs) — a community-clarified walkthrough of the metadata table layout.
