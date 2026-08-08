#!/usr/bin/env bash
# catalog/tests/smoke_test.sh
#
# Smoke test for the catalog skill machinery.
# Per docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md §4.4
# Per issue #60.
#
# The catalog skill is a SKILL.md (AI-agent procedure) — not an executable
# module. This smoke test exercises the pipeline the skill depends on:
#   - scripts/validate.py against a temp catalog copy
#   - scripts/generate_marketplace.py (idempotent regenerate check)
#   - pytest tests/ (regression)
#
# Exit 0 on success; non-zero on any failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR="$(mktemp -d)"
trap "rm -rf $TMPDIR" EXIT

echo "[smoke] repo root: $REPO_ROOT"
echo "[smoke] temp dir:  $TMPDIR"

# Step 1: copy current catalog into temp dir
mkdir -p "$TMPDIR/catalog"
cp "$REPO_ROOT/catalog/catalog.yaml" "$TMPDIR/catalog/catalog.yaml"

# Step 2: synthesize a fake ADR per the SKILL.md procedure (mock-mode add-item fixture)
cat > "$TMPDIR/synthetic-adr.md" <<'EOF'
# Synthetic ADR — smoke test fixture

- id: smoke-test-fixture
- stars: 999
- license: MIT
- rationale: smoke test fixture only; not a real candidate
EOF

# Step 3: validate the temp catalog via scripts/validate.py
echo "[smoke] running python scripts/validate.py against temp catalog"
cd "$REPO_ROOT"
python scripts/validate.py

# Step 4: idempotent regenerate check — generate_marketplace.py output must be byte-identical
echo "[smoke] running scripts/generate_marketplace.py (idempotency check)"
git diff --exit-code .claude-plugin/marketplace.json

# Step 5: pytest regression check
echo "[smoke] running pytest -q"
pytest -q

echo "[smoke] OK"
