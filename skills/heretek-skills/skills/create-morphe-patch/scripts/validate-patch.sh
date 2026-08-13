#!/usr/bin/env bash
#
# validate-patch.sh — build the patches bundle and check that a patch
#                    substring is present in the generated patches-list.json.
#
# Usage: bash scripts/validate-patch.sh "<patch-name-substring>"
#
# Exit 0 if found, exit 1 if not, exit 2 on misuse.
#
# Requires: ./gradlew on PATH (or run from the bundle root), jq for JSON parsing.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <patch-name-substring>" >&2
    echo "Builds the bundle and checks for <substring> in patches-list.json." >&2
    exit 2
fi

PATCH_SUBSTRING="$1"

if ! command -v jq >/dev/null 2>&1; then
    echo "::error::jq is required. Install via your package manager." >&2
    exit 1
fi

if [ ! -x "./gradlew" ]; then
    echo "::error::./gradlew not found. Run this from the bundle root (e.g., morphe-patches/)." >&2
    exit 1
fi

echo "==> Building :patches and generating patches-list.json"
./gradlew :patches:buildAndroid :patches:generatePatchesList --quiet

if [ ! -f "../patches-list.json" ] && [ ! -f "patches-list.json" ]; then
    echo "::error::patches-list.json not produced. Build may have failed." >&2
    exit 1
fi

LIST_FILE="patches-list.json"
[ -f "../patches-list.json" ] && LIST_FILE="../patches-list.json"

echo "==> Checking for \"${PATCH_SUBSTRING}\" in ${LIST_FILE}"
if jq -e --arg s "${PATCH_SUBSTRING}" '.patches[]? | select(.name | test($s; "i"))' "${LIST_FILE}" >/dev/null; then
    echo "✓ Found: $(jq -r --arg s "${PATCH_SUBSTRING}" '.patches[] | select(.name | test($s; "i")) | .name' "${LIST_FILE}")"
    exit 0
else
    echo "::error::Patch containing \"${PATCH_SUBSTRING}\" not found in ${LIST_FILE}." >&2
    echo "Available patches:" >&2
    jq -r '.patches[]? | "  - " + .name' "${LIST_FILE}" >&2 || true
    exit 1
fi
