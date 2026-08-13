---
name: android-re-dynamic-hook
description: |
  Use when the user wants to hook a method at runtime on a connected
  Android device, observe arguments/return values, trace execution,
  or dump runtime state. Triggers: "hook this method", "frida hook
  on <class>", "trace <method>", "watch this call", "intercept
  <function>", "runtime trace", "find what calls X". Requires a
  rooted device with frida-server running. Do NOT use for pure
  static analysis (use android-re-static-triage) or for native
  binary-only inspection (use android-re-native-triage).
effect:
  filesystem: read
  network: depends on hook (Frida scripts may exfiltrate)
  device: hooks a process; modifies runtime behavior; may need install/launch
requires:
  mcp:
    - android-re-dynamic
---

# Dynamic method hooking

Run a Frida hook against a running Android process, observe
arguments and return values, and capture runtime data.

## When to use

The user has a specific class/method in mind and wants to see:

- What arguments it receives at runtime
- What it returns
- Who calls it (backtrace)
- Whether a specific path is ever taken

If the user wants broad behavior analysis (which methods are called
when a button is tapped), use the frida_script_author skill to write
a tracer first. If they want SSL pinning bypass or root detection
bypass, use the dedicated skills.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `serial` | yes | Frida device id (from `frida_list_processes`) |
| `package` | yes | Target package |
| `class_name` | yes | FQCN in JNI form (e.g. `Lcom/example/Foo;`) |
| `method_name` | yes | Method to hook |
| `descriptor` | no | JVM descriptor (default: all overloads via Java.use.overload) |
| `args_to_log` | no | List of arg indices to log (default: all) |
| `backtrace` | no | Include backtrace in onEnter |
| `action` | no | `spawn` (default, attach to a fresh process) or `attach` (existing) |

## Workflow

1. **Connect to the device.**
   `mcp__android-re-dynamic__frida_list_processes` → confirm a
   device is reachable. If no devices are listed, stop and tell the
   user to plug in a rooted device and start frida-server.

2. **Spawn or attach.**
   - `spawn` (default): `mcp__android-re-dynamic__frida_spawn` with
     `serial` and `package`. Returns a `session_id`.
   - `attach`: `mcp__android-re-dynamic__frida_attach` with
     `serial` and `process_name=<package>` (or `pid`).
   Capture the `session_id`.

3. **Build the hook script.** Use the Java.use().overload(...) form
   for parameter access. A template:

   ```js
   Java.perform(function () {
     var Cls = Java.use('<class_name>');
     var overloads = Cls[<method_name>].overloads;
     overloads.forEach(function (m) {
       m.implementation = function () {
         console.log('[*] <class_name>.<method_name> called');
         for (var i = 0; i < arguments.length; i++) {
           console.log('    arg[' + i + ']:', arguments[i]);
         }
         var ret = this.<method_name>.apply(this, arguments);
         console.log('    return:', ret);
         return ret;
       };
     });
   });
   rpc.exports = { ping: function () { return 'pong'; } };
   ```

4. **Load the script.**
   `mcp__android-re-dynamic__frida_load_script` with `session_id`,
   `name=<descriptive>`, `source=<js above>`. Returns a `script_id`.

5. **Trigger the code path.** Tell the user to navigate the app
   such that the target method is called (e.g. "tap the Buy button
   to call `Payment.charge`").

6. **Read the messages.**
   `mcp__android-re-dynamic__build_session_report` with the
   `session_id`. Returns recent messages from each script.

7. **Iterate.** Adjust the script, unload, reload, repeat.

8. **Clean up.**
   `mcp__android-re-dynamic__frida_unload_script` and
   `mcp__android-re-dynamic__close_session`.

## Output

A markdown section with:

- **Session id**: <session_id>
- **Script id**: <script_id>
- **Target**: <class>.<method>
- **Observed calls**: list of arg/return tuples
- **Backtraces** (if requested): short stack frames

## Examples

### Example 1: hook `LoginActivity.validate`

> User: Hook `LoginActivity.validate` on the running app.

Steps:

1. `frida_list_processes` (verify device + PID).
2. `frida_attach` with `process_name="com.example"`.
3. `frida_load_script` with the Java.use hook.
4. Tell user to enter wrong password; observe the validate call.
5. `build_session_report` → return the args and return value.
6. `frida_unload_script` + `close_session`.

### Example 2: spawn-and-hook

> User: Spawn the app fresh and hook the `onCreate` of every Activity.

Steps: same as above, but use `frida_spawn`. The hook script
overrides `onCreate` of every class that extends Activity.

## Output convention

`take_screenshot`, `screenrecord`, and `build_session_report` write to:

```
Output/<apk-basename>-<short-sha>/dynamic/screenshot-<ts>.png
Output/<apk-basename>-<short-sha>/dynamic/screenrecord-<ts>.mp4
Output/<apk-basename>-<short-sha>/dynamic/session-report.json
```

(For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).) Override
with the `output_path` parameter on each tool.

## Notes

- frida-server version must match the frida Python client
  (17.10.1). `bin/doctor.sh` verifies this.
- Hooking a method that's called in a tight loop can overwhelm the
  logcat. Add a sampling counter in the script.
- The `rpc.exports` mechanism is a clean way to expose hook state
  to the MCP client: define an `rpc.exports.dump()` function in the
  script and call it via `frida_rpc_call` to retrieve structured
  data.
- For native (JNI) hooks, use `android-re-native` `disassemble_function`
  + `generate_frida_native_hook` to generate the JS, then load it
  here.
