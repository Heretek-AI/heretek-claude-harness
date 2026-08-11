#!/usr/bin/env bash
set -euo pipefail
mkdir -p src
cat > src/app.py <<'EOF'
import os

def main():
    return os.path.join("a", "b")
EOF
git init -q -b main
git add .
git -c user.email=t@t -c user.name=t commit -q -m init
