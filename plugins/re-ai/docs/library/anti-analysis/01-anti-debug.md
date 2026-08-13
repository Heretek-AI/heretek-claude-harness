---
title: "Anti-Debug Techniques"
category: "anti-analysis"
platforms: ["linux", "windows", "macos", "android", "ios"]
difficulty: "intermediate"
tags: ["dynamic-analysis", "detection", "protection"]
summary: "How software detects the presence of a debugger — ptrace, NtQueryInformationProcess, exception-based traps, /proc probes, timing checks — and the high-level shape of how to neutralise each."
updated: "2026-06-06"
related: ["anti-analysis/03-anti-sandbox", "anti-analysis/04-anti-frida", "anti-analysis/07-vm-bytecode-proprietary", "tools/04-frida"]
---

## Summary

Anti-debug is the most common form of anti-analysis: a binary checks at runtime whether a debugger is attached, and exits, corrupts state, or runs a decoy if it is. The checks fall into a small number of families; once you know the families, recognising a new one is mostly pattern-matching.

## Why this matters

If you can bypass anti-debug, you can attach a debugger, set breakpoints, trace execution, and inspect memory. If you can't, you're limited to static analysis — slower, lower-fidelity, and often not feasible for code that only makes sense at runtime (e.g. JIT'd code, dynamically-decrypted strings, callback-heavy code).

## Mechanics

The families, with the canonical examples for each major platform:

### 1. ptrace-based (Linux, macOS, some Android)

`ptrace(PTRACE_TRACEME, 0, ...)` is a one-shot way for a process to declare "a tracer is already attached to me". A second tracer cannot then attach — `ptrace(PTRACE_ATTACH, ...)` returns `EPERM`. Self-debugging is a classic detection trick: if `PTRACE_TRACEME` fails, somebody else is already debugging you.

```c
if (ptrace(PTRACE_TRACEME, 0, 0, 0) < 0) {
    exit(1);  // already being debugged
}
```

The bypass is to intercept the `ptrace` syscall (or, more cleanly, the `dlopen`/`dlsym` call) and return 0.

### 2. PEB inspection (Windows)

The Process Environment Block (PEB) contains an `BeingDebugged` byte (set by the kernel when a debugger attaches) and a `NtGlobalFlag` (which gains `FLG_HEAP_ENABLE_TAIL_CHECK | FLG_HEAP_ENABLE_FREE_CHECK | FLG_HEAP_VALIDATE_PARAMETERS` — 0x70 — under a debugger). Reading either is enough to detect.

```c
PPEB peb = (PPEB)__readgsqword(0x60);
if (peb->BeingDebugged) {
    ExitProcess(1);
}
```

Some apps go further and call `NtQueryInformationProcess` with `ProcessDebugPort`, `ProcessDebugObjectHandle`, `ProcessDebugFlags`, or `ProcessBasicInformation` to query the kernel for the same information more directly.

### 3. Exception-based (cross-platform)

A debugger typically receives (and either swallows or passes back) exceptions raised by the traced process. Code can set a "trap" — write a `INT 3` / `0xCC` byte over its own code, or `INT 2D`, or `UD2` — and then check whether the exception is still pending. Under a debugger, the trap is consumed silently; without a debugger, it propagates and is caught by a SEH/`__try` block or a signal handler.

### 4. Timing / latency probes

Debugger breakpoints, single-stepping, and syscall traps all change timing measurably. A common pattern is `rdtsc` before/after a known-fast operation; if the delta is above a threshold, a debugger is suspected.

```c
uint64_t t0 = __rdtsc();
volatile int x = 0; (void)x;
uint64_t t1 = __rdtsc();
if (t1 - t0 > 1000) {
    // probably being single-stepped
}
```

This is fiddly to bypass because it interacts with the legitimate performance of the machine; a common workaround is to scale the threshold by `QueryPerformanceCounter` or `clock_gettime` deltas taken before/after the user has had time to interact.

### 5. /proc and device probes (Linux, Android)

`/proc/self/status` contains a `TracerPid:` line that's non-zero only when a debugger is attached. Reading `/proc/self/maps` shows `[vdso]` and the loader; looking for the presence of `gdb`, `ltrace`, `strace` process names via `/proc/<pid>/comm` is also common.

### 6. Hardware breakpoint registers (cross-platform)

`GetThreadContext` / `SetThreadContext` (Windows) and `ptrace(PTRACE_GETREGS, ...)` (Linux) reveal whether the debug registers `DR0–DR7` are configured. Apps can periodically read their own context and check for non-zero debug addresses.

### 7. Self-integrity / checksum-over-self

A debugger requires `PROT_EXEC` on the code pages. Apps with self-checksumming can detect when their own `.text` has been modified (e.g. an `INT 3` planted by the analyst) and refuse to continue.

### Confirmation requirements — when a string-table hit is not enough

For each family above, a *string-table hit* alone is sometimes not enough evidence to fire the detection — the string may be a link-time artifact (e.g. C++ exception-fragment names, RTTI fragments, PDB suffix) rather than runtime code. The catalog (see [RE-AI: data/drm-indicators.yaml](https://github.com/Heretek-AI/RE-AI/blob/main/data/drm-indicators.yaml)) classifies each check by confirmation level:

| Confirmation | Meaning | Example |
|---|---|---|
| `string_only` | The string-table presence is sufficient — the API call is at a runtime-fixed address. | (None of the current checks — this is a degenerate case) |
| `import_only` | The binary must *import* the API (a link-time IAT entry); the string alone is not enough. C++ symbol fragments like `_Xlength_error` were the FPs the prior string-only-equal filter produced. | `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `OutputDebugString`, `NtQueryInformationProcess` |
| `requires_disasm` | The byte-pattern check (RDTSC, INT 2D, INT 3) must be backed by a disasm hit at a call site. The string-table presence of `"RDTSC"` alone is meaningless. | RDTSC (`0F 31`), INT 2D (`CD 2D`), INT 3 (`CC`), exception-hooking decoy stack writes |
| `requires_xref` | The check requires manual xref — the automated catalog can't count it. | Scattered-bit VM-register storage (a marker of the encrypted-VM bytecode interpreter; see [`07-vm-bytecode-proprietary`](../07-vm-bytecode-proprietary.md)) |

In practice this means: when a triage shows many `import_only` checks firing, the category is real (the binary actually imports the detection API). When a triage shows many `requires_disasm` checks firing, the *count* alone is suggestive but the analyst should confirm at least one disasm site before reporting the finding. The "scattered-bit register storage" check is the most diagnostic single signal — when a binary's `obfuscation.count` includes that specific marker, the proprietary-engine encrypted-VM bytecode interpreter is very likely present.

## Approach

The general workflow, in order of escalation:

1. **Static first.** `strings` the binary for known detection strings (`"gdb"`, `"TracerPid"`, debugger PEB names). Identify the API calls being made.
2. **Attach a tracer and watch.** Run the binary under `strace -f -e trace=ptrace,openat,read` (Linux) or Procmon + DebugDiag (Windows) to see what files / syscalls it uses to detect you. The first detection that fires is usually the right one to bypass.
3. **Patch the binary.** Where the check is a single conditional branch, flipping the branch or NOPing it out works. For `IsDebuggerPresent` and friends, a single-byte patch is often sufficient.
4. **Hook the detection API.** For more sophisticated checks, use a hooking engine (frida, libpatch, custom LD_PRELOAD) to make `ptrace` / `NtQueryInformationProcess` return "no debugger here" regardless of reality.
5. **Anti-anti-anti-debug.** A binary that detects *the detector* (e.g. by hashing the code at a known location) is a tier-2 problem. Solutions include: running from a custom hypervisor, emulating the binary entirely (unicorn), or modifying the binary to be aware of the bypass and patch it back.

## Common pitfalls

- **Patching out one check and missing the next.** Production binaries usually have *several* checks at different points; the first one you see is rarely the only one. A loop in a background thread that re-checks every few seconds is a common trap.
- **Time-based checks interacting with your test harness.** If you pause the process under a debugger to inspect state, you've just tripped the timing check.
- **Self-debugging checks that you can't bypass by hooking ptrace.** If the binary spawns a child that `PTRACE_TRACEME`s, you have to either let the child live (and accept the overhead) or patch the fork.
- **Checksumming the code at runtime.** If the binary computes a hash over its own `.text` and detects that you've patched a check, the patch won't survive long. Either disable the checksum or modify the binary to always report the expected hash.

## Tooling pointers

- [`frida`](../tools/04-frida.md) — runtime hooking across platforms; the standard tool for dynamic bypass.
- [`ghidra`](../tools/01-ghidra.md) — static analysis to find detection routines in advance.
- [`unicorn` / `qiling`](https://github.com/unicorn-engine/unicorn) — CPU emulation when the binary is too hostile to run live.
- [ScyllaHide](https://github.com/x64dbg/ScyllaHide) — Windows-specific anti-anti-debug plugin for x64dbg.

## References

- [Microsoft: NtQueryInformationProcess](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationprocess)
- [ptrace(2) — Linux man page](https://man7.org/linux/man-pages/man2/ptrace.2.html)
- [The "Ultimate" Anti-Debugging Reference (PDF, Peter Ferrie)](https://pferrie.host22.com/papers/antidebug.pdf)
