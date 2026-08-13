#!/usr/bin/env bash
# RE-AI agent-space installer
#
# Clones all per-MCP servers at their pinned versions (from versions.lock)
# into servers/<repo-name>/, then installs the agent-space skill symlinks.
#
# Usage:
#   ./install.sh           # clone all servers + link skills
#   ./install.sh --update  # pull latest pinned versions (re-clone at tags)
#   ./install.sh --clean   # remove all cloned servers
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSIONS_FILE="$SCRIPT_DIR/versions.lock"
SERVERS_DIR="$SCRIPT_DIR/servers"
SKILLS_DIR="$SCRIPT_DIR/skills"

# --- Parse args ---
ACTION="${1:-install}"

# --- Helpers ---
log()  { printf '\033[1;34m[re-ai]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[re-ai]\033[0m %s\n' "$*" >&2; }
ok()   { printf '\033[1;32m[re-ai]\033[0m %s\n' "$*"; }

# --- Clean mode ---
if [[ "$ACTION" == "--clean" ]]; then
  log "Removing $SERVERS_DIR/"
  rm -rf "$SERVERS_DIR"
  ok "Clean complete."
  exit 0
fi

# --- Parse versions.lock ---
declare -A PINS=()
while IFS= read -r line; do
  # Skip comments and blank lines
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  repo=$(echo "$line" | awk '{print $1}')
  tag=$(echo "$line" | awk '{print $2}')
  PINS["$repo"]="$tag"
done < "$VERSIONS_FILE"

log "Found ${#PINS[@]} server pins in versions.lock"

# --- Clone or update ---
mkdir -p "$SERVERS_DIR"

for repo in "${!PINS[@]}"; do
  tag="${PINS[$repo]}"
  target="$SERVERS_DIR/$repo"

  if [[ "$ACTION" == "--update" && -d "$target/.git" ]]; then
    log "Updating $repo → $tag"
    cd "$target"
    git fetch origin --tags 2>/dev/null
    git checkout "$tag" 2>/dev/null
    cd "$SCRIPT_DIR"
  elif [[ ! -d "$target/.git" ]]; then
    log "Cloning Heretek-RE/$repo@$tag"
    git clone --depth 1 --branch "$tag" \
      "https://github.com/Heretek-RE/$repo.git" "$target" 2>/dev/null || {
        err "Failed to clone $repo@$tag — skipping"
        continue
      }
  fi
done

# --- Link skills ---
if [[ -d "$SKILLS_DIR" ]]; then
  mkdir -p "$SCRIPT_DIR/.claude/skills" 2>/dev/null || true
  for skill in "$SKILLS_DIR"/*/; do
    skill_name=$(basename "$skill")
    target="$SCRIPT_DIR/.claude/skills/$skill_name"
    if [[ ! -e "$target" ]]; then
      ln -s "$skill" "$target" 2>/dev/null || true
      log "Linked skill: $skill_name"
    fi
  done
fi

ok "Install complete. ${#PINS[@]} servers cloned to servers/."
echo
echo "Each server runs as: uv --directory servers/<name> run <name>"
echo "Or register in your own .mcp.json with the snippet from each server's README."
