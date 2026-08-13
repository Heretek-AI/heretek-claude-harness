---
name: re-vm-reverse
description: Reverse engineer a custom bytecode VM in a binary. Use when the user says "this binary has a custom VM", "encrypted-VM bytecode", "what is this .vm section", "this looks like a packed interpreter", "I see a dispatcher pattern". Combines static section/import analysis with dynamic dispatcher tracing to lift, cluster, and document the handlers. Vendor-neutral.
---

# Custom VM Bytecode Reverse Engineering

## When to use

Use this skill when a binary contains a custom bytecode interpreter — a dispatcher that fetches the next handler from a table and jumps to it, where the original x86 logic is replaced with a register-based VM. Common scenarios:

- The user says "encrypted-VM bytecode" / ".vm section" / "this looks like a packed interpreter"
- The user points to a function that "looks like a dispatcher" or "loops on a handler table"
- `re-static-triage` flagged a suspicious large, W^X, no-exports section
- The user wants to "lift the VM" or "understand the bytecode"

**This skill does NOT bypass anti-tamper.** It identifies and documents the VM; the user decides what to do with the result.

## Companion data

Read `data/drm-indicators.yaml` from the plugin root before starting. Sections most relevant to this skill:

- `vm_dispatcher_patterns` — disassembly patterns for the dispatcher
- `section_indicators` — section-name / permission heuristics
- `pattern_indicators` — pattern-category mappings (vendor-neutral)

## Workflow

The skill runs in 5 stages. Stages 1-3 are static; stage 4 is dynamic; stage 5 is LLM-assisted.

### Stage 1 — Section triage (re-lief, parallel)

1. `re-lief.parse_binary(path)` for format, arch, hashes.
2. `re-lief.get_sections(path)` — look at the section list. The skill cares about:
   - Section names matching `\.vm`, `\.vmp`, `\.code`, `\.themida`, `\.winlice`, `\.securom` (from `drm-indicators.yaml::section_indicators.rules`).
   - Sections with W^X (R+W+X flags all set).
   - Sections with `virtual_size >> raw_size` (the VM bytecode is encrypted/compressed at rest; expands at runtime).
   - Sections with no exports, no debug info, no symbol table — the VM is deliberately opaque.
   - **v2.9.0 — Pattern A-DW (third-party-ATD-wrapped UE5 variant):**
     `.text + .rdata + .arch + .xcode + .xtext + .xtls +
     .trace` (7 sections, all present together). See
     `ANTI-TAMPER-TAXONOMY.md` Pattern A-DW for the
     canonical detection rule. Empirically confirmed
     in the v2.9.0 stress test (subdir 4).

**Stop here if no suspicious section is found.** The binary probably doesn't have a custom VM and the user is looking at a different problem.

### Stage 2 — Import signal (re-rizin, parallel)

1. `re-rizin.list_imports_exports(path)`. Look for the import patterns from `drm-indicators.yaml::hwid_apis` (a custom VM often pairs with a fingerprinting routine). Specifically:
   - Ordinal-only imports (no name) — common when the VM imports its helpers by ordinal.
   - Imports of `LoadLibraryA` + `GetProcAddress` — almost certain: the VM dynamically resolves helpers to defeat import hooking.
2. `re-lief.categorize_strings(path, min_length=5, max_per_category=200, skip_sections=[".idata", ".xtls", ".xpdata", ".udata", ".xdata", ".didata", ".ecode", ".00cfg"])` — the `obfuscation` and `crypto` buckets surface the dispatch / handler / license markers; the `hwid` and `anti_debug` buckets are the cross-check against the encrypted-VM-WinLicense-style family in `pattern_indicators`.  The `activation` bucket is the key one for the encrypted-VM-license-gate path (late-bound license calls).  The `by_category` map is the input to the `pattern_indicators` lookup at Stage 6.

### Stage 3 — Find the dispatcher (re-rizin)

This is the static half of the lift. The dispatcher is a function with one of the patterns in `drm-indicators.yaml::vm_dispatcher_patterns.x86_64_patterns`.

1. `re-rizin.analyze_function(path, level=2)` to get the function list.
2. For each large function (>= 50 instructions), `re-rizin.disassemble_function(path, function, max_insns=200)` and look at the tail.
3. A function whose last 5-10 instructions contain a `jmp reg` (or `ret` to a register-loaded address) is a dispatcher candidate.
4. Confirm with `re-rizin.get_xrefs(path, target=<function>, direction="from")` — a dispatcher should be called from many places, often as a tail-call.

If multiple candidates exist, prefer the one with the most incoming xrefs.

### Stage 4 — Trace the dispatcher (re-winedbg / re-gdb)

Dynamic confirmation. The dispatcher should be called many times; sampling its inputs gives a profile of the VM's behavior.

**Windows .exe target** (the typical case for a protected Unity binary):
1. `re-winedbg.start_winedbg_gdbserver(exe, port=0, session="vm")` to start the gdbserver.
2. `re-winedbg.attach_winedbg_gdbserver(session="vm", host="127.0.0.1", port=<port>, exe=exe)` to connect the gdb-client.
3. `re-winedbg.set_breakpoint(session="vm", target="*<dispatcher_addr>")`.
4. `re-winedbg.gef_trace_breakpoint(session="vm", target="*<dispatcher_addr>", register="$rcx", format="idx=%d\\n", max_hits=1000)` to drive the trace server-side. The tool returns a structured `{hits: [{n, regs}], truncated: bool}` table — the same as the v1 manual `commands 1; silent; printf ...; continue; end` workflow, but no GDB-command prose is needed. v2.4 of the server added this tool (replaces the v1 workaround described in earlier revisions of this skill).

**v2.9.0 — Frequency aggregation helper (the 10×1000 batching
pattern):** the v2.4 `max_hits=1000` cap on
`gef_trace_breakpoint` is the constraint that drove the
v2.9.0 stress test's vm-unpack subdir 5. To overcome
the cap, drive the MCP call N times in the same session
and feed each batch JSON to
`references/handler_frequency_analyzer.py`:

```bash
# Capture each batch JSON, then aggregate.
python3 references/handler_frequency_analyzer.py \
    --batch-json batch-1.json batch-2.json ... batch-N.json \
    --output handler-frequency-table.json \
    --target /path/to/binary \
    --dispatcher-rva 0x<hex> \
    --register $rcx
```

The helper aggregates per-handler-index counts and
emits the top-5 + the full frequency table. Pure
stdlib; the script does not call any MCP tool — the
caller (the Claude session running the PoC) drives
the `re-winedbg.gef_trace_breakpoint` MCP call N
times and feeds the results in. The frequency
table is the v2.9.1+ YARA seed for the catalog-
driven VM-scheme YARA rules (Gap 11).

**Linux ELF target** (rare for VM-pack samples, but possible):
1. `re-gdb.start_session(path, session="vm")` to open a GDB session.
2. `re-gdb.run_to_breakpoint(session="vm", target="<dispatcher_function>")`.
3. Workaround (v1 skill): use `re-gdb.step_count` in a loop, log the register, repeat. Slow but works for ~100 samples. v2.5 is expected to backport `gef_trace_breakpoint` to `re-gdb` for parity.

5. After sampling, you have a frequency table: `(handler_index, hit_count)`. The shape of the table tells you what the VM is doing:
   - **One or two handlers dominate (>50% of hits each):** likely a tight interpreter loop with a couple of hot opcodes (e.g. add, mov).
   - **Many handlers, roughly equal frequency:** likely a large instruction set with no hot path.
   - **Long tail of single-hit handlers:** likely one-off initializers; the VM is doing setup, not runtime interpretation.

### Stage 5 — Lift and cluster handlers (re-llm-decompile)

1. For the top-N handlers (by frequency), `re-rizin.disassemble_function` on each. Each handler is typically a small function (< 50 instructions).
2. `re-llm-decompile.explain_function` on each — get a one-line natural-language description. Cluster by description.
3. For the most interesting handlers (the ones that have side effects, branch, or call helpers), `re-llm-decompile.decompile_function` to get C pseudocode.
4. Synthesize a handler dictionary: `handler_index → {description, decompiled, side_effects}`.

### Stage 6 — Document the VM (the LLM does this)

Produce a Markdown report with these sections:

```markdown
## VM Reverse: <filename> (sha256: <hash>)

### VM metadata
- Section: .vm (0x1000–0x1A000, RWX)
- Entry point: 0x401050
- Dispatcher: 0x401080
- Handler table base: 0x402000
- Handler count: 87
- Sample size: 1000 dispatches

### Dispatcher
- One-line description: "mov rax, [rdi+rsi*8]; jmp rax"
- Cycle: tight (2 instructions, no validation)

### Handler frequency profile
| Handler | Hits | Description |
|---|---|---|
| 0x00 | 412 | "add two VM regs" |
| 0x01 | 187 | "mov VM reg from immediate" |
| 0x02 | 89  | "compare two VM regs" |
| ... | ... | ... |

### Most interesting handlers
(Each with decompiled C in a fenced block and 2-3 sentence explanation.)

### Vendor guess
Encrypted-VM bytecode interpreter (high confidence) — see data/drm-indicators.yaml::pattern_indicators.
- .vm section name match: yes
- HWID vector imports: yes (GetVolumeInformationW + GetUserNameW)
- Scattered-bit register storage: yes (see handler 0x42)
- Anti-exception-hooking decoys: yes (writes to [rsp+0x10]..[rsp+0x98])
- Vendor attribution: user-supplied (RE-AI does not name a specific commercial vendor)

### Recommendation
- For deeper deobfuscation: use `re-mba-deobfuscate` on handler 0x42.
- For control-flow understanding: use `re-symbolic-exec` on the dispatcher.
- For a final report: use `re-report`.
```

## When the dispatcher can't be found

Common reasons:

- **The VM is initialized by a constructor (`DllMain`, `__init_array`).** Try `re-rizin.analyze_function` filtered to small functions called from the entry point.
- **The dispatcher is hidden behind a function pointer table.** Each exported function is a stub that calls into the VM. Look at the export list, find the smallest functions, and disassemble them.
- **The VM uses a different dispatch mechanism** (e.g. a `ret`-based tail-call chain instead of a `jmp` table). Look for sequences like `pop reg; jmp reg` or `mov reg, [rsp]; add rsp, 8; jmp reg`.
- **The binary is statically dispatched** (no VM, just indirect calls). That's not a custom VM and is better analyzed with `re-vuln-research` or `re-symbolic-exec`.

## Limitations

- The skill is best at x86/x64 VMs. For ARM/ARM64 VMs, the dispatcher patterns are different — the catalog needs extending.
- The frequency-analysis stage depends on GDB interaction. On Windows targets, `re-winedbg.gef_trace_breakpoint` does the trace server-side (fast, structured). On Linux ELF targets, use `re-gdb.step_count` in a loop (slow; parity with `re-winedbg` is a v2.5 candidate).
- Lifting a handler that does dynamic control flow (e.g. computes its next handler index from VM state) requires symbolic execution — use `re-symbolic-exec` after the static lift.
- The skill does NOT attempt to remove the VM or restore the original x86. That's a v3 "VM removal" project, not a v1 "VM understanding" skill.

## What this skill does NOT do

- It does NOT bypass DRM. It documents the VM; the user decides what to do.
- It does NOT produce a YARA rule for the VM (v2 candidate).
- It does NOT compare two binaries' VMs (use `re-lief.normalize_for_diff` for that).
