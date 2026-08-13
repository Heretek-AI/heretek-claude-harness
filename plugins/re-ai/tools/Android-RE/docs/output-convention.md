# Output convention

Every Android-RE run produces a directory tree under:

```
Output/<apk-basename>-<short-sha>/<subdir>/<file>
```

- `<apk-basename>` — the `.apk` filename without extension.
- `<short-sha>` — first 8 hex chars of the APK's SHA-256.
- `<subdir>` — `static/`, `native/`, `dynamic/`, `secrets/`, `masvs/`,
  `triage/<id>/`, `repackage/`, `gradle/`, `network/`, or `scripts/`.

Computed by
[`android_re_core.paths.output_dir_for(apk_path)`](../android_re_core/src/android_re_core/paths.py).
The path is **stable across runs** of the same APK and **distinct across
different APKs** (even if they share a basename — the SHA-256
disambiguates).

## Overrides

| Scope | Mechanism | When |
|---|---|---|
| **Base path** | `ANDROID_RE_OUTPUT_DIR` env var | Set *before* launching Claude Code (read once at import time of `android_re_core.paths`). Use to relocate the whole tree, e.g. to a scratch disk. |
| **Per-file path** | `output_path` parameter on each MCP tool | When you want one specific deliverable in a specific spot. |
| **Per-directory** | `output_dir` parameter on each MCP tool | When you want every file from one tool call to land in a custom directory. |

Every file-producing MCP tool respects both `output_path` and
`output_dir` — no manual `cp` is needed after a run.

## Per-skill defaults

| Skill | Default `output_dir` |
|---|---|
| `android-re-triage-orchestrator` | `Output/<apk>-<sha>/<triage_id>/` |
| `android-re-static-triage` | `Output/<apk>-<sha>/static/` |
| `android-re-decompile` | `Output/<apk>-<sha>/sources/` (cache in `/tmp/android-re/`) |
| `android-re-masvs-report` | `Output/<apk>-<sha>/masvs/` |
| `android-re-native-triage` | `Output/<apk>-<sha>/native/` |
| `android-re-secrets-scan` | `Output/<apk>-<sha>/secrets/` |
| `android-re-repackage` | `Output/<apk>-<sha>/repackage/` |
| `android-re-gradle-rebuild` | `Output/<apk>-<sha>/gradle/` |
| `android-re-dynamic-hook` | `Output/<apk>-<sha>/dynamic/` |
| `android-re-sslpinning-bypass` | `Output/<apk>-<sha>/dynamic/` |
| `android-re-frida-script-author` | `Output/<apk>-<sha>/scripts/` |
| `android-re-network-intercept` | `Output/<apk>-<sha>/network/` |

Each skill's own `SKILL.md` has an "Output convention" section
documenting the exact `output_path` / `output_dir` to pass.

## What is **not** a deliverable

Internal caches at `/tmp/android-re/<project>-jadx-...` and
`/tmp/android-re/<project>-apktool/` are **not deliverables**. Do not
commit them; do not move them into `Output/`. They are regenerated on
the next `open_project` call against the same APK.

The legacy `.triage/` directory is retired. Per-triage workdirs now
live under `Output/<apk>-<sha>/<triage_id>/`. Anything written to
`./.triage/` is leftover from a pre-0.2 run and should be removed.

## Filesystem hygiene

- **Gitignored.** `Output/` is in `.gitignore`. Do not `git add` it.
- **Cleanup.** `rm -rf Output/<apk>-<sha>/` discards a run. The same
  directory name is re-used if the APK is unchanged.
- **Disk.** Decompiled output can be multi-GB for large APKs. Periodically
  prune `/tmp/android-re/` and `Output/` of completed projects.

## Bridge exception

The `mcp__android-re-bridge__adb_pull` / `adb_push` tools are
user-controlled file operations and do **not** participate in the
`Output/` convention. They take explicit `dst` / `src` arguments and
write wherever the caller asks.
