# Harbor CLI notes

Discovered via `harbor run --help`, `harbor job init --full`, and source
inspection of `harbor/agents/installed/claude_code.py` on 2026-08-11.
Harbor version: `0.21.0`.

## Core flags (long-form; short forms noted where they exist)

| Flag                | Short | Purpose                                                 |
|---------------------|-------|---------------------------------------------------------|
| `--dataset`         | `-d`  | Dataset name@version, e.g. `terminal-bench@2.0`         |
| `--agent`           | `-a`  | Built-in agent name OR `path.to.module:ClassName`       |
| `--model`           | `-m`  | Model name (repeatable for fallback chain)              |
| `--n-concurrent`    | `-n`  | Concurrent trials (default 4)                           |
| `--jobs-dir`        | `-o`  | Output dir for trial logs (default `./jobs`)            |
| `--include-task-name` | `-i` | Glob pattern to include tasks (repeatable)              |
| `--exclude-task-name` | `-x` | Glob pattern to exclude tasks (repeatable)              |
| `--n-tasks`         | `-l`  | Max number of tasks to run (applied after filters)      |
| `--ak`              |       | Agent kwarg `key=value` (repeatable); JSON-as-value     |

## Built-in agents

Harbor ships built-in adapters under `harbor.agents.installed`. From
`harbor/agents/factory.py`:

```
AgentName.CLAUDE_CODE: "harbor.agents.installed.claude_code:ClaudeCode"
```

Other built-ins: `aider`, `antigravity-cli`, `antigravity-sdk`, `cline-cli`,
`codex`, `gemini-cli`, `grok-build`, `openhands`, `terminus`, `terminus-2`,
`terminus-1`, `trae-agent`, `vibe`, etc. Run `harbor run --help` for the
full list.

## Claude Code adapter specifics

`harbor/agents/installed/claude_code.py`:

- `SUPPORTS_CONFIG = True` → the `--ak config=...` flag is honored
- API key env: `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`
- Base URL env: `ANTHROPIC_BASE_URL`
- Default provider: `anthropic`
- Settings file generated at `/tmp/claude-code-settings/settings.json`

## Output directory structure

Harbor writes per-job output to `<jobs-dir>/<job-name>/`. Each job dir contains:

```
<jobs-dir>/<job-name>/
├── config.json                 # Resolved JobConfig
├── trials/                     # Per-trial subdirs
│   └── <trial-id>/
│       ├── trial.log
│       ├── trajectory.json
│       ├── agent.log
│       ├── env.log
│       ├── verifier.log
│       └── result.json         # {"verdict": "pass"|"fail", ...}
└── job.log
```

The `summary.json` referenced by `comparison_report.py` is **NOT produced
by harbor directly** — it's our own roll-up. `comparison_report.py` will
need to read the trial results and aggregate them.

**Action item (deferred):** Task 2 of the implementation plan adds a
post-processing step in `terminal_bench_ab.sh` (or a separate script) that
walks `<jobs-dir>/<job-name>/trials/` and produces a `summary.json` per
agent. This was overlooked when the plan was written; updating the plan in
a follow-up commit.

## Task filtering

`--include-task-name` accepts a glob (repeatable). Example:

```bash
harbor run -d terminal-bench@2.0 \
  -a claude-code \
  --include-task-name cancel-async-tasks \
  --include-task-name fix-git \
  ...
```

For our `quick` tier (8 tasks), we pass the IDs from
`scripts/tb_subset_quick.txt` as repeated `--include-task-name` flags.

## `--ak` agent kwargs

Syntax: `--ak key=value`. JSON values are passed verbatim to the agent's
`__init__`. For Claude Code:

```bash
--ak 'config={"plugin_dir":"/abs/path/to/plugins"}'
```

This is the path the claude-code adapter uses to expose Claude Code's
`plugin_dir` setting.

## Dataset version

`terminal-bench@2.0` is the current version per `harbor download`. Task
count: 89.
