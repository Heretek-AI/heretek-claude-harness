# jadx decompilation tips

`decompile_class`, `decompile_method`, `decompile_apk`, and
`read_source` all route to `jadx-cli` via
`android_re_core.sources.SourcesView`. These tips will help
interpret the output.

## Deobfuscation flags

By default, `android_re_core.sources` invokes jadx with these flags:

```text
--no-res                 # do not decode resources (faster, smaller)
--show-bad-code          # show inconsistent code rather than dropping it
--no-imports             # do not collapse single-use imports
--escape-unicode         # keep Unicode escapes in strings
```

The MCP tools expose a per-call override:

| MCP param      | jadx flag             | Effect                                  |
|----------------|-----------------------|-----------------------------------------|
| `deobfuscate`  | `--deobf`             | R8 / ProGuard name recovery             |
| `threads`      | `--threads-count N`   | parallelise the decode                   |

> **Note**: `output_format="kotlin"` was supported in early 2025 but
> was **removed** because jadx 1.5.0 (the vendored version) rejects
> `--use-kotlin-source` with "Unknown option". jadx 1.5.0's
> `--output-format` flag only accepts `java` or `json`. Decompile
> with `output_format="java"` (the default) and let the Kotlin
> Gradle plugin compile the `.java` files alongside the
> `@kotlin.Metadata` annotations — the dex bytecode is
> indistinguishable from a real Kotlin build. For the full
> pipeline that turns a decompile into a buildable Gradle
> project, see the `android-re-gradle-rebuild` skill.

`deobfuscate` is part of the cache key: each combination gets its
own workdir under `/tmp/android-re/<id>-jadx-{deobf,plain}-java/`,
so flipping flags does not poison a prior decode.

To add additional jadx flags without editing the library, set the
`JADX_FLAGS` env var (space-separated). The MCP-tool flags are
appended after and win on conflict because jadx's CLI parser is
"last wins":

```bash
JADX_FLAGS="--deobf --deobf-min 4 --deobf-max 64" jadx ...
```

## Common quality issues

| Symptom                                | Cause                              | Fix                                   |
|----------------------------------------|------------------------------------|---------------------------------------|
| `<unknown>` type names                  | Missing dependency                 | Add the dep JAR to jadx's classpath   |
| `/* renamed from: a */`                 | Local-variable renaming            | Use jadx `--no-imports`               |
| `if (true) { ... } else { throw }`     | Unreachable code from optimizer    | jadx `--no-replace-consts`            |
| `/* access modifiers: ... */` comments | Inferred modifiers from synthetic | Informational, not an error           |
| `goto` / `label:`                       | Try/catch, switch on String         | jadx `--no-imports --no-replace-consts` |
| `a.a.a.a` everywhere                   | R8/ProGuard shrink + obfuscate     | `deobfuscate=True`                    |
| Method slice is empty / `found=false`  | Method not located in output       | Re-run with `deobfuscate=True`        |

## Cross-references

For a given class or method, find all callers with:

```bash
jadx --no-res -d out app.apk
grep -rE 'invoke.* Lcom/example/Foo;\.bar' out/sources/
```

The MCP equivalent is `find_methods` followed by `find_xrefs`.

## Resources

- jadx project: https://github.com/skylot/jadx
- jadx CLI: https://github.com/skylot/jadx/wiki/Command-line-Tools
- Deobfuscation guide:
  https://github.com/skylot/jadx/wiki/Dequick-guide
