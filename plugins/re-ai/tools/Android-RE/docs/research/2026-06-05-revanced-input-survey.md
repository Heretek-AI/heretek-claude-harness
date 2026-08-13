# Survey: `revanced-*` source repos + RE-Library sibling

**Date:** 2026-06-05
**Author:** Survey prepared for the Android-RE maintainer.
**Scope:** Five `revanced-*` repos cloned under `Input/` plus the
sibling documentation site at `/home/john/Desktop/RE-Library/`.
**Goal:** Identify which parts of those six projects could expand
Android-RE (MCP servers, skills, docs) without compromising the
repo's vendor-neutrality or Apache-2.0 license.

The companion execution spec for the top two items sits in the
plan file alongside this document.

---

## TL;DR

- The 5 `revanced-*` repos are pure framework code with one
  exception (`revanced-manager`, which is dominated by an end-user
  app's UI). All 5 are **GPLv3**, so the only safe porting posture
  is **clean-room re-implementation**: read the design, write fresh
  Apache-2.0 code.
- The 10 highest-value framework patterns are listed below in
  priority order. The first 4 (matching engine, patch orchestration,
  in-process signing, ADB install workaround) are the ones worth
  porting. The remaining 6 are backlog.
- `RE-Library` is an MIT-licensed, peer-registerable MCP server that
  complements Android-RE with no license friction. Adding it as a
  6th MCP server is the highest-payoff, lowest-effort integration
  in the survey.
- The top 2 items being implemented now are: **(1)** RE-Library peer
  integration, **(2)** clean-room port of the SDK-34+ `pm install`
  workaround into the existing `mcp__android-re-dynamic__install_apk`
  path. Full file-level design is in the plan file.

---

## 1. The 5 `revanced-*` repos

All five were cloned into `Input/` on 2026-06-05. The sub-sections
below use **category terms** only — no commercial app names, no
vendor names, no commercial protection scheme names. The repos
themselves are public; this document is vendor-neutral, like the
rest of Android-RE.

### 1.1 `revanced-cli` — CLI plumbing

| | |
|---|---|
| Language | Kotlin / JVM |
| Modules | 1 |
| ~LOC | 500 |
| License | GPLv3 |
| Framework share | 100% |
| App-specific share | 0% (loads RVP at runtime) |

A thin command-line wrapper. Takes an APK, a list of patches, and
options; dispatches to `revanced-patcher` and `revanced-library` at
runtime. No app-specific logic. The reusable pieces are CLI
plumbing — argument parsing, subcommand wiring, the
`bypass-vs-verify-with-bundle` `ArgGroup` pattern, and the
`OptionValueConverter` value-parsing helper.

### 1.2 `revanced-patcher` — the patching engine

| | |
|---|---|
| Language | Kotlin Multiplatform |
| Modules | 1 |
| ~LOC | 2,000 (+ ~25 vendored smali mutable wrappers) |
| License | GPLv3 |
| Framework share | 100% |
| App-specific share | 0% |

The core patch-orchestration engine. Pure framework. Loads patch
bundles at runtime, computes dependency order, applies each patch
in turn, returns a result. The reusable patterns here are the
most valuable in the survey: the "find a method by FQCN + name +
descriptor + opcode + string + access-flag" matching engine, the
patch orchestration loop, and a small set of generic dexlib2
utilities (class merger, method navigator, class proxy).

### 1.3 `revanced-library` — signing, ADB, install, serialization

| | |
|---|---|
| Language | Kotlin Multiplatform |
| Modules | 1 |
| ~LOC | 2,000 |
| License | GPLv3 |
| Framework share | 100% |
| App-specific share | 0% |

Shared services consumed by the CLI / Manager. The four reusable
pieces are: in-process APK signing (`apksig` + `apkzlib`), an
ADB install path that handles SDK 34+'s stricter ownership
semantics, PGP / SLSA verification, and the structured
serialization helpers. The SDK 34+ ADB install workaround is the
one Android-RE is most likely to need (see §3.2).

### 1.4 `revanced-jadx-plugin` — decompiler fingerprint solver

| | |
|---|---|
| Language | Kotlin / JVM 11 |
| Modules | 2 (`:app` + `:utils`) |
| ~LOC | 4,700 |
| License | GPLv3 |
| Framework share | ~30% (`solver/`, `core/`, `utils/`) |
| UI share | ~70% (Swing plugin UI) |

A jadx plugin that helps patch authors compute *stable* method
fingerprints. The interesting bits are the `Solver.kt` algorithm
(compute a minimal stable fingerprint by BFS over feature
combinations) and the Kotlin scripting host (`ScriptEvaluation.kt`
+ `FingerprintScriptTemplate.kt`) that runs the solver scripts
with a compile-time budget. The Swing UI is not reusable for
Android-RE; ignore.

### 1.5 `revanced-manager` — the end-user app (mostly out of scope)

| | |
|---|---|
| Language | Kotlin / Android (Compose) |
| Modules | 2 (`:app` + `:api`) |
| ~LOC | 27,500 |
| License | GPLv3 |
| Framework share | ~5% (DI modules, AIDL, Logger, HttpModule) |
| App-specific share | ~95% (Compose UI, ViewModels, Room, on-device worker process, ~50 `strings.xml` translations) |

The user-facing end-user app that picks APKs from local storage,
shows a patch list, and orchestrates patching. The framework bits
(Koin DI modules, the AIDL bridge between the UI process and the
on-device worker, the HTTP module) are the only general-purpose
content. The bulk — Compose screens, ViewModels, Room DAOs, the
on-device patcher worker process, the localization strings — is
specific to that end-user app and is **out of scope** for
Android-RE.

> Per-app patches for specific commercial apps live in the
> external `revanced-patches` RVP bundle, which is not present
> in `Input/`. The bundle is loaded at runtime by
> `revanced-patcher`. The bundle itself is not in this survey.

---

## 2. Top 10 framework porting candidates (ranked)

The list below is the result of reading the public source under
`Input/`. **The candidate files exist in the cloned repos; the
implementer should treat them as design references, not as
copy-paste sources.** Clean-room re-implementation is required
for everything in the top 10 — the design is reusable, the
Apache-2.0 code must be written fresh.

| # | Source (in `Input/`) | What it does | Why it's reusable for Android-RE |
|---|---|---|---|
| 1 | `revanced-patcher/.../Matching.kt` + `IndexedMatcher` | "Find a method by FQCN + name + descriptor + opcode + string + access-flag" with a generic indexed matcher engine | General-purpose method-finder pattern; informs any future richer query DSL on `mcp__android-re-static__find_methods` |
| 2 | `revanced-patcher/.../Patching.kt` | Patch orchestration loop: dependency-ordered apply, `PatchResult` callback, post-pass `afterDependents` | Pattern generalizes to any "apply ordered transforms to a structured artifact" flow |
| 3 | `revanced-library/.../ApkSigner.kt` + `ApkUtils.kt` | In-process APK signing / repackaging (uses Google's `apksig` + `apkzlib` libraries) | Direct replacement for the `apksigner` shell-out in the current `rebuild_apk` path; v2/v3 signing in-process removes a Java shell-out |
| 4 | `revanced-library/.../installation/installer/AdbInstaller.kt` + `AdbShellCommandRunner.kt` | The SDK 34+ `pm install` ownership / staging workaround | The path of `mcp__android-re-dynamic__install_apk` currently fails on Android 14+ devices; this is the documented mitigation |
| 5 | `revanced-jadx-plugin/.../solver/Solver.kt` | "Compute a minimal stable fingerprint" algorithm (BFS over feature combinations) | Useful only if/when a "stable patch" feature is added to the patcher skill |
| 6 | `revanced-library/.../Cryptography.kt` | PGP + SLSA verification | Not a current need; the wiring is here when it is |
| 7 | `revanced-cli/.../CommandUtils.kt` | `OptionValueConverter` + `ArgGroup` pattern | Reusable for the wizard / skill menus if they grow a more sophisticated arg-parsing need |
| 8 | `revanced-patcher/.../util/ClassMerger.kt` + `MethodNavigator.kt` + `util/proxy/ClassProxy.kt` | Generic dexlib2 utilities | Useful only if dexlib2 rewrites become a feature |
| 9 | `revanced-jadx-plugin/.../runtime/FingerprintScriptTemplate.kt` + `core/ScriptEvaluation.kt` | Kotlin scripting host with compile-time budget | Android-RE's hook story is Frida JS, not Kotlin scripts; no port |
| 10 | `revanced-jadx-plugin/app/build.gradle.kts` | Shaded plugin jar Gradle recipe (`relocate(...)`, `generatePluginMeta` task, plugin manifest) | Android-RE has no plugin-loader story; no port |

The implementer's selection (§3) picks #4 (Item 2) for this
session's work. #1, #3, and #5 are the next most valuable when
bandwidth allows; see the plan file for the deferred backlog.

---

## 3. Recommended actions — tiered

### 3.1 Tier 1 — implement now

| Item | Effort | Payoff | Where the design lives |
|---|---|---|---|
| **(1) RE-Library peer MCP integration** | ~140 LOC added, ~30 modified. No code in `android_re_core` or the existing MCP servers. | Highest — every Android-RE skill and every triage step can now consult a generic RE knowledge base | Plan file §"Item 1" |
| **(2) ADB install SDK-34+ workaround clean-room port** | ~260 LOC added (210 implementation + 200 unit tests + 25 dry-run test + 35 e2e test, with overlap) | High — the current `install_apk` path fails on Android 14+ devices | Plan file §"Item 2" |

### 3.2 Tier 2 — defer to a future session

- **In-process `ApkSigner` clean-room port** (candidate #3). The
  v2/v3 signing block in pure Python is non-trivial; this is a
  multi-day effort best done as its own focused session.
- **Method-fingerprint Matcher clean-room port** (candidate #1).
  The existing `mcp__android-re-static__find_methods` covers the
  most common case; a richer query DSL is a nice-to-have.
- **`Solver.kt` fingerprint-stability algorithm** (candidate #5).
  Useful only if/when a "stable patch" feature lands.
- **`CommandUtils.kt` OptionValueConverter** (candidate #7).
  Reusable for the wizard / skill menus if they grow a more
  sophisticated arg-parsing need.

### 3.3 Tier 3 — out of scope

- Any app-specific content from `revanced-manager`: Compose UI,
  ViewModels, Room DAOs, on-device worker process, ~50
  `strings.xml` translations.
- The Kotlin scripting host (candidate #9) — Android-RE's hook
  story is Frida JS, not Kotlin scripts.
- The shaded plugin jar Gradle recipe (candidate #10) — no
  plugin-loader story in Android-RE.
- Any port that would require a copyleft carveout or an
  attribute-and-relicense. Skip.

---

## 4. RE-Library — the killer integration

The sibling repo at `/home/john/Desktop/RE-Library/` is a public,
MIT-licensed documentation site (Astro 6 + Pagefind) backed by a
pip-installable Python MCP server (`re-library-mcp`) over stdio.
It exposes 5 tools:

- `search_re(query, category?, platform?, max_results?)` — free-text
  search with TF-IDF / BM25-ish ranking and a `<mark>`-highlighted
  snippet.
- `get_entry(slug)` — full body of one entry, indexed by
  `<category>/<NN>-<slug>`.
- `list_categories()` — counts per category.
- `list_entries(category)` — lightweight summary of one category.
- `get_anti_analysis_techniques(platform?)` — convenience
  aggregator over the `anti-analysis` category.

The current corpus is 8 categories × 1 entry each (~872 lines
of markdown): `android`, `ios`, `anti-analysis`, `drm`, `packers`,
`tools`, `native`, `web-hybrid`. Each entry has the same six
mandated sections — `Summary`, `Why this matters`, `Mechanics`,
`Approach`, `Common pitfalls`, `Tooling pointers` — plus
`References`. The repo's `_denylist.py` enforces a no-named-vendor
policy in CI, mirroring Android-RE's `CLAUDE.md` "Hard rule".

**Why it's the killer integration:** RE-Library describes
*techniques*; Android-RE ships *tool integrations*. The two are
orthogonal, not redundant. Peer-registering `re-library-mcp` as a
6th Android-RE MCP server (alongside the existing 5) means any
in-session Claude Code agent can call `mcp__re-library__search_re`
to look up a generic pattern *before* writing a Frida hook or
mapping a MASVS finding. No license friction (MIT vs. Apache-2.0).
No code change in `android_re_core` or any of the existing 5 MCP
servers. The full design — `.mcp.json` entry, `Justfile` recipe,
`bin/install.sh` opt-in step, 5 cross-linked skills, the
`tests/test_mcp_config.py` regression suite — is in the plan file.

---

## 5. Constraints

Every implementation that derives from this survey must respect:

- **GPLv3 → clean-room only.** Android-RE stays Apache-2.0. The
  source under `Input/` is for *design reference*. Code comments
  may describe patterns in category terms ("an SDK-34+ ownership
  workaround") but must not lift source from the cloned repos.
- **No-named-apps / no-named-vendors / no-named-DRM rule** (per
  `CLAUDE.md` §"Hard rule" and RE-Library's `_denylist.py`).
  Category terms only: "a paid streaming app", "a hardware-backed
  DRM scheme", "an integrity-attestation API", "a commercial
  bytecode obfuscator". The five cloned repos contain app-specific
  patches; that content is out of scope for this survey and must
  not be reproduced.
- **No `eval()` of Frida script source.** `S307` is in ruff's
  `select` list. Use `subprocess.run` with argv lists.
- **Confirm-gated tools.** `install_apk` / `uninstall_apk` /
  `setup_mitm` etc. require `confirm=true`; default to dry-run
  summary when `confirm=false`.
- **Output convention.** Every file-producing tool writes to
  `Output/<apk-basename>-<short-sha>/<subdir>/<file>`. Override
  with `ANDROID_RE_OUTPUT_DIR` or per-tool `output_path` /
  `output_dir`. No `.triage/` writes (the legacy directory is
  retired; per-triage workdirs now live under
  `Output/<apk>-<sha>/<triage_id>/`).
- **Apache-2.0 stays in place.** The new install module is added
  to the existing `android-re-core` workspace member; no new
  package, no new license header.

---

## 6. Verification

End-to-end verification for the implemented top 2 items is in the
plan file. In summary:

1. `just ci` — `ruff check .` + `pytest -m "not device"` passes.
   New tests: 8 in `tests/test_mcp_config.py`, 11 in
   `android_re_core/tests/test_adb_install.py`, 1 in
   `mcp_servers/dynamic/tests/test_install_dry_run.py`. Total: 20
   new tests, all green.
2. `just install-re-library` installs the PyPI package;
   `re-library-mcp --check` prints the category + entry summary
   JSON and exits 0.
3. In `claude`: `mcp__re-library__list_categories()` returns 8
   categories. `mcp__re-library__search_re(query="apk structure",
   max_results=3)` returns `android/01-apk-structure` first.
4. On a connected Android 14+ device or emulator:
   `mcp__android-re-dynamic__install_apk(serial=..., apk_path=...,
   confirm=false)` writes the dry-run summary at
   `Output/<sample>-<sha>/dynamic/install-attempt.dry-run.json`;
   rerun with `confirm=true` succeeds; `pm list packages | grep
   <id>` shows the package.
5. `just test-device` runs the one new `@pytest.mark.device` test
   end-to-end on the connected emulator.
6. `just lint` is clean: ruff + mypy on the new module.
7. This document is committed alongside the implementation.

---

## 7. Out of scope (explicit list)

- App-specific content from `revanced-manager` (UI, ViewModels,
  Room, Compose, ~50 `strings.xml` translations, on-device worker
  process).
- The external `revanced-patches` RVP bundle (not in `Input/`).
- The TS bridge parity work for the SDK-34+ install — separate
  Phase 4 task; the current plan notes this in the CHANGELOG.
- A MASVS-control field on RE-Library entries — would require a
  schema migration on RE-Library's side; coordinate with the
  RE-Library maintainer separately.
- Any work that would require a copyleft carveout or an
  attribute-and-relicense of a portion of Android-RE.
