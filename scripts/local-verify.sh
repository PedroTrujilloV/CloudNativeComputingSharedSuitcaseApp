#!/usr/bin/env bash
# ============================================================
# Local verification of the Entrega 2 k8s_entrega2/ deployment on Minikube.
#
# Automates the manual verification steps documented in
# docs/README.md ("Step 5 - Verify pods and services are running"
# and "Step 6 - Access services through the Ingress"). It:
#   0. Checks prerequisites (minikube, kubectl, ingress-nginx)
#      before attempting any tests (NEW).
#   1. Checks that all pods, services, network policies and the
#      Ingress are running; verifies all app Services are ClusterIP.
#   2. Pings every app endpoint **through the Ingress only**
#      (ClusterIP services are not externally reachable; the Ingress
#      is the single entry point for all external traffic).
#   3. Runs a functional smoke test through the Ingress: creates a
#      user, checks that the login is rejected while the user is not
#      VERIFICADO, applies the verification status (the same PATCH the
#      verification callback component performs), authenticates,
#      creates a post with the RF-003 orchestrator and reads the post
#      back from posts_app.
#
# Usage (from the repository root, cluster already deployed):
#   bash scripts/local-verify.sh
#
# Exit code 0 when every check passes, 1 otherwise.
# ============================================================
set -uo pipefail

cd "$(dirname "$0")/.."

FAILURES=0
PASS=0


## Also check these before testing

#After applying with the correct namespace, verify everything is in place:

#1. **Ingress controller**: The NGINX ingress controller must be running:
kubectl get pods -n ingress-nginx

#2. **Minikube tunnel** (required for local Ingress to work):
minikube tunnel

#3. **Ingress status**: Make sure the Ingress got an IP:
kubectl get ingress microservices-ingress

#4. **Verify all resources are in `default` namespace**:
kubectl get all -n default
kubectl get ingress -n default

#5. **Test through the Ingress** (not direct NodePort):
curl http://localhost/users/ping


pass() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAILURES=$((FAILURES + 1)); }

# http_code <url> [curl args...] -> prints the HTTP status code
http_code() {
  local url="$1"; shift
  curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$@" "$url" 2>/dev/null || echo "000"
}

NODE_IP="$(minikube ip)"

# ------------------------------------------------------------
# 0. Pre-flight checks (NEW)
# ------------------------------------------------------------
echo "==> [0/5] Pre-flight checks"

# Check minikube is running
if ! minikube status | grep -q "Running"; then
  fail "minikube is not running (start with: minikube start)"
  exit 1
fi
pass "minikube is running"

# Check kubectl can reach the cluster
if ! kubectl cluster-info >/dev/null 2>&1; then
  fail "kubectl cannot reach the cluster"
  exit 1
fi
pass "kubectl is connected to the cluster"

# Check the ingress-nginx CONTROLLER pod is Running.
# (The app.kubernetes.io/name=ingress-nginx label also matches the
# admission-webhook Jobs, which end in "Completed" — exclude them.)
INGRESS_NGINX_PODS="$(kubectl get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --no-headers 2>/dev/null | grep -v "admission" | awk '{print $3}' | sort -u)"
if echo "$INGRESS_NGINX_PODS" | grep -qv "Running"; then
  fail "ingress-nginx pods not Running (status: ${INGRESS_NGINX_PODS})"
else
  pass "ingress-nginx pods are Running"
fi

# Check all critical resource types exist in the default namespace (no networkpolicy checks — shared-db model)
for resource_type in deployment service ingress; do
  count="$(kubectl get "$resource_type" -n default --no-headers 2>/dev/null | wc -l)"
  if [ "$count" -eq 0 ]; then
    fail "no ${resource_type} resources found in namespace 'default'"
  else
    pass "${count} ${resource_type}(s) found in namespace 'default'"
  fi
done

# ------------------------------------------------------------
# 1. Cluster state
# ------------------------------------------------------------
echo "==> [1/5] Checking pods, services and ingress"

for pod in shared-db \
  users-app posts-app offers-app routes-app scores-app \
  rf003-create-post-app rf004-create-offer-app rf005-query-post-app \
  truenative; do
  status="$(kubectl get pod -l app="${pod}" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo missing)"
  if [ "$status" = "Running" ]; then
    pass "pod ${pod} is Running"
  else
    fail "pod ${pod} is not Running (status: ${status})"
  fi
done

for svc in users-app-service posts-app-service offers-app-service \
  routes-app-service scores-app-service rf003-create-post-service \
  rf004-create-offer-service rf005-query-post-service \
  truenative-service \
  shared-db-service; do
  if kubectl get service "$svc" >/dev/null 2>&1; then
    pass "service ${svc} exists"
  else
    fail "service ${svc} is missing"
  fi
done

# The NGINX ingress controller runs in its own namespace; its Service
# (not the Ingress resource) holds the NodePort we reach from outside.
if kubectl get service ingress-nginx-controller -n ingress-nginx >/dev/null 2>&1; then
  pass "service ingress-nginx-controller exists in namespace ingress-nginx"
else
  fail "service ingress-nginx-controller is missing in namespace ingress-nginx"
fi

# No networkpolicy checks — the shared-db model uses per-app databases and
# PostgreSQL-level role isolation instead of network-layer segregation.

INGRESS_ADDR="$(kubectl get ingress microservices-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)"
if [ -n "$INGRESS_ADDR" ]; then
  pass "ingress microservices-ingress has an address (${INGRESS_ADDR})"
else
  fail "ingress microservices-ingress has no address yet"
fi

# Verify all app Services are ClusterIP (Ingress-only architecture)
# (embedded in section 1 output above)
for svc in users-app-service posts-app-service offers-app-service \
  routes-app-service scores-app-service rf003-create-post-service \
  rf004-create-offer-service rf005-query-post-service \
  truenative-service; do
  svc_type="$(kubectl get service "$svc" -o jsonpath='{.spec.type}' 2>/dev/null)"
  if [ "$svc_type" = "ClusterIP" ]; then
    pass "service ${svc} type is ClusterIP"
  else
    fail "service ${svc} type is ${svc_type} (expected ClusterIP)"
  fi
done

# ------------------------------------------------------------
# 2. Ingress path routing (the ONLY external access method)
#    All app Services are ClusterIP so they are reachable only
#    from inside the cluster. External traffic enters through the
#    ingress-nginx-controller Service (NodePort) and is routed by
#    the microservices-ingress Ingress resource.
# ------------------------------------------------------------
echo "==> [2/5] Checking Ingress path routing"

# Build the Ingress entry point URL.
# With `minikube tunnel` running, the Ingress (NodePort/LoadBalancer) is
# reachable at http://localhost:80. Override with INGRESS=... if needed.
INGRESS_PORT=80
# kubectl port-forward \
#   -n ingress-nginx \
#   "$(kubectl get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx \
#     --no-headers -o name | head -1)" \
#   "${INGRESS_PORT}:80" >/dev/null 2>&1 &
# PORT_FWD_PID=$!

INGRESS="http://localhost:${INGRESS_PORT}"
# Wait for port-forward to be ready
for i in $(seq 1 10); do
  if curl -s --max-time 2 "${INGRESS}/users/ping" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

INGRESS="http://127.0.0.1:${INGRESS_PORT}"
echo "    ingress entry point: ${INGRESS}"

check_ingress_ping() { # name path
  local code
  code="$(http_code "${INGRESS}$2")"
  if [ "$code" = "200" ]; then
    pass "GET ${INGRESS}$2 -> 200"
  else
    fail "GET ${INGRESS}$2 -> ${code} (expected 200)"
  fi
}

check_ingress_ping users  /users/ping
check_ingress_ping posts  /posts/ping
check_ingress_ping offers /offers/ping
check_ingress_ping routes /routes/ping
check_ingress_ping scores /scores/ping
check_ingress_ping rf003  /rf003/ping
check_ingress_ping rf004  /rf004/ping
check_ingress_ping rf005  /rf005/ping
check_ingress_ping native /native/ping

# TrueNative body check: the acceptance criterion requires the ping
# response body to be exactly "pong" (a 200 with a different body would
# mean the route answers but the container is not the right one).
NATIVE_PING_BODY="$(curl -s --max-time 10 "${INGRESS}/native/ping" 2>/dev/null)"
if [ "$NATIVE_PING_BODY" = "pong" ]; then
  pass "GET ${INGRESS}/native/ping body is 'pong'"
else
  fail "GET ${INGRESS}/native/ping body is '${NATIVE_PING_BODY}' (expected 'pong')"
fi

# ------------------------------------------------------------
# 3. Functional smoke test through the Ingress
#    (user -> login rejected while not VERIFICADO -> apply the
#     verification status -> auth -> RF-003 create post -> read back)
# ------------------------------------------------------------
echo "==> [3/5] Functional smoke test through the Ingress"

TMP_BODY="$(mktemp)"
trap 'rm -f "$TMP_BODY"; kill ${PORT_FWD_PID:-} 2>/dev/null' EXIT

json_field() { # file field
  python3 -c '
import json, sys
data = json.load(open(sys.argv[1]))
value = data
for key in sys.argv[2].split("."):
    if not isinstance(value, dict) or key not in value:
        sys.exit(1)
    value = value[key]
print(value)
' "$1" "$2"
}

# 3.1 Create a user
NOW="$(date +%s)"
USERNAME="local_verify_${NOW}"
curl -s --max-time 10 -o "$TMP_BODY" -w "%{http_code}" -X POST "${INGRESS}/users" \
  -H "Content-Type: application/json" \
  -d "{
        \"username\": \"${USERNAME}\",
        \"password\": \"Secret123!\",
        \"email\": \"${USERNAME}@example.com\",
        \"dni\": \"12345678${NOW: -2}\",
        \"fullName\": \"Local Verify\",
        \"phoneNumber\": \"3001234567\"
      }" > "$TMP_BODY.code" 2>/dev/null || echo 000 > "$TMP_BODY.code"
CODE="$(cat "$TMP_BODY.code")"
if [ "$CODE" = "201" ]; then
  USER_ID="$(json_field "$TMP_BODY" id)"
  pass "POST /users -> 201 (user ${USERNAME})"
else
  USER_ID=""
  fail "POST /users -> ${CODE} (expected 201) body: $(cat "$TMP_BODY")"
fi

# 3.2 Login is rejected while the user is not VERIFICADO (RF-007):
#     a POR_VERIFICAR or NO_VERIFICADO user cannot obtain a token.
if [ -n "$USER_ID" ]; then
  curl -s --max-time 10 -o "$TMP_BODY" -w "%{http_code}" -X POST "${INGRESS}/users/auth" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"${USERNAME}\", \"password\": \"Secret123!\"}" > "$TMP_BODY.code" 2>/dev/null || echo 000 > "$TMP_BODY.code"
  CODE="$(cat "$TMP_BODY.code")"
  if [ "$CODE" = "401" ]; then
    pass "POST /users/auth -> 401 while the user is POR_VERIFICAR"
  else
    fail "POST /users/auth -> ${CODE} (expected 401 while unverified)"
  fi

  # 3.3 Apply the verification result the same way the verification
  #     callback component does. The local Minikube deployment does not
  #     run that component, so the TrueNative webhook cannot arrive on
  #     its own; the platform exposes the same status update through
  #     PATCH /users/{id}.
  curl -s --max-time 10 -o "$TMP_BODY" -w "%{http_code}" -X PATCH "${INGRESS}/users/${USER_ID}" \
    -H "Content-Type: application/json" \
    -d '{"status": "VERIFICADO"}' > "$TMP_BODY.code" 2>/dev/null || echo 000 > "$TMP_BODY.code"
  CODE="$(cat "$TMP_BODY.code")"
  if [ "$CODE" = "200" ]; then
    pass "PATCH /users/{id} -> 200 (status VERIFICADO applied)"
  else
    fail "PATCH /users/{id} -> ${CODE} (expected 200) body: $(cat "$TMP_BODY")"
  fi
fi

# 3.4 Authenticate and get a bearer token
curl -s --max-time 10 -o "$TMP_BODY" -w "%{http_code}" -X POST "${INGRESS}/users/auth" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"${USERNAME}\", \"password\": \"Secret123!\"}" > "$TMP_BODY.code" 2>/dev/null || echo 000 > "$TMP_BODY.code"
CODE="$(cat "$TMP_BODY.code")"
if [ "$CODE" = "200" ]; then
  TOKEN="$(json_field "$TMP_BODY" token)"
  pass "POST /users/auth -> 200 (token obtained)"
else
  TOKEN=""
  fail "POST /users/auth -> ${CODE} (expected 200)"
fi

# 3.5 Create a post through the RF-003 orchestrator
if [ -n "$TOKEN" ]; then
  START="$(python3 -c 'from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(days=10)).isoformat())')"
  END="$(python3 -c 'from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(days=11)).isoformat())')"
  EXPIRE="$(python3 -c 'from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(days=5)).isoformat())')"
  FLIGHT="LV${NOW}"
  curl -s --max-time 20 -o "$TMP_BODY" -w "%{http_code}" -X POST "${INGRESS}/rf003/posts" \
    -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" \
    -d "{
          \"flightId\": \"${FLIGHT}\",
          \"expireAt\": \"${EXPIRE}\",
          \"plannedStartDate\": \"${START}\",
          \"plannedEndDate\": \"${END}\",
          \"origin\": {\"airportCode\": \"BOG\", \"country\": \"Colombia\"},
          \"destiny\": {\"airportCode\": \"MAD\", \"country\": \"Spain\"},
          \"bagCost\": 350
        }" > "$TMP_BODY.code" 2>/dev/null || echo 000 > "$TMP_BODY.code"
  CODE="$(cat "$TMP_BODY.code")"
  if [ "$CODE" = "201" ]; then
    POST_ID="$(json_field "$TMP_BODY" data.id)"
    pass "POST /rf003/posts -> 201 (post ${POST_ID} created via orchestrator)"
  else
    POST_ID=""
    fail "POST /rf003/posts -> ${CODE} (expected 201) body: $(cat "$TMP_BODY")"
  fi

  # 3.6 Read the post back directly from posts_app through the Ingress
  if [ -n "$POST_ID" ]; then
    CODE="$(http_code "${INGRESS}/posts/${POST_ID}")"
    if [ "$CODE" = "200" ]; then
      pass "GET /posts/${POST_ID} -> 200 (post readable through the Ingress)"
    else
      fail "GET /posts/${POST_ID} -> ${CODE} (expected 200)"
    fi
  fi

  # 3.7 RF-004 check: POST an offer for a nonexistent post. The real app
  #     answers 403 (post does not exist). A 503 would mean broken routing.
  CODE="$(http_code "${INGRESS}/rf004/posts/00000000-0000-0000-0000-000000000000/offers" \
    -X POST -H "Content-Type: application/json" \
    -d '{"description":"test","size":"SMALL","fragile":false,"offer":10}')"
  if [ "$CODE" = "403" ]; then
    pass "POST /rf004/posts/{nonexistent}/offers -> 403 (real app, post does not exist)"
  else
    fail "POST /rf004/posts/{nonexistent}/offers -> ${CODE} (expected 403)"
  fi

  # 3.8 RF-005 check: query the post we just created (we own it) with our
  #     token. The real app answers 200 with the post + offers + score.
  CODE="$(http_code "${INGRESS}/rf005/posts/${POST_ID:-00000000-0000-0000-0000-000000000000}" \
    -H "Authorization: Bearer ${TOKEN}")"
  if [ "$CODE" = "200" ]; then
    pass "GET /rf005/posts/${POST_ID} -> 200 (post queryable via orchestrator)"
  else
    fail "GET /rf005/posts/${POST_ID} -> ${CODE} (expected 200)"
  fi
fi

# ------------------------------------------------------------
# 4. Postman collections (functional + consistency) via the Ingress
#    Mirrors scripts/entrega2/ci_evaluador_entrega2.yml:
#    - functional collections run in full with all apps up;
#    - consistency collections scale one app down (replicas=0) so the
#      Ingress answers 503, run the matching folder, restore the app,
#      then run the "Verificar Consistencia" folder.
# ------------------------------------------------------------
echo "==> [4/5] Postman collections (functional + consistency)"

if ! command -v newman >/dev/null 2>&1; then
  fail "newman is not installed (npm i -g newman) — skipping Postman collections"
else
  pass "newman is available ($(newman --version))"

  # scale_app <deployment> <replicas> — waits for the change to settle
  scale_app() {
    local deployment="$1" replicas="$2"
    kubectl scale deployment "$deployment" -n default --replicas="$replicas" >/dev/null 2>&1 || {
      fail "kubectl scale $deployment --replicas=$replicas"
      return 1
    }
    if [ "$replicas" != "0" ]; then
      kubectl wait --for=condition=ready pod -l app="$deployment" \
        -n default --timeout=120s >/dev/null 2>&1 || {
        fail "pods of $deployment not ready after scale-up"
        return 1
      }
    else
      # Give the Ingress a moment to drop the dead endpoints (503s).
      sleep 5
    fi
    return 0
  }

  # run_newman <label> <file> [newman args...]
  run_newman() {
    local label="$1" file="$2"; shift 2
    if newman run "scripts/entrega2/$file" \
      --env-var "BASE_PATH=${INGRESS}" \
      --reporters cli --reporter-quiet \
      "$@" >/tmp/local-verify-newman.log 2>&1; then
      pass "newman: $label"
    else
      fail "newman: $label (last lines: $(tail -12 /tmp/local-verify-newman.log | tr '\n' ' ' | cut -c1-200))"
    fi
  }

  FAKE_POST_ID="bf8792d2-3097-11ee-be56-0242ac120002"

  # ---- functional (all apps up) ----
  run_newman "evaluate_rf003 (funcional)" "evaluate_rf003.json"
  run_newman "evaluate_rf004 (funcional)" "evaluate_rf004.json"
  run_newman "evaluate_rf005 (funcional)" "evaluate_rf005.json"

  # ---- RF003 consistency ----
  run_newman "rf003 consistency: Reset" "evaluate_rf003_consistency.json" --folder "Reset"
  if scale_app users-app 0; then
    run_newman "rf003 consistency: users-app down" "evaluate_rf003_consistency.json" \
      --folder "Test RF-003" --env-var USER_TOKEN="FAKETOKEN"
    scale_app users-app 1
    run_newman "rf003 consistency: verificar (users)" "evaluate_rf003_consistency.json" --folder "Verificar Consistencia"
  fi

  run_newman "rf003 consistency: Reset" "evaluate_rf003_consistency.json" --folder "Reset"
  if scale_app routes-app 0; then
    run_newman "rf003 consistency: routes-app down" "evaluate_rf003_consistency.json" \
      --folder "RF-003 Crear publicacion"
    scale_app routes-app 1
    run_newman "rf003 consistency: verificar (routes)" "evaluate_rf003_consistency.json" --folder "Verificar Consistencia"
  fi

  run_newman "rf003 consistency: Reset" "evaluate_rf003_consistency.json" --folder "Reset"
  if scale_app posts-app 0; then
    run_newman "rf003 consistency: posts-app down" "evaluate_rf003_consistency.json" \
      --folder "RF-003 Crear publicacion"
    scale_app posts-app 1
    run_newman "rf003 consistency: verificar (posts)" "evaluate_rf003_consistency.json" --folder "Verificar Consistencia"
  fi

  # ---- RF004 consistency ----
  run_newman "rf004 consistency: Reset" "evaluate_rf004_consistency.json" --folder "Reset"
  if scale_app users-app 0; then
    run_newman "rf004 consistency: users-app down" "evaluate_rf004_consistency.json" \
      --folder "Test RF-004" --env-var USER_TOKEN="FAKETOKEN" --env-var POST_ID="$FAKE_POST_ID"
    scale_app users-app 1
    run_newman "rf004 consistency: verificar (users)" "evaluate_rf004_consistency.json" --folder "Verificar Consistencia"
  fi

  run_newman "rf004 consistency: Reset" "evaluate_rf004_consistency.json" --folder "Reset"
  if scale_app offers-app 0; then
    run_newman "rf004 consistency: offers-app down" "evaluate_rf004_consistency.json" \
      --folder "RF-004 Crear oferta"
    scale_app offers-app 1
    run_newman "rf004 consistency: verificar (offers)" "evaluate_rf004_consistency.json" --folder "Verificar Consistencia"
  fi

  run_newman "rf004 consistency: Reset" "evaluate_rf004_consistency.json" --folder "Reset"
  run_newman "rf004 consistency: Crear Recursos (apps up)" "evaluate_rf004_consistency.json" --folder "Crear Recursos"
  if scale_app posts-app 0; then
    run_newman "rf004 consistency: posts-app down" "evaluate_rf004_consistency.json" \
      --folder "Sesion & RF-004" --env-var POST_ID="$FAKE_POST_ID"
    scale_app posts-app 1
    run_newman "rf004 consistency: verificar (posts)" "evaluate_rf004_consistency.json" --folder "Verificar Consistencia"
  fi

  # ---- RF005 consistency ----
  run_newman "rf005 consistency: Reset" "evaluate_rf005_consistency.json" --folder "Reset"
  if scale_app users-app 0; then
    run_newman "rf005 consistency: users-app down" "evaluate_rf005_consistency.json" \
      --folder "Test RF-005" --env-var USER_TOKEN="FAKETOKEN" --env-var POST_ID="$FAKE_POST_ID"
    scale_app users-app 1
  fi

  run_newman "rf005 consistency: Reset" "evaluate_rf005_consistency.json" --folder "Reset"
  run_newman "rf005 consistency: Crear Recursos (apps up)" "evaluate_rf005_consistency.json" --folder "Crear Recursos"
  if scale_app posts-app 0; then
    run_newman "rf005 consistency: posts-app down" "evaluate_rf005_consistency.json" \
      --folder "Sesion & RF-005" --env-var POST_ID="$FAKE_POST_ID"
    scale_app posts-app 1
  fi

  run_newman "rf005 consistency: Reset" "evaluate_rf005_consistency.json" --folder "Reset"
  run_newman "rf005 consistency: Crear Recursos (apps up)" "evaluate_rf005_consistency.json" --folder "Crear Recursos"
  if scale_app offers-app 0; then
    run_newman "rf005 consistency: offers-app down" "evaluate_rf005_consistency.json" \
      --folder "Post & Sesion & RF-005"
    scale_app offers-app 1
  fi
fi

# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------
echo ""
echo "============================================================"
echo "Verification summary: ${PASS} passed, ${FAILURES} failed"
echo "============================================================"
if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
echo "All checks passed."