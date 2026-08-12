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

## Output directory structure (harbor 0.21.0, verified 2026-08-12)

Harbor writes per-job output to `<jobs-dir>/<job-name>/`. Each trial
directory contains:

```
<jobs-dir>/<job-name>/<trial-name>/
├── agent/         # Subdirectory; harbor's claude-code adapter writes here.
├── verifier/      # Subdirectory; contains reward.txt + reward.json.
├── artifacts/     # Collected artifacts from the environment.
├── config.json    # Resolved trial config.
├── lock.json      # Resolved trial inputs.
├── result.json    # TrialResult (pydantic model, JSON-encoded).
└── trial.log      # Logs from the trial.
```

The per-trial `result.json` is a `TrialResult` pydantic model. Fields
relevant to aggregation:

- `task_name` — task ID (e.g. `tb-001-fix-permissions`).
- `verifier_result.rewards` (`dict[str, float|int]`) — pass iff any value == 1.0.
- `agent_result.n_input_tokens` / `n_output_tokens` / `n_cache_tokens` / `cost_usd`.
- `started_at` / `finished_at` (ISO 8601) — wall-clock = `finished_at - started_at`.
- `agent_info.model_info.name` — model name.

**No** `trials/` subdir, **no** `trajectory.json`, **no** `agent.log`,
**no** `env.log`, **no** `verifier.log` files — those were recorded
from an older harbor version and are stale for 0.21.0.

Harbor ALSO writes a job-level `<jobs-dir>/<job-name>/result.json`
(`JobResult` with aggregated `JobStats` and the same `trial_results`
list). The aggregator does not consume this — it walks per-trial
files directly (robust to partial runs).

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

## Per-agent `summary.json`

Per-agent `summary.json` is aggregated from per-trial `result.json`
files by `scripts/aggregate_results.py`, invoked after each `harbor run`
in `terminal_bench_ab.sh`. See
`docs/superpowers/specs/2026-08-12-aggregate-results-design.md` for
the schema and edge-case handling.
