---
title: "Electron Apps"
category: "web-hybrid"
platforms: ["windows", "macos", "linux"]
difficulty: "beginner"
tags: ["webassembly", "static-analysis", "dynamic-analysis"]
summary: "How an Electron app is packaged — the asar archive, the bundled Chromium, the main/renderer process split, and the typical ways to read its source and intercept its network."
updated: "2026-06-04"
related: ["web-hybrid/02-webassembly", "web-hybrid/04-hybrid-frameworks", "tools/04-frida"]
---

## Summary

An Electron app is a Chromium browser, a Node.js runtime, and your code — packaged together. The Chromium and Node binaries are untouched; what the developer wrote is usually a small `app.asar` archive plus some glue. The "RE an Electron app" question reduces to: extract the asar, read the JS, and — for anything that's been minified or compiled to native — dive into the `node_modules`.

## Why this matters

A large fraction of desktop apps today are Electron (VS Code, Slack, Discord, Notion, Figma, Obsidian, the list goes on). They're not "native" — but they're not a webpage either. They have a Node.js context with full file-system and network access, a renderer context that runs Chromium, and a small native bridge (`@electron/remote` and friends). For the analyst, this means almost everything the app can do is also accessible from a debugger.

## Mechanics

### The on-disk layout

A typical Electron app on disk (macOS example):

```
MyApp.app/
└── Contents/
    ├── Info.plist                    # macOS bundle metadata
    ├── MacOS/
    │   └── MyApp                     # the Electron launcher (renamed)
    └── Resources/
        ├── app.asar                  # the developer's code, packed
        │                             # (or app/ as an unpacked directory)
        ├── locales/                  # Chromium locales
        ├── resources.pak             # Chromium resources
        ├── snapshot_blob.bin         # V8 startup snapshot
        ├── v8_context_snapshot.bin   # V8 pre-compiled JS
        ├── icudtl.dat                # ICU (Unicode/CLDR) data
        ├── chrome-sandbox            # SUID sandbox helper (Linux/macOS)
        └── <many other Chromium files>
```

On Windows and Linux the layout differs but the principle is the same: there's a launcher executable, a big blob of Chromium files, and a single `app.asar` containing the JS.

### What's in `app.asar`

`asar` is a simple read-only archive format invented by the Electron team. It's a tar-like file with a JSON header listing the files and their offsets. Browsing tools (`asar` CLI, `asar` Explorer) treat it as a virtual filesystem.

Common contents:

```
app.asar
├── package.json
├── main.js                        # or "main": "dist/main/index.js"
├── preload.js                     # the bridge script (runs in renderer)
├── renderer/                      # the UI bundle
│   ├── index.html
│   ├── index.js
│   └── styles.css
├── node_modules/                  # a *lot* of node_modules
│   └── ...
├── dist/                          # or "build/" for compiled output
└── native/                        # .node files (N-API addons)
```

If the developer has enabled `asar` integrity (`app.asar.unpacked` with signed contents) or has moved some files to `app.asar.unpacked` (often done for native modules that can't be loaded from inside an archive), the structure shifts slightly.

### The process model

An Electron app has at least three types of process:

1. **Main process** — runs Node.js with the developer's `main.js`. Full file system / network / native access. Manages windows, the app lifecycle, and IPC.
2. **Renderer process** — one per window (or BrowserView). Runs the UI code in a Chromium sandbox. By default, Node.js is **not** available in the renderer (since Electron 5+); the renderer talks to main via `contextBridge` / `ipcRenderer`.
3. **GPU / utility processes** — Chromium's own. Usually not interesting to the analyst.

The main ↔ renderer bridge is via `ipcMain` (in main) and `ipcRenderer` (in renderer), or via the modern `contextBridge.exposeInMainWorld` API which exposes a small, controlled surface from preload into the renderer's window object.

### Source maps

If the developer shipped source maps (`.map` files alongside the JS, or inline `//# sourceMappingURL=`), the original TypeScript / JSX is recoverable. Many "production" Electron apps accidentally ship source maps. Look for them inside the asar:

```bash
asar extract app.asar extracted/
grep -r "sourceMappingURL" extracted/
```

If the source map is referenced but the file isn't shipped, the path is often a leak — the original source tree location on the developer's machine.

## Approach

### Step 1: extract the asar

```bash
# Install once
npm install -g @electron/asar

# Extract
asar extract app.asar extracted/
```

This gives you the entire JS bundle, including the main process script, the renderer bundle, and a lot of `node_modules`. Most of the time, you can `grep` for interesting API calls and immediately see the equivalent of the app's source.

### Step 2: read the main process

The main process is the "real" entry point. It defines:
- The windows and their preload scripts.
- The IPC handlers — the privileged surface exposed to the renderer.
- All file system, network, and native module access.

Look for `ipcMain.handle(...)` and `ipcMain.on(...)` calls; these are the IPC entry points the renderer can hit. For each, the corresponding renderer-side call (`ipcRenderer.invoke('channel', ...)`) tells you the channel name and the arguments.

### Step 3: attach DevTools to the renderer

The cleanest path into the renderer. In production, the developer often hides DevTools, but it's still reachable:

- **Help → Toggle Developer Tools** (some apps leave the menu enabled).
- **`Cmd+Option+I`** (macOS) / **`Ctrl+Shift+I`** (Windows/Linux) — Chromium's standard DevTools toggle, intercepted by the app unless explicitly disabled.
- **Env var override** — launching the app with `ELECTRON_ENABLE_LOGGING=1` and the right flags sometimes opens DevTools. Or run with `--remote-debugging-port=9222` and connect Chrome at `chrome://inspect`.

Once in DevTools, you have full access to the renderer's JS context. The Sources panel shows the bundled JS; the Network panel shows every HTTP request; the Application panel shows cookies, IndexedDB, and local storage.

### Step 4: read the network traffic

For a real reverse-engineering session, you want to intercept the actual HTTPS requests. The standard tools apply:

- **mitmproxy** as the system proxy. The app will refuse to talk if it does certificate pinning — see the `cert-pinning` topic in [`android/07-ssl-pinning`](../android/01-apk-structure.md) for the pattern (the techniques are the same; the API surface differs).
- **DevTools' Network panel with "Preserve log"** for unencrypted traffic.
- **frida** to hook `net.request` (the Electron HTTP client) or `fetch` / `XMLHttpRequest` (the renderer).

### Step 5: native modules

`*.node` files in the asar are N-API / Node addons. They're standard ELF / Mach-O / PE binaries. Pull them out and load in your disassembler as you would any other shared library.

## Common pitfalls

- **Source maps that point to internal CI paths.** `//# sourceMappingURL=https://ci.internal/myapp/build/main.js.map` is a leak; it tells you the build system layout.
- **DevTools is not actually disabled.** Disabling DevTools in Electron means *not binding the menu shortcut* — but the renderer's own JS can still be inspected by running with `--remote-debugging-port`.
- **Obfuscated main process.** Some apps pack the main process with `bytenode` (V8 bytecode) or `nexe` (compiled to native). The asar is still there, but the `main.js` is a stub that loads the bytecode / native binary. In that case, headless interception (mitmproxy + frida on the runtime) is more productive than reading source.
- **The `node_modules` are huge.** Don't extract them to read them — `grep` the asar directly. Most of `node_modules` is unused.
- **The "Chromium" version is the Electron version's Chromium, not your system Chromium.** When you see Chromium-specific DevTools features, the relevant version is the one in the `chrome` string in the app's process.

## Tooling pointers

- `@electron/asar` — the official CLI; also importable as a Node module.
- `DevTools` (built into Chromium) — your primary renderer-side tool.
- [`frida`](../tools/04-frida.md) — for runtime hooks on the main or renderer process.
- `mitmproxy` — for network interception.
- [`ghidra`](../tools/01-ghidra.md) / IDA — for the native modules.
- `chrome://inspect` — connects to Electron apps started with `--remote-debugging-port=9222`.

## References

- [Electron documentation: Application Architecture](https://www.electronjs.org/docs/latest/tutorial/process-model)
- [Electron ASAR format](https://github.com/electron/asar)
- [Electron Security Checklist](https://www.electronjs.org/docs/latest/tutorial/security) — for what the developer *should* have done, useful for finding what they *didn't*.
