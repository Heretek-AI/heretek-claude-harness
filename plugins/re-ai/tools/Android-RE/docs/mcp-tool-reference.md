# MCP Tool Reference

> Auto-generated reference for every tool exposed by every Android-RE MCP
> server. Source of truth is the `mcp_servers/<server>/src/.../server.py`
> `FastMCP` registration. If this page drifts from the code, the code wins.

## Output convention

Every file-producing MCP tool accepts an `output_path` (single file) or
`output_dir` (directory) parameter. When omitted, the path is derived
from
[`android_re_core.paths.output_dir_for(apk_path)`](../android_re_core/src/android_re_core/paths.py):

```
Output/<apk-basename>-<short-sha>/<subdir>/<file>
```

Override the base with the `ANDROID_RE_OUTPUT_DIR` env var (read once
at import time of `android_re_core.paths`). The default base is
`<repo-root>/Output/`; the directory is git-ignored. The full
convention is documented in [`output-convention.md`](output-convention.md).

| Tool | Default subdir | Default filename |
|---|---|---|
| `finalize_triage` | `Output/<apk>-<sha>/<triage_id>/` | `triage-<id>.{md,json,sarif}` |
| `get_masvs_coverage` | `Output/<apk>-<sha>/masvs/` | `coverage.json` |
| `build_sarif_report` | `Output/<apk>-<sha>/masvs/` | `report.sarif` |
| `scan_secrets` | `Output/<apk>-<sha>/secrets/` | `secrets-findings.json` |
| `scan_with_quark` | `Output/<apk>-<sha>/secrets/quark/` | (quark's native layout) |
| `run_androwarn` | `Output/<apk>-<sha>/secrets/` | `androwarn.json` |
| `build_native_report` | `Output/<apk>-<sha>/native/` | `native-report.json` |
| `build_session_report` | `Output/<apk>-<sha>/dynamic/` | `session-report.json` |
| `rebuild_apk` | `Output/<apk>-<sha>/repackage/` | `rebuilt.apk` |
| `create_gradle_project` | (required) | n/a |
| `take_screenshot` | `Output/<apk>-<sha>/dynamic/` | `screenshot-<ts>.png` |
| `screenrecord` | `Output/<apk>-<sha>/dynamic/` | `screenrecord-<ts>.mp4` |
| `dump_heap` | (required) | n/a |
| `setup_mitm` | `Output/<apk>-<sha>/network/` | n/a |

## Servers

| Server               | Module                                  |
|----------------------|------------------------------------------|
| `android-re-static`  | `mcp_servers.static.android_re_mcp_static` |
| `android-re-native`  | `mcp_servers.native.android_re_mcp_native` |
| `android-re-dynamic` | `mcp_servers.dynamic.android_re_mcp_dynamic` |
| `android-re-triage`  | `mcp_servers.triage.android_re_mcp_triage` |
| `mcp_bridge`         | `mcp_bridge` (TypeScript)                  |

## android-re-static

26 tools (Phase 1 + 2 + 3 + Decompilation pipeline).

Project lifecycle:
- `open_project(apk_path, project_id?, max_size?) -> {project_id, sha256, size, ...}`
- `close_project(project_id) -> {ok}`
- `list_projects() -> [ProjectSummary]`

Manifest:
- `read_manifest(project_id, formatted?) -> manifest XML or structured`
- `list_components(project_id, component_type?) -> [Component]`
- `get_permissions(project_id, classification?) -> [Permission]`

DEX:
- `find_classes(project_id, query, limit?, exact?) -> [Class]`
- `find_methods(project_id, class_name?, name_substring?, native_only?, limit?) -> [Method]`

Decompilation (jadx):
- `decompile_class(project_id, class_name, deobfuscate=False, threads=None, output_format="java") -> {source, found, workdir, deobfuscated, output_format}`
- `decompile_method(project_id, class_name, method_name, descriptor, deobfuscate=False, output_format="java") -> {source, found, start_line, end_line, full_class_source, workdir, reason}` — slices the decompiled class by method signature; `start_line` / `end_line` are 1-indexed.
- `decompile_apk(project_id, force=False, deobfuscate=False, threads=None, output_format="java", limit=500, offset=0) -> {class_count, files, total_files, truncated, jadx_duration_s}` — enumerates the decompiled tree.
- `read_source(project_id, path, deobfuscate=False, output_format="java") -> {content, found, line_count, byte_size, reason}` — reads a file by path; refuses `..` and files > 10 MB.

Smali / repackage:
- `get_smali(project_id, class_name) -> {smali, found, workdir}`
- `decode_apk(project_id, force=False) -> {workdir, class_count, smali_dirs, manifest_path}`
- `rebuild_apk(project_id, output_path?, confirm=False) -> {output_path, size}` — requires `confirm=true`.
- `patch_manifest(project_id, patch, confirm=False) -> {applied, changes, ...}` — dry-run by default.

Signing:
- `verify_signature(project_id) -> {signed, versions, signers, ...}`
- `get_certificate_info(project_id, signer_index?) -> {subject, issuer, ..., fingerprint_sha256}`

Native (delegated from `android-re-native`):
- `list_native_libs(project_id) -> [lib_path]`
- `analyze_elf(project_id, lib_name) -> {format, architecture, security, sections, imports, exports}`
- `disassemble_native(project_id, lib_name, symbol?, offset?, length?, max_instructions?) -> [instruction]`

Secrets / reports:
- `scan_secrets(project_id, rules="default", limit=500) -> [SecretFinding]`
- `scan_with_quark(project_id, timeout_s=300) -> {matched_rules}`
- `run_androwarn(project_id, timeout_s=300) -> [Warning]`
- `build_sarif_report(project_id) -> SARIF log`
- `get_masvs_coverage(project_id) -> {by_group, controls, findings}`

Each decompile tool caches its workdir under
`/tmp/android-re/<project_id>-jadx-{deobf,plain}-{java,kotlin}/`.
`deobfuscate` and `output_format` are part of the cache key.

## android-re-native

(Phase 2) 19 tools — see `mcp_servers/native/src/.../server.py`.

## android-re-dynamic

(Phase 3) 30+ tools — see `mcp_servers/dynamic/src/.../server.py`.

### `install_apk` (SDK-34+ aware)

`install_apk(serial, apk_path, replace=True, allow_downgrade=False, confirm=false, output_path=None) -> InstallResult`

The dynamic server's `install_apk` tool delegates to
`android_re_core.device.adb_install.install_apk`, which runs a
3-strategy install ladder:

1. `adb_install` — one-shot `adb -s <serial> install [-r] [-d] <apk>`.
   Pre-34 fast path; tried first on every API level.
2. `push_then_pm_install` — push the APK to `/data/local/tmp/`
   on the device, then `pm install [-r] [-d] <tmp_path>`. Primary
   escalation on API 34+.
3. `staged_install` — `pm install-create` / `-write` / `-commit`.
   Last-resort fallback on API 34+ when (2) also fails.

Returns a structured `InstallResult`:

```json
{
  "status": "success" | "failure" | "partial",
  "api_level": 34,
  "strategy": "adb_install" | "push_then_pm_install" | "staged_install",
  "output": "Success\n",
  "package": "com.example",
  "elapsed_s": 1.23
}
```

`confirm=false` (the default) does **not** call adb. It writes a
structured dry-run summary to
`Output/<apk>-<short-sha>/dynamic/install-attempt.dry-run.json`
listing the strategy ladder, then returns the `confirm_required`
error envelope. Override the path with `output_path=...`.

Failure modes the ladder handles explicitly:

- `INSTALL_FAILED_OWNER_BLOCKED`, `INSTALL_FAILED_USER_RESTRICTED`,
  `INSTALL_FAILED_VERSION_DOWNGRADE` → strategy 2.
- `INSTALL_FAILED_INSUFFICIENT_STORAGE`, `INSTALL_FAILED_NO_INSTALL`,
  `INSTALL_FAILED_INTERNAL_ERROR` → strategy 3.
- An unknown 4th mode surfaces in `output` for triage; the
  implementer can extend the ladder with a 5-line PR.

The `ANDROID_RE_FORCE_STAGED=1` env var forces strategy 1 only
(for testing the override path; not the staged path itself).

**TS bridge parity gap** — the TypeScript `mcp_bridge` `adb_install`
tool still uses adbkit's `install()` and does not support the
SDK-34+ fix. Callers using the TS bridge on an API 34+ device
should use the Python dynamic server's `install_apk` instead.

## android-re-triage

(Phase 4) 12 tools — orchestrator; composes the other three.

## mcp_bridge (TypeScript)

(Phase 3) 18 tools — ADB / screencap / logcat / frida-ps.

## MCP resources

| Resource URI                                | Provided by              |
|---------------------------------------------|--------------------------|
| `apk://<project_id>/manifest`               | `android-re-static`      |
| `apk://<project_id>/smali/<fqcn>`           | `android-re-static`      |
| `apk://<project_id>/source/<fqcn>`          | `android-re-static`      |
| `native://<project_id>/lib/<lib_name>/...`  | `android-re-native`      |
| `device://<serial>/<topic>`                 | `mcp_bridge`             |

## Peer MCP servers

Android-RE's `.mcp.json` can register peer MCP servers alongside
the 5 in-workspace ones. Peers are external projects that live
outside this repo; they're opt-in and have no destructive tools.

### `re-library` (MIT)

Wrapper around the [RE-Library](https://heretek-ai.github.io/RE-Library/)
corpus — 8 categories (`android`, `ios`, `native`, `anti-analysis`,
`drm`, `packers`, `tools`, `web-hybrid`) of generic RE knowledge.
Used by 5 Android-RE skills as a "Background reading (peer MCP)"
step before writing Frida hooks or MASVS reports.

5 tools, all read-only:

- `mcp__re-library__list_categories()` — enumerate the 8 categories
  with entry counts.
- `mcp__re-library__list_entries(category)` — lightweight summary
  of one category (titles + summaries + difficulty).
- `mcp__re-library__search_re(query, category?, platform?, max_results?)` —
  free-text search with snippet + score. Returns up to `max_results`
  hits (default 5, max 50).
- `mcp__re-library__get_entry(slug)` — full body of one entry,
  indexed by `<category>/<NN>-<slug>`.
- `mcp__re-library__get_anti_analysis_techniques(platform?)` —
  convenience aggregator over the `anti-analysis` category.

Install once with `just install-re-library` (the `.mcp.json`
entry uses `uv tool run --from re-library-mcp …` as a fallback
if the package is not pre-warmed).
