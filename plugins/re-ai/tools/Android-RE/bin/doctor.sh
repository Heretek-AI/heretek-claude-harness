#!/usr/bin/env bash
# bin/doctor.sh — verify the Android-RE toolchain.
#
# Checks, in order:
#   1. OS and architecture
#   2. Required commands: uv, node, pnpm, java, adb
#   3. Python imports: androguard, lief, mcp, android_re_core
#   4. Node imports: @modelcontextprotocol/sdk
#   5. ADB devices and (optional) frida-server version on device
#   6. Vendored binaries (jadx, apktool, uber-apk-signer, frida-server)
#   7. Skill symlinks
#
# Exit codes:
#   0  all required checks green
#   1  one or more required checks failed
#   2  warning (recommended but not required)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ---- Styling ----
if [[ -t 1 ]]; then
    BOLD='\033[1m'; RED='\033[31m'; GRN='\033[32m'; YLW='\033[33m'; RST='\033[0m'
else
    BOLD=''; RED=''; GRN=''; YLW=''; RST=''
fi
ok()   { printf "${GRN}✓${RST} %s\n" "$*"; }
fail() { printf "${RED}✗${RST} %s\n" "$*"; FAILED=1; }
warn() { printf "${YLW}!${RST} %s\n" "$*"; }
section() { printf "\n${BOLD}== %s ==${RST}\n" "$*"; }
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

FAILED=0

section "1. System"
printf "OS: %s\nArch: %s\n" "$(uname -s)" "$(uname -m)"

section "2. Required commands"
for spec in "uv:0.5" "node:24" "pnpm:10" "java:17"; do
    cmd="${spec%%:*}"; min="${spec##*:}"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        fail "$cmd not found"
        continue
    fi
    have="$("$cmd" --version 2>/dev/null | head -1 | grep -oE '[0-9]+(\.[0-9]+){0,2}' | head -1 || true)"
    if [[ -z "$have" ]]; then
        warn "$cmd present, version not parseable"
    elif version_gte "$have" "$min"; then
        ok "$cmd $have >= $min"
    else
        fail "$cmd $have < $min"
    fi
done

if command -v adb >/dev/null 2>&1; then
    ok "adb $(adb version | head -2 | tail -1 | awk '{print $2}')"
else
    fail "adb not found (install Android Platform Tools)"
fi

section "3. Python imports"
if command -v uv >/dev/null 2>&1; then
    # Use the workspace venv if it exists, otherwise uv run resolves the
    # workspace's environment.
    for mod in "androguard" "lief" "mcp" "android_re_core" "android_re_mcp_static"; do
        if uv run --no-sync python -c "import $mod" >/dev/null 2>&1; then
            ok "python: import $mod"
        elif uv run python -c "import $mod" >/dev/null 2>&1; then
            ok "python: import $mod (via uv run --no-sync fallback)"
        else
            fail "python: import $mod (run ./bin/install.sh)"
        fi
    done
else
    fail "uv missing — cannot check Python imports"
fi

section "4. Node imports"
if [[ -d "${REPO_ROOT}/mcp_bridge/node_modules" ]]; then
    if [[ -d "${REPO_ROOT}/mcp_bridge/node_modules/@modelcontextprotocol" ]]; then
        ok "node: @modelcontextprotocol/sdk present"
    else
        fail "node: @modelcontextprotocol/sdk missing (run pnpm install)"
    fi
else
    fail "node: node_modules missing (run pnpm install)"
fi

section "5. ADB devices"
if command -v adb >/dev/null 2>&1; then
    if adb get-state >/dev/null 2>&1; then
        devices="$(adb devices | tail -n +2 | grep -E 'device$' || true)"
        if [[ -n "$devices" ]]; then
            ok "$(echo "$devices" | wc -l) device(s) connected:"
            echo "$devices" | sed 's/^/    /'
        else
            warn "no devices connected (Phase 3+ requires one)"
        fi
    else
        warn "adb server not running (start it with 'adb start-server')"
    fi
fi

section "6. Vendored binaries"
for tool in "vendor/jadx/${ANDROID_RE_VENDOR_VERSION:-0.1.0}/bin/jadx" \
            "vendor/apktool/${ANDROID_RE_VENDOR_VERSION:-0.1.0}/apktool.jar" \
            "vendor/uber-apk-signer/${ANDROID_RE_VENDOR_VERSION:-0.1.0}/uber-apk-signer.jar" \
            "vendor/frida-server/${ANDROID_RE_VENDOR_VERSION:-0.1.0}/frida-server-arm64"; do
    if [[ -e "${REPO_ROOT}/${tool}" ]]; then
        ok "${tool}"
    else
        warn "${tool} (run ./bin/pull-tools.sh)"
    fi
done

section "7. Skill symlinks"
INSTALL_DIR="${INSTALL_DIR:-${HOME}/.claude/skills}"
if [[ -d "${INSTALL_DIR}" ]]; then
    n=0; m=0
    for skill_dir in "${REPO_ROOT}"/skills/*/; do
        [[ ! -d "${skill_dir}" ]] && continue
        skill_name="$(basename "${skill_dir}")"
        target="${INSTALL_DIR}/${skill_name}"
        if [[ -L "${target}" ]]; then
            n=$((n + 1))
        else
            m=$((m + 1))
        fi
    done
    if (( n > 0 )); then ok "$n skills symlinked into $INSTALL_DIR"; fi
    if (( m > 0 )); then warn "$m skills NOT symlinked (run ./bin/install.sh)"; fi
else
    warn "${INSTALL_DIR} does not exist (run ./bin/install.sh)"
fi

section "Summary"
if (( FAILED == 0 )); then
    printf "${GRN}All required checks passed.${RST}\n"
    exit 0
else
    printf "${RED}${FAILED} required check(s) failed.${RST}\n"
    exit 1
fi
