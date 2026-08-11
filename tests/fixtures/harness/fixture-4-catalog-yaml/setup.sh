#!/usr/bin/env bash
set -euo pipefail
mkdir -p catalog
cat > catalog/catalog.yaml <<'EOF'
marketplace:
  name: fixture-marketplace
  description: "Demo marketplace for the harness fixture."
  owner:
    name: Fixture Author
    email: fixture@example.com
  metadata:
    pluginRoot: "./plugins"

plugins:
  - name: existing
    category: task
    tags: [example]
    source: { type: relative, path: existing }
    components: [skills]
    items:
      - id: existing-skill
        kind: skill
        upstream: local/existing-skill
        sha: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        license: MIT
        vetting:
          status: approved
          date: 2026-08-01
          stars: 1
          last_commit: 2026-08-01
          cve_scan: 2026-08-01
          review: reviews/existing-skill.md
EOF
git init -q -b main
git add .
git -c user.email=t@t -c user.name=t commit -q -m init
