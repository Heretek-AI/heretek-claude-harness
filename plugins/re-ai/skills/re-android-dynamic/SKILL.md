---
name: re-android-dynamic
description: Run-time analysis of an Android APK via Frida. Use when the user hands you an Android APK in Input/ and wants runtime hook traces, SSL-pinning bypass, root-bypass, or method-call replay. Combines re-apktool static info with re-frida start_session + hook_method + rpc_export to capture per-method traces, class-loader behavior, and runtime primitives. Falls back to canonical Frida scripts for root / FLAG_SECURE / cert-pinning. Does not auto-bypass anti-tamper; the analyst reviews the trace.
---

# Android Runtime Analysis (Frida)

## When to use

Use this skill when the user hands you an Android APK
(`.apk`) and asks for *runtime* visibility into what
the app does — root detection probes, SSL pinning,
method call traces, class-loader enumeration, network
beacon tracing.

The static side (`re-apktool.parse_apk` +
`re-apktool.classify_apk_protection`) is the
companion to the dynamic side. Pair them: static
first, dynamic second.

## What this skill returns

A Markdown report combining:

1. **Static** — APK package / version / min+target SDK /
   permissions / DEX class count.
2. **Protection classification** — per-category matches
   from `re-apktool.classify_apk_protection`:
   `apk_packager`, `dex_obfuscator`,
   `native_vm_bytecode_interpreter`, `anti_tamper_runtime`,
   `string_encryption`, `resource_encryption`,
   `anti_debug_native`, `anti_frida_native`,
   `root_detection`, `ssl_pinning`.
3. **Runtime** — per-method hook traces, class-loader
   dumps, root-bypass + SSL-pinning-bypass summaries,
   network beacon hits.
4. **Vendor-neutral summary** — every label is a
   category, never a commercial product.

## What this skill does NOT do

- **Does not bypass anti-tamper silently.** The skill
  installs a hook and reports what the hook saw. The
  analyst reviews the trace.
- **Does not auto-mutate the APK.** Smali patching
  is out of scope here; pair with a separate APK
  repackaging workflow.
- **Does not name specific commercial obfuscators /
  packagers / apps.** Categories only.

## Workflow

**Step 1 — Static first (parallel-safe)**

```
re-apktool.parse_apk(path)
re-apktool.classify_apk_protection(path)
re-apktool.list_dex_classes(path)
```

These three calls can run in parallel — the
report-write tool merges the outputs.

**Step 2 — Frida session start**

```
re-android-dynamic.start_android_session(target="com.example.app", device_id="usb")
```

Returns the session_id. Record it for the next calls.

**Step 3 — Install bypasses (optional)**

```
re-android-dynamic.check_root_bypass(session=session_id)
re-android-dynamic.check_ssl_pinning_bypass(session=session_id)
re-android-dynamic.install_objection(session=session_id)
```

Each loads a small Frida script and reports which
checks fired. The reports are *passive* — the analyst
decides whether to run the bypass.

**Step 4 — Trace a Java method**

```
re-android-dynamic.trace_method(
    session=session_id,
    target="com.example.app",
    class_fqn="com.example.Network",
    method_name="sendRequest",
)
```

Returns the hook install confirmation. Pair with
`re-frida.script_call` to invoke the trace.

**Step 5 — Class-loader dump**

```
re-android-dynamic.dump_class_loader(session=session_id, class_name="com.example.Network")
```

Returns the loaded-classes list. Useful for finding
the obfuscator's runtime class set (when the
static class names are encrypted).

**Step 6 — Network beacon trace**

Pair with `re-pcap` to confirm the network trace on
the wire. The Frida-side hook is the userland view;
the PCAP side is the kernel-side view.

## Output report format

```markdown
# Android Runtime Analysis — <package>

## Static
- Package: com.example.app
- Version: 1.2.3 (minSdk 24, targetSdk 33)
- Permissions: 12
- DEX classes: 412

## Protection classification
- dex_obfuscator: 412 (all classes have 1-2 letter names)
- string_encryption: 8 (decrypt stubs detected)
- native_vm_bytecode_interpreter: 2 (.so with .text=.bss shape)
- anti_tamper_runtime: 1 (one .so with anti-debug strings)
- ssl_pinning: 2 (OkHttp + NetworkSecurityConfig)

## Runtime
- root_probes: 3 (su, Magisk mount, SafetyNet)
- ssl_pinning_bypass_attempted: 3 (TrustManager, OkHttp, NSC)
- method_traces: 14 (see per-method summary)
- network_beacons: 0 (no HTTP/HTTPS calls in 30s)

## Limitations
- The trace only saw what the loaded classes did
  during the 30s window. The analyst should re-run
  with a longer duration or specific user actions.
- Class-loader dump returned the live class set;
  the obfuscator may swap classes at runtime.
```

## Pairing with other skills

- `re-static-triage` — the broader binary triage
  (imports, sections, capabilities). Use first.
- `re-format-decode` — for the native .so side
  (encrypted-VM bytecode interpreter, JNI dispatcher).
- `re-anti-analysis-scan` — when the analyst wants
  the full anti-analysis primitive surface (Android +
  native + memory-integrity).
- `re-pcap-correlate` — to confirm the network
  trace on the wire.
- `re-il2cpp-decompile` — for Unity IL2CPP games
  packaged as APKs.
