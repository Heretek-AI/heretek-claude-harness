#!/usr/bin/env bash
# scripts/ci.sh — single local-CI entry for the heretek harness.
# Replaces the 5-line bash block in CLAUDE.md with one command.
# Mirrors the GitHub Actions validate.yml pipeline:
#   pytest + validate (schema) + generate (marketplace.json) + smoke.
set -euo pipefail

# Tests
pytest -q

# Catalog/marketplace schema validation
python scripts/validate.py

# Regenerate the marketplace index from catalog.yaml
python scripts/generate_marketplace.py

# Marketplace.json must match the regenerated copy (no drift)
git diff --exit-code .claude-plugin/marketplace.json

# Heretek-specific smoke tests
bash tests/smoke/fast_gate_smoke.sh
bash catalog/tests/smoke_test.sh

# Lint the Terminal-Bench A/B workflow (actionlint is optional; skip with a notice)
if command -v actionlint >/dev/null 2>&1; then
  actionlint .github/workflows/terminal-bench-ab.yml
else
  echo "ci: actionlint not installed; skipping workflow lint (install: brew install actionlint)"
fi

echo "ci: OK"
