---
name: re-static-triage
description: First-pass triage of an unknown binary. Use when the user says "analyze this binary", "what is this file", "triage this", "categorize the strings", or hands you an unknown executable or DLL. Calls re-lief, re-rizin, and re-capa in parallel and surfaces file info, format, sections, imports, capabilities, and suspicious indicators. Does NOT decompile or do dynamic analysis — escalate to re-decompile or re-malware-triage if a deeper look is needed.
---

# Static Triage of an Unknown Binary

## When to use

Use this skill for the **first 60 seconds** with an unknown binary. The user gives you a path, you produce a one-page triage report: what it is, what it imports, what it can do, and what looks suspicious. The output is a triage summary, not a deep analysis.

**What this skill returns** (a Markdown report with these sections):

1. **File info** — format, architecture, type (EXE/DLL/SYS/lib), size, hashes
2. **Structure** — section layout, permissions (W^X), unusual section names
3. **Imports** — DLLs and APIs the binary calls, with a capability guess
4. **Capabilities** — high-level ATT&CK/MBC mappings (via `re-capa`)
5. **Strings of interest** — URLs, IPs, registry keys, mutexes, suspicious keywords
6. **Indicator triage** — Benign / Informational / Medium / High / Critical findings

After this skill finishes, the user can choose to:

- Drill into a specific function with `re-decompile`
- Run the binary in a sandbox and use `re-dynamic-analysis`
- Solve for inputs that reach a particular branch with `re-symbolic-exec`
- Get a malware-focused report with `re-malware-triage`

## Workflow (parallel where possible)

**Step 1 — File info (re-lief)**
- Call `re-lief.parse_binary(path)`. Get format, architecture, entrypoint, imagebase, hashes, and format-specific fields (imphash for PE, PIE/NX/RELRO for ELF, code signature for MachO).

**Step 2 — Sections (re-lief, in parallel with Step 1)**
- Call `re-lief.get_sections(path)`. Note any W^X sections, non-standard names, or `virtual_size >> raw_size` (packed).

**Step 3 — Imports / Exports (re-rizin, in parallel with Step 1)**
- Call `re-rizin.list_imports_exports(path)`. Group by DLL. Flag the suspicious API sets below.

**Step 4 — Capabilities (re-capa, in parallel with Step 3)**
- Call `re-capa.detect_capabilities(path)`. Use the result for the ATT&CK/MBC summary.

**Step 5 — Strings of interest (re-lief, in parallel with Step 4)**
- Call `re-lief.categorize_strings(path, min_length=5, max_per_category=200)`. The result is pre-bucketed into {crypto, network, registry, anti_debug, hwid, process, file, fingerprint, activation, obfuscation, misc}. Inspect each bucket's `count` + `samples[]` + `meets_threshold` to populate the "Strings of interest" table below.
- **`meets_threshold` interpretation (Cycle 3, 2026-06-06):** for categories with a `min_evidence:` field in the YAML (currently `anti_debug: 2` and `obfuscation: 3`), the consumer reports `meets_threshold: bool` per bucket. A high `count` with `meets_threshold: false` is a one-off match (e.g., a binary that only imports `IsDebuggerPresent` for legitimate reasons); a high `count` with `meets_threshold: true` is a pattern. Populate the "Strings of interest" table with both `count` and `meets_threshold` so the LLM can distinguish.
- On large binaries (>100 MB, e.g. a Unity IL2CPP `GameAssembly.dll` wrapped by an encrypted-VM bytecode interpreter), pass `skip_sections=[".idata", ".xtls", ".xpdata", ".udata", ".xdata", ".didata", ".ecode", ".00cfg"]` to skip the encrypted-VM bytecode regions.  (Note: on the bundled GameAssembly sample, the import-table strings live *inside* those sections — skip only when memory is a concern, not for full visibility.)

**Step 6 — Indicator triage**
- Combine the above into a single triage table using the framework at the end of this skill.

Steps 1, 2, 3, 4, 5 are independent. **Issue them in the same tool block** so they run concurrently.

## File-info signals

When reviewing the file info from `re-lief.parse_binary`, pay attention to:

| Signal | What it means |
|---|---|
| **Architecture mismatch** | An AMD64 binary on a sample claiming ARM, or vice versa — could be polyglot. |
| **Type=SYS** (PE) | Windows driver — has `IMAGE_FILE_EXECUTABLE_IMAGE` without GUI/CUI subsystem flags. `is_dll()` and `is_exe()` are both `False`. |
| **Very large file** (>100MB) | May have an overlay, be statically linked, or contain an embedded payload. |
| **Very small file** (<2KB) | Stub or decoy. Real code is somewhere else. |
| **Entry point in `.rdata`/`.data`/`.rsrc`** | Suspicious — usually the entry point is in `.text`. Real code is in a non-standard section. |
| **Relocs stripped** (`IMAGE_FILE_RELOCS_STRIPPED`) | Prevents ASLR. Common in old malware, also in VC6-era legitimate binaries. |
| **`imphash` is empty** | No imports — packed or statically linked. Must disassemble to understand. |
| **Signed + signed recently** | Authenticode is good for trust; check the signer. Self-signed is not the same as no signature. |

## Section signals

Sections with these properties warrant follow-up:

| Signal | What it suggests |
|---|---|
| **Non-standard name** (`.UPX0`, `.mpress1`, single-letter, random) | Packer (UPX, MPRESS, ASPack) or custom obfuscation. |
| **W^X section** (both EXECUTE and WRITE) | Self-modifying code or packer unpack stub. |
| **`virtual_size >> raw_size`** | Packed — payload expands at runtime. |
| **`.text` with WRITE** | Code section is writable. Patcher or anti-debug. |
| **Empty `.text`** (zero bytes) | All code is in other sections or generated at runtime. |
| **Many small sections** | Manual packing or custom section layout. |
| **`.rsrc` very large** | Legitimate for resource-only DLLs; suspicious if mixed with executable code. |

## Import patterns

When `re-rizin.list_imports_exports` returns, group imports by DLL. The DLL list itself reveals a lot:

- `kernel32.dll` / `ntdll.dll` — core OS (process, memory, file I/O). Every PE imports these.
- `advapi32.dll` — registry, services, security. Suspicious if you don't expect registry modification.
- `wininet.dll` / `urlmon.dll` — HTTP/HTTPS (downloader, C2 beacon).
- `ws2_32.dll` — Winsock sockets (raw network, packet crafting).
- `crypt32.dll`, `bcrypt.dll` — cryptography (legitimate for HTTPS, suspicious in a process-injection tool).
- `user32.dll`, `gdi32.dll` — GUI. Normal for apps, suspicious for hidden services.
- `ntdll.dll` direct syscalls — bypasses user-mode API hooks. Common in EDR-evasion malware.

Suspicious API patterns:

| Category | APIs | What they enable |
|---|---|---|
| Process manipulation | `OpenProcess`, `CreateRemoteThread`, `WriteProcessMemory`, `VirtualAllocEx`, `NtCreateThreadEx` | Process injection |
| Memory manipulation | `VirtualAlloc`, `VirtualProtect`, `HeapCreate`, `NtAllocateVirtualMemory` | Shellcode allocation |
| Code execution | `WinExec`, `ShellExecute`, `CreateProcess`, `NtCreateProcess` | Payload execution |
| Network | `WSAStartup`, `connect`, `send`, `recv`, `InternetOpen`, `HttpOpenRequest` | C2 communication |
| Persistence | `RegSetValueEx`, `CreateService`, `ChangeServiceConfig` | Registry/service persistence |
| Anti-analysis | `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`, `NtQueryInformationProcess`, `OutputDebugString` | Anti-debug |

For exports (DLLs only), watch for:

- **Ordinal-only exports** (no name) — common in malware DLLs, deliberately hiding names.
- **Nondescriptive names** (`a1`, `function_1`, `start`) — potential hidden entry points.
- **Exports that don't match the DLL's apparent purpose** — e.g. a `crypto.dll` exporting `Inject`.

## Strings of interest

After `re-lief.extract_strings`, scan the result for:

| Finding | Severity | Notes |
|---|---|---|
| Hardcoded IP:port | High | Possible C2 server. Cross-check with threat intel. |
| `\\.\pipe\` strings | High | Named pipe — inter-process communication in injection. |
| `%TEMP%` + `.exe` in same file | High | Drops an executable to temp. |
| Registry `Run` key paths | High | Persistence via startup. |
| `Sandboxie`, `wireshark`, `procmon` | Medium | Anti-analysis. |
| Mutex name `Global\` | Medium | Singleton enforcement — common in malware. |
| Embedded config JSON/XML | High | Configuration block — may contain C2 / keys. |
| Long base64-like strings | Medium | Possibly encoded payload, config, or key material. |
| `http://` / `https://` URLs | High | External endpoint — verify it's expected. |
| File paths to `C:\Windows\...` | Info | Normal for Windows binaries, but watch for paths to unusual locations. |

**False positive guide:**

- Many strings are compiler-inserted debug info (source paths, compiler version). Normal.
- OpenSSL embeds many readable strings — `OpenSSL` in strings usually means TLS, not malicious.
- Standard API error messages (`The parameter is incorrect`) are benign.
- MSVCRT/UCRT strings are compiler-inserted — ignore `__stdio_common_vfprintf` etc.

## Indicator triage table

After gathering everything, classify each finding into a severity bucket. Not every suspicious finding is malicious.

| Severity | Criteria | Action |
|---|---|---|
| **Benign** | Compiler-inserted strings, standard section layout, expected imports for file type, normal PE characteristics | Skip; note as "clean baseline" |
| **Informational** | Odd section name but no W^X, imphash matches known packers (UPX, MPRESS), large `.rsrc` with readable content | Note in findings; could be a legitimate packer |
| **Medium** | W^X section, network imports in a utility tool, registry persistence calls, single-section PE with no imports | Flag for deeper analysis (strings + disassembly) |
| **High** | Process-injection API set + network imports, encrypted strings, dynamic API resolution, embedded IPs/URLs, ordinal-only DLL exports | Full deep analysis required |
| **Critical** | Confirmed C2 URL with hardcoded IP, embedded config with encryption keys, shellcode detected in disassembly, process-hollowing detection | Escalate; full report required |

## Reference input targets (v2.9.0 stress test)

The `See the RE-AI output directory.`
documents the per-target triage results for the 8
canonical `Input/` targets the v2.9.0 cycle probed.
The 4 new targets the v2.9.0 cycle added are the
canonical reference inputs for new triage patterns.
The per-target paths live in `Input/`; only the
per-target *patterns* (the triage signals) are
documented here in vendor-neutral form:

- **IL2CPP-static-link Steamworks case** (2 of the 4 new
  targets): the Steamworks layer is in
  `GameAssembly.dll`, not the `.exe`. The
  Steam-stub search_bytes target is the
  `GameAssembly.dll` sibling, not the launcher.
  Pattern: thin Unity launcher with only
  `UnityMain` + `KERNEL32` imports.
- **IL2CPP + storefront SDK sibling case** (1 of
  the 4 new targets): same IL2CPP-static-link
  pattern; ALSO links a secondary storefront SDK
  (separate bypass path; see `re-eos-bypass` skill).
- **Clockwork launcher case** (1 of the 4 new
  targets): 0 hits for the canonical Steamworks
  call-string in the game `.exe` — the Steamworks
  layer is in a sibling clockwork launcher DLL
  (`launcher.exe` / `CA_Launcher.dll`). Triage
  must walk the install tree for the launcher DLL.
- **Encrypted-VM + Steamworks combo case** (1 of
  the 4 new targets): 1 hit for the canonical
  Steamworks call-string in the `.text` section
  (the encrypted-VM sections `.xtls + .trace`
  are separate from the Steamworks call site).
  The 1-hit pattern is the canonical native-binary
  layout (vs the 2-hit IL2CPP-static-link case).

The per-target artifacts (entitlement-classify.json,
rationale.md, NOTES_FOR_LO.md) are in
`See the RE-AI output directory.
per-target/<target>/` (Steamworks targets) +
`See the RE-AI output directory.
per-target/<managed-launcher-target>/` (managed-
launcher case) + the EOS case in
`See the RE-AI output directory.`.

## False positive sources

- **Delphi / Borland binaries**: non-standard section names, different import patterns. Check for `Borland` or `Delphi` debug strings.
- **.NET binaries**: PE has a CLI header stub. Look for `mscoree.dll` import — different analysis path needed.
- **NSIS / InnoSetup installers**: packed with their own formats, atypical section layout. Detect via installer signature strings.
- **AutoIT / AHK compiled scripts**: PE is a stub with embedded script. Strings show AutoIT library references. Requires AutoIT decompiler for full analysis.
- **Go binaries**: large file size, no standard import table, statically linked, many runtime strings. Look for `go` or `golang` in strings.
- **Rust binaries**: similar to Go — statically linked, distinct runtime strings.

## Output format

Produce a single Markdown report with these sections in order:

```
## Triage: <filename> (sha256: <hash>)

### File info
- Format: PE / ELF / MachO / DEX
- Architecture: AMD64 / I386 / ARM64 / ARM
- Type: EXE / DLL / SYS / lib / kernel module
- Size: <bytes>
- Entry point: <hex>
- Imphash: <hash> (PE only)
- Signed: yes/no
- PIE: yes/no
- NX: yes/no

### Structure
- Sections: <n> total
- Notable: <list of unusual sections / W^X / packed indicators>

### Imports (top by category)
- Network: <list>
- Process: <list>
- Persistence: <list>
- Crypto: <list>
- Anti-analysis: <list>

### Capabilities (re-capa)
- <list of capa's high-level matches>

### Strings of interest
- <URLs / IPs / paths / mutexes>

### Triage
| Finding | Severity | Notes |
|---|---|---|
| ... | High | ... |

### Recommendation
- <decompile / dynamic / symbolic / malware-triage / report>
```

The recommendation should be one of `re-decompile`, `re-dynamic-analysis`, `re-symbolic-exec`, `re-malware-triage`, or `re-report` — the natural next step.
