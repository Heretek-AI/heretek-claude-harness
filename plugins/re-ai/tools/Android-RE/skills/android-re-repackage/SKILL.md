---
name: android-re-repackage
description: |
  Use when the user wants to modify an APK and produce a new signed
  build. Common scenarios: add a debuggable flag, set
  allowBackup=true, change the network security config to trust a
  user CA, repackage with Frida gadget, or rebuild after a
  smali-level edit. Triggers: "modify the manifest", "set debuggable
  to true", "patch the APK", "repackage for testing", "rebuild and
  sign", "trust user CAs". Do NOT use this for static analysis
  (use android-re-static-triage) or for dynamic analysis (use
  android-re-dynamic-hook).
effect:
  filesystem:
    - read APK in current directory or absolute path
    - write decoded apktool project to /tmp/android-re/
    - write rebuilt APK to user-specified path
  network: none
  device: none
  requires:
    confirm: true (rebuild_apk and patch_manifest with confirm=true write to disk)
requires:
  mcp: android-re-static
---

# Repackage an APK

A structured workflow for modifying an APK and producing a new
unsigned (or debug-signed) build. The output is ready to be signed
with apksigner / uber-apk-signer and installed on a device.

## When to use

The user has an APK and wants to make a specific change before
re-installing. Typical cases:

- Set `android:debuggable="true"` so they can attach `jdb`.
- Set `android:allowBackup="true"` to test backup flows.
- Set `android:usesCleartextTraffic="true"` for a debug build.
- Inject a Frida gadget (use `apk-mitm` / `apk.sh patch`, not this
  skill — see Notes).
- Apply a smali patch (e.g. replace a constant), then rebuild.

For the network / Frida case, prefer `android-re-network-intercept`
(Phase 4) which composes with the dynamic MCP server.

## Inputs

| Field         | Required | Description                                        |
|---------------|----------|----------------------------------------------------|
| `apk_path`    | yes      | Path to the input `.apk`                           |
| `patch`       | yes      | Dict of manifest changes                           |
| `output_path` | no       | Where to write the rebuilt APK (default: workdir)  |

`patch` is a dict of ``application`` attribute overrides. Supported
keys (Phase 2):

- `debuggable` (e.g. `"true"`)
- `allowBackup` (e.g. `"true"`)
- `usesCleartextTraffic` (e.g. `"true"`)
- `networkSecurityConfig` (e.g. `"@xml/network_security_config"`)

## Workflow

1. **Open the project.**
   `mcp__android-re-static__open_project` → `project_id`.

2. **Decode the APK.**
   `mcp__android-re-static__decode_apk` with `force=true` if
   re-running. Returns the `workdir`, the number of smali classes,
   and the decoded manifest path.

3. **Dry-run the manifest patch.**
   `mcp__android-re-static__patch_manifest` with `patch=<dict>` and
   `confirm=false`. Returns the proposed changes and a preview of
   the patched manifest. **Show the diff to the user and ask for
   confirmation.**

4. **Apply the patch.**
   Re-call `patch_manifest` with `confirm=true`. The manifest file
   is written. (The APK is not yet rebuilt.)

5. **Rebuild the APK.**
   `mcp__android-re-static__rebuild_apk` with `confirm=true` and
   an `output_path`. Returns the path to the rebuilt APK.

6. **Tell the user to sign.**
   The output is unsigned. Recommend:

   ```bash
   apksigner sign --ks debug.keystore --ks-pass pass:android \
     --key-pass pass:android --out signed.apk rebuilt.apk
   ```

   Or with uber-apk-signer (vendored):

   ```bash
   java -jar vendor/uber-apk-signer/0.1.0/uber-apk-signer.jar \
     --apks rebuilt.apk
   ```

7. **Close the project.**
   `mcp__android-re-static__close_project`.

## Output

A markdown report:

```markdown
# Repackage Report — <package>

## Inputs
- APK: <input path>
- Patches: <dict>
- Output: <rebuilt APK path>

## Decoded workdir
- <workdir>
- Class count: <n>
- Smali dirs: <list>
- Manifest: <manifest path>

## Manifest diff
- application@debuggable: <old> → <new>
- application@allowBackup: <old> → <new>
- ...

## Rebuilt APK
- Path: <output path>
- Size: <bytes>

## Next steps
- Sign with apksigner / uber-apk-signer.
- Install on a device with `adb install`.
```

## Examples

### Example 1: enable debuggable

> User: Make this APK debuggable so I can attach jdb.

Steps:

1. Open project.
2. Decode.
3. Dry-run with `patch={"debuggable": "true"}`.
4. User confirms.
5. Apply patch.
6. Rebuild to `/tmp/foo.apk`.
7. Close project.
8. Sign + install.

### Example 2: trust user CAs

> User: Set the networkSecurityConfig so the app trusts my Burp
> cert.

This is a multi-file change (manifest + res/xml/network_security_config.xml).
Phase 2 supports setting the manifest attribute but not writing the
XML. If the user has the XML already, you can:

1. Decode the APK.
2. Write the network_security_config.xml to
   `<workdir>/res/xml/network_security_config.xml`.
3. Patch the manifest to reference it.
4. Rebuild.

## Output convention

Pass `output_path=Output/<apk-basename>-<short-sha>/repackage/rebuilt.apk`
to `rebuild_apk` so the rebuilt APK lands in the per-APK tree. The tool
defaults to this path if you omit it. Remember: both `patch_manifest`
and `rebuild_apk` are `confirm`-gated; always dry-run first.

For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md) and
`android_re_core.paths.output_dir_for`.

## Notes

- Phase 2 supports a small set of patch keys. To patch a class
  field or smali instruction, use `get_smali` to read, edit, write
  manually, then rebuild.
- The repackage round-trip can change the APK signature, the v2/v3
  block, and some metadata. Always re-sign.
- For Frida gadget injection, use `apk.sh patch` directly
  (https://github.com/ax/apk.sh) — the dex-rewriting approach is
  more reliable than smali round-tripping.
- See [`references/apktool-issues.md`](references/apktool-issues.md)
  for known issues and workarounds.
- **Size limit.** The MCP `open_project` tool caps APK files at
  `ANDROID_RE_MAX_APK_SIZE` bytes (default 500 MB) as a zip-bomb guard.
  For larger APKs, pass `max_size=<bytes>` to the `open_project` tool,
  or restart the MCP server with `ANDROID_RE_MAX_APK_SIZE=<bytes>` in
  its environment.
