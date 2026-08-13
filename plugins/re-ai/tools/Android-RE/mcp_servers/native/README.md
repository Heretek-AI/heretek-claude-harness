# android-re-mcp-native

MCP server exposing native-binary analysis primitives for Android.
Backed by `android-re-core` (LIEF 0.17.6 wrapper).

## Tools (19)

| Tool                          | Purpose                                         |
|-------------------------------|--------------------------------------------------|
| `list_binaries`               | Enumerate .so / OAT / VDEX / ART in a project    |
| `parse_binary`                | Full parse: format, arch, sections, security     |
| `get_sections`                | Section table                                    |
| `get_symbols`                 | Symbol table (filterable by name)                |
| `get_relocations`             | Relocation entries                               |
| `get_strings`                 | String extraction from a section                 |
| `get_imports`                 | Imported symbols / libraries                     |
| `get_exports`                 | Exported symbols                                 |
| `disassemble_function`        | Disassemble a single symbol                      |
| `disassemble_bytes`           | Disassemble a byte range                         |
| `detect_packers`              | Heuristic packer/protection detection            |
| `lookup_signature`            | YARA-style signature match (built-in rules)      |
| `generate_frida_native_hook`  | Generate a Frida native-hook JS template         |
| `generate_native_interceptor` | Generate an Interceptor.attach JS template       |
| `extract_certificate_chain`   | Pull embedded X.509 certs from a native lib      |
| `get_security_features`       | NX, RELRO, canary, PIE, fortify, RPATH, stripped |
| `compare_binaries`            | Diff two binaries (added / removed / modified)   |
| `yara_scan`                   | YARA rule scan (requires yara CLI)               |
| `build_native_report`         | Consolidated report for one or all libraries     |

## Running

```bash
uv run --package android-re-mcp-native python -m android_re_mcp_native
```

To register with Claude Code:

```bash
claude mcp add android-re-native -- uv run --package android-re-mcp-native python -m android_re_mcp_native
```

## License

Apache-2.0.
