# Android-RE

Claude Code skills and MCP servers for Android APK reverse engineering. Drop
in an APK, get a MASVS-aligned triage report in 60 seconds. Hook a method,
get a working Frida session. Inspect a `.so` file, get a hardening report.

This is a **monorepo** containing:

- **5 in-workspace MCP servers** (4 Python + 1 TypeScript) that wrap and
  compose the existing Android RE ecosystem (Apktool, jadx, androguard,
  LIEF, Frida, ADB, etc.). Plus **1 opt-in peer MCP server**
  ([`re-library`](https://heretek-ai.github.io/RE-Library/), MIT) for
  generic RE knowledge-base lookups — registered in `.mcp.json`, but
  installed on demand via `just install-re-library`.
- **12 Claude Code skills** that orchestrate the MCP tools into high-value
  workflows (triage, decompile, dynamic hooking, MASVS reporting, etc.).
- **A shared Python core library** (`android_re_core`) used by every Python
  MCP server so APK parsing, frida sessions, and tool paths are defined
  once. Includes the SDK-34+ aware install ladder
  (`android_re_core.device.adb_install`) so `install_apk` works on
  Android 14+ devices where the one-shot `adb install` is rejected with
  `INSTALL_FAILED_OWNER_BLOCKED`.
- **A unified `Output/` folder convention** — every run lands its
  deliverables at `Output/<apk>-<short-sha>/<subdir>/<file>`. See
  [`docs/output-convention.md`](docs/output-convention.md) for the
  full convention and [`docs/getting-started.md`](docs/getting-started.md)
  for the first-APK walkthrough.

## Repository Layout

```
Input/             drop APKs here (git-ignored)
Output/            every deliverable lands here (git-ignored, env-var-overridable)
android_re_core/   shared Python library (androguard, LIEF, frida, ADB)
mcp_servers/       4 Python MCP servers (static, native, dynamic, triage)
mcp_bridge/        1 TypeScript MCP server (ADB device bridge)
skills/            12 Claude Code skills (workflows that compose MCP tools)
bin/               install.sh, doctor.sh, pull-tools.sh, …
docs/              mkdocs site + docs/research/ (survey write-ups)
examples/          end-to-end walkthroughs (deliberately-vulnerable training apps)
tests/             cross-component / E2E
```

## Quick Start

Prerequisites: Python 3.12+, Node 24+, Java 17+, Android Platform Tools
(`adb`), and a rooted device or emulator (only for dynamic analysis).

```bash
# Install everything: Python packages, Node package, vendored jars, skill symlinks
./bin/install.sh

# Verify the toolchain
./bin/doctor.sh

# Drop an APK in and triage it
claude
> /android-re-triage-orchestrator
> triage path/to/app.apk
```

To install just the skills (and rely on the user installing the MCP servers
separately):

```bash
./bin/install.sh --skills-only
```

Optional: register the `re-library` peer MCP for generic RE background:

```bash
just install-re-library   # one-time; pre-warms the PyPI package
re-library-mcp --check    # smoke test
```

Then in Claude Code:

```text
> mcp__re-library__search_re("apk structure", max_results=3)
> /android-re-static-triage
```

See [`docs/getting-started.md`](docs/getting-started.md) for the full guide.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for an up-to-date
description of the components and how they fit together.

## Skills (12)

| Skill                          | Purpose                                                 |
|--------------------------------|---------------------------------------------------------|
| `android-re-triage-orchestrator` | Drop-in APK → MASVS report                            |
| `android-re-static-triage`     | 5-minute static overview                                |
| `android-re-decompile`         | Pull pseudocode/smali for specific methods              |
| `android-re-dynamic-hook`      | Hook a method, observe behavior on device               |
| `android-re-native-triage`     | Assess native library hardening                         |
| `android-re-network-intercept` | Capture HTTPS from app                                  |
| `android-re-secrets-scan`      | Deep secrets & risk findings                            |
| `android-re-sslpinning-bypass` | Bypass SSL pinning on a target app                      |
| `android-re-repackage`         | Modify + repackage APK for testing                      |
| `android-re-gradle-rebuild`    | Turn an APK into a buildable Gradle project             |
| `android-re-masvs-report`      | Single MASVS-aligned report                             |
| `android-re-frida-script-author` | Generate Frida scripts with helper templates         |

## MCP Servers (5 in-workspace + 1 opt-in peer)

| Server               | Language   | Purpose                              |
|----------------------|------------|--------------------------------------|
| `android-re-static`  | Python     | Static APK analysis (androguard)     |
| `android-re-native`  | Python     | Native binary analysis (LIEF)        |
| `android-re-dynamic` | Python     | Device + Frida instrumentation       |
| `android-re-triage`  | Python     | Orchestrates the other three         |
| `mcp_bridge`         | TypeScript | ADB / screencap / logcat / frida-ps  |
| `re-library` (peer)  | Python     | Generic RE knowledge base (MIT, opt-in) |

The `re-library` peer exposes 5 read-only tools —
`mcp__re-library__list_categories`, `mcp__re-library__list_entries`,
`mcp__re-library__search_re`, `mcp__re-library__get_entry`, and
`mcp__re-library__get_anti_analysis_techniques` — over the public
[RE-Library](https://heretek-ai.github.io/RE-Library/) corpus
(8 categories × markdown entries). Five high-traffic skills open
with a "Background reading (peer MCP)" subsection that calls these
tools before writing Frida hooks or MASVS reports. The peer is
read-only and never overrides a verified observation on the target.

## What changed recently

The latest commit on `main` adds two peer-reviewed items. Both are
documented in the changelog; the survey write-up for the upstream
review is committed under `docs/research/`.

- **RE-Library peer MCP integration** — adds the 6th MCP server
  (`re-library`) to `.mcp.json`, opt-in install via
  `just install-re-library`, a "Peer MCP servers" subsection in
  the tool reference, and a "Background reading (peer MCP)"
  subsection in 5 high-traffic skills. 15 new regression tests
  in `tests/test_mcp_config.py`.
- **SDK-34+ aware APK install (clean-room)** — the dynamic server's
  `install_apk` tool now runs a 3-strategy install ladder
  (`adb_install` → `push_then_pm_install` → `staged_install`) so
  it works on Android 14+ devices. Implementation is written from
  AOSP docs, not lifted from any third-party patching framework;
  the repo stays Apache-2.0. 11 unit tests + 2 dry-run tests + 3
  `@pytest.mark.device` e2e tests.
- **Survey write-up** —
  [`docs/research/2026-06-05-revanced-input-survey.md`](docs/research/2026-06-05-revanced-input-survey.md)
  consolidates the upstream review of the 5 third-party repos
  cloned into `Input/` (all GPLv3) and the sibling RE-Library
  site, with a tiered recommendation and explicit constraints
  (clean-room only, no-named-apps policy, output convention).

See [`CHANGELOG.md`](CHANGELOG.md) for the full history.

## Status

The 4-phase roadmap scaffolded in the original plan is now live:
Phase 1 (foundation) is in; Phase 2 (native + jadx decompile),
Phase 3 (Frida + ADB + device), and Phase 4 (triage orchestrator +
MASVS reporting) are functional and shipping. Two peer-reviewed
items landed in the latest commit (RE-Library peer + SDK-34+
install ladder); 176 tests pass, 1 is skipped (offline SARIF
schema fetch), 5 are device-bound and run under `just test-device`.

The MVP "drop an APK in, get a MASVS report in 60 seconds" flow
works end-to-end with `goals=["masvs"]` against the
`android-re-triage-orchestrator` skill.

## License

Apache-2.0. See [`LICENSE`](LICENSE). Note that `frida-server` is bundled
under the wxWindows Library Licence with a personal-use restriction; see
[`LICENSE-3rdparty.md`](LICENSE-3rdparty.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

See [`SECURITY.md`](SECURITY.md). Report vulnerabilities to
`security@heretek-ai.example` (replace with the real address when the org
sets up a security inbox).
