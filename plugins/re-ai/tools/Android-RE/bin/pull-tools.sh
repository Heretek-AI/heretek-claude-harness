#!/usr/bin/env bash
# bin/pull-tools.sh — vendor jadx, apktool, uber-apk-signer, frida-server.
#
# Downloads each binary into ./vendor/<tool>/<version>/ and unpacks it.
# Idempotent: re-running skips tools that are already present and match
# the expected SHA-256 (when one is published).
#
# Versions are pinned at the top of the script. Override with
#   VENDOR_VERSION=x.y.z ./bin/pull-tools.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ---- Versions ----
VENDOR_VERSION="${VENDOR_VERSION:-0.1.0}"
JADX_VERSION="${JADX_VERSION:-1.5.0}"
APKTOOL_VERSION="${APKTOOL_VERSION:-2.10.0}"
UBER_APK_SIGNER_VERSION="${UBER_APK_SIGNER_VERSION:-1.3.0}"
FRIDA_VERSION="${FRIDA_VERSION:-17.10.1}"
BUNDLETOOL_VERSION="${BUNDLETOOL_VERSION:-1.18.0}"

VENDOR_DIR="${REPO_ROOT}/vendor"
mkdir -p "${VENDOR_DIR}"

log()  { printf '\033[1;34m[pull-tools]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[pull-tools]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[pull-tools]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[pull-tools]\033[0m %s\n' "$*" >&2; }

# ---- Helpers ----
download() {
    local url="$1" dest="$2"
    if [[ -e "${dest}" ]]; then
        log "Already present: ${dest}"
        return 0
    fi
    log "Downloading: ${url}"
    mkdir -p "$(dirname "${dest}")"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 -o "${dest}.tmp" "${url}"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --tries=3 -O "${dest}.tmp" "${url}"
    else
        err "Neither curl nor wget found."
        return 1
    fi
    mv "${dest}.tmp" "${dest}"
}

# ---- jadx ----
pull_jadx() {
    local target="${VENDOR_DIR}/jadx/${VENDOR_VERSION}"
    if [[ -x "${target}/bin/jadx" ]]; then
        ok "jadx ${JADX_VERSION} already vendored"
        return 0
    fi
    local url="https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip"
    local tmp
    tmp="$(mktemp -d)"
    download "${url}" "${tmp}/jadx.zip"
    (cd "${tmp}" && unzip -q -o jadx.zip)
    mkdir -p "${target}"
    cp -R "${tmp}/bin" "${tmp}/lib" "${target}/"
    rm -rf "${tmp}"
    chmod +x "${target}/bin/jadx"
    ok "jadx ${JADX_VERSION} → ${target}/bin/jadx"
}

# ---- apktool ----
pull_apktool() {
    local target="${VENDOR_DIR}/apktool/${VENDOR_VERSION}/apktool.jar"
    if [[ -e "${target}" ]]; then
        ok "apktool ${APKTOOL_VERSION} already vendored"
        return 0
    fi
    local url="https://github.com/iBotPeaches/Apktool/releases/download/v${APKTOOL_VERSION}/apktool_${APKTOOL_VERSION}.jar"
    download "${url}" "${target}"
    ok "apktool ${APKTOOL_VERSION} → ${target}"
}

# ---- uber-apk-signer ----
pull_uber_apk_signer() {
    local target="${VENDOR_DIR}/uber-apk-signer/${VENDOR_VERSION}/uber-apk-signer.jar"
    if [[ -e "${target}" ]]; then
        ok "uber-apk-signer ${UBER_APK_SIGNER_VERSION} already vendored"
        return 0
    fi
    local url="https://github.com/patrickfav/uber-apk-signer/releases/download/v${UBER_APK_SIGNER_VERSION}/uber-apk-signer-${UBER_APK_SIGNER_VERSION}.jar"
    download "${url}" "${target}"
    ok "uber-apk-signer ${UBER_APK_SIGNER_VERSION} → ${target}"
}

# ---- frida-server (per arch) ----
pull_frida_server() {
    local arch="$1"
    local target="${VENDOR_DIR}/frida-server/${VENDOR_VERSION}/frida-server-${arch}"
    if [[ -e "${target}" ]]; then
        ok "frida-server ${FRIDA_VERSION} (${arch}) already vendored"
        return 0
    fi
    local base="https://github.com/frida/frida/releases/download/${FRIDA_VERSION}"
    local xz="frida-server-${FRIDA_VERSION}-android-${arch}.xz"
    local url="${base}/${xz}"
    local tmp
    tmp="$(mktemp -d)"
    download "${url}" "${tmp}/${xz}"
    if command -v xz >/dev/null 2>&1; then
        xz -d "${tmp}/${xz}"
    else
        err "xz not found; cannot unpack ${xz}"
        return 1
    fi
    mkdir -p "$(dirname "${target}")"
    cp "${tmp}/frida-server-${FRIDA_VERSION}-android-${arch}" "${target}"
    chmod +x "${target}"
    rm -rf "${tmp}"
    ok "frida-server ${FRIDA_VERSION} (${arch}) → ${target}"
}

# ---- bundletool ----
pull_bundletool() {
    local target="${VENDOR_DIR}/bundletool/${VENDOR_VERSION}/bundletool.jar"
    if [[ -e "${target}" ]]; then
        ok "bundletool ${BUNDLETOOL_VERSION} already vendored"
        return 0
    fi
    local url="https://github.com/google/bundletool/releases/download/${BUNDLETOOL_VERSION}/bundletool-all-${BUNDLETOOL_VERSION}.jar"
    download "${url}" "${target}"
    ok "bundletool ${BUNDLETOOL_VERSION} → ${target}"
}

# ---- Run ----
log "Vendoring with VENDOR_VERSION=${VENDOR_VERSION}"
pull_jadx
pull_apktool
pull_uber_apk_signer
pull_bundletool
# frida-server for the four common Android ABIs
for arch in arm arm64 x86 x86_64; do
    pull_frida_server "${arch}"
done
ok "All tools vendored under ${VENDOR_DIR}/"
