# AGENTS.md

> This file is loaded automatically by Claude Code (and other agents
> that read the `AGENTS.md` convention) whenever a session is opened
> against this directory. It is the single source of truth for how an
> agent should behave when the user drops an APK into `Input/` and asks
> for analysis.
>
> **Apache-2.0**. This file is part of the Android-RE monorepo. See
> [`LICENSE`](LICENSE) for the full license text. frida-server is
> bundled separately under the wxWindows Library Licence with a
> personal-use restriction — see [`LICENSE-3rdparty.md`](LICENSE-3rdparty.md).

## What this repo is

Android-RE is a monorepo of **5 MCP servers** and **12 Claude Code
skills** that wrap the standard Android reverse-engineering toolchain
(jadx, apktool, androguard, LIEF, Frida, ADB) into MASVS-aligned
workflows. Phase 1 through Phase 4 of the roadmap are all scaffolded;
the static, native, dynamic, and triage servers are all functional.

The high-value user-facing flows are:

- **Drop an APK into `Input/` and get a MASVS report** in 60 seconds.
- **Hook a method on a running app** with a Frida session in 3 calls.
- **Audit a `.so` file's hardening + symbols + strings** in one call.
- **MITM an app's HTTPS traffic** with a bundled SSL-pinning bypass.

The repo is **not**: a UI automation tool, a malware scanner, or a
Frida competitor. It composes those things.

## Repo layout (TL;DR)

```
Input/           drop APKs here (git-ignored)
Output/          every deliverable lands here (git-ignored)
examples/        end-to-end walkthroughs (DIVA, MASTG CrackMe, …)
skills/          12 Claude Code skills (workflows that compose MCP tools)
mcp_servers/     4 Python MCP servers (static, native, dynamic, triage)
mcp_bridge/      1 TypeScript MCP server (ADB / screencap / logcat)
android_re_core/ shared Python library (androguard, LIEF, frida, ADB)
vendor/          vendored jadx / apktool / uber-apk-signer / frida-server
bin/             install.sh, doctor.sh, pull-tools.sh
docs/            mkdocs site (https://heretek-ai.github.io/Android-RE/)
tests/           pytest cross-component / E2E
```

The old `.triage/` directory has been **retired**. Per-triage workdirs
and per-skill reports now live under `Output/` (see "Output convention"
below). Anything written to `./.triage/` is a leftover from a pre-0.2
run.

## First-Run Wizard

When a user opens the repo in Claude Code and starts a conversation,
follow this sequence. It is designed to be safe, narrow the goal
quickly, and degrade gracefully when devices or skills are missing.

### 1. Detect APKs in `Input/`

```bash
ls -la Input/ 2>/dev/null
find Input/ -maxdepth 3 -name "*.apk" -type f
```

If zero APKs, the wizard does NOT fire — stay in free-form Q&A.

If one APK, skip to step 3.

### 2. Ask which APK (only if 2+)

Use the `AskUserQuestion` tool:

> **Question**: "I found N APKs in `Input/`. Which one would you like me to work on?"
> **Header**: "Pick APK"

Options: one per APK found (`<filename> (<size> MB)` with a short
description of the SHA-256 prefix), plus "I want to specify a different
path".

### 3. Compute SHA-256 + size of the picked APK

```bash
sha256sum <path>
stat -c%s <path>  # bytes
```

The size is critical for step 5: the default `open_project` cap is
**500 MB**. APKs over that need `max_size=<apk_size * 2>` (rounded up
to the next GB) on the first call.

### 4. Ask the goal (4 options, fits the AskUserQuestion 2-4 limit)

> **Question**: "What would you like to do with `<apk-basename>`?"
> **Header**: "Analysis goal"

| Option | Description |
|---|---|
| **Run a full MASVS-aligned triage (Recommended)** | Static + native + MASVS coverage + correlation. Falls back to static-only if no device is attached. Always produces a report. |
| **Static analysis only** | Decompile + secrets scan + MASVS report. No device, no Frida. Fastest. |
| **Audit the native (.so) libraries** | Hardening flags, symbols, strings, packer detection. No device needed. |
| **Dynamic analysis (requires a rooted device + frida-server)** | Spawn / attach + a generic Frida hook. No MASVS coverage. |

For Gradle rebuild, repackage, network intercept, or custom Frida
scripts, the user picks **Other** and types free-form. See
[`docs/skills.md`](docs/skills.md) for the full list of skills and
their `Skill` invocations.

### 5. Execute

- For goals 1-3: call `mcp__android-re-triage__start_triage(apk_path=..., apk_sha256=<sha>, goals=..., output_dir=Output/<apk>-<sha>)`. Then follow the
  multi-step plan returned in the `plan` field.
- For goal 4: call `Skill("android-re-dynamic-hook")` and prompt for
  `device_serial` (from `mcp__android-re-dynamic__frida_list_processes`).
- For free-form "Other": match the request to a skill
  (`Skill("android-re-gradle-rebuild")`, `-repackage`,
  `-network-intercept`, `-frida-script-author`, etc.) and pass the
  `output_dir` / `output_path` overrides as documented in each
  `SKILL.md`'s "Output convention" section.

**Always pass `max_size=<apk_size * 2>` on the first `open_project`
call** if the APK exceeds 500 MB. The Input/ folder already has an
853 MB example; without the override, `open_project` will refuse it.

### 6. Hand-off

After the chosen skill finishes:

1. Surface the report path to the user.
2. Show a 1-paragraph summary of the top 3 findings.
3. Ask: "Want me to (a) dig into a specific finding, (b) run the next
   goal, (c) compare against another APK version, or (d) wrap up?"

## Output convention

Every Android-RE run produces a directory tree under:

```
Output/<apk-basename>-<short-sha>/<subdir>/<file>
```

- `<apk-basename>` = the `.apk` filename without extension.
- `<short-sha>` = first 8 hex chars of the APK's SHA-256.
- `<subdir>` = `static/`, `native/`, `dynamic/`, `secrets/`, `masvs/`,
  `triage/<id>/`, `repackage/`, `gradle/`, `network/`, or `scripts/`.

Override the **base** with the `ANDROID_RE_OUTPUT_DIR` env var (read
once at import time of `android_re_core.paths`). Override the **per-file
path** with the `output_path` / `output_dir` parameter on each MCP
tool. Every file-producing MCP tool respects this — no manual `cp` is
needed.

Computed by [`android_re_core.paths.output_dir_for(apk_path)`](android_re_core/src/android_re_core/paths.py).
The default base is `<repo-root>/Output/`; set `ANDROID_RE_OUTPUT_DIR`
**before** launching Claude Code to relocate it (e.g. to a scratch
disk). The directory is automatically added to `.gitignore`.

## Goal menu cheat sheet

| User says… | Skill to invoke | Default `output_*` |
|---|---|---|
| "triage", "MASVS audit", "what does this app do" | `Skill("android-re-triage-orchestrator")` with `goals=["masvs"]` | `Output/<apk>-<sha>/<triage_id>/` |
| "static only", "decompile + secrets", "no device" | `Skill("android-re-triage-orchestrator")` with `goals=["static_only"]` | same |
| "native only", ".so", "audit the libraries" | `Skill("android-re-triage-orchestrator")` with `goals=["native_only"]` | same |
| "dynamic only", "Frida hook", "MITM this" | `Skill("android-re-dynamic-hook")` (requires device) | `Output/<apk>-<sha>/dynamic/` |
| "rebuild as Gradle", "buildable project" | `Skill("android-re-gradle-rebuild")` with `output_dir=Output/<apk>-<sha>/gradle` | `Output/<apk>-<sha>/gradle/` |
| "repackage", "set debuggable", "trust user CAs" | `Skill("android-re-repackage")` with `output_path=Output/<apk>-<sha>/repackage/rebuilt.apk` | `Output/<apk>-<sha>/repackage/` |
| "intercept traffic", "MITM", "Burp this" | `Skill("android-re-network-intercept")` | `Output/<apk>-<sha>/network/` |
| "scan for secrets", "AWS key in the code" | `Skill("android-re-secrets-scan")` | `Output/<apk>-<sha>/secrets/` |
| "show me the source of `Foo.bar`" | `Skill("android-re-decompile")` | `Output/<apk>-<sha>/sources/` (cache in `/tmp/android-re/`) |
| "write a frida script" | `Skill("android-re-frida-script-author")` | `Output/<apk>-<sha>/scripts/` |

## Skill reference

| Skill | One-line description | Primary MCP tool(s) | Confirm-gated? | Requires device? |
|---|---|---|---|---|
| `android-re-triage-orchestrator` | Master: drop in APK → MASVS report. Composes every other skill. | `mcp__android-re-triage__start_triage`, `add_finding`, `correlate_findings`, `finalize_triage` | No (orchestrator manages internally) | Optional (falls back to static) |
| `android-re-static-triage` | 5-minute static overview: manifest, components, permissions, signature, classes. | `mcp__android-re-static__open_project`, `read_manifest`, `list_components`, `get_permissions`, `get_masvs_coverage` | No | No |
| `android-re-decompile` | Pull Java / smali source for a class or method (FQCN + method + descriptor). | `mcp__android-re-static__decompile_class` / `decompile_method` / `read_source` / `get_smali` | No | No |
| `android-re-masvs-report` | Per-MASVS-control coverage with cross-source correlation. | `mcp__android-re-static__get_masvs_coverage`, `build_sarif_report`, `mcp__android-re-triage__correlate_findings` | No | No |
| `android-re-native-triage` | Audit `.so` libraries for hardening, symbols, strings, packer detection. | `mcp__android-re-native__list_binaries`, `parse_binary`, `get_security_features`, `detect_packers`, `build_native_report` | No | No |
| `android-re-secrets-scan` | Regex scan decompiled Java for hard-coded secrets. | `mcp__android-re-static__scan_secrets` (+ `scan_with_quark`, `run_androwarn`) | No | No |
| `android-re-repackage` | Patch manifest, rebuild APK, sign, install. | `mcp__android-re-static__patch_manifest`, `rebuild_apk` (+ `mcp__android-re-bridge__adb_install`) | **Yes** (all three) | Optional (install step) |
| `android-re-gradle-rebuild` | Turn an APK into a buildable Gradle project. | `mcp__android-re-static__open_project`, `decompile_apk`, `decode_apk`, `jadx_cleanup_workdir`, `create_gradle_project` | **Yes** (`create_gradle_project`) | No |
| `android-re-dynamic-hook` | Spawn / attach, load a Frida script, collect runtime data. | `mcp__android-re-dynamic__frida_spawn` / `frida_attach`, `frida_load_script`, `build_session_report` | Implicit (destructive) | **Yes** |
| `android-re-sslpinning-bypass` | Load the universal SSL-bypass script. | `mcp__android-re-dynamic__frida_load_script` (`scripts/universal-ssl-bypass.js`) | Implicit | **Yes** (rooted, frida-server) |
| `android-re-frida-script-author` | Author a focused Frida JavaScript hook for a target. | `mcp__android-re-static__find_methods` + the agent's own `.js` output | No | No (script only) |
| `android-re-network-intercept` | MITM proxy + SSL-pinning bypass. | `mcp__android-re-dynamic__setup_mitm`, `tcp_forward`, `frida_load_script` | **Yes** (`setup_mitm` with `install_cert=true`) | **Yes** (rooted) + host proxy |

Each `SKILL.md` in `skills/<name>/` has an "Output convention" section
documenting the exact `output_path` / `output_dir` to pass.

## MCP server reference

| Server | FQN prefix | Tool count | Primary use |
|---|---|---|---|
| `android-re-static` | `mcp__android-re-static__` | ~22 | APK open, manifest, components, permissions, decompile (jadx), decode (apktool), gradle scaffold, secrets scan, manifest patch, rebuild, smali, MASVS coverage, signature verification, SARIF. **All file-producing tools accept `output_path` / `output_dir`.** |
| `android-re-native` | `mcp__android-re-native__` | ~17 | List / parse ELF binaries, sections, symbols, imports, exports, strings, security features, relocations, certificates, disassembly, Frida native-hook templates, packer / YARA detection, native reports. **Owns its own `ProjectStore`; does not share state with the static server.** |
| `android-re-dynamic` | `mcp__android-re-dynamic__` | ~25 | Frida device / session / script / RPC, MITM setup, TCP forward, logcat, screenshot / screenrecord, APK install / launch, heap dump, intent / broadcast, clipboard, network state, session reports. **Most file-producing tools accept `output_path` / `output_dir`.** |
| `android-re-triage` | `mcp__android-re-triage__` | ~10 | Long-running multi-step plan: start, add_finding, link evidence, correlate, propose tests, finalize, history, status. **Long-running state in `~/.android-re/triage.db`.** |
| `android-re-bridge` | `mcp__android-re-bridge__` | ~15 | Low-level adb primitives: shell, pull, push, install, logcat, screencap, screenrecord, dumpsys, input, frida-ps. **No Output/ override; user-controlled paths only.** |

## Security model summary

- **APK size cap.** `open_project` defaults to 500 MB
  (`ANDROID_RE_MAX_APK_SIZE`). For larger APKs, pass `max_size=` to
  the call. The 853 MB `gptos-your-ai-copilot-2-0-410.apk` in
  `Input/` requires `max_size=1073741824` (1 GB). The wizard does this
  automatically based on the size computed in step 3.
- **Confirm gates.** `rebuild_apk`, `patch_manifest`,
  `create_gradle_project`, `setup_mitm` (when `install_cert=true`),
  `adb_install`, `adb_uninstall`, `adb_push` all require
  `confirm=true`. **Always dry-run first** (`confirm=False`), show
  the user the summary, and re-call with `confirm=True` only after
  approval. Never silently set `confirm=true`.
- **frida-server version pin.** frida-server is pinned to **17.10.1**
  in `bin/pull-tools.sh`. Mismatched client / server versions will
  fail. Don't `pip install frida-tools` to a different version
  without bumping the server too.
- **No eval of APK content.** Never `eval()` or `exec()` strings
  extracted from an APK. Never `frida_load_script` with a script
  sourced from inside the APK. The only sanctioned script is
  `skills/android-re-sslpinning-bypass/scripts/universal-ssl-bypass.js`.
- **Filesystem hygiene.** Workdirs under `/tmp/android-re/<project>-...`
  are not auto-cleaned. `rm -rf` the workdir of a closed project to
  free disk (especially for multi-GB decompiles).
- **No `.triage/` write.** The legacy `.triage/` directory has been
  retired. Per-triage workdirs now live under `Output/`. Don't write
  to `.triage/` directly.
- **License.** Apache-2.0. Quoting or redistributing APKs users drop
  in `Input/` must respect that APK's license.

## Output folder conventions

- **Default base path:** `<repo-root>/Output/`.
- **Override with env:** `export ANDROID_RE_OUTPUT_DIR=/path/to/output`
  *before* launching Claude Code. Read once at import time of
  `android_re_core.paths`.
- **Per-APK subdir:** `Output/<apk-basename>-<short-sha>/`. Stable
  across runs of the same APK; distinct across different APKs (even
  if they share a basename — the SHA-256 disambiguates).
- **Per-triage subdir:** `Output/<apk>-<sha>/<triage_id>/`. Set by
  the orchestrator; overridable via `output_dir` on `start_triage`.
- **Internal caches:** `/tmp/android-re/<project>-jadx-.../`,
  `/tmp/android-re/<project>-apktool/`. **Not deliverables** — do
  not commit them, do not put them in `Output/`.
- **Gitignored.** `Output/` is in `.gitignore`. Don't `git add` it.
- **Cleanup.** `rm -rf Output/<apk>-<sha>/` to discard a run.
  The same dir name will be re-used if the APK is unchanged.

## Common pitfalls

- **Output format "kotlin" is rejected by jadx 1.5.0.** The MCP layer
  documents this; passing `output_format="kotlin"` raises `ValueError`.
  Use `output_format="java"` and let the Kotlin Gradle plugin compile
  the `.java` files alongside the `@kotlin.Metadata` annotations.
- **The native MCP server has its own `ProjectStore`** and does not
  share state with the static server. If `mcp__android-re-native__*`
  returns `project_not_found` after you opened a project on the
  static server, re-open it on the native server with the same APK
  path. (Or use the static server's `mcp__android-re-static__list_native_libs`,
  `analyze_elf`, `disassemble_native` which wrap LIEF and share
  state.)
- **`create_gradle_project` is `confirm`-gated** AND `agressivo=True`
  cleanup requires the project to be scaffolded first (chicken-and-egg).
  See [`skills/android-re-gradle-rebuild/SKILL.md`](skills/android-re-gradle-rebuild/SKILL.md) for the full 6-step pipeline.
- **The 853 MB `gptos-your-ai-copilot-2-0-410.apk` in `Input/`**
  exceeds the default 500 MB cap. The wizard passes `max_size=` automatically.
  If you skip the wizard, remember to pass it manually.
- **Universal SSL bypass doesn't always defeat SPKI pinning.** Apps
  with custom pinning (SPKI hash, CT log checks, custom OkHttp
  interceptors) need a per-app hook. Use
  `android-re-frida-script-author` to write one.
- **The `mcp__android-re-bridge__adb_pull` / `adb_push` tools** are
  user-controlled file ops and do NOT participate in the Output/
  convention. They take an explicit `dst` / `src` argument.
- **First `open_project` call is slow** (jadx decompile + apktool
  decode both run on the first static-triage). Subsequent calls hit
  the cache.
- **`decompile_method` returns `found=false`** with a reason on miss.
  Try `deobfuscate=True` if the APK is R8-shrunk.

## Contributor quick-ref

- Full contributor guide: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Pre-commit hooks: `uv tool install pre-commit && pre-commit install`.
  Enforces Conventional Commits, ruff, mypy --strict.
- After editing code:

  | Recipe | When |
  |---|---|
  | `just install-skills` | After adding / renaming a skill under `skills/`. |
  | `just lint` | Before committing. Runs `ruff check .` + `mypy --strict android_re_core mcp_servers`. |
  | `just format` | After editing Python. Runs `ruff format` + `ruff check --fix`. |
  | `just test` | Before committing. Runs `pytest -m "not device"`. |
  | `just test-device` | When a device is connected. Runs the `device`-marked tests. |
  | `just doctor` | After any environment change. Verifies Python / Java / adb / frida. |

- Adding a new skill: `skills/<name>/SKILL.md` with frontmatter
  `name` + `description` (trigger phrases), reference MCP tools by
  FQN, add an "Output convention" section, then `just install-skills`.
- Adding a new MCP tool: implement in
  `mcp_servers/<server>/src/.../tools/<topic>.py`, register in
  `server.py`, add an in-memory `mcp.Client` test in
  `tests/test_mcp_<server>.py`, document in
  [`docs/mcp-tool-reference.md`](docs/mcp-tool-reference.md).
- The PR template (`.github/PULL_REQUEST_TEMPLATE.md`) is the
  canonical checklist.

## Verification checklist

End-to-end tests for the wizard + Output/ convention:

1. **No `Input/`.** Empty `Input/` → wizard does not fire. Free-form.
2. **One APK in `Input/`.** Wizard skips the APK question, fires the
   goal question. Output/ created. Report lands there.
3. **Two APKs in `Input/`.** Wizard asks which one. Output/ created
   per-APK.
4. **"Just triage it" path.** Direct call to
   `mcp__android-re-triage__start_triage` with `goals=["masvs"]`.
   Report lands at `Output/<apk>-<sha>/<triage_id>/triage-<id>.md`.
5. **Confirm-gated tools.** Pick "Rebuild as a Gradle project". First
   call with `confirm=False` returns a dry-run summary. User
   approves. Second call with `confirm=True` writes the project.
6. **Device required, no device.** Pick "Dynamic analysis" without a
   device. Tool returns a clear "no device" error; the wizard
   suggests a static-only fallback.
7. **Gitignore.** `git check-ignore Output/test.txt` returns 0.

## Glossary

- **`apk_path`** — absolute or CWD-relative path to the `.apk` file.
- **`apk_sha256`** — hex SHA-256 of the APK. Computed once per
  wizard run via `sha256sum`.
- **`project_id`** — opaque string returned by `mcp__android-re-static__open_project`
  (or the native equivalent). Identifies the in-memory `ProjectStore`
  entry. Format: `apk-<first 12 hex of SHA-256>`.
- **`triage_id`** — UUID-ish string returned by `mcp__android-re-triage__start_triage`.
  Identifies the SQLite triage record and the per-triage subdir.
- **`goal`** — one of `masvs`, `full`, `static_only`, `dynamic_only`,
  `native_only`. Drives the multi-step plan in `start_triage`.
- **`MASVS control id`** — e.g. `MASVS-NETWORK-1`. Tags findings with
  the OWASP MASVS v2 control they violate.
- **`output_path`** — host filesystem path passed to a tool to
  override the default file location.
- **`output_dir`** — host filesystem directory passed to a tool to
  override the default subdir.

## Versioning + freshness

This file was written against `CHANGELOG.md` [Unreleased] + Phase 1–4
tooling. The decompilation pipeline, per-flag jadx cache, and
`decompile_apk` / `read_source` tools are fresh. See
[`CHANGELOG.md`](CHANGELOG.md) for what's new since the last release.

## Footer

- Issues: <https://github.com/Heretek-AI/Android-RE/issues>
- Security disclosure: see [`SECURITY.md`](SECURITY.md) (placeholder:
  `security@heretek-ai.example` until the org sets up a real inbox).
- License: Apache-2.0. Bundled frida-server: wxWindows Library Licence
  (personal-use only — see [`LICENSE-3rdparty.md`](LICENSE-3rdparty.md)).
