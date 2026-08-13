#!/usr/bin/env bash
#
# First-time deployment simulation + frontend<->backend communication test.
#
# Reproduces exactly what a new user does on a clean machine:
#   1. cp .env.example .env  (if no .env exists yet)
#   2. set a known HERETEK_API_KEY (and a placeholder OPENAI_API_KEY)
#   3. docker compose up -d --build   (all 6 containers)
#   4. wait for the api + dashboard containers to report healthy
#   5. run scripts/verify_integration.py to assert the dashboard (npm/nginx)
#      and the backend (docker/python) actually communicate
#   6. (optionally) tear the stack down
#
# This is transport-only: it does NOT require a working LLM, so a placeholder
# OPENAI_API_KEY is fine.
#
# Usage:
#   scripts/first_time_deploy_test.sh            # build, up, verify, leave running
#   scripts/first_time_deploy_test.sh --down     # ...and docker compose down at the end
#   KEEP_ENV=1 scripts/first_time_deploy_test.sh # do not overwrite an existing .env
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEARDOWN=0
[[ "${1:-}" == "--down" ]] && TEARDOWN=1

API_KEY="${HERETEK_API_KEY:-htsk_first_time_deploy_test_key}"
API_BASE="${API_BASE:-http://localhost:8000}"
DASHBOARD_BASE="${DASHBOARD_BASE:-http://localhost:3000}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. .env bootstrap (the documented first-time step)
# ---------------------------------------------------------------------------
if [[ -f .env && "${KEEP_ENV:-0}" == "1" ]]; then
    log "Reusing existing .env (KEEP_ENV=1)"
else
    log "Bootstrapping .env from .env.example"
    cp .env.example .env
    # Configure a known API key and a placeholder LLM key (LLM not needed here)
    sed -i "s|^HERETEK_API_KEY=.*|HERETEK_API_KEY=${API_KEY}|" .env
    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=sk-placeholder-not-used-in-comm-test|" .env
    # Allow the dashboard origin through CORS for the transport test
    sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=*|" .env
fi

# ---------------------------------------------------------------------------
# 2. Build + start the full stack
# ---------------------------------------------------------------------------
log "docker compose up -d --build (all services)"
docker compose up -d --build

# ---------------------------------------------------------------------------
# 3. Wait for api + dashboard to become healthy / reachable
# ---------------------------------------------------------------------------
wait_for() {
    local url="$1" name="$2" deadline=$((SECONDS + HEALTH_TIMEOUT))
    log "Waiting for $name at $url (timeout ${HEALTH_TIMEOUT}s)"
    until curl -sf -o /dev/null "$url"; do
        if (( SECONDS >= deadline )); then
            echo "ERROR: $name did not become reachable in ${HEALTH_TIMEOUT}s" >&2
            docker compose ps
            docker compose logs --tail=50 api || true
            return 1
        fi
        sleep 3
    done
    echo "  $name is reachable."
}

wait_for "${API_BASE}/api/health" "backend API"
wait_for "${DASHBOARD_BASE}/" "dashboard"

# ---------------------------------------------------------------------------
# 4. Run the communication verifier
# ---------------------------------------------------------------------------
log "Verifying frontend <-> backend communication"
set +e
python3 scripts/verify_integration.py \
    --api-base "$API_BASE" \
    --dashboard-base "$DASHBOARD_BASE" \
    --api-key "$API_KEY"
RESULT=$?
set -e

# ---------------------------------------------------------------------------
# 5. Optional teardown
# ---------------------------------------------------------------------------
if [[ "$TEARDOWN" == "1" ]]; then
    log "Tearing down (docker compose down)"
    docker compose down
fi

if [[ "$RESULT" == "0" ]]; then
    log "RESULT: PASS — frontend and backend communicate correctly"
else
    log "RESULT: FAIL — see check output above"
fi
exit "$RESULT"
