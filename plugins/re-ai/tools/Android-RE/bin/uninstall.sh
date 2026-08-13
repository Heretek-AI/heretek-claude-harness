#!/usr/bin/env bash
# bin/uninstall.sh — remove Android-RE skill symlinks and Python/Node packages.
#
# Modes:
#   --skills    Remove only the symlinks from INSTALL_DIR (default).
#   --packages  Remove the uv-managed Python packages and the bridge pnpm store.
#   --all       Both --skills and --packages.
#
# Does NOT touch ~/.android-re/triage.db or vendored tools in ./vendor/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MODE="skills"
if [[ $# -gt 0 ]]; then
    case "$1" in
        --skills)   MODE="skills" ;;
        --packages) MODE="packages" ;;
        --all)      MODE="all" ;;
        -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
fi

INSTALL_DIR="${INSTALL_DIR:-${HOME}/.claude/skills}"

log()  { printf '\033[1;34m[uninstall]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[uninstall]\033[0m %s\n' "$*" >&2; }

remove_skills() {
    log "Removing skill symlinks from ${INSTALL_DIR}/…"
    local n=0
    for skill_dir in "${REPO_ROOT}"/skills/*/; do
        [[ ! -d "${skill_dir}" ]] && continue
        local skill_name target
        skill_name="$(basename "${skill_dir}")"
        target="${INSTALL_DIR}/${skill_name}"
        if [[ -L "${target}" ]] && [[ "$(readlink "${target}")" == "${skill_dir}" ]]; then
            rm -f "${target}"
            n=$((n + 1))
        fi
    done
    log "Removed ${n} symlinks."
}

remove_packages() {
    log "Removing uv workspace venv…"
    if [[ -d "${REPO_ROOT}/.venv" ]]; then
        rm -rf "${REPO_ROOT}/.venv"
    fi
    log "Removing pnpm node_modules…"
    find "${REPO_ROOT}" -name node_modules -type d -prune -exec rm -rf {} +
    log "Removing uv lockfile (will be regenerated on next install)…"
    rm -f "${REPO_ROOT}/uv.lock"
    warn "Vendored tools in ./vendor/ left intact. Remove with: rm -rf vendor/"
}

case "${MODE}" in
    skills)   remove_skills ;;
    packages) remove_packages ;;
    all)      remove_skills; remove_packages ;;
esac
log "Done."
