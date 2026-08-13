---
name: re-origin-stub-drop
description: Bypass the managed-launcher store-gate on a PE / Mono binary that uses a managed (C# / Mono) launcher front-end for a C++ engine. Use when the user says "bypass the managed launcher gate", "remove the Mono entitlement check", or "the launcher is blocking launch". Mirrors re-steam-stub-unwrap for the managed-launcher category.
---

# Bypass the Managed-Launcher Store-Gate

## When to use

Use this skill when a PE binary has a managed-code (C# / Mono)
launcher front-end that wraps a C++ engine, and the launcher
enforces a managed-launcher store-gate (per the v2.7.0 B3
catalog entry). The gate is implemented in the managed
launcher's `MainWindow` class and reached before the C++ engine
launches.

Common prompts:

- "Remove the managed-launcher entitlement from this Mono launcher"
- "The Mono launcher is blocking launch — bypass the entitlement"
- "Bypass the managed launcher store-gate on this binary"
- "NOP the launcher gate so the engine launches directly"

**Does NOT** bypass anti-tamper wrappers (the encrypted-VM /
section-protected variety). Use `re-drm-fingerprint` to
identify those first; this skill only handles the
storefront-level gate.

## Workflow

### 1. Confirm the managed launcher front-end is present

```
re-lief.parse_binary(path)                # confirm PE32+ (Mono launches as a managed PE)
re-lief.get_imports_exports(path)         # look for mscoree.dll import (Mono / .NET)
re-dotnet.parse_assembly(path)            # confirm a .NET TypeDef table is present
re-dotnet.get_methods(path, fqn="<MainWindow fqn>")
                                          # look for GetStoreRegistryKey + GetLauncherType
```

The B3 catalog entry's signature is a `MainWindow`-class field
named `_isSteam` / `_isStore` / `_isLauncher` plus a
`GetStoreRegistryKey`-shaped method. If the assembly is
plain native PE (no `mscoree.dll` import), the binary uses
the native-launcher variant — use `re-steam-stub-unwrap`
instead.

### 2. Identify the gate

```
re-dotnet.get_fields(path, fqn="<MainWindow fqn>")
                                          # locate the _isStore / _isLauncher field
re-rizin.search_bytes(path,
    pattern="<entitlement-call canonical bytes>")
                                          # find the call site
```

The entitlement call is typically a virtual call through the
managed SDK's bridge; the byte pattern is the
`call [rax+offset]` instruction at the gate's tail.

### 3. Classify the SDK version (optional but recommended)

```
re-rizin.list_imports_exports(path="<sibling native SDK .dll>")
```

The managed-launcher SDK's companion native DLL has a
distinct export set per SDK generation. See
`references/origin_stub_classifier.py` for the structured
detection.

### 4. (DOC-ONLY) Side-file convention

The managed-launcher store-gate category has **no Valve-style
`steam_appid.txt` equivalent**. The launcher client is a
separate process from the game; it holds the entitlement state
in its own registry / per-user store. The side-file step is
therefore a documented no-op.

```
references/origin_appid_dropper.py
# Returns: {"side_file_convention": null,
#           "reason": "managed launcher client holds entitlement
#                      state in its own per-user store; no
#                      Valve-style side-file applies"}
```

This is the canonical "absent convention" signal. The skill
documents the absence; the analyst moves to Step 5.

### 5. NOP the gate (the canonical step)

The gate is a managed-code function (or a native bridge). For
the managed-code case, use `re-dotnet-patch.nop_method` (the
v2.8.1 C8 backend):

```
re-dotnet-patch.nop_method(
    path=<binary copy>,
    method_fqn="<MainWindow fqn>::GetStoreRegistryKey",
    dst=<output>,
    confirm_legal="<audit-trail reference>")
```

The patched copy is still a valid .NET assembly (the v2.8.1
C8 backend preserves the type graph; the type/method/field/
property/event counts are unchanged).

For the native-bridge case, use `re-patch.apply_patch` with
the standard 5-byte NOP primitive (`E8 → 90 ×5`).

## Live-test (manual; outside the run scope)

```bash
wine Input/.../<game>/<launcher>.exe
```

If the launcher skips the entitlement check and the engine
launches directly — bypass worked. If the launcher still
blocks, the entitlement check is in a deeper layer (the
activation-server round-trip) and the local-launch NOP is
necessary-but-insufficient. The skill does not bypass the
activation-server gate; that is a separate, larger problem.

## What this skill does NOT do

- It does NOT bypass anti-tamper. Combine with the relevant
  skill (`re-vm-reverse`, `re-encrypted-vm-tamper`) for the
  anti-tamper layer.
- It does NOT bypass the activation-server round-trip. The
  local-launch entitlement NOP skips the launcher-side
  check; the engine's activation-server handshake is a
  separate gate that this skill does not address.
- It does NOT touch other managed-launcher SDKs (GOG Galaxy
  / Epic Online Services / Amazon Games). Each managed
  launcher has its own canonical bypass. The
  `managed launcher store-gate` descriptor is the
  category-wide label; per-storefront bypasses are
  separate skills. See
  `data/drm-indicators.yaml::pattern_indicators.mappings`
  (descriptor `managed launcher store-gate`) for the
  catalog entry.
- It does NOT vendor or distribute any third-party
  managed-launcher emulator.

## References

- `references/origin_stub_classifier.py` — classify the
  managed-launcher SDK version from the sibling native DLL's
  export list
- `references/origin_appid_dropper.py` — returns
  `{"side_file_convention": null}` (the documented absence
  of a Valve-style side-file convention)
- `skills/re-steam-stub-unwrap/SKILL.md` — the native-side
  analogue (the native-launcher variant of the gate)
- `data/drm-indicators.yaml::pattern_indicators.mappings` —
  `managed launcher store-gate` (B3) catalog entry
- `See the RE-AI output directory.` —
  the LIR per-target walk that exercises this skill
