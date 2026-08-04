# python

> heretek marketplace — Python task plugin.

## What

`ruff` LSP + a `ruff-check` skill. Ruff is the de-facto Python linter in
2026 and is used here for both roles (inline LSP diagnostics and a one-shot
project-wide lint pass) per the plan's "pragmatic" note — one tool, one
install, one config file.

## Install

```bash
/plugin install python@heretek
```

## Install the LSP binary

```bash
pip install ruff
# or, if you use uv:
uv tool install ruff
```

The plugin's `.lsp.json` assumes `ruff` is on `$PATH` (`ruff --version`
should print something like `ruff 0.16.1`). The plugin does NOT ship the
binary (per D7).

## Use

Open any `.py` or `.pyi` file. Claude Code auto-attaches the LSP for inline
lint and format diagnostics. Ruff's LSP is intentionally lint/format-only —
for full type checking pair it with `mypy` or `pyright` outside the plugin.

For a one-shot project-wide lint pass, ask Claude Code to "run ruff check"
— the `ruff-check` skill will surface the findings.

## Components

- `.lsp.json` — ruff LSP config (`ruff server`)
- `skills/ruff-check/SKILL.md` — `ruff check` workflow

## License

MIT — see [LICENSE](../../LICENSE).
