#!/usr/bin/env bash
set -euo pipefail
cat > .pre-commit-config.yaml <<'EOF'
repos:
  - repo: local
    hooks:
      - id: trailing-whitespace
        name: Trim trailing whitespace
        entry: bash -c 'sed -i "s/[[:space:]]*$//" "$@"'
        language: system
        types: [text]
        args: []
EOF
cat > package.json <<'EOF'
{
  "name": "fixture-skeleton",
  "version": "0.0.0"
}
EOF
git init -q -b main
git add .
git -c user.email=t@t -c user.name=t commit -q -m init
