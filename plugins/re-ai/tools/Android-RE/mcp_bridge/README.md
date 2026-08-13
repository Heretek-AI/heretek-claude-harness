# @android-re/mcp-bridge

TypeScript MCP server providing an RE-focused Android device bridge.
Backed by `adbkit` for connection-pooled async access to `adb`, plus
`@modelcontextprotocol/sdk` for the MCP transport.

## What this is

This server is the **TypeScript counterpart** to the Python
`android-re-mcp-dynamic` server. They share the same ADB binary and
the same device list, but expose different tool surfaces:

- **Python (`android-re-dynamic`)** — Frida session lifecycle,
  script loading, RPC, logcat streaming, dumpheap, screenshots,
  MITM setup, intent / broadcast / clipboard.
- **TypeScript (`mcp_bridge`)** — Low-level `adb` primitives:
  `shell`, `pull`, `push`, `install`, `forward`/`reverse`,
  `logcat` (with follow), `screencap`, `screenrecord`, `dumpsys`,
  `input`, `getprop`/`setprop`, `frida-ps`.

Compose them in a single Claude Code session for full dynamic
control.

## Why not just use one server?

The Python server focuses on **Frida** (the heavy-lifting
instrumentation tool) because the Python frida client is the
canonical binding. The TypeScript server focuses on **adb** because
`adbkit` is a mature async pool and fits the Node event loop.

## Tools (18)

| Tool | Purpose |
|------|---------|
| `adb_devices` | List connected devices |
| `adb_shell` | Run `adb shell <command>` |
| `adb_pull` | Pull a file device → host |
| `adb_push` | Push a file host → device |
| `adb_install` | Install an APK |
| `adb_uninstall` | Uninstall a package |
| `adb_forward` | Forward device port → host |
| `adb_reverse` | Reverse host port → device |
| `adb_logcat` | Stream or fetch logcat |
| `adb_screencap` | Capture screen PNG |
| `adb_screenrecord` | Record screen MP4 |
| `adb_getprop` | Read system property |
| `adb_setprop` | Set system property |
| `adb_list_packages` | List installed packages |
| `adb_dumpsys` | Run `dumpsys` |
| `adb_input` | Send tap / swipe / keyevent |
| `frida_list_processes` | List processes on a device |
| `frida_ps` | Alias for `frida_list_processes` |

## Building

```bash
pnpm install
pnpm build
```

The server is launched via:

```bash
node dist/index.js
```

To register with Claude Code:

```bash
claude mcp add android-re-bridge -- node /path/to/mcp_bridge/dist/index.js
```

## License

Apache-2.0.
