#!/usr/bin/env bash
#
# compute-signature.sh — extract the delegated signer SHA-256 from an Android APK.
#
# Usage: bash scripts/compute-signature.sh <path-to-apk>
#
# Outputs the SHA-256 digest (one line, lowercase hex) used in
# Compatibility.signatures. The delegated signer is the certificate the
# Play Store uses to sign the APK delivered to users — NOT the upload cert
# you signed with before upload, and NOT the v2/v3 signing scheme cert.
#
# Requires: apksigner (from Android SDK build-tools/<version>/apksigner).
# If apksigner is on PATH, this script works. Otherwise, supply a path via
# $APKSIGNER_BIN or set $ANDROID_HOME so it can be located.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-apk>" >&2
    echo "Outputs the Play-delegated signer SHA-256 to stdout." >&2
    exit 2
fi

APK="$1"

if [ ! -f "$APK" ]; then
    echo "::error::APK not found: $APK" >&2
    exit 1
fi

# Locate apksigner.
APKSIGNER="${APKSIGNER_BIN:-}"
if [ -z "$APKSIGNER" ]; then
    if command -v apksigner >/dev/null 2>&1; then
        APKSIGNER="$(command -v apksigner)"
    elif [ -n "${ANDROID_HOME:-}" ] && [ -d "${ANDROID_HOME}/build-tools" ]; then
        # Pick the highest-versioned build-tools/apksigner.
        APKSIGNER="$(find "${ANDROID_HOME}/build-tools" -name apksigner -type f 2>/dev/null | sort -V | tail -1)"
    fi
fi

if [ -z "$APKSIGNER" ] || [ ! -x "$APKSIGNER" ]; then
    echo "::error::apksigner not found." >&2
    echo "Install the Android SDK build-tools and ensure apksigner is on PATH," >&2
    echo "or set APKSIGNER_BIN to its absolute path." >&2
    exit 1
fi

# Print the certificate chain. apksigner prints blocks like:
#   Signer #1 certificate DN: CN=...
#   Signer #1 certificate SHA-256 digest: <hex>
#   Signer #1 certificate SHA-1 digest: <hex>
# We want the SHA-256 digest under Signer #1 (the delegated signer).
SHA256="$(
    "$APKSIGNER" verify --print-certs "$APK" 2>/dev/null \
        | awk '
            /Signer #1 certificate DN/ { in_signer = 1; next }
            /Signer #2/ { in_signer = 0 }
            in_signer && /SHA-256 digest:/ { print $NF; exit }
        '
)"

if [ -z "$SHA256" ]; then
    echo "::error::Could not parse SHA-256 digest for Signer #1." >&2
    echo "Run '$APKSIGNER verify --print-certs \"$APK\"' manually to inspect." >&2
    exit 1
fi

# Lowercase + strip whitespace.
echo "$SHA256" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]'
