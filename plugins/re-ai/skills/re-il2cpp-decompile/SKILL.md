---
name: re-il2cpp-decompile
description: Triage a Unity IL2CPP game — read global-metadata.dat to recover class/method/field/param names, then cross-reference GameAssembly.dll RVAs to recover code. Use when the user says "this is a Unity game", "IL2CPP binary", "GameAssembly.dll", "global-metadata.dat", "recover the C# class names", "what does this Unity method do", or hands you a Unity 2019–2022 game directory. Calls the re-il2cpp MCP server and cross-references re-rizin against GameAssembly.dll. Does NOT crack commercial anti-tamper — for that, use re-drm-fingerprint first.
---

# Unity IL2CPP Triage

## When to use

Use this skill when the user is working on a Unity-built game (or any
Unity-built app) and wants to recover the original C# class graph that
IL2CPP erased from `GameAssembly.dll`.

**This skill is post-anti-tamper, not pre-anti-tamper.** It does not crack
encrypted-VM bytecode, MBA-obfuscated arithmetic, or any other
protection wrapping the actual code in `GameAssembly.dll`. If the user
hands you a Unity game directory and the binary shows signs of
encrypted-VM protection (run `re-drm-fingerprint` first — look for a
`.vm` section, HWID-vector imports, scattered-bit register storage,
or a high-entropy `.xtls` section), say so up front. The IL2CPP-level
C# symbol recovery is still valuable: the class FQNs and method names
tell you the architecture, save format structure, gameplay state
machine, network message shapes, etc., even if you can't read the
function bodies yet.

Common prompts:

- "This is a Unity game — what classes does it have?"
- "What does `PlayerController.TakeDamage` do?"
- "I have a `global-metadata.dat` — recover the C# names"
- "Find the save-game class in this Unity game"
- "What string literals are in the IL2CPP metadata?"
- "Where does this Unity game make network calls?"

## Workflow

The unprotected `global-metadata.dat` is the key artifact — typically
5–15 MB of plain UTF-8 strings containing the original C# identifiers.
The format is identical across Unity 2019.4 / 2020.3 / 2021.3 / 2022.3
LTS (metadata versions 24–29). The `re-il2cpp` MCP server handles
parsing.

**Step 1 — Find the metadata file**

The file is always at:

```
<game>_Data/il2cpp_data/Metadata/global-metadata.dat
```

If the directory layout differs, search the input directory for
`global-metadata.dat`.

**Step 2 — Validate and confirm the format**

```
re-il2cpp.check_il2cpp("<path-to-global-metadata.dat>")
```

Expect: `version` in 24–29, `size_bytes` > 1 MB, `magic` = `0xFAB11BAF`.
A bad magic means the file is corrupted, encrypted, or not actually
an IL2CPP metadata file. A version outside 24–29 means the user has
a Unity 6+ (2023+) build, which we don't support yet.

**Step 3 — Orient on the namespace layout**

```
re-il2cpp.list_namespaces(metadata_path, limit=200)
```

Returns a sorted list of namespaces with class counts. Top hits should
include the engine namespaces (`UnityEngine.*`, `System.*`) plus the
publisher's namespaces (e.g. `<PublisherStudio>.*` for a small studio).
Asset-store packages show up too — `Rewired.*` (input system),
`Cinemachine.*` (camera controller), `TMPro.*` (text mesh),
`Boxophobic.*` (shaders).

**Step 4 — Drill into the publisher's classes**

Pick the publisher's namespace (usually a short root like the studio
name) and list its classes:

```
re-il2cpp.list_classes(metadata_path, namespace="<PublisherStudio>", limit=200)
```

If the user wants *structure* (parent class, method/field counts, type
index), use the binary table walker instead:

```
re-il2cpp.get_type_definitions(metadata_path, namespace="<PublisherStudio>", limit=200)
# -> [{fqn, namespace, parent, type_index, method_count, field_count, ...}, ...]
```

The string-table scan is faster for a quick inventory; the table
walker gives you the parent/child relationships and per-class
member counts.

**Step 5 — Find a specific class**

If the user is hunting for a specific concept (save game, combat,
inventory, network message), substring search the C# symbol table:

```
re-il2cpp.search_strings(metadata_path, "SaveGame", limit=20)
re-il2cpp.search_strings(metadata_path, "Combat", limit=20)
```

When the user wants *typed* methods, parameters, and fields, walk the
binary tables instead. First find the FQN via `list_classes`, then
enumerate:

```
re-il2cpp.get_methods(metadata_path, class_fqn="<PublisherStudio>.SaveGameManager", limit=50)
# -> [{name, token, return_type_index, parameter_count, ...}, ...]
re-il2cpp.get_fields(metadata_path, class_fqn="<PublisherStudio>.SaveGameManager", limit=50)
re-il2cpp.get_parameters(metadata_path, method_fqn="<PublisherStudio>.SaveGameManager.Save", limit=10)
```

**Step 6 — Map a class to its code in `GameAssembly.dll`**

The new `resolve_method_rva` tool does this for you. It walks the
typeDef/method tables AND parses GameAssembly.dll's runtime
registration structures to return the exact RVA of the native
function:

```
re-il2cpp.resolve_method_rva(
    metadata_path="<path-to-global-metadata.dat>",
    gameassembly_path="<path-to-GameAssembly.dll>",
    method_fqn="<PublisherStudio>.PlayerController.TakeDamage",
)
# -> {
#      fqn: "<PublisherStudio>.PlayerController.TakeDamage",
#      class_fqn: "<PublisherStudio>.PlayerController",
#      name: "TakeDamage",
#      image_name: "Assembly-CSharp.dll",
#      method_index: 700,
#      pointer_table_rva: "0x18C4A20",   # when binary is non-stripped
#      function_rva: "0x0B7E150",         # when binary is non-stripped
#      rva_status: "resolved",
#      source: "GameAssembly.dll@LIEF",
#    }
```

Then disassemble the body directly with `function_rva`:

```
re-rizin.disassemble_function(
    gameassembly_path,
    function="0x0B7E150",
    max_insns=200,
)
```

**Fallback (if the binary is stripped):** if `resolve_method_rva`
returns `rva_status: "binary_stripped"`, the shipped Unity game has
its registration symbols stripped (this is the default for release
builds). The response includes `il2cpp_mangled_name` — feed it to
`re-rizin.search_bytes` for the manual workflow. The mangled name
format is `Namespace/ClassName$$MethodName` (note the `/` separator
between namespace and class).

**Step 7 — Cross-reference decompiler (optional)**

For harder cases, hand the disassembly to the LLM decompiler:

```
re-llm-decompile.decompile_function(
    disasm=<disasm-text-from-step-6>,
    arch="x86_64",
    calling_conv="SystemV",
    context="this is the Unity IL2CPP method Namespace.ClassName.MethodName",
)
```

The LLM produces C-like pseudocode that is much more readable than
raw disassembly.

## Network capture (Unity games)

For games that talk to a server (telemetry, anti-cheat, online
multiplayer), the `re-mitm2swagger` MCP server can capture traffic
while the game runs. The full flow:

```
1. re-mitm2swagger.start_capture(port=8080, output_path="./re-ai.flow")
   # returns a PID
2. Set HTTP_PROXY=http://localhost:8080 and HTTPS_PROXY=... in the
   shell that launches the game (or use --mode transparent)
3. Launch the game, exercise the feature of interest
4. re-mitm2swagger.stop_capture(pid)
5. re-mitm2swagger.parse_flows("./re-ai.flow")
6. re-mitm2swagger.filter_flows("./re-ai.flow", host="<api-host>")
7. re-mitm2swagger.har_to_swagger("./re-ai.flow", output_path="./api.yaml")
```

The output is an OpenAPI 3.0 spec you can hand back to `re-api-reverse`
for endpoint-by-endpoint analysis.

## Output

A Markdown report in the `re-static-triage` shape:

1. **File info** — metadata version, file size, sha256
2. **Engine fingerprints** — namespace breakdown (top 15 by class count)
3. **Publisher's classes** — full namespace tree, sorted by class count
4. **High-value classes** — for a single-player game, this is typically
   Player, SaveGame, Combat, Inventory. For a multiplayer game, add
   NetworkMessage and PacketHandler.
5. **String findings** — any asset-bundle paths, save keys, telemetry
   hostnames, or DRM tokens that surface in the string literal table.
6. **GameAssembly.dll cross-references** — RVAs of the top 5–10 high-
   value classes' methods, ready for `re-rizin.disassemble_function`.
7. **Anti-tamper note** — if `re-drm-fingerprint` flagged encrypted-VM bytecode protection
   on GameAssembly.dll, say so here. The class graph is recoverable;
   the bodies are not (without first defeating the protection).

## Limitations

- Does not crack encrypted-VM bytecode (any commercial variant) on
  `GameAssembly.dll`. For that, see `re-drm-fingerprint` and
  `re-vm-reverse`.
- Does not recover C# source code — only class/method/field NAMES. The
  function bodies are in the protected `GameAssembly.dll`.
- Does not fully resolve `return_type_index` / `type_index` to a C#
  type name. The walker returns the raw index into the runtime
  `Il2CppType` table; full name resolution requires reading
  `s_Il2CppMetadataRegistration::types[]` from GameAssembly.dll, which
  is a v2.3.0 follow-up. For now, cross-reference the type index
  against the `typeDefinitions` table.
- RVA resolution requires non-stripped GameAssembly.dll. Shipped
  Unity release builds strip the `s_Il2CppCodeRegistrations` symbol;
  for these, `resolve_method_rva` returns the structured data plus
  the IL2CPP mangled name to use with `re-rizin.search_bytes`.
- Does not handle Unity 2023+ / Unity 6 metadata layout changes. The
  format shifted (different field names, different byte offsets) and
  is not yet supported.
- Does not parse Unity asset bundles (`level*`, `sharedassets*`).
  Use `re-format-decode` for those — see the magic-bytes table there
  for `UnityFS` / `UnityWeb` / `UnityRaw` and the `AF 1B B1 FA` IL2CPP
  metadata magic.
