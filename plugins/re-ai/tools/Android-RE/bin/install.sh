#!/usr/bin/env bash
# bin/install.sh — install Android-RE on a fresh host.
#
# Modes:
#   --skills-only   Install ONLY the Claude Code skills (no Python or Node
#                   packages, no vendored jars). Use this if you already have
#                   the MCP servers installed via pip/uv/npm.
#   --full          Install everything (default).
#
# Environment:
#   INSTALL_DIR    Where to symlink skills. Default: ~/.claude/skills
#   SKIP_PULL      Set to 1 to skip vendoring jars (faster re-installs).
#   SKIP_PY        Set to 1 to skip Python workspace sync.
#   SKIP_NODE      Set to 1 to skip Node workspace install + bridge build.
#   SKIP_RE_LIBRARY Set to 1 to skip the RE-Library peer MCP install.
#
# Exit codes:
#   0 success
#   1 missing prerequisite
#   2 user abort
#   3 install failure
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ---- Mode parsing ----
MODE="full"
if [[ $# -gt 0 ]]; then
    case "$1" in
        --skills-only) MODE="skills-only" ;;
        --full)        MODE="full" ;;
        -h|--help)
            sed -n '2,18p' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
fi

# ---- Config ----
INSTALL_DIR="${INSTALL_DIR:-${HOME}/.claude/skills}"
# Workspace Python is pinned in pyproject.toml via `requires-python`; uv sync
# enforces it. We only need to make sure `uv` itself is new enough here.
UV_MIN_VERSION="0.5"
NODE_MIN_VERSION="24"
JAVA_MIN_VERSION="17"

# ---- Logging ----
log()  { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; }
ok()   { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }

# ---- Prereq checks ----
check_command() {
    local cmd="$1" min_ver="$2" compare="$3"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        err "Required command not found: ${cmd}"
        return 1
    fi
    if [[ -n "${min_ver}" && -n "${compare}" ]]; then
        local have
        have="$("${cmd}" --version 2>/dev/null | head -1 | grep -oE '[0-9]+(\.[0-9]+){0,2}' | head -1 || true)"
        if [[ -n "${have}" ]] && ! "${compare}" "${have}" "${min_ver}"; then
            err "${cmd} version ${have} is older than required ${min_ver}"
            return 1
        fi
    fi
    return 0
}

# version_gte A B — returns true if A >= B (loose semver-ish).
version_gte() {
    local a="$1" b="$2"
    local IFS=.
    local -a av=($a) bv=($b)
    local n=${#av[@]}
    [[ ${#bv[@]} -gt $n ]] && n=${#bv[@]}
    for ((i=0; i<n; i++)); do
        local ai=${av[i]:-0} bi=${bv[i]:-0}
        (( ai > bi )) && return 0
        (( ai < bi )) && return 1
    done
    return 0
}

log "Android-RE installer (mode: ${MODE})"

if [[ "${MODE}" == "skills-only" ]]; then
    log "Skipping Python / Node / vendor steps (--skills-only)."
else
    check_command uv     "${UV_MIN_VERSION}"      version_gte || {
        err "Install uv ${UV_MIN_VERSION}+: https://astral.sh/uv/install.sh"
        exit 1
    }
    check_command node   "${NODE_MIN_VERSION}"    version_gte || {
        err "Install Node 24+: https://nodejs.org/"
        exit 1
    }
    check_command pnpm   "10"                    version_gte || {
        err "Install pnpm 10+: npm install -g pnpm"
        exit 1
    }
    check_command java   "${JAVA_MIN_VERSION}"   version_gte || {
        err "Install Java 17+: apt install default-jdk / brew install openjdk@17"
        exit 1
    }
fi

# ---- Step 1: Python workspace ----
if [[ "${MODE}" == "full" && -z "${SKIP_PY:-}" ]]; then
    log "Syncing Python workspace (uv sync --all-packages)…"
    if ! uv sync --all-packages; then
        err "uv sync failed. See output above."
        exit 3
    fi
    ok "Python workspace synced."
fi

# ---- Step 2: Node workspace + bridge build ----
if [[ "${MODE}" == "full" && -z "${SKIP_NODE:-}" ]]; then
    log "Installing Node workspace (pnpm install)…"
    if ! pnpm install --frozen-lockfile=false; then
        warn "pnpm install failed (no lockfile yet?). Retrying with auto-lockfile…"
        pnpm install
    fi
    log "Building the TypeScript bridge (pnpm build)…"
    pnpm -r --filter='./mcp_bridge' build || {
        err "Bridge build failed. See output above."
        exit 3
    }
    ok "Node workspace + bridge ready."
fi

# ---- Step 3: Vendor binaries ----
if [[ "${MODE}" == "full" && -z "${SKIP_PULL:-}" ]]; then
    log "Vendoring tools (bin/pull-tools.sh)…"
    if ! "${SCRIPT_DIR}/pull-tools.sh"; then
        warn "pull-tools.sh failed. Continuing without vendored jars; you'll "
        warn "need them for decompile_class / get_smali (Phase 2) and "
        warn "frida-based dynamic analysis (Phase 3)."
    fi
fi

# ---- Step 4: Skill symlinks ----
log "Installing skills into ${INSTALL_DIR}/…"
mkdir -p "${INSTALL_DIR}"
SKILL_COUNT=0
SKILL_FAIL=0
for skill_dir in "${REPO_ROOT}"/skills/*/; do
    [[ ! -d "${skill_dir}" ]] && continue
    skill_name="$(basename "${skill_dir}")"
    target="${INSTALL_DIR}/${skill_name}"
    if [[ -L "${target}" ]]; then
        # Existing symlink — repoint to the current repo path.
        rm -f "${target}"
    elif [[ -e "${target}" ]]; then
        warn "Refusing to clobber non-symlink at ${target}; skipping ${skill_name}."
        SKILL_FAIL=$((SKILL_FAIL + 1))
        continue
    fi
    ln -s "${skill_dir}" "${target}"
    SKILL_COUNT=$((SKILL_COUNT + 1))
done
ok "Installed ${SKILL_COUNT} skills into ${INSTALL_DIR}/"
if (( SKILL_FAIL > 0 )); then
    warn "${SKILL_FAIL} skills skipped (existing non-symlink entries)."
fi

# ---- Step 5: Friendly next steps ----
# ---- Step 5.5: RE-Library peer MCP (opt-in) ----
if [[ "${MODE}" == "full" && -z "${SKIP_RE_LIBRARY:-}" ]]; then
    log "Installing RE-Library peer MCP (re-library-mcp) — set SKIP_RE_LIBRARY=1 to skip…"
    if command -v re-library-mcp >/dev/null 2>&1; then
        log "re-library-mcp already on PATH — skipping."
    elif uv tool install re-library-mcp 2>/dev/null; then
        ok "re-library-mcp installed."
    else
        warn "re-library-mcp install failed; the .mcp.json entry uses 'uv tool run --from re-library-mcp …' as a fallback, so the MCP client can still launch it on first use."
    fi
fi

# ---- Step 6: Friendly next steps ----
cat <<EOF

\033[1;32m✓ Android-RE installed.\033[0m

Next steps:
  1. Run \033[1m./bin/doctor.sh\033[0m to verify the toolchain.
  2. To register the static MCP server with Claude Code:
     \033[1mclaude mcp add android-re-static -- uv run --package android-re-mcp-static python -m android_re_mcp_static\033[0m
  3. Open Claude Code and try a skill:
     \033[1mclaude\033[0m
     > /android-re-static-triage
     > /path/to/app.apk

(Optional) 4. Install the RE-Library peer MCP for generic RE background:
     \033[1mjust install-re-library\033[0m
     Then restart Claude Code and try:
     > mcp__re-library__search_re("apk structure", max_results=3)
EOF
