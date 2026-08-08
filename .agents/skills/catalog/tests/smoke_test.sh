#!/usr/bin/env bash
# catalog/tests/smoke_test.sh
#
# Smoke test for the catalog skill machinery.
# Per docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md §4.4
# Per issue #60.
#
# The catalog skill is a SKILL.md (AI-agent procedure) — not an executable
# module. This smoke test exercises the pipeline the skill depends on:
#   - scripts/validate.py against the real catalog
#   - scripts/generate_marketplace.py (idempotent regenerate check)
#   - pytest tests/ (regression)
#
# Exit 0 on success; non-zero on any failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "[smoke] repo root: $REPO_ROOT"

# validate the real catalog via scripts/validate.py
echo "[smoke] running python scripts/validate.py"
cd "$REPO_ROOT"
python scripts/validate.py

# idempotent regenerate check — generate_marketplace.py output must be byte-identical
echo "[smoke] running scripts/generate_marketplace.py (idempotency check)"
git diff --exit-code .claude-plugin/marketplace.json

# pytest regression check
echo "[smoke] running pytest -q"
pytest -q

echo "[smoke] OK"
