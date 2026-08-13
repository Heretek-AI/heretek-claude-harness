---
title: "Ghidra"
category: "tools"
platforms: ["linux", "windows", "macos"]
difficulty: "beginner"
tags: ["disassembler", "decompiler", "static-analysis"]
summary: "NSA's open-source RE suite — disassembler, decompiler, scripting, and a headless mode that fits into pipelines. The free, scriptable, multi-target baseline of modern RE."
updated: "2026-06-04"
related: ["tools/02-ida", "tools/03-binary-ninja", "native/02-elf-format"]
---

## Summary

Ghidra is a free, open-source reverse engineering suite developed by the NSA and released in 2019. It includes a disassembler, a decompiler (the famous *Decompile* window), a scripting environment based on Java/Python, and a headless mode for batch analysis. It handles every common executable format (PE, ELF, Mach-O, COFF, a.out) and most common ISAs (x86, x86-64, ARM, AArch64, MIPS, PowerPC, RISC-V, …).

## Why this matters

For most RE tasks, the question isn't "should I use Ghidra" but "which Ghidra script do I want." The decompiler alone replaces hours of manual stack-and-register reasoning. The headless mode makes it a peer of IDA in pipeline settings. The price (free) and the openness (full source) mean it's the default for analysts who can't justify an IDA Pro license.

## Mechanics

### Projects, folders, and files

- A **project** holds a set of folders. Each folder holds one or more files. Files can be raw binaries, archives, or imported from a `git` repository. Ghidra stores project state in `.gpr` and `.rep` files; both should be excluded from version control and treated as build artifacts.
- When you import a file, Ghidra runs the **analyzers** — auto-analysis passes that identify functions, recognise library code, build the call graph, and so on. You can configure which analyzers run per file.

### The default workflow

1. **File → Import File** — pick the binary. Ghidra detects format and ISA. Choose "Yes" to analyse, or "No" to control analyzers.
2. **CodeBrowser** opens. The **Listing** is the disassembly; the **Decompile** window is the decompiled C-like output; the **Symbol Tree** lists functions; the **Defined Strings** view is searchable.
3. Double-click a function in the Symbol Tree to navigate. `G` goes to an address. `Ctrl+Shift+E` (or `L`) renames a function. `;` adds a comment.
4. The **References** panel shows callers and callees of the current function — `Ctrl+Shift+F6` for callers, `Ctrl+Shift+F7` for callees.
5. Type information is critical: setting a function's signature in the **Function Call Fixup** dialog propagates types to callers. Use **Edit → Function Signature** to import from a header or define inline.
6. **Window → Script Manager** for Java/Python scripts. Ghidra's API is large; the high-traffic surface is `currentProgram`, `currentAddress`, `getSymbolTable()`, `getListing()`, `getFunctionManager()`, `getReferenceManager()`.

### Decompiler tips

- The decompiler is *decompiler-as-a-tool*, not a C compiler. It does not run; it analyses the SSA form of the function and produces pseudo-C.
- Type inference is the most important knob. Define types (`Data Type Manager`) for any struct you can recover from the binary; the decompiler will then name fields and unflatten loops.
- The decompiler's *p-code* intermediate representation is itself a target — for very hard functions, switching to the **P-code** view in the Listing and stepping through the IR is more productive than reading the decompiled C.
- **Recovering structure from a CTF or packed binary:** identify the major function boundaries first (using the Symbol Tree and cross-references), then work inward. Don't try to fully decompile a packed function; mark it as a stub and follow its callees instead.

### Headless mode

```bash
analyzeHeadless /path/to/project MyProject \
  -import /path/to/binary \
  -postScript /path/to/script.py \
  -deleteProject
```

This is the standard CI integration: import, run a Python script (or chain of scripts), optionally export, then delete the project. Common pipeline uses:

- Function extraction to JSON for downstream tooling.
- Symbol/type recovery for use in other tools.
- Diffing two versions of a binary: import both, script the comparison, write a report.

The headless mode is *significantly* slower than the GUI for the same analysis because the GUI re-uses the same JVM and starts with already-loaded metadata. For CI, give it a warm-up step (an initial analyse of a small dummy file) if your project has many concurrent jobs.

## Approach

### First pass on a new binary

1. Import with the default analyzers. For non-standard binaries, disable *Embedded Media* and *Decompiler Parameter ID* analyzers (they can take a long time on huge binaries).
2. In the Symbol Tree, sort by size. The largest functions are usually the most interesting.
3. Search the Defined Strings view for version numbers, file paths, URLs. These give you anchor points into the code.
4. For each major function, set the type signature, then run *Analysis → One Shot → Decompiler Parameter ID* to recover arguments.
5. Mark interesting functions with a custom label (e.g. "PROT") so the script manager can find them later.

### Comparing two builds

Use Ghidra's built-in **Version Tracker** (Window → Version Tracker). It correlates functions across two binaries and labels matches. For more flexibility, write a Python script that exports the function list and signatures from both, diffs them, and produces a CSV.

### Recovering types from a system library

If you suspect a function is `malloc`, import a matching glibc / ntdll / dyld binary alongside the target. Ghidra's *Function ID* database has known library fingerprints; matching is usually automatic for glibc, msvcrt, and the standard Apple/iOS/Android system libraries.

## Common pitfalls

- **The default analyzers take *forever* on a 100+ MB binary.** Disable the slow ones (Decompiler Parameter ID, Embedded Media, Complex Ptr Analysis) for an initial pass, then re-enable on a per-function basis.
- **Stale analysis state.** If you re-import a file or change a function by hand, the existing analysis can be wrong. Use *Analysis → One Shot → Clear Code Bytes* to invalidate a range, then re-analyse.
- **Trusting the decompiler output as C.** It's pseudo-C, generated from p-code. Variable names, types, and control flow are the decompiler's *guess*; for high-stakes claims, verify in the Listing.
- **Project files in version control.** A `.gpr` file is a small handle; the `.rep` next to it is a multi-GB database. Add both to `.gitignore` and never commit them.
- **Hard-coded script paths.** Ghidra's `Script Manager` resolves scripts by name, not path. For portable pipelines, use the `GHIDRA_SCRIPTS` environment variable or `-preScript` / `-postScript` arguments.

## Tooling pointers

- [Ghidra download and docs](https://ghidra-sre.org/) — the official source.
- [Ghidra Scripts repo](https://github.com/NationalSecurityAgency/ghidra/tree/master/GhidraScripts) — bundled scripts; a good starting point.
- [ghidra_boilerplate](https://github.com/cmu-sei/GHOST) — community resources.
- [pwndbg](https://github.com/pwndbg/pwndbg) and [GEF](https://github.com/hugsy/gef) — GDB plugins that pair well with Ghidra's static view.

## References

- [Ghidra official site](https://ghidra-sre.org/)
- [Ghidra API Javadoc](https://ghidra.re/ghidra_docs/api/) — extensive; bookmark it before writing scripts.
- ["The Ghidra Book" (No Starch Press)](https://nostarch.com/ghidra-book) — the canonical reference.
