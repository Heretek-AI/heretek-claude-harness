#!/usr/bin/env bash
# PostToolUse hook: run pre-commit on the changed files.
set -euo pipefail

input="$(cat)"
tool="$(echo "$input" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')"
[[ "$tool" =~ ^(Edit|Write|MultiEdit)$ ]] || exit 0

path="$(echo "$input" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')"
[[ -n "$path" ]] || exit 0

cd "$(git rev-parse --show-toplevel)"
if [[ -f .pre-commit-config.yaml ]]; then
  pre-commit run --files "$path" || {
    echo "pre-commit failed for $path" >&2
    exit 1
  }
fi
exit 0
