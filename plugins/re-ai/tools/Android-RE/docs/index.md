# Android-RE

Claude Code skills and MCP servers for Android APK reverse engineering.

Drop in an APK → get a MASVS-aligned triage report in 60 seconds. Hook a method
→ get a working Frida session. Inspect a `.so` file → get a hardening report.

## Quick Links

- [Getting Started](getting-started.md)
- [Architecture](architecture.md)
- [MCP Tool Reference](mcp-tool-reference.md)
- [Skills Catalog](skills.md)
- [Security Model](security-model.md)
- [Contributing](../CONTRIBUTING.md)

## What is this?

This monorepo contains:

- **5 MCP servers** (4 Python, 1 TypeScript) that wrap and compose the existing
  Android RE ecosystem — Apktool, jadx, androguard, LIEF, Frida, ADB, MobSF,
  apkleaks, androwarn, quark-engine, and more.
- **11 Claude Code skills** that orchestrate the MCP tools into high-value
  workflows.
- **A shared Python core library** (`android_re_core`) that all four Python
  MCP servers depend on, so APK parsing, frida sessions, and tool paths are
  defined once.

## What it's not

- **Not a generic UI automation tool.** For cross-platform mobile UI driving
  we recommend [mobile-next/mobile-mcp](https://github.com/mobile-next/mobile-mcp).
  Our `mcp_bridge` is intentionally RE-focused.
- **Not a malware scanner.** It composes with MobSF, apkleaks, androwarn,
  and quark-engine; it does not replace them.
- **Not a Frida competitor.** It composes Frida (via `frida` + `frida-tools`)
  and provides a Python-first MCP surface for the workflows where Frida is
  the right tool.

## Status

Phase 1 (Foundation) is in progress. See `CHANGELOG.md` for the latest
state, and `/home/john/.claude/plans/calm-juggling-clarke.md` for the full
4-phase roadmap.
