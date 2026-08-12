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

## Smoke run (Phase 5 verification)

Performed on 2026-08-11 with a mocked harbor binary at `/tmp/fake-harbor/`.
The fake harbor records each invocation to a log and writes a single
`result.json` per trial. End-to-end flow verified:

- `scripts/terminal_bench_ab.sh` invokes harbor twice with the right flags:
  Agent A passes `--ak 'config={"plugin_dir":"/tmp/smoke/plugins"}'`;
  Agent B has no `--ak`. Both pass all 8 `--include-task-name` IDs from
  `scripts/tb_subset_quick.txt`.
- `scripts/comparison_report.py` reads both stub `summary.json` files,
  renders a Markdown body with all required sections (Headline,
  Per-task, helped/hurt). Secret-leak guard does not abort on clean
  fixtures.

A live run on `main` is gated on repo secrets being configured by a
maintainer (`ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_AUTH_TOKEN`).

## Follow-up: `summary.json` aggregation

The current smoke uses stub `summary.json` files because **harbor does
not produce `summary.json` directly** — it writes per-trial
`result.json` files under `<jobs-dir>/<job-name>/trials/<trial-id>/`.

A future task must add a post-processing step (in
`terminal_bench_ab.sh` or a separate script) that walks
`<results_dir>/agent-{a,b}/jobs/*/trials/*/result.json` and emits a
`summary.json` per agent. Until that step ships, real harbor runs will
not produce the inputs `comparison_report.py` expects.

Captured here rather than as a plan amendment so the T8 plan stays
frozen at the design boundary; the aggregation step is the natural
follow-up spec.
