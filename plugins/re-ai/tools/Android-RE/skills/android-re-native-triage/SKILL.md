---
name: android-re-native-triage
description: |
  Use when the user wants to assess the native (JNI / C / C++) code
  inside an APK, audit hardening on .so libraries, or get a report
  on what a native library does. Triggers: "native triage", "check
  the .so", "audit libfoo.so", "what does libnative do", "is the
  native code hardened", "PIE / RELRO / NX on this library", "check
  for packers / obfuscation in libfoo". Do NOT use for pure DEX
  analysis (use android-re-static-triage) or for dynamic analysis
  (use android-re-dynamic-hook).
effect:
  filesystem: read APK in current directory or absolute path
  network: none
  device: none
requires:
  mcp:
    - android-re-static
    - android-re-native
---

# Native library triage

A focused report on the native libraries inside an APK. Surfaces
format, architecture, hardening (NX / RELRO / PIE / canary / fortify),
symbols, strings, and packer / obfuscation indicators.

## When to use

The user has identified that the APK ships native code (or suspects
it does) and wants to know:

- Which ABIs ship native code
- Whether the libraries use modern hardening
- What symbols are exported / imported
- What embedded strings look like (C2 servers, error messages, crypto constants)
- Whether the library is packed, obfuscated, or otherwise suspicious

If the user wants full decompilation of the DEX, use
`android-re-static-triage` first. If they want to hook the library
at runtime, escalate to `android-re-dynamic-hook`.

## Inputs

| Field        | Required | Description                                       |
|--------------|----------|---------------------------------------------------|
| `apk_path`   | yes      | Path to the `.apk`                                |
| `lib_name`   | no       | Single library to focus on. If omitted, all libs. |

## Workflow

1. **Open the project.**
   `mcp__android-re-static__open_project` → `project_id`.
   (Or `mcp__android-re-native__open_project` if the flow is
   entirely native — both tools exist and return matching
   `project_id`s for the same APK, but the underlying stores
   are process-local and do not share state.)

2. **Enumerate native binaries.**
   Call `mcp__android-re-native__list_binaries` with the
   `project_id`. Capture `abis` and the list of `binaries`.

3. **If `lib_name` was given, focus on that library. Otherwise
   loop the next steps over every binary.**

4. **Parse the binary.**
   `mcp__android-re-native__parse_binary` returns format, arch,
   bits, endianness, entrypoint, base address, PIE, stripped
   status, security features, and counts.

5. **Security features in detail.**
   `mcp__android-re-native__get_security_features` returns the
   security flags in a flat dict.

6. **Imports and exports.**
   `mcp__android-re-native__get_imports` and
   `mcp__android-re-native__get_exports`.

7. **String extraction.**
   `mcp__android-re-native__get_strings` with `section=".rodata"`
   and `limit=200`. Look for C2 URLs, license-check messages,
   hard-coded paths, crypto constants.

8. **Packer / anti-RE detection.**
   `mcp__android-re-native__detect_packers` and
   `mcp__android-re-native__lookup_signature` with `sigset="default"`.

9. **Consolidated report.**
   `mcp__android-re-native__build_native_report` for the full
   picture.

10. **Close the project.**
    `mcp__android-re-static__close_project`.

## Output

A markdown section per library:

```markdown
## libfoo.so (arm64-v8a, ELF, 1.2 MB)

### Format & architecture
- **Format**: ELF, AArch64, little-endian
- **Entry point**: 0x12340
- **PIE**: yes
- **Stripped**: no

### Hardening
| Flag            | Status        |
|-----------------|---------------|
| NX              | enabled       |
| RELRO           | full          |
| Stack canary    | enabled       |
| PIE             | enabled       |
| Fortify         | enabled       |
| Symbols stripped| no            |
| RPATH / RUNPATH | none          |

### Exports (<n>)
- <list, abbreviated>

### Imports (<n>)
- <top 20 by frequency>

### Notable strings (first 20)
- <list>

### Packer / anti-RE matches
- <list with severity>
```

## Examples

### Example 1: full triage of all libs

> User: Triage the native code in `app.apk`.

Steps:

1. Open project.
2. `list_binaries` → 3 libs across arm64-v8a, armeabi-v7a, x86_64.
3. For each, `parse_binary` + `get_security_features` + `get_imports` +
   `get_exports` + `get_strings` + `detect_packers` +
   `lookup_signature`.
4. Emit a markdown section per lib.
5. Close project.

### Example 2: focus on one library

> User: Check `lib/arm64-v8a/libcocos2dcpp.so`.

Same workflow but `lib_name="lib/arm64-v8a/libcocos2dcpp.so"`.

## Background reading (peer MCP)

While running this skill, the agent can consult the RE-Library peer
MCP for generic patterns. Triggers: "what does the literature say
about <observed pattern>". The peer is read-only; it never
overwrites a verified observation on the target.

- `mcp__re-library__list_categories()` — enumerate the 8 categories.
- `mcp__re-library__search_re(query="<category> <pattern>", max_results=3)` — up to 3 hits with snippet + score.
- `mcp__re-library__get_entry(slug="<category>/<NN>-<slug>")` — full body of one entry.

Pair with the hardening and packer findings from this skill; the
`native` category in particular is the right lookup for ELF
hardening, RELRO, and packer mechanics.

The peer is registered in `.mcp.json`; install it once with
`just install-re-library` (opt-in).

## Output convention

`build_native_report` writes a JSON copy to:

```
Output/<apk-basename>-<short-sha>/native/native-report.json
```

(For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).) Override
with the `output_path` parameter. Remember: the native MCP server has
its own `ProjectStore` that does not share state with the static
server; if you get `project_not_found`, re-open the project on the
native server.

## Notes

- Reads are static. No decompilation. Use the strings + symbols
  output to inform what to disassemble.
- If the user wants disassembly of a specific function, use
  `mcp__android-re-native__disassemble_function` directly.
- For Frida-ready hooks against a discovered function, use
  `mcp__android-re-native__generate_frida_native_hook`.
- **Size limit.** The MCP `open_project` tool caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
