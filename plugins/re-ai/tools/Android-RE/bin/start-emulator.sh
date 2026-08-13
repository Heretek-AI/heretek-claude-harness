#!/usr/bin/env bash
# bin/start-emulator.sh — start an Android emulator for testing.
#
# Usage:
#   ./bin/start-emulator.sh                       # start a default AVD
#   ./bin/start-emulator.sh --avd Pixel_API_33    # specific AVD
#   ./bin/start-emulator.sh --headless            # no GUI (for CI)
#   ./bin/start-emulator.sh --wipe-data           # reset user data first
set -euo pipefail

AVD=""
HEADLESS=0
WIPE=0
for arg in "$@"; do
    case "${arg}" in
        --avd) AVD="$2"; shift 2 ;;
        --headless) HEADLESS=1; shift ;;
        --wipe-data) WIPE=1; shift ;;
        -h|--help)
            sed -n '2,8p' "${BASH_SOURCE[0]}"
            exit 0
            ;;
    esac
done

if ! command -v emulator >/dev/null 2>&1; then
    echo "emulator binary not found. Install via Android Studio's SDK Manager or" >&2
    echo "set ANDROID_HOME and add \$ANDROID_HOME/emulator to PATH." >&2
    exit 1
fi

if [[ -z "${AVD}" ]]; then
    AVD_LIST="$(emulator -list-avds 2>/dev/null | head -1 || true)"
    if [[ -z "${AVD_LIST}" ]]; then
        echo "No AVDs found. Create one with:" >&2
        echo "  avdmanager create avd -n test33 -k 'system-images;android-33;google_apis;x86_64'" >&2
        exit 1
    fi
    AVD="${AVD_LIST}"
    echo "Using first available AVD: ${AVD}"
fi

ARGS=(-avd "${AVD}" -no-snapshot-load -no-audio -no-boot-anim)
if (( HEADLESS )); then
    ARGS+=(-no-window -gpu swiftshader_indirect)
fi
if (( WIPE )); then
    ARGS+=(-wipe-data)
fi

echo "Starting emulator: ${ARGS[*]}"
exec emulator "${ARGS[@]}"
