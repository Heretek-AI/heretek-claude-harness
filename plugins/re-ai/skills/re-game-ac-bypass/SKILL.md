---
name: re-game-ac-bypass
description: Analyze a Windows game binary that ships with an anti-cheat runtime. Use when the analyst is working on a Windows .exe that has a sibling .sys driver, or that the user names as a "game with anti-cheat", or that the static-triage flags as having kernel-mode callbacks. Wraps re-frida for the userland hook surface, re-winedbg for kernel-mode single-step on the loaded driver, and re-static-triage for the import/export surface. Vendor-neutral: the skill talks about observable anti-cheat primitives (kernel callbacks, integrity checks, telemetry beacons, driver loads), not specific commercial products.
---

# Game Anti-Cheat Runtime Analysis

## When to use

Use this skill when the analyst is working on a
Windows game binary that ships with an anti-cheat
runtime and needs to understand which primitives
the runtime installs. The trigger conditions:

- The static triage flags a sibling `.sys` driver.
- The user names the binary as "a game with
  anti-cheat" (or hands you a sample + asks for
  the anti-cheat analysis).
- The `.text` section has a per-frame polling
  loop (a sign of a watchdog integrity check).

The output is a per-primitive map of the
anti-cheat surface. Categories only — never
names a specific commercial product.

## What this skill returns

1. **Kernel-callback enumeration** — the
   register/unregister pattern catalog. Each
   callback is a category (process-creation,
   thread-creation, image-load, registry-change,
   object-handle, driver-load).
2. **Anti-cheat primitive map** — kernel-callback,
   integrity-check, telemetry-beacon, driver-load,
   file-system-watch, registry-watch, per-category
   counts.
3. **Telemetry beacon trace** — the runtime
   hook surface for HTTP / WinHTTP / ws2_32
   calls. Paired with `re-pcap` to confirm
   on the wire.
4. **Runtime class** — ``userland-only``,
   ``driver-attached``, ``kernel-callback-rich``,
   ``telemetry-rich`` (or ``unknown`` when the
   walker can't classify).

## What this skill does NOT do

- **Does not auto-bypass.** The skill reports
  the surface; the analyst decides what to
  bypass.
- **Does not patch the driver.** Driver
  patching is out of scope; the override-scope
  contract from `CLAUDE.md` only covers the
  Output/<run-id>/patches/ directory.
- **Does not name specific commercial
  anti-cheat products.** Categories only.

## Workflow

**Step 1 — Static triage (parallel-safe)**

```
re-static-triage(path=game_exe_path)
re-game-ac-bypass.map_anti_cheat_primitives(path=game_exe_path)
```

The static side flags the import / export /
section surface.

**Step 2 — Driver enumeration (if a .sys sibling is present)**

```
re-winedbg.launch_under_wine(exe=game_exe_path)
re-winedbg.info_modules(session=wine_session)
```

The driver list comes from the loaded-module
view under Wine. Pair with
``re-game-ac-bypass.enumerate_kernel_callbacks``
to catalog the registration patterns.

**Step 3 — Runtime hook install**

```
re-frida.start_session(session=ac_session, target=game_exe_path)
re-frida.hook_method(session=ac_session, module=target, symbol=<integrity_check_export>)
```

The analyst picks which exports to hook based
on the static map.

**Step 4 — Telemetry beacon trace**

```
re-game-ac-bypass.trace_telemetry_beacon(
    session=frida_session,
    target=game_exe_path,
    duration_s=30,
)
```

Pairs with `re-pcap` to confirm on the wire.

**Step 5 — Runtime classification**

```
re-game-ac-bypass.classify_anti_cheat_runtime(path=game_exe_path)
```

Returns the runtime class label.

## Output report format

```markdown
# Game Anti-Cheat Runtime Analysis — <game_exe>

## Static
- imports: 412
- exports: 18 (4 anti-cheat-specific ordinals)
- sections: .text 0x..., .rdata 0x...
- sibling drivers: 1 (anti_cheat_driver.sys)

## Kernel callbacks
- process-creation: 4 (PsSetCreateProcessNotifyRoutine)
- thread-creation: 2 (PsSetCreateThreadNotifyRoutine)
- image-load: 1 (PsSetLoadImageNotifyRoutine)
- driver-load: 3 (IoRegisterPlugPlayNotification + 2 ob callbacks)

## Anti-cheat primitives
- kernel-callback: 10
- integrity-check: 5 (text-section SHA-256 + IAT walk)
- telemetry-beacon: 7 (WinHTTP calls per minute)
- driver-load: 1
- file-system-watch: 4
- registry-watch: 2

## Runtime class
driver-attached + kernel-callback-rich + telemetry-rich

## Telemetry beacon trace (30s)
- POST https://ac-vendor.example/api/v1/heartbeat (every 60s)
- POST https://ac-vendor.example/api/v1/integrity (every 5min)

## Limitations
- The trace only saw what the loaded driver did
  in 30s. The analyst should re-run with
  longer duration or specific user actions
  (e.g. aim, click) to see the per-action
  callbacks.
```

## Pairing with other skills

- `re-static-triage` — the broader binary
  triage. Use first to identify the import /
  section surface.
- `re-pcap` — for the wire-side confirmation
  of the telemetry beacon.
- `re-format-decode` — for the driver binary
  (`.sys`) — a separate KSY walk if the
  driver has a custom IoControl interface.
- `re-anti-analysis-scan` — for the broader
  anti-analysis primitive surface (the
  anti-cheat runtime is *one* surface; the
  game itself has a separate anti-piracy
  surface).
