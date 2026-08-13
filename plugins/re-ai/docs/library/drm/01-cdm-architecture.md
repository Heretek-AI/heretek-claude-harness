---
title: "CDM Architecture"
category: "drm"
platforms: ["android", "ios", "linux", "windows", "macos", "web"]
difficulty: "advanced"
tags: ["architecture", "cryptography", "fundamentals"]
summary: "The generic shape of a Content Decryption Module: the OEMCrypto boundary, the license-acquisition flow, the key-ladder, and the parts that move between hardware and software."
updated: "2026-06-06"
related: ["drm/02-publisher-internal-telemetry-relay"]
---

## Summary

A Content Decryption Module (CDM) is the client-side component that turns an encrypted media stream and a license into viewable frames. The shape is remarkably consistent across the major systems: an HTTP-based license dance, a key-ladder that derives per-session keys from a device-bound root, a sandboxed crypto core, and a hardware/software boundary that the security level of the deployment depends on.

> **Note on scope.** This entry describes the *architecture* — the protocol shape, the key-ladder, the hardware/software boundary — without naming specific systems. Readers who work in the space will recognise which system each paragraph is about. The library's content policy (see [CONTRIBUTING.md](../../CONTRIBUTING.md)) explains why.

## Why this matters

If you understand the CDM shape, you understand the *attack surface* the security model is trying to defend. The choices about where keys live, which side does the decryption, and what's attested to the server, all flow from this shape. Without it, every other DRM entry in this library reads like folklore.

## Mechanics

### The high-level components

A typical CDM has three logical pieces:

1. **The client library** (in the browser engine, in the media player, in the OS framework). Talks to the server, holds session state, hands encrypted samples to the CDM core.
2. **The CDM core** (sometimes called the *CDM*, sometimes the *OEMCrypto* module, sometimes a *vendor-specific binary*). Receives encrypted samples, returns clear samples. Holds the keys.
3. **The key-store / TEE bridge**. Where the device-bound root keys live. May be a TEE (ARM TrustZone, SGX enclave), a hardware secure element, or — at the lowest security level — the CDM core's own obfuscated binary.

The boundary between (2) and (3) is the security boundary. The CDM core is treated as untrusted by the key-store; the key-store only ever releases a *key handle* that the CDM core uses to decrypt specific samples. The CDM core never holds the raw device key.

### The license flow

1. The client requests a license from the license server, including a *license request* that contains a device identifier, the content ID, and (for higher security levels) an attestation token.
2. The license server validates the device/attestation, mints a license, and returns it. The license contains the *content key*, optionally wrapped in something device-specific.
3. The CDM unwraps the content key, derives per-sample keys via the key-ladder, and uses them to decrypt the media as it streams.

The license request is the place where attestation is performed — see [`drm/05-attestation`](05-attestation.md) for the chain of trust.

### The key-ladder

Keys are derived in tiers:

- A device-bound **root key** lives in the key-store. Never leaves the TEE.
- A **service key** is bound to a specific service (e.g. "the streaming app"). Server-side, this gates whether a device can play content from a particular service.
- A **content key** is the symmetric key for one piece of content. The license binds it to a particular device, period of validity, and policy (e.g. "no HD", "no offline").
- **Sample keys** (often per-segment IVs combined with a derived key, or per-sample subkeys) are used to decrypt the actual media frames.

Each tier is wrapped by the tier below. A compromise of the content key compromises only that piece of content; a compromise of the device-bound root key compromises the whole device.

### The OEMCrypto boundary

The CDM core talks to the key-store through a small, audited interface — sometimes called *OEMCrypto*, sometimes *CDM host*, sometimes simply the "keybox" API. The interface is roughly:

```
oemcrypto_open_buffer(handle, key_handle, ciphertext, iv, dst) -> plaintext_or_error
oemcrypto_get_key_handle(session_id, key_id) -> key_handle
oemcrypto_close_buffer(handle) -> status
```

The CDM core passes *encrypted* sample data and a *key handle* (not the key) to the key-store. The key-store decrypts inside its secure world and returns the cleartext. The CDM core can copy the cleartext into the media pipeline (or, at higher security levels, hand it directly to a hardware decoder path so the cleartext is never visible to the application CPU at all).

### The hardware/software boundary

This is what security levels measure. The canonical tier model (L1 / L2 / L3 / L4 in the industry-standard classification) is summarised inline below; a deeper dive is the standard text on the topic. Briefly:

- At the highest level, the entire CDM core — key-ladder, decryption, even sometimes the license parser — runs inside the TEE, and the cleartext is handed straight to a hardware decoder that draws it to a hardware-protected video path.
- At the lowest level, the CDM core is a software binary on the main CPU, the key-store is obfuscated but inspectable, and the cleartext is just a buffer in the application's address space.

The boundary defines the difficulty of *any* attack on the system. Higher levels require either compromising the TEE, finding a protocol-level bug, or going around the device (server-side mitigations). Lower levels can be attacked by patching the software CDM, or by attaching a debugger to the application and reading the cleartext buffer.

## Approach

If you're studying a CDM for defensive research, hardening, or to understand the threat model:

1. **Map the components.** Identify which binary / library / module implements the client library, the CDM core, and the key-store. On Android, this is often three separate `.so` files; on the web, the CDM core may be a sandboxed NaCl/wasm module.
2. **Trace the license flow.** With a network capture, watch the license request and license response. The size, structure, and the specific fields (especially any opaque blobs) tell you what the server is asserting.
3. **Find the OEMCrypto boundary.** On Android, the `liboemcrypto.so` interface is a small, well-defined JNI surface; on iOS, the analogous interface is the *voucher* and *vendor proprietary* libraries. Listing the exports is the first step.
4. **Identify the security level.** The tier classification (L1 / L2 / L3 / L4 in the industry-standard model) is described in most public CDM documentation; the canonical reference is the latest published specification. Most commercial deployments cluster at one of three tiers; identifying which one you're looking at collapses the rest of the analysis.
5. **Read the protocol shape, not the protocol names.** The protocol is rarely documented publicly, but the *shape* — license request, license response, key-ladder, sample decryption — is. See [`drm/03-key-ladders`](03-key-ladders.md) and [`drm/04-proxy-relay`](04-proxy-relay.md).

## Common pitfalls

- **Conflating "the protocol" with "the implementation".** The protocol is what the server expects; the implementation is what runs in the client. Both have bugs; the interesting attacks often exploit the gap between them.
- **Ignoring the server side.** The hardest part of modern DRM is the *server-side* validation: device attestation, licence-binding, anomaly detection. A protocol-level weakness in the client can be mitigated by the server refusing to issue licenses.
- **Assuming a single TCB.** A typical device has multiple TEEs (one per SoC vendor, sometimes one per OS), and the CDM may bridge between them. The actual trusted computing base is the *intersection*, not the union.
- **Reading "hardware-backed" as "unbreakable".** Hardware TEEs have had their share of CVEs (trustzone, SGX, secure boot). Hardware-rooted is a higher bar than software-only, not a perfect one.

## Tooling pointers

- `strace` / `ltrace` / frida — to watch the client library talk to the CDM core.
- A protocol-aware proxy (e.g. mitmproxy with a custom script) — to inspect the license dance.
- The disassembly tools in [`tools/`](../tools/) — for the CDM core binary itself.
- [`drm/02-publisher-internal-telemetry-relay`](02-publisher-internal-telemetry-relay.md) — the publisher-side telemetry pattern; pairs with the CDM architecture for the leak-detection side.

## References

- [W3C: Encrypted Media Extensions (EME)](https://www.w3.org/TR/encrypted-media/)
- [Marlin: DRM Reference Architecture](https://www.marlin-community.com/)
- Various academic papers on TEE-based media pipelines (search "TEE media pipeline attestation").
