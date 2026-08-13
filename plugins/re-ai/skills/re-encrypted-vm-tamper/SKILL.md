---
name: re-encrypted-vm-tamper
description: Unified encrypted-VM bytecode detection + family identification + lazy-decrypt-stub characterization. Use when the user says "is this binary protected by an encrypted VM", "what family of bytecode protection is this", "characterize the encrypted-VM handler", "where's the lazy-decrypt stub", or hands you a binary whose section table has unusual names (.vmp0, .xtls, .arch, .themida, .ecode, etc.). Calls re-lief.get_sections + re-rizin.disassemble_function + re-llm-decompile.decompile_function and produces a per-family characterization. Pairs with re-vm-reverse (which adds the dynamic Wine-trace half) and re-drm-fingerprint (which adds the broader catalog score).
---

# Encrypted-VM Bytecode Tampering Analysis

## When to use

Use this skill when the analyst's first read of a binary's section
table shows encrypted-VM-bytecode indicators: unusual section names
(`.vmp0`, `.vmp1`, `.xtls`, `.didata`, `.ecode`, `.xdata`,
`.xpdata`, `.udata`, `.00cfg`, `.arch`, `.link`, `.xcode`,
`.xtext`, `.sbss`), W^X (writable + executable) permissions, or
a `.rodata` that is suspiciously large and high-entropy.

The user gives you a binary path (or a section name from a prior
analysis) and asks for "what kind of encrypted-VM bytecode is
this" or "where does it decrypt itself at runtime". The output is
a per-family characterization — no specific commercial product
named.

**What this skill returns** (a Markdown report):

1. **Header** — file path, section count, suspected family
2. **Section table** — every section, its permissions, size,
   entropy, and the family it suggests
3. **Family identification** — the closest matching entry from
   `data/drm-indicators.yaml::pattern_indicators.mappings`
4. **Lazy-decrypt-stub detection** — whether the binary has a
   1-bit done-flag + page-walk pattern at startup
5. **Disassembly excerpts** — the entry of the dispatcher +
   the first 3 handler entries
6. **Limitations** — what this skill did NOT recover (handler
   semantic inference, dynamic trace)

## What this skill does NOT do

- **Does not produce a runtime trace.** The encrypted-VM bytecode
  body is decrypted on first use; for a runtime trace, escalate
  to `re-vm-reverse` (which uses Wine + `re-winedbg`).
- **Does not name a commercial product.** Family identification
  is descriptive (the "encrypted-VM bytecode, IL2CPP target"
  category, the "encrypted-VM bytecode, proprietary-engine target"
  category, etc.) — not a vendor attribution.
- **Does not crack the bytecode.** The handlers are reported as
  raw disassembly; the analyst's job is to map them to
  virtual-instruction semantics over time.

## Workflow

**Step 1 — Section table + entropy**

```
re-lief.get_sections(path)
```

For each section, note:
- **Name** — match against the `section_indicators.rules` in
  `data/drm-indicators.yaml` (the rules cover all known families).
- **Permissions** — W^X (W + X) is a strong signal that the
  section is decrypted in place at runtime.
- **Entropy** — high-entropy (>7.5) read-only sections are
  likely the encrypted body; low-entropy `.text` is the real
  native code.
- **Size ratio** — if `.rodata` is 100x larger than `.text`,
  the encrypted body is in `.rodata`.

**Step 2 — Family identification**

Cross-reference the section table against
`data/drm-indicators.yaml::pattern_indicators.mappings`:

- `.xtls / .didata / .ecode / .xdata / .xpdata / .udata / .00cfg`
  → encrypted-VM bytecode, Unity IL2CPP target
- `.arch / .link / .xcode / .xtext / .sbss` (with `.rodata` as
  encrypted body) → encrypted-VM bytecode, proprietary-engine target
- `.vmp0 / .vmp1` (with `VMP` handler prefixes) → encrypted-VM
  bytecode (alternative dispatcher variant)
- `.themida / .winlice` → encrypted-VM bytecode (WinLicense-family)
- `.code` with W^X → encrypted-VM bytecode (CISC-dispatch variant)

The `confidence` field in each mapping is the heuristic strength,
not a guarantee. For low-confidence matches, confirm with a
deeper pass.

**Step 3 — Lazy-decrypt-stub detection**

The "lazy decrypt stub" is a startup-time routine that decrypts
one page of the encrypted body and sets a "done" flag. The
canonical pattern is:

```
mov  rax, [done_flag]      ; read the 1-bit flag
test rax, rax              ; already decrypted?
jnz  skip_decrypt
; (decrypt one page here)
mov  [done_flag], 1        ; mark decrypted
skip_decrypt:
; (continue with the real entry point)
```

To detect: disassemble the entry function, look for a
"read-modify-write to a global byte" + "conditional jump over
the decrypt block" pattern. The decrypt block itself is
small (one page = 4 KB) and ends with a memory barrier or
serializing instruction.

**Step 4 — Disassemble the dispatcher**

The dispatcher is the function that, on every VM-step, reads a
byte from the bytecode stream and jumps to the corresponding
handler. Look for an indirect-jump with a register index:

```
jmp  [reg + rax*8]         ; or similar — the handler table lookup
```

Disassemble the dispatcher and the first 3 handler entries:

```
re-rizin.disassemble_function(path, function="<dispatcher_addr>")
```

The handler bodies are the encrypted-VM bytecode's virtual
instructions. They are typically small (10-30 native instructions
each) and use only a small register set (rax, rcx, rdx, rsi, rdi).

**Step 5 — LLM decompile (optional, high-value)**

The handler bodies are often 10-30 instructions of obfuscated
arithmetic. Run them through `re-llm-decompile.decompile_function`
for a higher-level reading. The LLM decompiler is much better
than `pdc` at producing readable C-like pseudocode from short,
arithmetic-heavy sequences.

**Step 6 — Cross-reference the dynamic half**

The lazy-decrypt-stub tells you where the body is decrypted. The
dispatcher tells you where the handlers live. To map the
handlers to virtual-instruction semantics, you need a runtime
trace: escalate to `re-vm-reverse` for the Wine + `re-winedbg`
half.

## Output report format

```markdown
# Encrypted-VM Bytecode Analysis — <path>

## Header
- File: ...
- Section count: N
- Suspected family: "encrypted-VM bytecode, proprietary-engine target"
- Confidence: Medium-High

## Section table (encrypted-VM-relevant only)

| Section | Flags | Size | Entropy | Family signal |
|---|---|---|---|---|
| .text | RX | 1.6 MB | 6.2 | real native code |
| .rodata | R | 300 MB | 7.95 | encrypted body |
| .arch | R | 200 KB | 5.1 | proprietary-engine target |
| .link | R | 80 KB | 4.8 | proprietary-engine target |
| .xcode | RWX | 1 MB | 7.6 | encrypted-VM bytecode body |
| .xtext | RX | 200 KB | 5.5 | proprietary-engine target |
| .sbss | RW | 4 KB | 0.0 | proprietary-engine target |

## Family identification
- Closest match: "encrypted-VM bytecode, proprietary-engine target"
- Confidence: Medium-High
- Other candidates (in order):
  - "encrypted-VM bytecode, Unity IL2CPP target" (Low — no
    GameAssembly.dll / global-metadata.dat pairing)
  - "encrypted-VM bytecode (CISC-dispatch variant)" (Low — no
    .code W^X)

## Lazy-decrypt stub
- Found: yes, at 0x180001234
- Done-flag: byte at 0x180020000
- Decrypts: one page of .xcode

## Dispatcher disassembly
- Address: 0x180005678
- Handler table: 0x180100000
- First 3 handler entries (raw disassembly):
  - handler[0]: 0x180105000
  - handler[1]: 0x180105080
  - handler[2]: 0x180105100

## Limitations
- The handler bodies are short, arithmetic-heavy sequences.
  The LLM decompiler produces a C-like reading but the
  underlying virtual-instruction semantics are not yet
  recovered.
- The dynamic half (which virtual instruction corresponds to
  which handler index) is not in this report. Run
  `re-vm-reverse` for the runtime trace.
```

## Pairing with other skills

- `re-drm-fingerprint` — for the broader catalog score. The
  fingerprint skill consumes `data/drm-indicators.yaml` and
  reports the matches across all families.
- `re-vm-reverse` — for the dynamic Wine + `re-winedbg` half.
  The encrypted-VM bytecode body is decrypted on first use;
  a runtime trace is the only way to map the handlers to
  virtual-instruction semantics.
- `re-mba-deobfuscate` — for the MBA-obfuscated arithmetic
  inside individual handlers. `re-triton.solve_constraint` is
  the entry point (after the z3.BitVec fix in Cycle 1 / T1.4).
- `re-llm-decompile` — for the higher-level reading of
  individual handler bodies.
