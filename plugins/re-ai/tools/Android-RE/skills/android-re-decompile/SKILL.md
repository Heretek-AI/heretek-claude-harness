---
name: android-re-decompile
description: |
  Use when the user wants to read the implementation of a specific
  method or class, pull Java/smali source for a function, or understand
  what a particular entry point does. Triggers: "decompile this method",
  "show me the source of <Class>.<method>", "what does
  com.example.Foo.bar do", "read <FQCN>", "smali for <method>". Do NOT
  use for a project-wide overview — use android-re-static-triage for
  that.
effect:
  filesystem: read APK in current directory or absolute path
  network: none
  device: none
requires:
  mcp: android-re-static
---

# Decompile a class or method

Pull pseudocode/smali for a specific class or method, given its FQCN
and (optionally) a method name.

## When to use

The user knows (or suspects) a specific class or method is interesting
and wants the source. Typical scenarios:

- "Show me `Lcom/example/Payment;.charge:(Ljava/lang/String;J)V`"
- "What does `MainActivity.onCreate` do?"
- "I think the secret is in `CryptoHelper.decrypt`. Pull that."

If the user doesn't know where to look, use `android-re-static-triage`
first to enumerate classes/methods.

## Inputs

| Field          | Required | Description                                                  |
|----------------|----------|--------------------------------------------------------------|
| `apk_path`     | yes      | Path to the `.apk`                                           |
| `class_name`   | yes      | FQCN in JNI form, e.g. `Lcom/example/Foo;`                  |
| `method_name`  | no       | If omitted, list all methods in the class                    |
| `descriptor`   | no       | JVM type descriptor, e.g. `(I)V`. Required if `method_name`  |

Ask one short question if any required field is missing.

## Workflow

1. **Open the project.**
   `mcp__android-re-static__open_project` → `project_id`.

2. **Confirm the class exists.**
   `mcp__android-re-static__find_classes` with `query=class_name` and
   `exact=true`. If zero results, the class is not in this APK (it may
   be in a dependency, a native library, or dynamically loaded). Tell
   the user.

3. **List methods in the class (optional).**
   If `method_name` was not given, call
   `mcp__android-re-static__find_methods` with
   `class_name=class_name` and `limit=200`. Present the list to the
   user and ask which method they want.

4. **Decompile the method.**
   Call `mcp__android-re-static__decompile_method` with the
   `project_id`, `class_name`, `method_name`, and `descriptor`. The
   first call in a project (per deobfuscate / output_format
   combination) runs the full jadx decode; subsequent calls reuse
   the cached workdir. The response includes `source` (the
   method body as a slice), `start_line` / `end_line` (1-indexed
   against the decompiled class), `found` (false if jadx could
   not locate the signature — try `deobfuscate=True` and retry),
   and `full_class_source` (for callers that want context around
   the slice).

5. **Close the project.**
   `mcp__android-re-static__close_project`.

## Output

A markdown section with:

- The class declaration (superclass, interfaces, access flags)
- A table of the class's methods (name, descriptor, native, access flags)
- For a single-method decompile: the decompiled Java source as a
  span, with the line range in the decompiled class

## Whole-APK navigation

`decompile_method` and `decompile_class` are for one class / one
method at a time. To enumerate the decompiled tree or read files
by path, use the new `decompile_apk` and `read_source` tools:

- **`decompile_apk(project_id, force=False, deobfuscate=False, threads=None, output_format="java", limit=500, offset=0)`**
  returns `{class_count, files: [{path, line_count, byte_size}], total_files, truncated, jadx_duration_s}`.
  Use this to see what jadx produced and to choose which files to
  inspect. The first call per (deobfuscate, output_format) runs
  jadx; later calls hit the cache.

- **`read_source(project_id, path, deobfuscate=False, output_format="java")`**
  reads one file by path relative to the decompiled `sources/`
  dir. Refuses `..` traversal, absolute paths, symlinks that
  escape the sources tree, and files larger than 10 MB.

## Deobfuscation cookbook

jadx's `--deobf` flag recovers the original names from R8 /
ProGuard-shrunk APKs (R8 renames classes to `a.a.a.a` and methods
to `a()`, `b()`, etc.). Trade-offs:

- **`deobfuscate=True`** — required when an APK has been shrunk
  with R8. The first call re-runs jadx with `--deobf`; results
  are cached separately so non-deobfuscated output is preserved.
- **`threads=N`** — speed up jadx on large APKs (jadx is
  single-threaded by default; `--threads-count` parallelises the
  decode).
- **`output_format="kotlin"` is not supported.** jadx 1.5.0
  rejects `--use-kotlin-source`. To decompile a Kotlin-heavy APK,
  use `output_format="java"` and let the Kotlin Gradle plugin
  compile the `.java` files alongside the `@kotlin.Metadata`
  annotations.

`decompile_class`, `decompile_method`, `decompile_apk`, and
`read_source` all accept `deobfuscate` and `output_format`. Keep
the values consistent across calls in the same project — they
determine the cache key.

## Examples

### Example 1: list all methods in `MainActivity`

> User: What methods does `Lcom/example/MainActivity;` have?

Steps:

1. Open project.
2. `find_classes` with `query="Lcom/example/MainActivity;"`, `exact=true`.
3. `find_methods` with `class_name="Lcom/example/MainActivity;"`, `limit=200`.
4. Close project. Output: a table of methods.

### Example 2: decompile a specific method

> User: Show me `Lcom/example/Payment;.charge:(Ljava/lang/String;J)V`.

Steps:

1. Open project.
2. `find_classes` with `query="Lcom/example/Payment;"`, `exact=true`.
3. `find_methods` with `class_name="Lcom/example/Payment;"` and
   `name_substring="charge"`. Confirm the descriptor.
4. `decompile_method` with the full signature. If the method
   can't be located (typical for obfuscated names), retry with
   `deobfuscate=True`.
5. Close project.

### Example 3: enumerate the decompiled tree

> User: What classes are in this APK?

Steps:

1. Open project.
2. `decompile_apk` with `limit=200`. Show the user a sortable
   table of `path`, `line_count`, `byte_size`.
3. To drill in: `read_source` with one of the returned paths.
4. Close project.

## Output convention

Decompile caches live under `/tmp/android-re/<project>-jadx-.../` (an
internal cache; the agent treats them as scratch). To mirror selected
sources into the user-facing `Output/` tree, copy them to:

```
Output/<apk-basename>-<short-sha>/sources/<FQCN>.java
```

For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md) and
`android_re_core.paths.output_dir_for`. The first call opens a project,
so pass `max_size=<apk_bytes * 2>` on `open_project` for any APK over
the 500 MB default cap.

## Notes

- Decompilation is rarely perfect. Obfuscated code, control-flow
  flattening, and string encryption all reduce jadx output quality.
  Try `deobfuscate=True` on R8-shrunk APKs.
- Smali is the always-correct fallback — `get_smali` reads the
  apktool-disassembled smali for a class, byte-for-byte the same
  as the original DEX.
- For native (JNI) methods, `decompile_method` returns `found=false`;
  the implementation is in a `.so` library. Use `android-re-native-triage`.
- **Size limit.** The MCP `open_project` tool caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
