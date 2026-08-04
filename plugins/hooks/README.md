# hooks

> heretek marketplace — flagship plugin. Three layers of quality gates wired into both Claude Code's hook system and git.

## What

The `hooks` plugin is the heretek marketplace's differentiator. It runs:
- **Layer 1 (fast blocking, <100ms):** `ruff` for Python, `rustfmt` for Rust, `biome` for JS/TS/JSON/CSS on every Claude Code `Edit`/`Write`/`MultiEdit`. Fail-open on time-budget overrun.
- **Layer 2 (on-demand):** `/quality-gate:run` slash command runs clippy, megalinter, tdd-guard, jscpd, sonarqube on the repo.
- **Layer 3 (git hooks):** `/hooks:install-git-hooks` installs pre-commit + pre-push hooks via the pre-commit framework.

## Install

```bash
/plugin install hooks@heretek
```

## Install Layer-1 tools

Layer 1 requires these binaries on your `PATH`:

```bash
# Python:
pip install ruff

# Rust (via rustup):
rustup component add rustfmt

# JavaScript/TypeScript/JSON/CSS:
npm install -g @biomejs/biome
# or use npx (the dispatcher will fall back automatically)
```

## Install Layer-3 framework

```bash
pip install pre-commit
/hooks:install-git-hooks
```

## D15 — strict hooks ownership

The `hooks` plugin is the **sole owner** of all hooks firing on `Edit`/`Write`/`PreToolUse`/`PostToolUse`/`Notification`. No other plugin in the heretek marketplace ships such hooks — including security-scoped hooks.

If you enable another Claude Code marketplace that includes hooks, ordering is resolved at the manifest level (strict mode, `plugin.json` is authority). The heretek `hooks` plugin's hooks will run; the other plugin's hooks will not.

To enforce this in the marketplace: the catalog generator ensures no other plugin entry in `catalog/catalog.yaml` declares `hooks` in its `components` list.

## Usage

**Automatic (Layer 1):** every Edit/Write/MultiEdit is gated. Lint failures block the tool call; lint passes are silent.

**On-demand (Layer 2):** `/quality-gate:run` for whole-repo, `/quality-gate:run diff` for staged/unstaged changes, `/quality-gate:run src/foo` for a path.

**Git hooks (Layer 3):** after `/hooks:install-git-hooks`, every `git commit` runs ruff + the heretek fast gate as pre-commit hooks; `git push` re-runs them as pre-push hooks.

## Components

- `hooks/` — `hooks.json` manifest (PreToolUse matcher for Edit/Write/MultiEdit)
- `scripts/fast_gate.py` — Layer 1 dispatcher
- `scripts/quality_gate.py` — Layer 2 runner
- `scripts/install_git_hooks.sh` — Layer 3 installer
- `commands/quality-gate.md` — `/quality-gate:run` slash command
- `commands/install-git-hooks.md` — `/hooks:install-git-hooks` slash command
- `.pre-commit-config.yaml` — pre-commit framework config

## License

MIT — see [LICENSE](../../LICENSE).
