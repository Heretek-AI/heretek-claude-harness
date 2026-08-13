#!/usr/bin/env bash
# PreToolUse hook: refuse destructive Bash commands.
set -euo pipefail

cmd="$(cat)"
tool="$(echo "$cmd" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')"
if [[ "$tool" != "Bash" ]]; then
  exit 0
fi
bcmd="$(echo "$cmd" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"

for pat in 'rm -rf' 'git push --force' 'git reset --hard' 'git push -f' ':(){:|:&};:'; do
  if [[ "$bcmd" == *"$pat"* ]]; then
    echo "BLOCKED: destructive pattern '$pat' in command: $bcmd" >&2
    exit 2
  fi
done
exit 0
