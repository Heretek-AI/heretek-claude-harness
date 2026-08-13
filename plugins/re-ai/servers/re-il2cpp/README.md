# re-il2cpp

An MCP server that reads Unity IL2CPP `global-metadata.dat` files to recover
the original C# class, method, field, and parameter names that the IL2CPP
compiler stripped from `GameAssembly.dll`. Drives Claude Code's reverse
engineering on Unity games.

The format is reverse-engineered from the public
[Il2CppDumper](https://github.com/Perfare/Il2CppDumper) `MetadataLoader.cs`.

## Install

```bash
pip install -e ./servers/re-il2cpp[rva]   # [rva] pulls in LIEF for resolve_method_rva
```

Without the `[rva]` extra, all 12 tools in the table walker work; only
`resolve_method_rva` requires LIEF. The repo's `install.sh` calls the
`[rva]` form automatically.

## What it does

IL2CPP compiles a Unity C# project into native x86_64 / ARM64 code. The
resulting `GameAssembly.dll` (often 100s of MB) has all the C# class names
mangled away. But the *unprotected* `global-metadata.dat` (typically
5-15 MB) sitting next to it still has every original C# symbol name as a
plain UTF-8 string. This server reads that file and exposes the class
graph as JSON.

## What it does NOT do

- Does not crack encrypted-VM bytecode (any commercial variant) —
  use `re-drm-fingerprint` on `GameAssembly.dll` for that.
- Does not recover C# source code — only the class/method/field names.
  The bodies are in `GameAssembly.dll`, which is the encrypted-VM
  bytecode-protected IL2CPP runtime.
- Does not parse Unity asset bundles (`level*`, `sharedassets*`).
  Use `re-format-decode` for those.
- Does not fully resolve `return_type_index` / `type_index` for
  methods and fields to a C# type name. The walker returns raw type
  indices; full name resolution requires reading
  `s_Il2CppMetadataRegistration::types[]` from GameAssembly.dll, which
  is a v2.3.0 follow-up.

## Supported versions

Unity 2019.4 - 2022.3 LTS lines (metadata header versions 24, 25, 26,
27, 28, 29). The bundled test target (Unity 2020.3.15f2, header v27) is
the canonical integration-test sample.

## Tools

### Metadata header

- `check_il2cpp(metadata_path)` — confirm the file is a real
  `global-metadata.dat`, return Unity version, header version, and
  per-table counts.

### String table (fast enumeration)

- `list_strings(metadata_path, substring="", limit=500)` — return
  strings from the string table (the unprotected C# symbol table).
  Filter by substring.
- `list_namespaces(metadata_path)` — return a sorted list of namespaces
  extracted from class FQNs in the string table.
- `list_classes(metadata_path, namespace="", limit=500)` — return
  class FQNs (filterable by namespace).
- `search_strings(metadata_path, substring, limit=50)` — substring
  search; useful for finding asset-bundle paths, save keys, or
  specific gameplay terms in the metadata.

### Binary tables (structured class graph)

- `get_type_definitions(metadata_path, namespace="", limit=500)` —
  walk the `typeDefinitions` table; return per-class parent,
  method/field/property/event counts, type index, and token.
- `get_methods(metadata_path, class_fqn, limit=500)` — typed methods
  of a class with token, parameter count, return type index.
- `get_fields(metadata_path, class_fqn, limit=200)` — typed fields of
  a class with type index.
- `get_parameters(metadata_path, method_fqn, limit=50)` — typed
  parameters of a method in declaration order.
- `get_properties(metadata_path, class_fqn, limit=200)` — properties
  with `has_getter` / `has_setter` flags.
- `get_events(metadata_path, class_fqn, limit=200)` — events with
  `has_add` / `has_remove` / `has_raise` flags.
- `get_images(metadata_path)` — list of IL2CPP images (assemblies)
  with type ranges and exported-type counts.

### RVA cross-reference (requires `pip install re-il2cpp[rva]`)

- `resolve_method_rva(metadata_path, gameassembly_path, method_fqn)` —
  resolve a `Namespace.ClassName.MethodName` to its GameAssembly.dll
  RVA by parsing the runtime registration structures. Pass the
  returned `function_rva` to `re-rizin.disassemble_function` to read
  the function body. For stripped GameAssembly.dll (the default for
  shipped Unity games), returns the structured data plus the IL2CPP
  mangled name to use with `re-rizin.search_bytes`.
