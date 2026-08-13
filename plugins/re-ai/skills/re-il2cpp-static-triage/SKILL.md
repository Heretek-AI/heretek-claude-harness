---
name: re-il2cpp-static-triage
description: First-pass static triage of a Unity IL2CPP game. Use when the user says "what classes does this Unity game have", "give me the C# class graph", "what's in Assembly-CSharp.dll", or hands you a Unity 2019-2022 game directory. Calls re-il2cpp.get_images + re-il2cpp.get_assembly_types + re-il2cpp.search_strings and produces a one-page class graph report. Explicitly does NOT crack protection on GameAssembly.dll or read function bodies — for those, escalate to re-drm-fingerprint and re-decompile.
---

# Unity IL2CPP Static Triage

## When to use

Use this skill for the **first 30 seconds** with a Unity-built game. The user
gives you a `_Data/` directory or a `global-metadata.dat` path, and you
produce a one-page class graph: which IL2CPP assemblies are present, which
classes are in the publisher's `Assembly-CSharp.dll`, and what the high-value
classes are (save, inventory, combat, network).

**What this skill returns** (a Markdown report):

1. **Metadata header** — version, file size, supported flag
2. **Assemblies** — every IL2CPP image with type counts (the publisher's
   `Assembly-CSharp.dll` is usually the largest)
3. **Publisher's class graph** — every type in `Assembly-CSharp.dll` (or
   whichever assembly the user names), sorted by `method_count` descending
4. **String findings** — high-value substrings (SaveGame, Inventory, Player,
   Network, etc.) with the assembly that owns them
5. **Limitations** — what this skill does NOT recover (function bodies, source
   code, runtime type resolution)

## What this skill does NOT do

- **Does not read function bodies.** Bodies live in `GameAssembly.dll`,
  which is often protected (commercial code-protection products or
  IL2CPP's stripping). For body recovery, use `re-decompile` and
  `re-rizin` — but expect encrypted-VM bytecode on shipped titles.
- **Does not crack encrypted-VM bytecode (any commercial variant).** Run `re-drm-fingerprint`
  on `GameAssembly.dll` first to see if it's protected. If it is, the
  class graph is still recoverable from `global-metadata.dat`; the function
  bodies are not.
- **Does not resolve `return_type_index` / `type_index` to a C# type name.**
  The walker returns the raw type index. Cross-reference against
  `get_type_definitions` if you need the type's FQN.

## Workflow

**Step 1 — Find the metadata file**

The file is always at:

```
<game>_Data/il2cpp_data/Metadata/global-metadata.dat
```

If the directory layout differs, search the input directory for
`global-metadata.dat`.

**Step 1a — Metadata-stripped or non-standard-location case**

The v2.9.0 stress test surfaced a class of targets (Gap 26)
where Step 1 returns no `global-metadata.dat` at the standard
location AND `re-rizin.search_bytes` against `GameAssembly.dll`
finds zero hits for the magic `AF 1B B1 FA` (little-endian
`0xFAB11BAF`, the global-metadata.dat magic). The target uses
one of three patterns:

  (a) **Metadata stripped/encrypted at packaging.** Common in
      titles shipping a crash-reporting SDK (e.g. Sentry
      resources in the `Resources/` subdir) that includes its
      own type registry. The metadata may live in an
      obfuscated form in `GameAssembly.dll`'s `.rdata` or
      behind a runtime-decryption routine.

  (b) **Metadata at non-standard path.** Some Unity 6+ games
      relocate the file (e.g. into a streaming assets archive
      or a pak file). Search for `*.dat` under the game root
      recursively; check the `StreamingAssets/` and `Resources/`
      subdirs.

  (c) **IL2CPP with no metadata.** Rare; the binary uses a
      pre-baked type registry compiled into the binary. The
      `GameAssembly.dll` symbol table may have the original
      FQNs.

For all three, the static C# class graph recovery is blocked.
Escalation:

  1. `re-rizin.list_strings(GameAssembly.dll, encoding="all",
     min_length=8)` — type FQNs often remain in the `.rdata`
     section even when `metadata.dat` is gone.
  2. `re-frida.attach_pid(<game>.exe)` + a small JS that hooks
     `il2cpp_init` / `il2cpp_class_get_name_space` and dumps
     the runtime type table. This is the canonical recovery
     path for case (a) and (c). See the `re-frida` and
     `re-android-dynamic` skills.
  3. Treat `GameAssembly.dll` as a stripped C++ binary and use
     `re-static-triage` + `re-capa` for capability discovery.

The canonical empirical case is documented in the 2026-06-07
stress-test artifacts at `See the RE-AI output directory.`
(the per-target directory under the relevant target name) and
the vendor-named research notes at
the vendor attribution catalog..

**Step 2 — Validate the metadata**

```
re-il2cpp.check_il2cpp("<path-to-global-metadata.dat>")
```

Expect: `version` in 24-31, `size_bytes` > 1 MB, `magic` = `0xFAB11BAF`.
A bad magic means the file is corrupted, encrypted, or not actually an
IL2CPP metadata file. A version >= 30 (Unity 2023.1+ / Unity 6) is
admitted by the v2.9.1 walker; the response carries a `v30plus_warning`
field flagging the forward-compat assumption (the v30/v31 on-disk
layout is aliased over the v25plus record format). If records are
malformed on a v30+ target, file a bug — we'll need a per-version
layout table.

**Step 3 — List the assemblies**

```
re-il2cpp.get_images("<path-to-global-metadata.dat>")
```

Returns a list of IL2CPP images (one per assembly), each with a
`type_count` field. The publisher's actual game code is almost always
in `Assembly-CSharp.dll` — look for the highest `type_count` that isn't
a Unity engine module (`UnityEngine.*`, `Unity.*`).

**Step 4 — Enumerate the publisher's classes**

This is the key step. The `re-il2cpp.list_classes` string-table scan
cannot surface root-namespace types (the publisher's game code is
typically in the root namespace of `Assembly-CSharp.dll`), so use the
dedicated image-scope tool:

```
re-il2cpp.get_assembly_types(
    metadata_path="<path-to-global-metadata.dat>",
    image_name="Assembly-CSharp.dll",
    limit=500,
)
```

This returns the full typeDef records for that image. Sort the
results by `method_count` descending to find the meatiest classes
(gameplay controllers, save systems, etc.).

**Step 5 — String findings (optional but recommended)**

```
re-il2cpp.search_strings(metadata_path, "SaveGame", limit=20)
re-il2cpp.search_strings(metadata_path, "Inventory", limit=20)
re-il2cpp.search_strings(metadata_path, "Player", limit=20)
re-il2cpp.search_strings(metadata_path, "Network", limit=20)
```

Each hit is `{index, string}`. Look for class FQNs, event names,
field names, and parameter names that hint at game architecture.

## Output

A Markdown report with these sections (one page):

1. **Metadata** — `version`, `size_bytes`, `magic`
2. **Top 10 assemblies by `type_count`** — Markdown table; the publisher
   assembly is called out separately
3. **Publisher's top 20 classes by `method_count`** — Markdown table;
   the largest is usually the main player / game controller
4. **High-value string findings** — Markdown table of `substring →
   first 5 hits` for the chosen high-value terms
5. **Limitations** — bullet list of what was NOT recovered (function
   bodies, source, runtime type resolution)

## Escalation paths

After this triage:

- **Class is interesting** → use `re-il2cpp.get_methods(metadata, fqn)`
  to enumerate its methods, then `re-decompile` on a chosen method
  (after running `re-drm-fingerprint` if `GameAssembly.dll` is shipped)
- **Function body is unreadable** → the binary is protected; escalate
  to `re-vm-reverse` or note "function body is in the protected
  section of GameAssembly.dll" and stop
- **Save format reverse engineering** → use `re-il2cpp.search_strings`
  for keys like `savePath`, `filePath`, `JsonUtility`, `BinaryFormatter`
- **Network message shapes** → use `re-il2cpp.search_strings` for
  `Message`, `Packet`, `Rpc`, `Request`, `Response`
- **Metadata missing entirely (Step 1a case)** → fall back to
  `re-frida` runtime hook of `il2cpp_init` + `il2cpp_class_get_name_space`
  to dump the runtime type table, or treat `GameAssembly.dll` as a
  stripped C++ binary via `re-static-triage` + `re-capa`. See
  Step 1a for the full escalation chain.

## Limitations

- Does not read function bodies. Bodies are in `GameAssembly.dll`,
  which is often protected. Use `re-drm-fingerprint` to detect
  protection and `re-decompile` to read individual functions.
- Does not resolve `type_index` values to FQNs. The walker returns raw
  indices; cross-reference against the `typeDefinitions` table for the
  type FQN.
- Supports metadata versions 24-31 (Unity 2019.4 LTS through
  Unity 6). v30/v31 entries are forward-compatibility aliases
  over the v25plus record format; if the parser returns malformed
  records on a v30+ target, file a bug — we'll need a per-version
  layout table.
- Does not crack encrypted-VM bytecode (any commercial variant). If `GameAssembly.dll`
  is protected, the class graph is still fully recoverable; the
  function bodies are not.
