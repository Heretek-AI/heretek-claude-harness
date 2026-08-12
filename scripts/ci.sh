#!/usr/bin/env bash
# scripts/ci.sh — single local-CI entry for the heretek harness.
set -euo pipefail

# 1. Pytest suite
pytest -q

# 2. Schema validation
python scripts/validate.py

# 3. Regenerate marketplace index
python scripts/generate_marketplace.py

# 4. Marketplace.json drift check
git diff --exit-code .claude-plugin/marketplace.json

# 5. Catalog smoke test
if [ -f catalog/tests/smoke_test.sh ]; then
  bash catalog/tests/smoke_test.sh
fi

echo "ci: OK"
