# re-dotnet

MCP server for .NET assembly analysis. Vendor-neutral wrapper around [AsmResolver](https://github.com/Washi1337/AsmResolver) (PE + .NET metadata) and [ICSharpCode.Decompiler / ILSpy](https://github.com/icsharpcode/ILSpy) (C# decompiler).

## Why

The other RE-AI MCP servers (`re-lief`, `re-rizin`, `re-capa`) handle native PE, ELF, MachO, DEX, ART, OAT — but **none of them read the .NET CLI header** or the ECMA-335 metadata tables. A `MonoLauncher`-style launcher that ships its payload as a managed .NET assembly is invisible to those tools; the import hash is empty, the strings table is uninformative, and rizin only sees native wrapper code.

`re-dotnet` fills that gap. It enumerates TypeDef / MethodDef / FieldDef, walks the #US string heap, and decompiles a single class or method to C# on demand.

## Architecture

The MCP server itself is pure Python. The heavy lifting is done by a small .NET 10 CLI binary, `re-dotnet-cli`, built from `src/re_dotnet/dotnet/Re.Dotnet.Cli/`:

```
Claude Code (MCP stdio)
  │
  ▼
re-dotnet server (Python, this directory)
  │  subprocess.run(...)
  ▼
re-dotnet-cli (self-contained .NET 10 binary, single-file publish)
  │
  ├─ AsmResolver 6.x        (PE + .NET metadata, obfuscation-robust)
  └─ ICSharpCode.Decompiler 9.x  (C# decompiler)
```

The subprocess boundary is intentional:

- **No `pythonnet`.** `pythonnet` is a fragile ABI bridge that breaks on every Python minor. Process isolation is robust.
- **No Mono.** .NET 10 is the only supported runtime.
- **Single-file publish.** The CLI is a self-contained binary; no `dotnet --info` dance, no `DOTNET_ROOT` env vars, no GAC.

The Python wrapper locates the binary via this fallback chain (see `runner.py`):

1. `$RE_DOTNET_CLI_PATH` (escape hatch for tests)
2. `<server>/bin/re-dotnet-cli` (install.sh default)
3. The dev build under `src/re_dotnet/dotnet/.../bin/`
4. `re-dotnet-cli` on `$PATH`

## Tools

| Tool | What it does |
|---|---|
| `check_dotnet` | Health check — return .NET runtime + AsmResolver + Decompiler versions |
| `parse_assembly` | Enumerate TypeDef rows; return assembly header + one row per type |
| `decompile_type` | Decompile a single class to C# via ILSpy |
| `decompile_method` | Decompile a single method to C# via ILSpy |
| `list_strings` | Walk field-default constant strings (the #US heap subset) |
| `get_entry_point` | Return the managed entry point (`<Module>::.cctor` or `Main`) |

## Install

`./install.sh` builds the .NET CLI via `dotnet publish` and copies the resulting binary to `servers/re-dotnet/bin/`.

To build standalone:

```bash
cd servers/re-dotnet/src/re_dotnet/dotnet/Re.Dotnet.Cli
dotnet publish -c Release -o ../../../../bin
```

To run:

```bash
re-dotnet                          # stdio transport (default for MCP)
python -m re_dotnet                # equivalent
```

## Requirements

- .NET 10 SDK or runtime (`dotnet --version` ≥ 10.0)
- 2 GB disk for the .NET SDK + the self-contained binary

## Deobfuscation notes

The ILSpy decompiler produces clean C# for **non-obfuscated** assemblies. For binaries that have been through commercial obfuscation (control-flow flattening, string encryption, JIT-hooking), the decompiler will surface `Unable to decompile ...` errors. The remediation path is to run the .NET deobfuscator first (the OSS `de4dot` shells out, GPL-3.0 — the RE-AI plugin keeps it process-isolated so the plugin's own distribution stays clean) and then re-run `decompile_type` / `decompile_method` on the cleaned output.

## Pairing with `re-leak-scan`

A .NET-style launcher that calls out to telemetry endpoints (Sentry, Logstash, Confluence, Google Drive) will have those URLs as field-default constants. Run `re-leak-scan` (T2.2) on the assembly, or call `list_strings` here and pipe the output through a regex filter for the four endpoint families.
