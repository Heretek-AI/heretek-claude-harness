# android-re-mcp-dynamic

MCP server for dynamic Android instrumentation. Backed by
`android-re-core` (frida 17.10.1 + adb wrapper).

## Tools (30+)

| Tool | Purpose | Confirm? |
|------|---------|----------|
| `list_devices` | Enumerate Frida devices | no |
| `connect_device` | Select a specific device by id | no |
| `pair_device` | ADB pair with a wireless device | no |
| `disconnect_device` | Release a device | no |
| `install_apk` | `adb install` | **yes** |
| `uninstall_apk` | `adb uninstall` | **yes** |
| `launch_app` | `adb shell am start` | no |
| `force_stop` | `adb shell am force-stop` | no |
| `list_processes` | Enumerate PIDs on a device | no |
| `frida_spawn` | Spawn + attach a fresh process | no |
| `frida_attach` | Attach to a running process | no |
| `frida_load_script` | Load a Frida JS script on a session | no |
| `frida_unload_script` | Unload a script | no |
| `frida_list_scripts` | List scripts on a session | no |
| `frida_rpc_call` | Call `rpc.exports.<method>` | no |
| `frida_list_classes` | Enumerate Java classes in a process | no |
| `frida_eval` | Evaluate arbitrary JS in a session | no |
| `read_file_via_runas` | Read a file with the app's UID | no |
| `list_app_files` | List files in /data/data/<pkg>/ | no |
| `start_logcat` | Begin a logcat follow (returns token) | no |
| `stop_logcat` | Stop a logcat follow | no |
| `dump_heap` | Capture a heap dump | **yes** |
| `list_activities` | Enumerate activities in a package | no |
| `start_intent` | Send an intent | no |
| `send_broadcast` | Send a broadcast | no |
| `set_clipboard` | Set the clipboard | no |
| `take_screenshot` | Capture screen PNG | no |
| `tcp_forward` | Forward a device port to host | no |
| `setup_mitm` | Configure MITM cert | **yes** |
| `build_session_report` | Per-session report (logs + scripts + rpc) | no |
| `list_sessions` | List active sessions | no |
| `close_session` | Detach a session | no |

## Running

```bash
uv run --package android-re-mcp-dynamic python -m android_re_mcp_dynamic
```

To register with Claude Code:

```bash
claude mcp add android-re-dynamic -- uv run --package android-re-mcp-dynamic python -m android_re_mcp_dynamic
```

## License

Apache-2.0.
