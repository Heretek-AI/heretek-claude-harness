#!/usr/bin/env bash
# scripts/terminal_bench_ab.sh — run Harbor Terminal-Bench 2 with two agents:
# Agent A: claude-code + heretek harness (via --ak config={plugin_dir}).
# Agent B: claude-code baseline (no harness).
#
# Env vars (consumed):
#   ANTHROPIC_MODEL          — required. e.g., "claude-sonnet-5-20260301"
#   ANTHROPIC_BASE_URL       — optional. Read by harbor/claude-code adapter.
#   ANTHROPIC_AUTH_TOKEN     — required. Read by claude-code adapter.
#   HERETEK_PLUGIN_DIR       — required. Absolute path to plugins/ checkout.
#   HERETEK_N_CONCURRENT     — optional. Default 8.
#   HERETEK_DATASET          — optional. Default "terminal-bench@2.0".
#   HERETEK_QUICK_SUBSET     — optional. Path to subset file.
#                              Default scripts/tb_subset_quick.txt.
#   RESULTS_DIR              — optional. Default ./results.
#
# Per-agent results land in:
#   ${RESULTS_DIR}/agent-a/jobs/<job-name>/trials/<trial-id>/...
#   ${RESULTS_DIR}/agent-b/jobs/<job-name>/trials/<trial-id>/...
# After each agent's harbor run, aggregate_results.py emits:
#   ${RESULTS_DIR}/agent-a/summary.json
#   ${RESULTS_DIR}/agent-b/summary.json
# (consumed by scripts/comparison_report.py).
#
# Exit code: 0 if both agents succeed; non-zero if either fails.

set -euo pipefail

ANTHROPIC_MODEL="${ANTHROPIC_MODEL:?ANTHROPIC_MODEL must be set}"
HERETEK_PLUGIN_DIR="${HERETEK_PLUGIN_DIR:?HERETEK_PLUGIN_DIR must be set}"
HERETEK_N_CONCURRENT="${HERETEK_N_CONCURRENT:-8}"
HERETEK_DATASET="${HERETEK_DATASET:-terminal-bench@2.0}"
RESULTS_DIR="${RESULTS_DIR:-./results}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERETEK_QUICK_SUBSET="${HERETEK_QUICK_SUBSET:-${SCRIPT_DIR}/tb_subset_quick.txt}"

# Build --include-task-name flags from subset file (one ID per line; blank lines ignored).
# `|| [[ -n "$task_id" ]]` handles files that lack a trailing newline on the last line.
TASK_ARGS=()
if [[ -f "$HERETEK_QUICK_SUBSET" ]]; then
  while IFS= read -r task_id || [[ -n "$task_id" ]]; do
    [[ -n "$task_id" ]] && TASK_ARGS+=(--include-task-name "$task_id")
  done < "$HERETEK_QUICK_SUBSET"
fi

# Wipe results dir and recreate per-agent subdirs.
rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR/agent-a" "$RESULTS_DIR/agent-b"

# Per-agent jobs dirs (harbor writes <jobs-dir>/<job-name>/trials/... under each).
AGENT_A_JOBS="${RESULTS_DIR}/agent-a/jobs"
AGENT_B_JOBS="${RESULTS_DIR}/agent-b/jobs"

echo "[terminal_bench_ab] agent A (with heretek) -> ${AGENT_A_JOBS}"
harbor run \
  --dataset "$HERETEK_DATASET" \
  --agent claude-code \
  --model "$ANTHROPIC_MODEL" \
  --n-concurrent "$HERETEK_N_CONCURRENT" \
  --ak "config={\"plugin_dir\":\"${HERETEK_PLUGIN_DIR}\"}" \
  --jobs-dir "$AGENT_A_JOBS" \
  "${TASK_ARGS[@]}"

echo "[terminal_bench_ab] agent B (baseline) -> ${AGENT_B_JOBS}"
harbor run \
  --dataset "$HERETEK_DATASET" \
  --agent claude-code \
  --model "$ANTHROPIC_MODEL" \
  --n-concurrent "$HERETEK_N_CONCURRENT" \
  --jobs-dir "$AGENT_B_JOBS" \
  "${TASK_ARGS[@]}"

echo "[terminal_bench_ab] aggregating results for agent A -> ${RESULTS_DIR}/agent-a/summary.json"
python scripts/aggregate_results.py \
  --jobs-dir    "$AGENT_A_JOBS" \
  --agent-label agent-a-with-heretek \
  --model       "$ANTHROPIC_MODEL" \
  --commit-sha  "${GITHUB_SHA:-local}" \
  --output      "${RESULTS_DIR}/agent-a/summary.json"

echo "[terminal_bench_ab] aggregating results for agent B -> ${RESULTS_DIR}/agent-b/summary.json"
python scripts/aggregate_results.py \
  --jobs-dir    "$AGENT_B_JOBS" \
  --agent-label agent-b-baseline \
  --model       "$ANTHROPIC_MODEL" \
  --commit-sha  "${GITHUB_SHA:-local}" \
  --output      "${RESULTS_DIR}/agent-b/summary.json"

echo "[terminal_bench_ab] both agents complete"
