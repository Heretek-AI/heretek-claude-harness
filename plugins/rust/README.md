# rust

> heretek marketplace — Rust task plugin.

## What

`rust-analyzer` LSP + a `cargo-check` skill.

## Install

```bash
/plugin install rust@heretek
```

## Install the LSP binary

```bash
rustup component add rust-analyzer
```

The plugin's `.lsp.json` assumes `rust-analyzer` is on `$PATH`. The plugin does NOT ship the binary (per D7).

## Use

Open any `.rs` file. Claude Code auto-attaches the LSP for diagnostics, jump-to-definition, and hover.

For a one-shot `cargo check`, ask Claude Code to "run cargo check" — the `cargo-check` skill will surface errors.

## Components

- `.lsp.json` — rust-analyzer config
- `skills/cargo-check/SKILL.md` — `cargo check` workflow

## License

MIT — see [LICENSE](../../LICENSE).
