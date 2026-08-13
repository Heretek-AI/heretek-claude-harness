---
name: android-re-frida-script-author
description: |
  Use when the user wants to write a custom Frida script (not just
  a one-off hook) and needs help authoring it. Triggers: "write a
  Frida script", "I need a custom frida agent", "help me write a
  hook for <case>", "tracer for <method>", "build a frida
  gadget". Loads the user-described agent into a session, verifies
  it compiles, and offers iteration. Requires a rooted device
  with frida-server running.
effect:
  filesystem: read
  network: depends on the agent
  device: loads a custom Frida agent on a process
requires:
  mcp:
    - android-re-dynamic
    - android-re-static
    - android-re-native  # for native hook templates
---

# Write a custom Frida script

Author a custom Frida JavaScript agent for a specific use case.
The skill scaffolds the script, loads it into a session, and
verifies it works.

## When to use

The user has a use case that the universal scripts don't cover.
Typical cases:

- "Trace every URL the app loads."
- "Build a runtime credential harvester that hooks getSharedPreferences."
- "I need a per-method hook for OkHttp interceptor X."
- "Native tracer for `Java_com_example_App_nativeFoo`."
- "Log every JNI call to libc."

The skill is the right starting point for any of these.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `serial` | yes | Frida device id |
| `package` | yes | Target package |
| `goal` | yes | What the agent should accomplish |
| `language` | no | `js` (default) or `qjs` (QuickJS) |
| `rpc` | no | Whether to expose an `rpc.exports.*` API for retrieval |

The user must describe the goal in one or two sentences. If
ambiguous, ask one short clarifying question.

## Workflow

1. **Gather context.**
   - `mcp__android-re-dynamic__frida_list_processes` to confirm
     a device is available.
   - If the user has a target class/method in mind, use
     `mcp__android-re-static__find_classes` /
     `mcp__android-re-static__find_methods` to verify the FQCN.
   - For native (JNI) targets, use
     `mcp__android-re-native__find_symbol` /
     `mcp__android-re-native__generate_frida_native_hook` for
     template JS.

2. **Plan the script.**
   Decide which Frida APIs to use:
   - `Java.use(...)` for Java-side hooks
   - `Interceptor.attach(Module.findExportByName(...))` for native
   - `Stalker.follow(...)` for code tracing
   - `Memory.*` for raw memory access
   - `rpc.exports.*` for structured retrieval
   - `Java.scheduleOnMainThread(...)` for UI-thread work

3. **Write the script.** Use the templates in
   [`scripts/`](scripts/) as starting points. Common patterns:

   ```js
   // Template: trace every call to a method
   Java.perform(function () {
     var Cls = Java.use('com.example.Foo');
     Cls.bar.overloads.forEach(function (m) {
       m.implementation = function () {
         console.log('[*] bar called with', arguments);
         return this[Cls.bar.name].apply(this, arguments);
       };
     });
   });
   rpc.exports = { count: function () { return counter; } };
   ```

4. **Spawn or attach.**
   `mcp__android-re-dynamic__frida_spawn` (or `frida_attach`).

5. **Load the script.**
   `mcp__android-re-dynamic__frida_load_script` with
   `session_id`, `name=<descriptive>`, `source=<js>`.

6. **Validate.**
   - If `frida_load_script` returns `{"error": ...}`: read the
     `message` field for the compile error, fix, retry.
   - On success, call `mcp__android-re-dynamic__frida_rpc_call`
     with `script_id` and `rpc_method="ping"` to verify the agent
     is alive.
   - Build the session report and inspect any console output.

7. **Iterate.**
   Adjust the script based on the user's feedback. Re-load
   after each iteration.

8. **Clean up.**
   `frida_unload_script` + `close_session`.

## Output

The final script source, plus:

- **Session id** and **script id** if the agent is loaded.
- **RPC API** (the `rpc.exports.*` methods, if any).
- **Test invocation**: a sample `frida_rpc_call` to validate.

## Examples

### Example 1: trace every URL the app loads

> User: I need a frida script that logs every URL the app fetches
> (URLConnection, OkHttp, WebView).

Steps:

1. Open the project to verify the OkHttp version (if present).
2. Spawn the app.
3. Load a script that hooks:
   - `okhttp3.OkHttpClient$Builder.build`
   - `java.net.URL.openConnection` (fallback)
   - `android.webkit.WebView.loadUrl`
4. Have the user perform a few actions.
5. `build_session_report` → return the log lines.
6. Iterate: add a filter, add JSON parsing, etc.

### Example 2: native tracer for a JNI method

> User: I want a tracer for `Java_com_example_App_nativeFoo`.

Steps:

1. `mcp__android-re-native__generate_frida_native_hook` to
   produce the Interceptor.attach template.
2. Wrap it in a full agent script (with `rpc.exports`).
3. Spawn the app + load the script.
4. User calls the function → log lines arrive.

## Output convention

The authored `.js` script should be saved to:

```
Output/<apk-basename>-<short-sha>/scripts/<descriptive-name>.js
```

Use the `Write` tool (not an MCP tool) to persist the script. The Frida
session / runtime output still flows through `build_session_report` and
lands at:

```
Output/<apk-basename>-<short-sha>/dynamic/session-report.json
```

For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).

## Notes

- The script source can be large (>500 lines). If it exceeds
  MCP tool-call limits, write it to a file in
  `/tmp/android-re/<project_id>-frida/` and pass `cat` output
  to `frida_load_script`.
- For complex agents (multi-file, with stubs), use
  `frida-compile` to bundle. This is a Phase 4 enhancement.
- Stalker (code tracing) is heavy; warn the user.
- For per-app pinning bypass, see `android-re-sslpinning-bypass`.
