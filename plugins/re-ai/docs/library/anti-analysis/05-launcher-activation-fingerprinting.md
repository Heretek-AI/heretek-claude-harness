---
title: "Launcher Activation Library — Fingerprinting + Anti-Debug"
category: "anti-analysis"
platforms: ["windows"]
difficulty: "advanced"
tags: ["hwid", "fingerprint", "launcher", "activation", "ordinal-exports", "protection", "static-analysis"]
summary: "A small native DLL with ordinal-only exports that gates launch on a license-server round-trip and a host fingerprint — the WinHTTP + OpenSSL + X.509 import catalogue, the high-signal HWID-vector API set, the split anti-debug surface between the activation DLL and the game DLL, and how to read the strings dump to confirm."
updated: "2026-06-05"
related: ["anti-analysis/01-anti-debug", "anti-analysis/02-vm-bytecode-interpreter", "native/02-pe-section-layout", "tools/01-ghidra"]
---

## Summary

A launcher activation library is a small native DLL (1-3 MB) sitting alongside the main game binary, gating launch on a license-server round-trip and a host fingerprint. The activation library and the game library are *separate* layers; the launcher `.exe` is the glue. The composition is distinct from any encrypted-VM bytecode interpreter in the game DLL — and the two often coexist, layering on the same install.

## Why this matters

This composition is the *license-gate* layer, separate from any protection embedded inside the game DLL. Skipping it means a static review of the game DLL alone misses the entire host-fingerprint + license-server surface. The activation library is also where most of the Win32 anti-debug primitives live — `IsDebuggerPresent`, `OutputDebugStringW`, `NtQueryInformationProcess` — so a triage that looks only at the game DLL's anti-debug will miss the activation library's contribution.

A caveat: the composition isn't intrinsically malicious. Many legitimate launchers look like this; many malware droppers do too. The category is descriptive of a *structural shape*, not a verdict. Treat the result as a recommendation to read the activation library carefully, not a flag for maliciousness.

## Mechanics

The 7-observable composition that fires together. When 5+ of these are present on a single small native DLL, the category is the launcher activation fingerprinting routine.

### 1. Ordinal-only exports on the activation DLL

A 1-3 MB native DLL with **ordinal-only exports** — `@100`, `@101` — no symbol names. Exports are deliberately stripped; the names would help an analyst identify the role of each export. The launcher `.exe` knows the ordinals (it imports them by ordinal), but a third-party reader of the binary sees only `@100`.

### 2. Launcher imports only 2-3 ordinals from the activation DLL

The launcher `.exe` imports only 2-3 ordinals from the activation DLL. Nothing else. The DLL is opaque to the launcher. A typical launcher `.exe` is 500-800 KB with 5-15 total imports; the bulk of the imports are to the activation DLL by ordinal.

### 3. The activation DLL statically links a recognizable crypto library

The activation DLL statically links a crypto library. The fingerprint is the `.\crypto\...` path fragments in `.rdata` — 1,000+ of them on a typical build, with names like `.\crypto\asn1\a_bitstr.c`, `.\crypto\rsa\rsa_gen.c`, `.\crypto\evp\e_aes.c`. OpenSSL is the most common (look for `EVP_*`, `RSA_*`, `X509*`, `PKCS*`, `BIO_*`, `PEM_*` substrings); mbedTLS and BoringSSL use different but recognizable substring sets.

### 4. WinHTTP + X.509 / Authenticode imports

The activation DLL's import table shows WinHTTP plus the X.509 / Authenticode APIs:

```
WinHttpOpen, WinHttpConnect, WinHttpOpenRequest, WinHttpSendRequest,
WinHttpReceiveResponse, WinHttpQueryHeaders, WinHttpReadData,
WinHttpCrackUrl, WinHttpSetOption, WinHttpSetCredentials,
WinHttpSetStatusCallback, WinHttpCloseHandle

CryptQueryObject, PFXImportCertStore, CertFindCertificateInStore,
CryptMsgGetParam, WinVerifyTrust
```

WinHTTP is the license-server HTTP client. The X.509 / Authenticode APIs are the cert validation chain. Together, they're the license-gate's network-and-crypto surface.

### 5. 8+ of the 12 HWID-vector APIs imported

The activation DLL imports 8 or more of the 12 high-signal HWID APIs:

```
GetComputerNameW, GetUserNameW, GetVolumeInformationW, GetSystemDirectoryW,
GetWindowsDirectoryW, GetAdaptersInfo, GetAdaptersAddresses,
GetNetworkParams, NtQuerySystemInformation, NtQuerySystemInformationEx,
CryptAcquireContextW, CryptGenRandom
```

This is the *fingerprint* set — the APIs the activation routine calls to assemble a host fingerprint before sending it to the license server.

### 6. Anti-debug primitives imported

The activation DLL imports the catalog's anti-debug primitives:

```
IsDebuggerPresent        (kernel32)
OutputDebugStringW       (kernel32)
NtQueryInformationProcess  (ntdll)
```

This is the activation library's anti-debug surface. The combination of these three (and the absence of other anti-debug tricks) is the typical activation-library signature.

### 7. Strings dump shows the activation + obfuscation categories

`re-lief.categorize_strings` populates the `activation` and `obfuscation` buckets with non-trivial counts on a typical activation DLL (50-200 strings each on a 3 MB binary). The `activation` bucket surfaces the `Activate`, `License`, `Entitlement`, `Recipient`, `SignedData`, `EnvelopedData` PKCS#7 / CMS strings; the `obfuscation` bucket surfaces the `decrypt`, `dispatch`, `handler` markers from the embedded OpenSSL build.

## The split anti-debug surface

**Important observation**: when a Unity IL2CPP game is layered with an encrypted-VM bytecode interpreter *and* a launcher activation library, the anti-debug primitives are typically *split* between the two DLLs:

- The **activation DLL** owns the Win32 anti-debug APIs (`IsDebuggerPresent`, `OutputDebugStringW`, `NtQueryInformationProcess`).
- The **game DLL** (encrypted-VM wrapped) owns the VM-encrypted anti-debug. The strings from the encrypted bytecode are not directly grep-able, but the `obfuscation` bucket in `re-lief.categorize_strings` surfaces the VM-side anti-debug fingerprints.

When you see anti-debug primitives split between two DLLs in the same install directory, both layers are firing. A triage that runs `categorize_strings` on only one DLL will miss the other.

## Approach

1. **Launcher `.exe` import list.** The 2-3 ordinal-only imports from a single sibling DLL are the category-shape signal.
2. **Activation DLL export list.** `@100` / `@101` with no names confirms the opacity-by-design.
3. **Activation DLL import list** (WinHTTP + X.509 + 8+ HWID APIs + anti-debug primitives). This is the category confirmation.
4. **Strings dump** — `re-lief.categorize_strings` for `activation.count` (≥ 50) and `crypto.count` (≥ 100); `obfuscation.count` and `anti_debug.count` for the cross-check.
5. **Cross-reference the game DLL's imports** for the same HWID set. If the game DLL also imports 8+ of the 12, the binary is in *both* the encrypted-VM bytecode interpreter category and the hardware-fingerprinting routine category. This *layered* composition is the common Unity IL2CPP shipped-binary shape.

## Common pitfalls

- **Treating the launcher `.exe` as the binary to analyze.** The launcher is a 5-import forwarder; the analysis happens on the activation DLL and the game DLL.
- **Missing the split anti-debug surface.** Run `re-lief.categorize_strings` on *both* DLLs separately; the union of the `anti_debug` and `obfuscation` buckets is the full surface.
- **Assuming "ordinal-only" = "packed" or "malicious".** Many legitimate launchers ship this way; the *combination* with WinHTTP + OpenSSL + HWID APIs is the category signal, not the ordinal exports alone.
- **Missing the late-bound entry-point handshake.** The activation DLL is called *before* the encrypted-VM bytecode interpreter completes initialization. Your dynamic instrumentation must respect this order; if the launcher calls the activation library synchronously and the interpreter waits for a return, your breakpoint sequence needs to mirror that.
- **Treating the activation library as a one-time call.** Some launchers call the activation library on *every* game launch; some cache the result for N days; some re-check on every level transition. The cadence affects the dynamic instrumentation strategy.

## Tooling pointers

- [`ghidra`](../tools/01-ghidra.md) — static decompilation of the activation DLL.
- [`anti-analysis/02-vm-bytecode-interpreter`](../anti-analysis/02-vm-bytecode-interpreter.md) — the encrypted-VM family the activation library is *separate from*; both layers can coexist.
- [`native/02-pe-section-layout`](../native/02-pe-section-layout.md) — primer on the ordinal-only-exports + WinHTTP + X.509 import surface.
- [`re-lief.categorize_strings`](https://github.com/Heretek-AI/RE-AI) — keyword-bucketed strings dump; no `skip_sections` (the activation DLL is small enough to walk in full).
- [`re-rizin.list_imports_exports`](https://github.com/Heretek-AI/RE-AI) — for the WinHTTP + X.509 + HWID import confirmation.
- [`re-rizin.analyze_function`](https://github.com/Heretek-AI/RE-AI) — to identify the export functions' callers (the launcher calls the activation library's ordinals; this is the disassembly of those callsites).

## References

- [RE-AI: ANTI-TAMPER-TAXONOMY.md](https://github.com/Heretek-AI/RE-AI/blob/main/ANTI-TAMPER-TAXONOMY.md) — "Recognizing the patterns in arbitrary binaries" section.
- [OpenSSL source](https://github.com/openssl/openssl) — for the `.\crypto\...` substring patterns; the version-string pattern is the static-link fingerprint.
- [Microsoft: WinHTTP](https://learn.microsoft.com/en-us/windows/win32/winhttp/winhttp-start-page) — for the WinHTTP API family.
- [Microsoft: WinVerifyTrust](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust) — for the Authenticode / X.509 validation surface.
