# TerminalBench A/B Evaluation GitHub Action 🏆

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-TerminalBench%20A%2FB%20Action-blue?logo=github)](https://github.com/marketplace?type=actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

Benchmark your **Claude Code plugins**, agent prompts, MCP servers, and mechanical quality guardrails against **[TerminalBench 2.0](https://www.tbench.ai/)** using the **[Harbor Framework](https://github.com/harbor-framework/harbor)**.

---

## ⚡ Features

- **Automated A/B Benchmarking**: Runs **Agent A** (configured with your plugins/harness) vs **Agent B** (unmodified baseline) in parallel container environments.
- **Harbor 0.21.0 Integration**: Uses Harbor Framework for reproducible, isolated trial execution.
- **Detailed Markdown Reports**: Renders headline pass rates, pass rate deltas (`+Δ%`), wall-clock execution runtimes, token counts, and per-task outcome matrices.
- **Secret Scanning Protection**: Built-in regex interceptor guarantees no Anthropic API keys, GitHub PATs, or JWT tokens leak into workflow logs or GitHub issue reports.
- **Automated GitHub Issue Posting**: Posts formatted evaluation comparison reports directly to repository GitHub Issues.

---

## 🚀 Quickstart Example Workflow

Add the following workflow file to your repository at `.github/workflows/terminal-bench-ab.yml`:

```yaml
name: TerminalBench A/B Evaluation

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      n_tasks:
        description: "Number of TerminalBench tasks ('8' for quick subset, or 'all')"
        default: "8"

permissions:
  contents: read
  issues: write

jobs:
  benchmark:
    runs-on: ubuntu-latest
    timeout-minutes: 360

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Run TerminalBench A/B Benchmark Action
        uses: Heretek-AI/harness-audit@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
          anthropic_model: 'claude-sonnet-5-20260301'
          plugin_dir: ${{ github.workspace }}/plugins
          n_tasks: ${{ github.event.inputs.n_tasks || '8' }}
```

---

## ⚙️ Inputs Reference

| Input | Description | Required | Default |
| :--- | :--- | :---: | :--- |
| `anthropic_api_key` | Anthropic API key or authentication token | **Yes** | — |
| `anthropic_model` | Model name for evaluation | No | `claude-sonnet-5-20260301` |
| `plugin_dir` | Path to Claude Code plugins directory to benchmark (Agent A) | No | `""` |
| `n_tasks` | Number of TerminalBench tasks (`"8"` for quick subset, or `"all"`) | No | `"8"` |
| `n_concurrent` | Per-agent trial concurrency level | No | `"8"` |
| `open_issue` | Open GitHub Issue with evaluation report (`"true"` or `"false"`) | No | `"true"` |

---

## 📤 Outputs Reference

| Output | Description |
| :--- | :--- |
| `pass_rate_delta` | Pass rate improvement delta (Agent A vs Agent B) |
| `markdown_report_path` | Path to generated Markdown comparison report (`/tmp/comparison.md`) |

---

## 💻 Local Execution

You can also run TerminalBench A/B evaluation tests locally:

```bash
export ANTHROPIC_AUTH_TOKEN="your-api-key"
export ANTHROPIC_MODEL="claude-sonnet-5-20260301"
export HERETEK_PLUGIN_DIR="$(pwd)/plugins"

./scripts/terminal_bench_ab.sh
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Built with ❤️ by [Heretek-AI](https://github.com/Heretek-AI).
