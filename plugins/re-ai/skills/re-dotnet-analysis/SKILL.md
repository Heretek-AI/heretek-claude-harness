---
name: re-dotnet-analysis
description: Analyze a .NET-style launcher or mod loader (Mono launcher-shaped files with no native imports). Use when the user says "decompile this .NET binary", "what does this managed executable do", "give me the class graph of a C# assembly", "deobfuscate this managed DLL", or hands you a .dll / .exe whose imphash is empty / whose .text section starts with the standard mscoree.dll entry stub. Calls re-dotnet.parse_assembly + re-dotnet.decompile_type + re-dotnet.decompile_method + re-dotnet.list_strings and produces a one-page class graph report. For native binaries (imphash non-empty, .text starts with prologue), use re-static-triage instead.
---

# .NET Assembly Static Analysis

## When to use

Use this skill when a binary is a **.NET-style managed assembly** — usually detected by an empty or near-empty imphash, a `.text` section that begins with the standard mscoree.dll entry stub, or by file metadata that names `mscoree.dll` as the only meaningful import.

The user gives you a `.dll` or `.exe` that re-lief + re-rizin can parse but can't decompile (those tools see the native wrapper, not the managed payload). `re-dotnet` reads the ECMA-335 metadata tables directly and decompiles via ILSpy.

**What this skill returns** (a Markdown report):

1. **Assembly header** — name, version, target framework, entry point, corlib
2. **Class graph** — every TypeDef, sorted by `method_count` descending
3. **Entry-point decompile** — the C# source of the method that runs first
4. **String findings** — high-value substrings (URLs, paths, registry keys)
5. **Deobfuscation escalation** — if the decompiler fails on a type, the recommended remediation path

## What this skill does NOT do

- **Does not read native PE bytecode.** Native `call`/`jmp` targets in the host binary are out of scope — for that, escalate to `re-static-triage` + `re-rizin`.
- **Does not unpack commercial .NET obfuscation products.** The ILSpy decompiler refuses to lift certain control-flow-flattened or string-encrypted constructs. Deobfuscation is a separate workflow; this skill reports the failure cleanly and points to the remediation.
- **Does not resolve cross-assembly references.** If the target depends on a NuGet package we don't have on the search path, the decompiler emits "missing assembly" placeholders. The output is still useful; the placeholders are honest about what we couldn't see.

## Workflow

**Step 1 — Confirm the binary is .NET**

Before calling `re-dotnet`, verify the target is actually managed:

1. Call `re-lief.parse_binary(path)` — note the imphash and entry point.
2. If the imphash is empty / 0-length, or the entry point is a stub that calls `_CorExeMain` / `_CorDllMain`, the binary is .NET.
3. If the imphash is non-empty (real kernel32 / user32 imports), use `re-static-triage` instead — this skill will produce a thin class graph with no real findings.

**Step 2 — Read the assembly header + class graph**

```
re-dotnet.parse_assembly(path)
```

Note:
- **Target framework** — tells you the .NET BCL to expect (`net8.0`, `net48`, etc.)
- **Entry point** — the first method the runtime calls
- **Type count** — heuristic for "mod loader" (50-200 types) vs "obfuscated payload" (thousands of synthetic types)

**Step 3 — Decompile the entry point**

```
re-dotnet.decompile_method(path, fqn="<entry_point_fqn>")
```

The entry-point decompile is the highest-value decompile call. For a launcher, this is the first custom code that runs; for a mod loader, this is the injection root. The C# source is the analyst's first read of what the binary actually does.

**Step 4 — Enumerate the high-value types**

Sort the `types` list by `method_count` descending. The top 10-20 types are the ones to read; the rest are likely support / data containers. For each high-value type:

```
re-dotnet.decompile_type(path, fqn="<type_fqn>")
```

Read the class-level decompile. Look for:

- **`DllImport` / `extern` declarations** — calls into native code (the .NET assembly's "real" payload)
- **`HttpClient` / `WebRequest` / `SentrySdk` references** — telemetry leaks
- **`Process.Start` / `File.WriteAllText`** — process / filesystem side effects
- **`RegistryKey` / `Registry.LocalMachine`** — persistence vectors

**Step 5 — String findings**

```
re-dotnet.list_strings(path, mode="field-default", limit=500)
```

Filter the output for:

- `http://` / `https://` — telemetry endpoints
- `\\Registry\\` / `HKEY_` — registry keys (config, persistence, mutexes)
- `\\AppData\\` / `\\ProgramData\\` — filesystem paths (config, logs)
- `Sentry` / `DSN` — Sentry SDK + DSN (the highest-priority leak pattern)

**Step 6 — Deobfuscation escalation (if needed)**

If `decompile_type` returns `code: null` and a non-null `error` field, the binary has been through a commercial .NET obfuscator. The remediation is:

1. Run the .NET deobfuscator on a copy of the binary (not the original — keep the original as evidence).
2. Re-run `re-dotnet.parse_assembly` on the cleaned output.
3. Resume the workflow at Step 3.

Do not attempt to deobfuscate in-place. The obfuscation may involve JIT-hooking, anti-tamper stubs, or load-time mutation that the deobfuscator needs to neutralize before the decompiler can lift the code.

## Output report format

The skill produces a Markdown report with these sections:

1. **Header** — assembly name, version, target framework, entry point
2. **Class graph (top 20)** — sorted by method count
3. **Entry-point decompile** — the C# of `<Module>::.cctor` or `Main`
4. **High-value decompiles** — top 10 types by method count
5. **String findings** — URLs, registry keys, paths, SDK names
6. **Deobfuscation status** — clean / commercial-obfuscator-detected / unpacked
7. **Limitations** — what the skill did not recover (native code paths, cross-assembly references)

## Pairing with other skills

- `re-static-triage` — call FIRST to confirm the binary is .NET. If `parse_binary` shows a non-empty imphash, this skill will produce a thin class graph with no findings.
- `re-decompile` — for the C# decompiler's native counterpart (when a DllImport in a managed assembly calls into a native DLL that the decompiler can't reach).
- `re-leak-scan` — for the string-side counterpart; covers #US heap strings + native binary strings in a single unified detector.
- `re-vm-reverse` — for the (uncommon) case where the .NET assembly is a wrapper around an encrypted-VM bytecode interpreter (a C# loader that allocates RWX and copies native code in). The IL2CPP-target / proprietary-engine-target families are documented in the anti-tamper taxonomy.
