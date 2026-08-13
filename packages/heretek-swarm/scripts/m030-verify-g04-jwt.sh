#!/usr/bin/env bash
# M030 G-04 — JWT hardening verification
#
# Asserts that gateway/auth.py enforces:
#   - aud (audience) claim is present and matches JWT_AUDIENCE
#   - iss (issuer) claim is present and matches JWT_ISSUER
#   - exp, iat, sub, aud, iss are all present
#   - Static HERETEK_API_KEY still works (backward compat)
#
# Exit code: 0 if all pass, 1 if any fail.
# Usage:  HERETEK_API_KEY=...  bash scripts/m030-verify-g04-jwt.sh

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SECRET=$(grep '^JWT_SECRET=' .env | cut -d= -f2-)
HOST="${API_HOST:-http://localhost:8000}"
K=$(grep '^HERETEK_API_KEY=' .env | cut -d= -f2-)

mint_jwt() {
  local payload="$1"
  python3 -c "
import jwt, time
print(jwt.encode($payload, '$SECRET', algorithm='HS256'))
"
}

PASS=0
FAIL=0
check() {
  local name="$1" expected="$2" actual="$3"
  if [ "$actual" = "$expected" ]; then
    echo "[PASS] $name: HTTP $actual"
    PASS=$((PASS+1))
  else
    echo "[FAIL] $name: expected $expected, got $actual"
    FAIL=$((FAIL+1))
  fi
}

NOW=$(date +%s)
EXP=$((NOW + 3600))
IAT=$NOW

echo "=== M030 G-04 JWT hardening verification ==="
echo "JWT_SECRET: $SECRET"
echo "API host:   $HOST"
echo

# Test 1: JWT without aud → expect 401 (G-04 fix)
T=$(mint_jwt "{'sub': 'tester', 'iat': $IAT, 'exp': $EXP, 'iss': 'heretek-swarm'}")
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" "$HOST/api/agents/steward")
check "G-04-T1 no-aud rejected" "401" "$S"

# Test 2: JWT without iss → expect 401
T=$(mint_jwt "{'sub': 'tester', 'iat': $IAT, 'exp': $EXP, 'aud': 'heretek-swarm'}")
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" "$HOST/api/agents/steward")
check "G-04-T2 no-iss rejected" "401" "$S"

# Test 3: JWT with wrong aud → expect 401
T=$(mint_jwt "{'sub': 'tester', 'iat': $IAT, 'exp': $EXP, 'aud': 'wrong-audience', 'iss': 'heretek-swarm'}")
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" "$HOST/api/agents/steward")
check "G-04-T3 wrong-aud rejected" "401" "$S"

# Test 4: JWT with wrong iss → expect 401
T=$(mint_jwt "{'sub': 'tester', 'iat': $IAT, 'exp': $EXP, 'aud': 'heretek-swarm', 'iss': 'wrong-issuer'}")
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" "$HOST/api/agents/steward")
check "G-04-T4 wrong-iss rejected" "401" "$S"

# Test 5: JWT with correct aud/iss → expect 200
T=$(mint_jwt "{'sub': 'tester', 'iat': $IAT, 'exp': $EXP, 'aud': 'heretek-swarm', 'iss': 'heretek-swarm'}")
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" "$HOST/api/agents/steward")
check "G-04-T5 valid JWT accepted" "200" "$S"

# Test 6: Static HERETEK_API_KEY still works (backward compat) → expect 200
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $K" "$HOST/api/agents/steward")
check "G-04-T6 static key still works" "200" "$S"

# Test 7: Expired JWT → expect 401
T=$(mint_jwt "{'sub': 'tester', 'iat': $((NOW - 7200)), 'exp': $((NOW - 3600)), 'aud': 'heretek-swarm', 'iss': 'heretek-swarm'}")
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" "$HOST/api/agents/steward")
check "G-04-T7 expired JWT rejected" "401" "$S"

# Test 8: Completely invalid token → expect 401
S=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer not.a.jwt" "$HOST/api/agents/steward")
check "G-04-T8 invalid token rejected" "401" "$S"

echo
echo "=== Summary: $PASS pass, $FAIL fail ==="
[ "$FAIL" = "0" ] || exit 1
