# lsp-pack

> heretek marketplace — first-party plugin

## What

Generic LSP configs: rust-analyzer (Rust), basedpyright (Python), gopls
(Go), clangd (C/C++). One plugin covers four major languages for users
who want cross-stack LSP coverage without installing per-language
plugins.

If you already use the per-language first-party plugins (`rust`,
`python`, etc.), those entries are merged at runtime — installing
`lsp-pack` does not conflict, it adds the slot each language's slot
also covers.

## Install

```bash
/plugin install lsp-pack@heretek
```

## Components

- **LSP** — `rust-analyzer`, `basedpyright-langserver`, `gopls`,
  `clangd` (see `.lsp.json` for the file-extension mapping).

## Binary install

Each LSP server must be on `$PATH` before Claude Code can spawn it.
The plugin ships *configuration only*; the binaries are not bundled
or downloaded.

| Language | Command | Install |
|---|---|---|
| Rust      | `rust-analyzer` | `rustup component add rust-analyzer` |
| Python    | `basedpyright-langserver` | `pip install basedpyright` (or `uv tool install basedpyright`) |
| Go        | `gopls` | `go install golang.org/x/tools/gopls@latest` |
| C / C++   | `clangd` | distro package (`apt install clangd`, `brew install clangd`, `dnf install clangd`) or build from source at https://github.com/clangd/clangd |

Verify each binary is on `$PATH` after install:

```bash
command -v rust-analyzer
command -v basedpyright-langserver
command -v gopls
command -v clangd
```

## License

MIT — see [LICENSE](../../LICENSE).
