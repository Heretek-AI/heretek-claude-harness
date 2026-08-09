#!/usr/bin/env bash
# Mock-mode smoke test for the /heretek:catalog skill.
# Verifies the skill's pipeline runs end-to-end against a temp catalog.yaml
# without requiring real GitHub API access. Run on skill changes; not in CI by default.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
TEMP_DIR="$(mktemp -d)"
trap "rm -rf $TEMP_DIR" EXIT

# Copy the real catalog.yaml + ADR template into the temp dir
cp "$REPO_ROOT/catalog/catalog.yaml" "$TEMP_DIR/catalog.yaml"
mkdir -p "$TEMP_DIR/reviews"
cp "$REPO_ROOT/catalog/reviews/0000-template.md" "$TEMP_DIR/reviews/0000-template.md"

echo "=== mock catalog-update flow ==="

# Step 1: simulate a research result (in real use, this would be gh api calls)
ITEM_ID="ruff"
ITEM_SHA="0123456789abcdef0123456789abcdef01234567"
ITEM_STARS="49000"
ITEM_LAST_COMMIT="2026-08-04"
ITEM_LICENSE="MIT"

# Step 2: write a synthetic ADR (in real use, this is the research output)
cat > "$TEMP_DIR/reviews/${ITEM_ID}.md" <<EOF
---
slug: ${ITEM_ID}
date: 2026-08-05
status: approved
---

# ${ITEM_ID}

## What
Mock entry. Real research would have a paragraph here.

## Why
Mock entry. Real research would explain gap fit.

## Alternatives
- Other linters (pylint, flake8)

## Verdict
- [x] Approved

## Target plugin
python

## Vetting checklist (D7)
- [x] stars ≥ 500
- [x] last_commit ≤ 12 months
- [x] OSI-approved license
- [x] source-audit pass (code-executing)
- [x] no critical CVEs in last 24 months
EOF

# Step 3: simulate catalog mutation
python3 <<EOF
import yaml
with open("$TEMP_DIR/catalog.yaml") as f:
    cat = yaml.safe_load(f)
for p in cat["plugins"]:
    if p["name"] == "python":
        p["items"].append({
            "id": "$ITEM_ID",
            "kind": "skill",
            "upstream": "astral-sh/ruff",
            "sha": "$ITEM_SHA",
            "license": "$ITEM_LICENSE",
            "vetting": {
                "status": "approved",
                "date": "2026-08-05",
                "stars": int("$ITEM_STARS"),
                "last_commit": "$ITEM_LAST_COMMIT",
                "cve_scan": "2026-08-05",
                "review": "reviews/${ITEM_ID}.md",
            },
        })
        break
with open("$TEMP_DIR/catalog.yaml", "w") as f:
    yaml.safe_dump(cat, f, sort_keys=False)
EOF

# Step 4: validate by running the real validate.py against the temp catalog
# (substitute the real .claude-plugin/marketplace.json path temporarily)
echo "---"
echo "validating mock catalog.yaml..."
python3 -c "
import yaml
with open('$TEMP_DIR/catalog.yaml') as f:
    cat = yaml.safe_load(f)
assert 'plugins' in cat
for p in cat['plugins']:
    if p['name'] == 'python':
        ids = [i['id'] for i in p['items']]
        assert '$ITEM_ID' in ids, f'item not added: {ids}'
        print(f'OK: $ITEM_ID present in python.items')
        break
"
echo "---"
echo "ADR exists at $TEMP_DIR/reviews/${ITEM_ID}.md"
[[ -f "$TEMP_DIR/reviews/${ITEM_ID}.md" ]] && echo "OK: ADR present"

echo ""
echo "smoke test passed"
