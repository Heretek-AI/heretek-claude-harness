# Getting Started

## Prerequisites

| Tool             | Version  | Why                                                       |
|------------------|----------|-----------------------------------------------------------|
| Python           | 3.12+    | Runs all Python MCP servers                               |
| uv               | 0.5+     | Workspace + dependency management                          |
| Node.js          | 24+      | Runs the TypeScript `mcp_bridge`                          |
| pnpm             | 10+      | Workspace + Node dependency management                     |
| Java             | 17+      | Runs Apktool, jadx, uber-apk-signer                        |
| Android Platform Tools | latest | `adb` for device interaction                            |
| git-lfs          | latest   | Stores APK/.so/.jar fixtures                              |

A rooted Android device or emulator is required **only for dynamic analysis
skills** (Phase 3+). Static analysis works entirely on-host.

## Install

### Full install (recommended)

```bash
git clone https://github.com/Heretek-AI/Android-RE.git
cd Android-RE
./bin/install.sh --full
```

This will:

1. Sync the uv workspace (`uv sync --all-packages`).
2. Install pnpm dependencies (`pnpm install`).
3. Build the TypeScript bridge (`pnpm build`).
4. Vendor the latest jadx, apktool, uber-apk-signer, and frida-server into
   `./vendor/`.
5. Symlink all 11 skills into `~/.claude/skills/`.

### Skills-only install

If you prefer to manage the Python/Node packages yourself:

```bash
./bin/install.sh --skills-only
```

### Project-local install

```bash
INSTALL_DIR=./.claude/skills ./bin/install.sh --skills-only
```

## Verify

```bash
./bin/doctor.sh
```

You should see green checkmarks for: `adb`, `java`, `frida-server` (if a
device is connected), `uv`, `pnpm`, and the Python packages.

## Triage your first APK

```bash
# In a Claude Code session
claude
> /android-re-static-triage
> /path/to/app.apk
```

Or invoke the orchestrator directly:

```
> /android-re-triage-orchestrator
> Triage /path/to/app.apk and produce a MASVS report.
```

### Where do the results land?

Every Android-RE run produces a directory tree under
`Output/<apk-basename>-<short-sha>/<subdir>/<file>` at the repo root.
For example, a triage of `<your-app>.apk` (SHA-256 starts `<first-8-of-sha>`) lands at:

```
Output/<your-app>-<first-8-of-sha>/<triage-id>/triage-<id>.md
Output/<your-app>-<first-8-of-sha>/masvs/coverage.json
Output/<your-app>-<first-8-of-sha>/masvs/report.sarif
Output/<your-app>-<first-8-of-sha>/secrets/secrets-findings.json
Output/<your-app>-<first-8-of-sha>/native/native-report.json
Output/<your-app>-<first-8-of-sha>/dynamic/session-report.json
```

The `Output/` directory is git-ignored. Override the base path with:

```bash
export ANDROID_RE_OUTPUT_DIR=/scratch/android-re-output  # set BEFORE launching claude
```

Set this env var before launching Claude Code (it's read once at
import time of `android_re_core.paths`). See
[`output-convention.md`](output-convention.md) for the full convention and the per-skill
output paths.

## What's next?

- [Architecture](architecture.md) — how the pieces fit together.
- [MCP Tool Reference](mcp-tool-reference.md) — every tool, every input.
- [Skills](skills.md) — every skill, every trigger phrase.
- [Contributing a Tool](contributing-a-tool.md) — add your own MCP tool.
