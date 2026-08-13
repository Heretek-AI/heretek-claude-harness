# android-re-mcp-static

MCP server exposing static-analysis primitives for Android APKs. Backed by
`android-re-core` (androguard 4.1.4 wrapper) and jadx + apktool subprocesses.

## Tools (26)

Project lifecycle:
- `open_project`, `close_project`, `list_projects`

Manifest:
- `read_manifest`, `list_components`, `get_permissions`

DEX:
- `find_classes`, `find_methods`

Decompilation (jadx):
- `decompile_class`, `decompile_method` — single class / single method.
- `decompile_apk` — enumerate the decompiled tree (file paths + line
  counts; supports `deobfuscate`, `threads`, `output_format`).
- `read_source` — read a file by path relative to the decompiled
  `sources/` dir (refuses `..` and files > 10 MB).

Smali / repackage:
- `get_smali`, `decode_apk`, `rebuild_apk`, `patch_manifest`

Signing:
- `verify_signature`, `get_certificate_info`

Native (delegated):
- `list_native_libs`, `analyze_elf`, `disassemble_native`

Secrets / reports:
- `scan_secrets`, `scan_with_quark`, `run_androwarn`,
  `build_sarif_report`, `get_masvs_coverage`

Each decompile tool caches its workdir under
`/tmp/android-re/<project_id>-jadx-{deobf,plain}-{java,kotlin}/`. The
`deobfuscate` and `output_format` MCP parameters are part of the
cache key — flipping either triggers a fresh jadx run with the new
flags.

## Running

```bash
uv run --package android-re-mcp-static python -m android_re_mcp_static
```

The server communicates over **stdio**. To register with Claude Code:

```bash
claude mcp add android-re-static -- uv run --package android-re-mcp-static python -m android_re_mcp_static
```

## License

Apache-2.0. See `LICENSE` in the monorepo root.
