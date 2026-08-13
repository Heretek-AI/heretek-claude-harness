# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### SDK-34+ aware APK install (clean-room)

- **New module** `android_re_core.device.adb_install` implements a
  3-strategy install ladder for the dynamic MCP server's
  `install_apk` tool. Strategy 1 is the existing one-shot
  `adb install` (pre-34 fast path). Strategy 2 pushes the APK to
  `/data/local/tmp/` and calls `pm install <tmp_path>`. Strategy 3
  is the staged `pm install-create` / `-write` / `-commit` flow
  used as a last-resort fallback. On API 34+ the ladder escalates
  through strategies 1 → 2 → 3 as needed. On API < 34 the one-shot
  path is unchanged (zero regression risk).
- **Failure modes handled** — `INSTALL_FAILED_OWNER_BLOCKED`,
  `INSTALL_FAILED_USER_RESTRICTED`, `INSTALL_FAILED_VERSION_DOWNGRADE`
  escalate from strategy 1 to strategy 2;
  `INSTALL_FAILED_INSUFFICIENT_STORAGE`, `INSTALL_FAILED_NO_INSTALL`,
  `INSTALL_FAILED_INTERNAL_ERROR` escalate from strategy 2 to
  strategy 3. An unknown 4th mode surfaces in
  `InstallResult.output` for triage.
- **`mcp__android-re-dynamic__install_apk` rewrite** — the MCP
  tool body is a thin delegation to the new module. The
  `confirm=false` dry-run path now writes a structured JSON
  summary to
  `Output/<apk>-<short-sha>/dynamic/install-attempt.dry-run.json`
  with the full strategy ladder, then returns the
  `confirm_required` error envelope.
- **`ANDROID_RE_FORCE_STAGED=1`** env var forces strategy 1 only
  (for testing the override path; not the staged path itself).
- **Clean-room** — the implementation is written from the
  documented Android 14 platform install semantics; no source is
  copied from the `revanced-*` repos in `Input/`. The repo stays
  Apache-2.0.
- **11 new unit tests** in
  `android_re_core/tests/test_adb_install.py` cover the
  `detect_api_level` parser, all 3 strategy dispatch paths, the
  `InstallResult` schema, the no-`eval` / no-shell-string-concat
  policy, and the `ANDROID_RE_FORCE_STAGED` escape hatch. All 11
  pass.
- **2 new dry-run tests** in
  `mcp_servers/dynamic/tests/test_install_dry_run.py` cover the
  MCP tool's `confirm=false` path, including the
  `output_path` override. All 2 pass.
- **3 new device-bound tests** in
  `mcp_servers/dynamic/tests/test_adb_install_e2e.py` exercise
  the install against a real emulator. Marked
  `@pytest.mark.device`; skipped under `just test`, run under
  `just test-device`.
- **TS bridge parity gap** — the TypeScript `mcp_bridge`'s
  `adb_install` still uses adbkit's `install()` and does not
  support the SDK-34+ fix. This is a known follow-up; callers
  using the TS bridge on an API 34+ device should use the
  Python dynamic server's `install_apk` instead.

### RE-Library peer MCP integration

- **New 6th MCP server** `re-library` is registered in `.mcp.json`.
  It's an opt-in, read-only peer that wraps the public
  [RE-Library](https://heretek-ai.github.io/RE-Library/) corpus
  (8 categories × markdown entries; 5 tools: `search_re`,
  `get_entry`, `list_categories`, `list_entries`,
  `get_anti_analysis_techniques`). The peer is launched via
  `uv tool run --from re-library-mcp …` so it does not require
  `re-library-mcp` to be pre-installed; `just install-re-library`
  pre-warms the package into an isolated uv tool venv for a
  faster cold start.
- **`.mcp.json` entry** — `uv tool run --from re-library-mcp
  python -m re_library_mcp`. Consistent with the in-workspace
  `uv run --package …` pattern.
- **`Justfile`** — new `install-re-library` and `dev-re-library`
  recipes. `install-re-library` is opt-in (mirrors the existing
  `SKIP_PULL` / `SKIP_PY` / `SKIP_NODE` pattern); the main
  `just install` flow does not pull PyPI packages by design.
- **`bin/install.sh`** — new `SKIP_RE_LIBRARY=1`-gated step 5.5
  that runs `uv tool install re-library-mcp` in `--full` mode
  when the console script is not already on PATH. Idempotent.
- **5 skill cross-links** — `android-re-triage-orchestrator`,
  `android-re-static-triage`, `android-re-native-triage`,
  `android-re-masvs-report`, `android-re-secrets-scan` each gain
  a "Background reading (peer MCP)" subsection that calls
  `mcp__re-library__*` for generic patterns before writing
  Frida hooks or MASVS reports. The peer is read-only and never
  overrides a verified observation on the target.
- **`CLAUDE.md` / `README.md` / `docs/mcp-tool-reference.md`** —
  updated architecture diagram, MCP server reference table,
  goal menu cheat sheet, and a "Peer MCP servers" subsection in
  the tool reference.
- **8 new tests** in `tests/test_mcp_config.py` lock in the 6th
  server entry, the CLAUDE.md reference, the `bin/install.sh`
  step, and the 5 skill cross-links. All 8 pass.

### Unified `Output/` folder convention

- **New `docs/output-convention.md`** — single source of truth for the
  `Output/` layout, the `ANDROID_RE_OUTPUT_DIR` env override, the
  `output_path` / `output_dir` per-tool overrides, the per-skill default
  subdirs, and the `/tmp/android-re/` cache vs. deliverable distinction.
  Linked from `README.md`, `docs/architecture.md`,
  `docs/getting-started.md`, `docs/mcp-tool-reference.md`, and every
  `skills/*/SKILL.md`'s Output convention section.
- **New `Output/` directory convention** — every file-producing MCP
  tool now writes to `Output/<apk-basename>-<short-sha>/<subdir>/<file>`.
  Implemented in [`android_re_core.paths.output_dir_for()`](android_re_core/src/android_re_core/paths.py).
- **Env-var override** — `ANDROID_RE_OUTPUT_DIR` overrides the base
  path. Read once at import time. Defaults to `<repo-root>/Output/`.
- **New `output_path` / `output_dir` parameters** added to 10 MCP
  tools: `finalize_triage`, `start_triage`, `scan_secrets`,
  `scan_with_quark`, `run_androwarn`, `get_masvs_coverage`,
  `build_sarif_report`, `build_native_report`, `build_session_report`,
  `setup_mitm`. Five tools that already accepted a path
  (`create_gradle_project`, `rebuild_apk`, `take_screenshot`,
  `screenrecord`, `dump_heap`) had their default paths updated to
  the new convention.
- **`.triage/` directory retired** — the per-triage workdir now lives
  at `Output/<apk>-<sha>/<triage_id>/`. `TRIAGE_DIR` is kept as a
  backwards-compatible alias for `OUTPUT_DIR` and will be removed in
  a future release.
- **`scan_with_quark` no longer hardcodes `/tmp/quark-out`** — its
  output dir is now `Output/<apk>-<sha>/secrets/quark/` by default.
- **`Output/` added to `.gitignore`** alongside the existing
  `Input/`, `.triage/`, `out/`, `tmp/`, `.worktrees/`, `vendor/`
  entries.
- **12 SKILL.md files updated** with an "Output convention" section
  documenting the per-skill `output_path` / `output_dir` to pass.
- **Docs updated** — `docs/getting-started.md`,
  `docs/architecture.md`, `docs/mcp-tool-reference.md`, and
  `README.md` all reference the new convention and link to
  `docs/output-convention.md`.
- **13 new tests** in `android_re_core/tests/test_paths.py` cover
  `OUTPUT_DIR` resolution, `output_dir_for` naming, basenames with
  identical content, missing-APK error, and the `TRIAGE_DIR`
  alias. All 13 pass.

### Decompilation pipeline (jadx-backed, full pipeline)
- **New tools**: `decompile_apk` and `read_source` in the static MCP
  server. `decompile_apk` enumerates the decompiled tree (path +
  line count + byte size, with `limit` / `offset` for large APKs).
  `read_source` reads a single file by path relative to the
  decompiled `sources/` dir, with `..` and symlink-traversal
  defence and a 10 MB size cap.
- **`decompile_method` un-stubbed** — was a Phase-1 placeholder
  that returned `source=None`; now routes to
  `SourcesView.decompile_method`, which slices the decompiled
  class by method signature (descriptor-aware) with a token-aware
  brace counter. Returns `start_line` / `end_line` (1-indexed)
  and a `found=false` reason on miss.
- **Per-flag jadx cache** — `SourcesView.decompile` no longer
  wipes the workdir on every call. The MCP layer derives a
  per-flag workdir name (`-jadx-{deobf,plain}-{java,kotlin}`) so
  flipping `deobfuscate` or `output_format` does not poison a
  prior decode.
- **Deobfuscation flags exposed** — `decompile_class`,
  `decompile_method`, `decompile_apk`, and `read_source` all
  accept `deobfuscate` (`--deobf`), `threads`
  (`--threads-count N`), and `output_format` (`java` or
  `kotlin`, with `--use-kotlin-source`).
- **Skill update** — `android-re-decompile` no longer mentions
  the Phase 1 stub; the workflow now ends in a real method slice
  with line numbers. New "Whole-APK navigation" and
  "Deobfuscation cookbook" sections.
- **Tests** — 29 new tests in `test_smali_sources.py` covering
  descriptor mapping, method-slice adversarial cases (string
  braces, block-comment braces, anonymous inner classes, Java
  text blocks), `read_source` path-traversal and size-cap
  defence, cache hit/miss/force semantics, and flag pass-through.
  Driven by a new `tests/fixtures/bin/fake-jadx` shell fixture
  that records argv to a file and writes canned `.java` /
  `.kt` output — no real jadx install or binary APK required
  in CI.
- **Tool count** — 24 → 26. The hard-coded
  `assert len(tools) == 24` in the MCP tests has been replaced
  with a name-subset check so future tools don't break the
  assertion.

### Phase 1 — Foundation (in progress)
- Monorepo skeleton (uv workspace, pnpm workspace, Justfile, pre-commit, mkdocs).
- `android_re_core` shared library: `apk`, `manifest`, `dex`, `certs`,
  `errors`, `paths`, `project`.
- `android-re-static` MCP server: 11 tools (project lifecycle, manifest,
  components, permissions, classes, methods, decompile, signature, cert).
- `bin/install.sh` (with `--skills-only` and `--full` modes),
  `bin/doctor.sh`, `bin/pull-tools.sh`.
- Skills: `android-re-static-triage`, `android-re-decompile`,
  `android-re-masvs-report` (stub).
- CI: ruff, mypy --strict, pytest with OWASP MASTG CrackMe + DIVA + DVA
  fixtures; in-memory `mcp.Client` contract tests.

### Planned — Phase 2 (weeks 3–4)
- `android_re_core/native` (LIEF 0.17.6), `smali` (apktool), `sources` (jadx).
- `android-re-native` MCP server.
- Static server additions: native lib tools, SARIF/MASVS reporting, secrets
  scanning, repackage roundtrip.
- Skills: `android-re-native-triage`, `android-re-secrets-scan`,
  `android-re-repackage`.

### Planned — Phase 3 (weeks 5–6)
- `android_re_core/frida` and `android_re_core/device`.
- `android-re-dynamic` MCP server.
- `mcp_bridge` TypeScript server.
- Skills: `android-re-dynamic-hook`, `android-re-sslpinning-bypass`,
  `android-re-frida-script-author`.

### Planned — Phase 4 (weeks 7–8)
- `android-re-triage` MCP server (orchestrator).
- `android_re_core/store/sqlite.py` for triage state + checkpointing.
- Skills: `android-re-triage-orchestrator`, `android-re-network-intercept`,
  full `android-re-masvs-report`.
- Docs site, examples walkthroughs, v0.1.0 release.
