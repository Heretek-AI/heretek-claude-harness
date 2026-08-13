# Security Model

## Threat model

The primary attack surface is the ingestion of **potentially malicious
APKs**. A hostile APK could attempt:

- **Zip-bomb attacks** — an APK that expands to gigabytes of data.
- **Path-traversal in manifest analysis** — crafted `AndroidManifest.xml`
  with `..` segments.
- **Resource exhaustion** — DEX files with millions of classes or methods.
- **Code injection** — strings/bytecode in the APK that, if `eval`-ed by
  the RE tool, executes attacker code on the analyst's host.
- **Frida-gadget injection of the analyst's host** — a malicious
  frida-server binary posing as a legitimate version.

## Mitigations in the codebase

### `android_re_core.apk` (zip-bomb guard)

Every call that opens an APK enforces:

| Limit                       | Default | Override env var          |
|-----------------------------|---------|----------------------------|
| Max file size               | 500 MB  | `ANDROID_RE_MAX_APK_SIZE`  |
| Max decompression ratio     | 100:1   | `ANDROID_RE_MAX_ZIP_RATIO` |
| Max entries in the ZIP      | 100,000 | `ANDROID_RE_MAX_ZIP_ENTRIES` |

If any limit is exceeded, the `open_project` tool returns a typed error
(`AndroidReError::APKTooLarge`) rather than continuing.

### No `eval()` of APK content

All decompilation (`jadx`, `apktool`, `baksmali`) is invoked as a subprocess
that writes its output to a file. We never pipe APK-extracted strings into
`eval()` or `exec()`. This is enforced by:

- Lint rule: `S307` (`eval`) is in our `select` list.
- Code review: any new call to `eval`, `exec`, or `subprocess.Popen(shell=True)`
  requires justification in the PR description.

### Subprocess isolation

External tools (`apkleaks`, `androwarn`, `quark-engine`, `objection`,
`apk-mitm`, `jadx`, `apktool`) are wrapped in `tools/<name>/` modules that:

- Run each tool in its own virtual environment (managed by `uv tool install`).
- Apply timeouts (default 5 minutes; override with `<TOOL>_TIMEOUT_S`).
- Capture stdout/stderr separately and return a structured
  `SubprocessResult` (no shell interpolation of tool output).

### Destructive tools require `confirm: bool`

Tools that modify the device or write to disk outside the working
directory declare `confirm: bool` in their input schema. The MCP client
must explicitly pass `confirm: true` for the call to proceed. Examples:

- `android-re-dynamic.install_apk` — `confirm: bool` required
- `android-re-dynamic.uninstall_apk` — `confirm: bool` required
- `android-re-dynamic.ssl_unpin` — `confirm: bool` required
- `android-re-static.rebuild_apk` — `confirm: bool` required

Skills that compose destructive tools must also declare `requires.confirm`
in their frontmatter so the user is warned before the workflow runs.

### Frida server version pinning

`android_re_core.frida.session` pins the frida client to a specific
version (17.10.1 in v0.1.0). `bin/doctor.sh` checks the frida-server
version on any connected device and refuses to start a session if it
does not match exactly. This blocks the "malicious frida-server"
threat mentioned above.

### Skill effect envelope

Each skill declares its effect envelope in its `SKILL.md` frontmatter
(see [`skill-authoring.md`](skill-authoring.md)):

```yaml
effect:
  - filesystem: read APK in current directory
  - network: none
  - device: none
```

The agent uses this declaration to show the user a confirmation prompt
before invoking a destructive workflow.

## Reporting a vulnerability

See [`SECURITY.md`](../SECURITY.md). Report issues to
`security@heretek-ai.example` (replace with the real address when the
org sets up a security inbox).
