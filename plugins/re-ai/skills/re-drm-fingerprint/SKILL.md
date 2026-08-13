---
name: re-drm-fingerprint
description: Detect anti-tamper / hardware-fingerprinting routines in a binary. Use when the user says "is this DRM-protected", "find the fingerprint routine", "is this a hardware-locked binary", "what's reading the host fingerprint", "encrypted-VM bytecode", "this looks like a packed interpreter". Combines static import + section analysis with the drm-indicators.yaml catalog to produce a confidence score and a pattern indicator. Vendor-neutral — attribution is up to the user.
---

# Anti-Tamper / Hardware-Fingerprint Detection

## When to use

Use this skill when you want to know whether a binary contains an anti-tamper routine that fingerprints the host. The skill produces a **confidence score** (Low / Medium / High) and a **pattern indicator** (the *category* of anti-tamper — encrypted-VM bytecode interpreter, MBA-obfuscated arithmetic, legacy disc-based protection, etc.) but it does NOT crack the protection — it just identifies the fingerprint routine's location and components.

Common prompts:

- "Is this binary DRM-protected?"
- "What reads the hardware fingerprint?"
- "What kind of anti-tamper is this? (encrypted-VM bytecode / MBA-obfuscated / legacy disc-based / ...)"
- "Where in the binary is the host-fingerprint code?"
- "What anti-debug techniques does this use?"

**This skill does NOT crack the protection.** It identifies the fingerprint routine. Cracking is a separate, much larger effort.

## Companion data

Read `data/drm-indicators.yaml` from the plugin root. The skill uses five sections:

- `kuser_shared_data` — KUSER offset catalog
- `peb` — PEB field catalog
- `hwid_apis` — HWID-vector API catalog
- `section_indicators` — section-name / permission heuristics
- `anti_debug_indicators` — anti-debug detection catalog
- `pattern_indicators` — heuristic pattern-category mappings (vendor-neutral)

## Workflow

The skill runs in 5 stages. Stages 1-4 are static; stage 5 is LLM-assisted synthesis.

### Stage 1 — Section triage (re-lief, parallel with Stage 2)

1. `re-lief.parse_binary(path)`. Note format, arch, hashes, signed.
2. `re-lief.get_sections(path)`. Match section names against `data/drm-indicators.yaml::section_indicators.rules`. Flag:
   - **High signal:** name match against `\vm`, `\vmp`, `\code`, `\themida`, `\winlice`, `\securom`, `\xtls`, `\didata`, `\ecode`, `\xdata`, `\xpdata`, `\udata`, `\00cfg`.
   - **Medium signal:** W^X flags.
   - **Medium signal:** `virtual_size >> raw_size` on a code-like section.
3. Score: each high signal +3, each medium signal +1.

### Stage 2 — Import signal (re-rizin, parallel with Stage 1)

1. `re-rizin.list_imports_exports(path)`.
2. For each import in `data/drm-indicators.yaml::hwid_apis::high_signal`, check if the binary imports it. Each match +2.
3. For each import in `hwid_apis::medium_signal`, +1.
4. Specifically flag:
   - `LoadLibraryA` + `GetProcAddress` — the binary dynamically resolves helpers, defeating import hooks. +1.
   - Ordinal-only imports — common in anti-tamper-wrapped binaries. +0.5.

### Stage 3 — String scan (re-lief, parallel with Stage 4)

1. `re-lief.categorize_strings(path, min_length=5, max_per_category=200)`.
2. The `hwid` bucket is the score: count it.  Each matched high-signal HWID API from `data/drm-indicators.yaml::hwid_apis.high_signal` is worth +2.
3. The `anti_debug` bucket counts checks whose `confirmation:` is `string_only` or `import_only` (e.g., IsDebuggerPresent, OutputDebugString, NtQueryInformationProcess, CheckRemoteDebuggerPresent, PEB.BeingDebugged) at +0.5 each. **`requires_disasm` checks (RDTSC, INT 2D, INT 3, exception-hooking decoys) are NOT counted here** — they are detected in Stage 4 via `re-rizin.search_bytes` for the canonical opcodes. **`requires_xref` checks (e.g., scattered-bit register storage) are deferred to Stage 6 manual review.** The categorizer's `meets_threshold: bool` field surfaces whether the bucket has at least `min_evidence: 2` distinct primitives — a single-primitive match (e.g., a binary that only imports `IsDebuggerPresent` for legitimate reasons) is still in the `samples[]` list but is `meets_threshold: false`.
4. The `obfuscation` bucket contains the VM-pack byte-pattern indicators (the seed keywords include `decrypt`, `dispatch`, `handler`, `vm_entry`, `kUSER`, `PEB`, `BeingDebugged`, `NtGlobalFlag`).  +2 per unique match. The `min_evidence: 3` gate suppresses single-keyword hits (e.g., a binary that only mentions `xor` in a string).
5. Runtime strings that suggest HWID assembly land in the `fingerprint` bucket (`Volume{...}`, `MachineGuid`, `SMBIOS` keywords).  +0.5 each.
6. **Special case — encrypted-VM bytecode interpreter:** if the binary has a `large_section_with_tiny_text` shape and a `\.xtls` / `\.didata` / `\.ecode` / `\.xdata` / `\.xpdata` / `\.udata` / `\.00cfg` section (from the section_indicators rules), the categorizer's `obfuscation` bucket will fire on the encrypted bytecode region's *string-table entries* (lookup / dispatch / handler strings) even though the bytecode itself is opaque.  That's the encrypted-VM bytecode category signal — the LLM cross-references with the section list to confirm.
7. **v2.9.0 — Special case — Pattern A-DW (third-party-ATD-
   wrapped UE5 variant):** the section set is different
   (`.text + .rdata + .arch + .xcode + .xtext + .xtls
   + .trace` — see `ANTI-TAMPER-TAXONOMY.md` Pattern
   A-DW). The `\.arch` + `\.trace` + `\.xpdata` trio
   is the third-party-ATD-specific layer; `\.xcode` +
   `\.xtext` is the encrypted-VM bytecode body. The
   categorizer's `obfuscation` bucket fires on the
   encrypted bytecode region's string-table entries
   the same way as Pattern A; the section set is
   the deciding signal between Pattern A and
   Pattern A-DW. Confirmed empirically in the v2.9.0
   stress test (see
   `See the RE-AI output directory.
   per-target/<ue5-target>/stage8-seven-section-co-occur.md`).

### Stage 3a — Debug-directory / POGO scan (v2.9.0; re-lief)

For PE binaries, the debug directory carries the
IMAGE_DEBUG_TYPE_CODEVIEW (type 2, the PDB pointer)
+ IMAGE_DEBUG_TYPE_POGO (type 10) + miscellaneous
entries. The POGO entry is the **third-party-ATD's
trigger-arming metadata**; its presence in a UE5
binary is a Pattern A-DW signal.

```bash
# MCP path (preferred; added v2.9.0):
mcp__re-lief__get_debug_directory(path=...)
# Returns {debug_entries, has_pogo_entry, has_codeview_entry,
#          pogo_indices, codeview_indices, entries: [...]}
# A POGO entry surfaces with kind: "POGO" in the entries list.

# Skill-side fallback (the v2.9.0 ship path for hosts
# that don't have the new MCP tool installed):
python3 references/pogo_debug_check.py <path-to-pe>
# Same output shape (JSON via --json flag).
```

The PDB filename vendor-tag signal (a non-matching
tag in the CODEVIEW RSDS stream) is resolved by
`re-pdb.parse_pdb` rather than this read-path.

### Stage 4 — Anti-debug / direct read check (re-rizin, parallel)

1. `re-rizin.search_bytes(path, "0F 31")` for RDTSC. Each hit +0.5.
2. `re-rizin.search_bytes(path, "CD 2D")` for INT 2D. Each hit +1.
3. `re-rizin.search_bytes(path, "CC")` and check surroundings for SEH (a high CC count in `.text` is suspicious; the skill uses 10+ as a threshold).
4. `re-rizin.list_imports_exports` for `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `OutputDebugString`. Each +0.5.
5. For each high-signal hit, `re-rizin.disassemble_function` on the enclosing function and look for the patterns in `data/drm-indicators.yaml::anti_debug_indicators.checks`.

### Stage 5 — Synthesis (the LLM does this)

Combine the section score, import score, string score, and anti-debug score into a single confidence bucket:

| Total | Confidence |
|---|---|
| 0–3 | **Low** — generic anti-RE; not a DRM-specific signal. |
| 4–8 | **Medium** — likely a DRM or anti-tamper routine; pattern unclear. |
| 9+ | **High** — high-confidence anti-tamper; pattern indicator below is likely correct. |

**Score-gating rule (Cycle 3, 2026-06-06):** the `anti_debug` and `obfuscation` buckets contribute their per-match score only when `meets_threshold: true` is reported in the categorizer output (i.e., the bucket has at least the `min_evidence:` count of distinct catalog primitives). A bucket with `count > 0` but `meets_threshold: false` is surfaced in `samples[]` for the LLM's context but does not contribute to the score. This eliminates the single-primitive false positives (e.g., a binary that imports only `IsDebuggerPresent` for legitimate reasons, or a binary that mentions `xor` in a string but has no VM-pack shape).

Then cross-reference with `data/drm-indicators.yaml::pattern_indicators` to produce a pattern indicator. The pattern indicator is independent of the confidence score — a binary with confidence 4 might be 90% encrypted-VM bytecode if the imports and section names line up. The user supplies vendor attribution based on their context.

### Stage 6 — Locate the fingerprint routine (re-rizin)

If the user wants to find the actual code (not just confirm it exists):

1. From the imports in Stage 2, the fingerprint routine must call the HWID-vector APIs. Use `re-rizin.get_xrefs(path, target="<api_name>", direction="to")` to find the callers.
2. For each caller, `re-rizin.disassemble_function` and look for the API call. The "first big function that calls the HWID APIs" is the candidate.
3. Confirm by checking that the function *also* reads KUSER or PEB (a quick `re-rizin.search_bytes` for the offset values).
4. Report the address, size, and a 1-2 paragraph description of what the function does.

## Output

Produce a Markdown report:

```markdown
## Anti-Tamper Fingerprint Report: <filename> (sha256: <hash>)

### Section indicators
- Matched: encrypted-VM-style section (size 0x18000, RWX, no exports) — **+3**
- W^X on .text: yes — **+1**

### Import indicators
- GetVolumeInformationW — **+2**
- GetComputerNameW — **+2**
- GetUserNameW — **+2**
- NtQuerySystemInformation — **+2**
- LoadLibraryA + GetProcAddress — **+1**
- (medium) GetAdaptersInfo — **+1**

### String indicators
- vendor-tagged string literal in PDB filename — **+2**

### Anti-debug indicators
- 12x RDTSC — **+6** (capped at +3)
- IsDebuggerPresent — **+0.5**

### Score
- Section: 4
- Imports: 10
- Strings: 2
- Anti-debug: 3.5
- **Total: 19.5 → High confidence anti-tamper**

### Pattern indicator
**Encrypted-VM bytecode interpreter (Unity IL2CPP target)** — see data/drm-indicators.yaml::pattern_indicators:
- section match: yes
- HWID-vector imports: yes (4 of 5 high-signal)
- vendor-tagged PDB filename: yes
- anti-exception-hooking pattern: not confirmed (would need dynamic analysis)

### Recommended next steps
- Locate the fingerprint routine: use re-rizin.get_xrefs on GetVolumeInformationW.
- Trace the routine: re-gdb.run_to_breakpoint + step.
- For VM lifting: re-vm-reverse (this binary almost certainly has an encrypted-VM-style .vm section).
- For a final report: re-report.
```

## Limitations

- The skill is **static-only**. It does not run the binary. Anti-analysis that activates only at runtime (timing checks, exception-based detection) is not fully verifiable statically.
- A binary can import a HWID API for legitimate reasons (e.g. a system-info tool). The skill reports the import; the LLM uses context to decide if it's an anti-tamper routine.
- The score weights in Stage 5 are heuristics. A binary with `+10` from RDTSC alone isn't a DRM — it's just a benchmark or game.
- The skill is best for Windows PE. ELF binaries (Linux) have less coverage in the catalog; extend `data/drm-indicators.yaml` if you encounter a Linux anti-tamper scheme.

## What this skill does NOT do

- It does NOT crack the protection. It identifies the fingerprint routine.
- It does NOT bypass anti-debug. For that, v3 candidate.
- It does NOT produce a YARA rule for the protection (v2 candidate).
- It does NOT compare two binaries' protection schemes (use `re-lief.normalize_for_diff` for that).
- It does NOT name a specific commercial vendor — see ANTI-TAMPER-TAXONOMY.md for why.

## Extending the catalog

When you encounter a new DRM scheme with a public analysis, add a new entry to `data/drm-indicators.yaml`:

- A new entry under `section_indicators.rules` if the scheme has a recognizable section.
- A new entry under `hwid_apis.high_signal` if the scheme reads an unusual API.
- A new entry under `anti_debug_indicators.checks` if the scheme uses a novel anti-analysis technique.
- A new entry under `pattern_indicators.mappings` for the pattern category.

**Note on `confirmation:` for new anti-debug checks:** every new entry under `anti_debug_indicators.checks` must carry a `confirmation:` field with one of `string_only` / `import_only` / `requires_disasm` / `requires_xref`. Checks tagged `requires_xref` have no automated detection path — they are surfaced manually via `re-vm-reverse` Stage 3 (the scattered-bit register storage pattern) when the VM dispatcher is located.

Keep the catalog LLM-readable: prose where possible, structured fields only where the LLM needs to query them.
