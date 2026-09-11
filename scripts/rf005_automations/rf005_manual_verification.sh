#!/usr/bin/env bash
# rf005_manual_verification.sh - Automated manual verification for the
# RF-005 Query Post endpoint (GET /rf005/posts/{id}).
#
# Mirrors the "Manual verification (curl)" section of
# rf005_query_post_app/README.md and asserts the exact documented behavior:
#   403 empty body : missing bearer token
#   401 empty body : invalid/expired token
#   404 empty body : post does not exist
#   403 empty body : authenticated user is not the post owner
#   503 {"msg": ...}: a downstream service is unreachable
#   200 {"data": {route, offers}}: owner query, offers sorted by score desc
#                                  (nulls last), each offer with its score
#
# Services are NOT started by this script. Bring them up first (all
# environment variables are overridable):
#
#   USERS_URL    (default http://localhost:8000)   users_app
#   ROUTES_URL   (default http://localhost:8006)   routes_app
#   POSTS_URL    (default http://localhost:8002)   posts_app
#   OFFERS_URL   (default http://localhost:8003)   offers_app
#   SCORES_URL   (default http://localhost:8004)   scores_app
#   RF003_URL    (default http://localhost:8001)   rf003_create_post_app
#   RF005_URL    (default http://localhost:8005)   rf005_query_post_app
#
# The business services run with DB_DRIVER=sqlite (file-backed databases
# under /tmp so the script stays idempotent across runs).
#
# The script is idempotent: it reuses the users created on a previous run
# (a 412 on create is treated as success) and every run creates a fresh
# flight/post/offer pair, so sort-order assertions are never affected by
# stale data.

set -uo pipefail

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
USERS_URL="${USERS_URL:-http://localhost:8000}"
ROUTES_URL="${ROUTES_URL:-http://localhost:8006}"
POSTS_URL="${POSTS_URL:-http://localhost:8002}"
OFFERS_URL="${OFFERS_URL:-http://localhost:8003}"
SCORES_URL="${SCORES_URL:-http://localhost:8004}"
RF003_URL="${RF003_URL:-http://localhost:8001}"
RF005_URL="${RF005_URL:-http://localhost:8005}"
HTTP_TIMEOUT="${HTTP_TIMEOUT:-10}"

# Port of a dead listener used to prove the 503 contract. A temporary
# orchestrator instance is pointed at this port for POSTS_SERVICE_URL.
DEAD_PORT="${DEAD_PORT:-9999}"
RF005_DOWN_URL="http://127.0.0.1:8007"

PASS=0
FAIL=0
TOTAL=0

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
pass_test() {
  PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
  echo "  ✓ PASS: $1"
}

fail_test() {
  FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
  echo "  ✗ FAIL: $1"
}

# get_code <url> [curl args...] -> single request; prints the response
# body followed by the HTTP status code as the LAST line (000 on
# connection failure). Callers use `| tail -1 | tail -c 4` for the code
# (the body may lack a trailing newline, e.g. /ping -> "pong200") and
# `| head -n -1` for the body.
get_code() {
  local body_file code
  body_file=$(mktemp /tmp/rf005_verify_body.XXXXXX)
  code=$(curl -s -o "$body_file" -w "%{http_code}" --max-time "$HTTP_TIMEOUT" "$@" 2>/dev/null) || code="000"
  cat "$body_file"
  echo "$code"
  rm -f "$body_file"
}

# code_of <multi-line output of get_code> -> the 3-char status code.
code_of() {
  # The status code is the final 3 characters of the whole output
  # (body may or may not end with a newline, e.g. /ping -> "pong200").
  printf '%s' "$1" | tail -c 4 | tail -c 3
}

# get_code_body <url> [curl args...] -> single request; prints
# "code<TAB>body".
get_code_body() {
  local url="$1"; shift
  local body_file code
  body_file=$(mktemp /tmp/rf005_verify_body.XXXXXX)
  code=$(curl -s -o "$body_file" -w "%{http_code}" --max-time "$HTTP_TIMEOUT" "$url" "$@" 2>/dev/null) || code="000"
  local body
  body=$(cat "$body_file")
  rm -f "$body_file"
  printf "%s\t%s" "$code" "$body"
}

# assert_status <name> <expected> <url> [curl args...] [empty]
# The trailing `empty` flag (not a curl arg) requires an empty body.
assert_status() {
  local name="$1" expected="$2" url="$3"; shift 3
  local out code body expect_empty="no"
  if [ "${@: -1}" = "empty" ]; then
    expect_empty="yes"
    set -- "${@:1:$#-1}"
  fi
  out=$(get_code_body "$url" "$@")
  code="${out%%$'\t'*}"
  body="${out#*$'\t'}"
  if [ "$code" = "$expected" ]; then
    if [ "$expect_empty" = "yes" ]; then
      if [ -z "$body" ]; then
        pass_test "$name (expected $expected empty body, got $expected)"
      else
        fail_test "$name (expected $expected empty body, body was '$body')"
      fi
    else
      pass_test "$name (expected $expected, got $expected)"
    fi
  else
    fail_test "$name (expected $expected, got $code, body='$body')"
  fi
}

# ------------------------------------------------------------------
# Pre-flight: all services must be reachable
# ------------------------------------------------------------------
echo "=== Pre-flight checks ==="
PING_PATHS=(
  "users|${USERS_URL}/users/ping"
  "routes|${ROUTES_URL}/routes/ping"
  "posts|${POSTS_URL}/posts/ping"
  "offers|${OFFERS_URL}/offers/ping"
  "scores|${SCORES_URL}/scores/ping"
  "rf003|${RF003_URL}/rf003/ping"
  "rf005|${RF005_URL}/rf005/ping"
)

ABORT=0
for entry in "${PING_PATHS[@]}"; do
  svc="${entry%%|*}"
  url="${entry#*|}"
  code=$(code_of "$(get_code "$url")")
  if [ "$code" = "200" ]; then
    echo "  ✓ ${svc} is UP (${url})"
  else
    echo "  ✗ ${svc} is DOWN (${url}) — code=$code"
    ABORT=1
  fi
done
if [ "$ABORT" = "1" ]; then
  echo "  Aborting: start the required services first (see script header)."
  exit 1
fi

# ------------------------------------------------------------------
# Setup: users (idempotent), then a fresh post + offers + scores
# ------------------------------------------------------------------
echo ""
echo "=== Setup: users, post, offers, scores ==="

# --- Users (idempotent: create once, authenticate every run) ---
OWNER_CREATE_CODE=$(code_of "$(get_code -X POST "$USERS_URL/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005owner","password":"Secret123!","email":"rf005owner@example.com","dni":"12345678","fullName":"RF005 Owner","phoneNumber":"3001112233"}')")
if [ "$OWNER_CREATE_CODE" = "201" ] || [ "$OWNER_CREATE_CODE" = "412" ]; then
  pass_test "Owner user present (create returned $OWNER_CREATE_CODE)"
else
  fail_test "Owner user create (expected 201 or 412, got $OWNER_CREATE_CODE)"
fi

STRANGER_CREATE_CODE=$(code_of "$(get_code -X POST "$USERS_URL/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005stranger","password":"Secret123!","email":"rf005stranger@example.com","dni":"87654321","fullName":"RF005 Stranger","phoneNumber":"3009998877"}')")
if [ "$STRANGER_CREATE_CODE" = "201" ] || [ "$STRANGER_CREATE_CODE" = "412" ]; then
  pass_test "Stranger user present (create returned $STRANGER_CREATE_CODE)"
else
  fail_test "Stranger user create (expected 201 or 412, got $STRANGER_CREATE_CODE)"
fi

# NOTE: the Users service stores ONE token per user — every /users/auth
# call invalidates the previous token. So both the token and the user id
# must be read from a SINGLE auth response.
OWNER_AUTH=$(curl -s --max-time "$HTTP_TIMEOUT" -X POST "$USERS_URL/users/auth" \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005owner","password":"Secret123!"}')
OWNER_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$OWNER_AUTH" 2>/dev/null || true)
TOKEN_OWNER=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['token'])" "$OWNER_AUTH" 2>/dev/null || true)
if [ -n "${TOKEN_OWNER:-}" ] && [ -n "${OWNER_ID:-}" ]; then
  pass_test "Obtained owner token (user id $OWNER_ID)"
else
  fail_test "Obtain owner token (could not authenticate rf005owner)"
fi

TOKEN_STRANGER=$(curl -s --max-time "$HTTP_TIMEOUT" -X POST "$USERS_URL/users/auth" \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005stranger","password":"Secret123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null || true)
if [ -n "${TOKEN_STRANGER:-}" ]; then
  pass_test "Obtained stranger token"
else
  fail_test "Obtain stranger token (could not authenticate rf005stranger)"
fi

if [ -z "${TOKEN_OWNER:-}" ] || [ -z "${TOKEN_STRANGER:-}" ]; then
  echo "  Cannot continue without valid tokens. Aborting."
  exit 1
fi

# --- Fresh post via RF-003 (unique flight per run → no 412 duplicates) ---
# RF-003 business rule: now < expireAt <= plannedStartDate, and the
# journey must be in the future. Dates are computed dynamically so the
# script keeps working as time passes.
DATES=$(python3 - <<'PYEOF'
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc).replace(microsecond=0)
expire = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S")
start = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
end = (now + timedelta(days=32)).strftime("%Y-%m-%dT%H:%M:%S")
print(f"{expire} {start} {end}")
PYEOF
)
read -r EXPIRE_AT START_AT END_AT <<< "$DATES"
FLIGHT="PM$(date +%s)"
BODY="{\"flightId\":\"$FLIGHT\",\"expireAt\":\"$EXPIRE_AT\",\"plannedStartDate\":\"$START_AT\",\"plannedEndDate\":\"$END_AT\",\"origin\":{\"airportCode\":\"BOG\",\"country\":\"Colombia\"},\"destiny\":{\"airportCode\":\"MAD\",\"country\":\"Spain\"},\"bagCost\":350}"

POST_CREATE_CODE=$(curl -s -o /tmp/rf005_verify_post.json -w "%{http_code}" \
  --max-time "$HTTP_TIMEOUT" -X POST "$RF003_URL/rf003/posts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN_OWNER" \
  -d "$BODY")
if [ "$POST_CREATE_CODE" = "201" ]; then
  pass_test "Created test post via RF-003 (201)"
else
  fail_test "Create test post via RF-003 (expected 201, got $POST_CREATE_CODE)"
fi

POST_ID=$(python3 -c "import json; print(json.load(open('/tmp/rf005_verify_post.json'))['data']['id'])" 2>/dev/null || true)
if [ -n "${POST_ID:-}" ]; then
  pass_test "Extracted post id: $POST_ID"
else
  fail_test "Extract post id (could not parse RF-003 response: $(cat /tmp/rf005_verify_post.json 2>/dev/null))"
fi

# --- Two offers for the post (directly via the Offers service API) ---
OFFER1_CODE=$(curl -s -o /tmp/rf005_verify_offer1.json -w "%{http_code}" \
  --max-time "$HTTP_TIMEOUT" -X POST "$OFFERS_URL/offers" \
  -H "Content-Type: application/json" \
  -d "{\"postId\":\"$POST_ID\",\"userId\":\"$OWNER_ID\",\"description\":\"Bag 23kg for Madrid trip\",\"size\":\"LARGE\",\"fragile\":false,\"offer\":150}")
OFFER1_ID=$(python3 -c "import json; print(json.load(open('/tmp/rf005_verify_offer1.json'))['id'])" 2>/dev/null || true)
if [ "$OFFER1_CODE" = "201" ] && [ -n "${OFFER1_ID:-}" ]; then
  pass_test "Created offer #1 (201, id $OFFER1_ID)"
else
  fail_test "Create offer #1 (expected 201, got $OFFER1_CODE, body=$(cat /tmp/rf005_verify_offer1.json 2>/dev/null))"
fi

OFFER2_CODE=$(curl -s -o /tmp/rf005_verify_offer2.json -w "%{http_code}" \
  --max-time "$HTTP_TIMEOUT" -X POST "$OFFERS_URL/offers" \
  -H "Content-Type: application/json" \
  -d "{\"postId\":\"$POST_ID\",\"userId\":\"$OWNER_ID\",\"description\":\"Extra checked bag\",\"size\":\"MEDIUM\",\"fragile\":true,\"offer\":200}")
OFFER2_ID=$(python3 -c "import json; print(json.load(open('/tmp/rf005_verify_offer2.json'))['id'])" 2>/dev/null || true)
if [ "$OFFER2_CODE" = "201" ] && [ -n "${OFFER2_ID:-}" ]; then
  pass_test "Created offer #2 (201, id $OFFER2_ID)"
else
  fail_test "Create offer #2 (expected 201, got $OFFER2_CODE, body=$(cat /tmp/rf005_verify_offer2.json 2>/dev/null))"
fi

# --- Scores: offer #1 = 4.8, offer #2 intentionally unscored (null) ---
SCORE1_CODE=$(curl -s -o /tmp/rf005_verify_score1.json -w "%{http_code}" \
  --max-time "$HTTP_TIMEOUT" -X POST "$SCORES_URL/scores" \
  -H "Content-Type: application/json" \
  -d "{\"offerId\":\"$OFFER1_ID\",\"score\":4.8}")
if [ "$SCORE1_CODE" = "201" ] || [ "$SCORE1_CODE" = "200" ]; then
  pass_test "Created score 4.8 for offer #1 ($SCORE1_CODE)"
else
  fail_test "Create score for offer #1 (expected 201, got $SCORE1_CODE, body=$(cat /tmp/rf005_verify_score1.json 2>/dev/null))"
fi

if [ -z "${POST_ID:-}" ] || [ -z "${OFFER1_ID:-}" ] || [ -z "${OFFER2_ID:-}" ]; then
  echo "  Setup incomplete — cannot run the test suite. Aborting."
  exit 1
fi

# ------------------------------------------------------------------
# Test suite
# ------------------------------------------------------------------
echo ""
echo "=== Test Suite: $RF005_URL ==="

# 1. Health check (no auth needed) -> 200
assert_status "T1 Health check" 200 "$RF005_URL/rf005/ping"

# 2. Missing Authorization header -> 403 (empty body)
assert_status "T2 Missing auth header" 403 "$RF005_URL/rf005/posts/$POST_ID" empty

# 3. Invalid token -> 401 (empty body)
assert_status "T3 Invalid token" 401 "$RF005_URL/rf005/posts/$POST_ID" \
  -H "Authorization: Bearer sk_test_rf005_invalid_xyz789" empty

# 4. Whitespace-only token -> 403 (empty body)
assert_status "T4 Whitespace-only token" 403 "$RF005_URL/rf005/posts/$POST_ID" \
  -H "Authorization: Bearer    " empty

# 5. Non-existent post (valid token) -> 404 (empty body)
assert_status "T5 Non-existent post" 404 "$RF005_URL/rf005/posts/00000000-0000-0000-0000-000000000000" \
  -H "Authorization: Bearer $TOKEN_OWNER" empty

# 6. Non-existent post, other valid UUID -> 404 (empty body)
assert_status "T6 Non-existent post (other UUID)" 404 "$RF005_URL/rf005/posts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" \
  -H "Authorization: Bearer $TOKEN_OWNER" empty

# 7. Non-owner access -> 403 (empty body)
assert_status "T7 Non-owner access" 403 "$RF005_URL/rf005/posts/$POST_ID" \
  -H "Authorization: Bearer $TOKEN_STRANGER" empty

# 8. Owner access -> 200 with the full aggregated structure
echo "  -- T8 Owner access: full response validation --"
OWNER_OUT=$(get_code_body "$RF005_URL/rf005/posts/$POST_ID" \
  -H "Authorization: Bearer $TOKEN_OWNER")
OWNER_CODE="${OWNER_OUT%%$'\t'*}"
OWNER_BODY="${OWNER_OUT#*$'\t'}"
if [ "$OWNER_CODE" != "200" ]; then
  fail_test "T8 Owner access (expected 200, got $OWNER_CODE, body='$OWNER_BODY')"
else
  VALIDATION=$(python3 - "$OWNER_BODY" "$OFFER1_ID" "$OFFER2_ID" "$FLIGHT" "$OWNER_ID" <<'PYEOF'
import json, sys
body, offer1, offer2, flight, owner_id = sys.argv[1:6]
try:
    payload = json.loads(body)
except Exception:
    print("FAIL: body is not valid JSON"); sys.exit(0)

errors = []
if set(payload) != {"data"}:
    errors.append(f"top-level keys are {sorted(payload)}, expected ['data']")
data = payload.get("data", {})
if set(data) != {"route", "offers"}:
    errors.append(f"data keys are {sorted(data)}, expected ['route','offers']")

route = data.get("route", {})
for key in ("id", "flightId", "origin", "destiny", "bagCost",
            "plannedStartDate", "plannedEndDate"):
    if key not in route:
        errors.append(f"route missing key '{key}'")
if route.get("flightId") != flight:
    errors.append(f"route.flightId is {route.get('flightId')!r}, expected {flight!r}")
if route.get("bagCost") != 350:
    errors.append(f"route.bagCost is {route.get('bagCost')!r}, expected 350")
if route.get("origin") != {"airportCode": "BOG", "country": "Colombia"}:
    errors.append(f"route.origin is {route.get('origin')!r}")
if route.get("destiny") != {"airportCode": "MAD", "country": "Spain"}:
    errors.append(f"route.destiny is {route.get('destiny')!r}")

offers = data.get("offers")
if not isinstance(offers, list):
    errors.append("data.offers is not a list")
else:
    if len(offers) != 2:
        errors.append(f"expected 2 offers, got {len(offers)}")
    by_id = {o.get("id"): o for o in offers}
    for oid in (offer1, offer2):
        if oid not in by_id:
            errors.append(f"offer {oid} missing from response")
    if offers and offers[0].get("id") != offer1:
        errors.append(f"offers[0] is {offers[0].get('id')!r}, expected scored offer {offer1!r} (score 4.8 must sort first)")
    if len(offers) > 1 and offers[1].get("id") != offer2:
        errors.append(f"offers[1] is {offers[1].get('id')!r}, expected unscored offer {offer2!r} (null score must sort last)")
    for o in offers:
        for key in ("id", "userId", "description", "size", "fragile",
                    "offer", "score", "createdAt"):
            if key not in o:
                errors.append(f"offer {o.get('id')} missing key '{key}'")
        if o.get("userId") != owner_id:
            errors.append(f"offer {o.get('id')} userId is {o.get('userId')!r}, expected owner {owner_id!r}")
    o1 = by_id.get(offer1, {})
    if o1.get("score") != 4.8:
        errors.append(f"offer1 score is {o1.get('score')!r}, expected 4.8")
    o2 = by_id.get(offer2, {})
    if o2.get("score") is not None:
        errors.append(f"offer2 score is {o2.get('score')!r}, expected null")
    if o1.get("offer") != 150.0:
        errors.append(f"offer1 offer amount is {o1.get('offer')!r}, expected 150")
    if o2.get("fragile") is not True:
        errors.append(f"offer2 fragile is {o2.get('fragile')!r}, expected true")

if errors:
    print("FAIL: " + "; ".join(errors))
else:
    print("OK")
PYEOF
)
  if [ "$VALIDATION" = "OK" ]; then
    pass_test "T8 Owner access -> 200 with full aggregated data (route + 2 offers, sorted by score desc, null last)"
  else
    fail_test "T8 Owner access -> 200 but invalid payload: $VALIDATION"
    echo "      Raw body: $OWNER_BODY"
  fi
fi

# 9. Downstream (Posts) service unreachable -> 503 {"msg": ...}
echo "  -- T9 Posts service unreachable: 503 contract --"
DOWN_LOG=/tmp/rf005_verify_down.log
# Clean up any leftover instance from a previous (crashed) run.
pkill -f "entrypoints.api.main:app --host 127.0.0.1 --port 8007" 2>/dev/null || true
sleep 0.5
(
  cd "$(cd "$(dirname "$0")/.." && pwd)/rf005_query_post_app"
  USERS_SERVICE_URL="$USERS_URL" \
  POSTS_SERVICE_URL="http://127.0.0.1:$DEAD_PORT" \
  ROUTES_SERVICE_URL="$ROUTES_URL" \
  OFFERS_SERVICE_URL="$OFFERS_URL" \
  SCORES_SERVICE_URL="$SCORES_URL" \
  HTTP_TIMEOUT=2 \
  PYTHONPATH="$(pwd)/src" poetry run uvicorn entrypoints.api.main:app \
    --host 127.0.0.1 --port 8007 >>"$DOWN_LOG" 2>&1
) &
DOWN_PID=$!

DOWN_UP=0
for _ in $(seq 1 30); do
  code=$(code_of "$(get_code "$RF005_DOWN_URL/rf005/ping")")
  if [ "$code" = "200" ]; then
    DOWN_UP=1
    break
  fi
  sleep 0.5
done

if [ "$DOWN_UP" = "1" ]; then
  DOWN_OUT=$(get_code_body "$RF005_DOWN_URL/rf005/posts/$POST_ID" \
    -H "Authorization: Bearer $TOKEN_OWNER")
  DOWN_CODE="${DOWN_OUT%%$'\t'*}"
  DOWN_BODY="${DOWN_OUT#*$'\t'}"
  if [ "$DOWN_CODE" = "503" ]; then
    MSG_OK=$(python3 -c "
import json, sys
try:
    print('yes' if json.loads(sys.argv[1]).get('msg') == 'El servicio está temporalmente fuera de servicio.' else 'no')
except Exception:
    print('no')
" "$DOWN_BODY")
    if [ "$MSG_OK" = "yes" ]; then
      pass_test "T9 Posts unreachable -> 503 with documented msg"
    else
      fail_test "T9 Posts unreachable -> 503 but body is '$DOWN_BODY' (expected the documented msg)"
    fi
  else
    fail_test "T9 Posts unreachable (expected 503, got $DOWN_CODE, body='$DOWN_BODY')"
  fi
else
  fail_test "T9 Could not start the temporary orchestrator instance (see $DOWN_LOG)"
fi

# Kill the whole temporary instance (poetry + uvicorn children).
pkill -f "entrypoints.api.main:app --host 127.0.0.1 --port 8007" 2>/dev/null || true
kill "$DOWN_PID" 2>/dev/null
wait "$DOWN_PID" 2>/dev/null

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  RF-005 Manual Verification Summary"
echo "=============================================="
echo "  Total: $TOTAL | Passed: $PASS | Failed: $FAIL"
echo "=============================================="
if [ "$FAIL" -gt 0 ]; then
  echo "  Some tests FAILED. Review the output above."
  exit 1
fi
echo "  All tests PASSED ✓"
exit 0
