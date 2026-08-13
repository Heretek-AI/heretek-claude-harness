---
name: android-re-gradle-rebuild
description: |
  Turn an APK into a buildable Gradle project. Composes
  mcp__android-re-static__open_project, decompile_apk, decode_apk,
  jadx_cleanup_workdir, and create_gradle_project into a 6-step
  workflow that produces `./gradlew :app:assembleDebug` output.
---

# Rebuild an APK as a Gradle project

Composes the jadx + apktool + Gradle-scaffolder MCP tools into a single
workflow. Use this when the user has an APK and wants a buildable
source-level project (e.g. for code review, modification, malware
analysis of a known-good app, or to verify the original APK matches its
public source).

For a deeper audit of the APK (security review, MASVS compliance,
dynamic analysis) use `android-re-triage-orchestrator` instead. For
smali-level repackaging (modify manifest, rebuild signed APK) use
`android-re-repackage`.

## When to use

The user has an APK and wants to:

- Compile the decompiled source under their own build environment.
- Modify a function or class and rebuild.
- Verify an APK matches a claimed source tree.
- Read the decompiled code in an IDE.

If the user only wants to **read** a method or class, use
`android-re-decompile` instead — it does not require a Gradle project.

## Inputs

| Field | Required | Description |
|---|---|---|
| `apk_path` | yes | Absolute path to the `.apk` on the build host. |
| `output_dir` | yes | Absolute path of an empty directory (or non-existent) to write the project into. |
| `aapt2_path` | no | Default: resolved via `find_aapt2()` (checks `$ANDROID_HOME/build-tools/<v>/aapt2`, then `./vendor/`). |
| `gradle_version` | no | Default: 8.11.1. Override only if a different version is already extracted on the build host. |
| `agressivo_cleanup` | no | Default: true. When true, the jadx_cleanup_workdir pass also runs the Gradle compile and moves broken files to `java-broken/`. |

## Workflow

1. **Open the project.** Call `mcp__android-re-static__open_project`
   with `apk_path` and `max_size` large enough for the APK
   (default cap is 500 MB; APKs over 500 MB need `max_size` ≥ the APK
   size, e.g. `1073741824` for an 853 MB APK). Capture `project_id`.

2. **Decompile.** Call `mcp__android-re-static__decompile_apk` with
   `deobfuscate=True`, `output_format="java"`, `threads=8`. The
   workdir lands in
   `/tmp/android-re/<project>-jadx-deobf-java/sources/`. **Do not pass
   `output_format="kotlin"`** — that flag is not supported by jadx
   1.5.0 (the `MCP` description no longer advertises it; the
   underlying `SourcesView.decompile()` will raise `ValueError`).

3. **Decode resources.** Call `mcp__android-re-static__decode_apk` with
   `force=True` (idempotent). The workdir lands in
   `/tmp/android-re/<project>-apktool/`.

4. **Native triage (optional but recommended).** Invoke the
   `android-re-native-triage` skill — its output
   `reports/native-triage.md` is consumed by `create_gradle_project` as
   the project README's native-libs appendix. If the native server's
   `list_binaries` returns `project_not_found` (it has its own
   `ProjectStore` that doesn't share state with the static server), use
   the static server's native tools instead:
   `mcp__android-re-static__list_native_libs`,
   `mcp__android-re-static__analyze_elf`,
   `mcp__android-re-static__disassemble_native`. These wrap the same
   LIEF calls and share the static server's project store.

5. **Clean up the decompile.** Call
   `mcp__android-re-static__jadx_cleanup_workdir` with
   `agressivo=True`. This runs all 9 in-place transforms
   (rename_p004ui, fix_jadx_qq_types, drop_assignment_before_jadx_error,
   rename_kotlin_metadata_fields, rename_debug_metadata_fields,
   rename_apache_commons_static_fields,
   replace_autofill_hint_constants, replace_enum_entries_with_values,
   remove_duplicate_getter_methods) and then runs a Gradle compile
   attempt to identify structurally-broken files (the 10th
   `move_broken_files` transform). The tool returns a `CleanupReport`
   with the list of transforms applied and any files moved to
   `java-broken/`.

6. **Scaffold the Gradle project.** Call
   `mcp__android-re-static__create_gradle_project` with the default
   `cleaned_sources` and `apktool_workdir` (the tool auto-resolves them
   from the project store). **First call with `confirm=False`** —
   inspect the dry-run summary (the cleaned manifest, the BuildConfig
   fields that would be injected, the planned file list). **Then
   re-call with `confirm=True`** to actually write the project.

7. **Build.** On a build host with JDK 21 and Android SDK 35:
   ```bash
   cd <output_dir>
   ./gradlew :app:assembleDebug --no-daemon
   ```
   The output APK is at
   `<output_dir>/app/build/outputs/apk/debug/app-debug.apk`.

8. **Iterate.** If the build fails, the error log is at
   `<output_dir>/reports/build-log.md`. The most common cause is
   `cleanup_workdir` was not run with `agressivo=True`. Re-run it; the
   pass re-runs the Gradle compile and quarantines any newly-discovered
   problem files.

9. **Document.** The generated `README.md` is auto-written by
   `create_gradle_project` and includes the original APK's
   `package` / `versionCode` / `versionName` / `applicationId` /
   `application class`. Pin the tool versions (`jadx 1.5.0`,
   `apktool 2.10.0`, AGP `8.7.3`, Kotlin `2.0.21`, Gradle `8.11.1`)
   in the README's "How to build" section so the next person can
   reproduce the environment.

## Output

The MCP tool returns a `GradleProjectReport` dict with:

- `output_dir`: where the project was written.
- `project_name`: `rootProject.name` (from the APK's package).
- `application_id`: `applicationId` (same as package).
- `manifest_stripped`: count of attrs removed from the apktool manifest.
- `build_config_fields_injected`: count of `buildConfigField` entries.
- `files_written`: count of files the builder wrote.
- `files_copied`: count of files copied from apktool (res, assets, jniLibs).
- `warnings`: human-readable warnings (e.g. "BeanShell AWT classes
  not copied, will not compile").

## Examples

### Example 1: full pipeline

> User: rebuild `myapp-release.apk` as a Gradle project at `~/rebuild/myapp`.

1. `mcp__android-re-static__open_project(apk_path="~/Input/myapp-release.apk", max_size=1073741824)` → `project_id="apk-<your-app-full-hash>"`.
2. `mcp__android-re-static__decompile_apk(project_id="apk-<your-app-full-hash>", deobfuscate=True, output_format="java", threads=8)`.
3. `mcp__android-re-static__decode_apk(project_id="apk-<your-app-full-hash>", force=True)`.
4. (optional) android-re-native-triage skill → `reports/native-triage.md`.
5. `mcp__android-re-static__jadx_cleanup_workdir(project_id="apk-<your-app-full-hash>", agressivo=True)`.
6. `mcp__android-re-static__create_gradle_project(project_id="apk-<your-app-full-hash>", output_dir="~/rebuild/myapp", confirm=True)`.
7. (on build host) `cd ~/rebuild/myapp && ./gradlew :app:assembleDebug --no-daemon`.

### Example 2: dry-run before writing

> User: I want to see the project layout before you actually write 800 MB to my disk.

Call `mcp__android-re-static__create_gradle_project(...)` with
`confirm=False`. The tool returns the cleaned manifest text, the
BuildConfig fields it would inject, the planned file inventory, and the
exact Gradle command to run afterwards. Re-call with `confirm=True`
only after the user approves.

## Output convention

Pass `output_dir=Output/<apk-basename>-<short-sha>/gradle` to
`create_gradle_project` so the buildable project lands in the per-APK
tree. The tool requires `output_dir` (no default); you must supply it.
First call with `confirm=False` for the dry-run summary, then re-call
with `confirm=True`.

For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).

## Notes

- **Why "Java with @kotlin.Metadata annotations" instead of .kt source.**
  jadx 1.5.0's `--use-kotlin-source` flag is rejected as "Unknown
  option". jadx instead emits `.java` files that carry
  `@kotlin.Metadata(...)` annotations on every Kotlin class; the Kotlin
  Gradle plugin compiles these as Java while preserving the
  Kotlin-shaped dex bytecode. This is the same pipeline Android Studio
  uses for "Decompile to Java" view, and it's how every rebuild via
  this skill works.
- **Why "java-broken/" rather than fixing every decompile artifact.**
  Some of jadx 1.5.0's outputs are structurally broken (orphan
  function-call continuations inside @Composable lambdas, inlined
  anonymous classes with synthetic names that don't match their
  references). Surgically fixing these costs hours per file and yields
  no benefit — the runtime would have a non-zero chance of diverging
  from the original APK anyway. We move the broken files aside and
  ship stubs for the few classes that the manifest references.
- **Why a stub for `bsh.Interpreter.eval`.** The full
  `bsh.Interpreter.eval` requires the entire bsh AST tree to
  compile, including the JavaCC-generated `bsh.Parser` which jadx
  produces with broken `th`/`e` catch variable scope. The stub
  throws `EvalError` on `eval()` so the rest of the app can
  compile. The AI agent's `handleBeanShell` is a runtime feature,
  not a compile-time requirement; restore it by re-vendoring
  `bsh/Parser.java` and applying a hand-rolled scope fix (out of
  scope for this skill).
- **Why `agressivo=True` requires a build.gradle.kts.** The
  `move_broken_files` transform runs `./gradlew :app:compileDebugJavaWithJavac`
  to identify the erroring files. This requires that
  `create_gradle_project` has been run first (chicken-and-egg). If
  you're running the cleanup before the project is scaffolded, the
  transform silently no-ops. Re-run after the project is scaffolded
  to get the full benefit.
