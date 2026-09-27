#!/usr/bin/env bash
# ============================================================
# Manual verification of the RF-006 asynchronous card
# verification flow on the AWS dev environment (student1).
#
# Prerequisites:
#   - AWS credentials of the dev account (us-east-1) with access to
#     the deployed resources (aws sts get-caller-identity works)
#   - The full platform deployed: the config.yaml tf_stacks
#     (1_database, 2_registry, 3_dynamodb, eks, 4_sns, 5_sqs), the
#     k8s manifests, and the post_k8s_stacks (6_lambda). The
#     ci_entrega2_deploy.yml pipeline, or the helper scripts in
#     this folder, cover that.
#   - aws cli v2, curl, jq, python3, kubectl (with a kubeconfig
#     pointing at the dev cluster for the deployment checks)
#
# What it verifies (the same steps are documented in
# docs/development-view.md, "Manual verification of RF-006"):
#   1. Infrastructure: the card verification queue + dead letter
#      queue, the DynamoDB table, the SNS result notification
#      topic, the Lambda function + execution role + event source
#      mapping, the credit cards and TrueNative Deployments, and
#      the ingress load balancer host.
#   2. The synchronous contract of POST /credit-cards through the
#      single external host: 403 without token, 401 with an invalid
#      token, 400 with missing fields, 412 with an expired card. Plus
#      the utility endpoints (TASK-025), which need no bearer token:
#      GET /credit-cards/ping answers "pong", GET /credit-cards/count
#      answers the count, and POST /credit-cards/reset (used for the
#      final cleanup) answers the exact documented message.
#   3. The asynchronous seam (TASK-022): the card is stored as
#      POR_VERIFICAR and the card_worker Lambda moves it to
#      RECHAZADA (SUCCESS_RATE=0) and APROBADA (SUCCESS_RATE=100);
#      the terminal states are observed through the listing endpoint
#      GET /credit-cards (TASK-024, the same contract the grader
#      collection uses), and the queue drains while the dead letter
#      queue stays empty.
#   4. The duplicate rejection (409) for an already stored card.
#   5. The result email notification (TASK-023): the worker
#      publishes the result, the stored card basics and the RUV to
#      the SNS topic after every terminal state, for both outcomes
#      (visible in the CloudWatch log group of the function).
#   6. The TrueNative side of the polled contract
#      (GET /native/cards/{ruv}).
#
# Usage (from the repository root):
#   bash scripts/terraform_scripts/verify-aws-rf006.sh
#
# Options:
#   --skip-infra   skip the infrastructure checks (step 1)
#   --keep         do not delete the created cards at the end
#
# Exit code 0 when every check passes, 1 otherwise.
# ============================================================
set -uo pipefail

cd "$(dirname "$0")/../.."

REGION="${REGION:-us-east-1}"
QUEUE_NAME="${QUEUE_NAME:-grupo33-card-verification}"
DLQ_NAME="${DLQ_NAME:-grupo33-card-verification-dlq}"
TABLE_NAME="${TABLE_NAME:-grupo33-credit-cards}"
FUNCTION_NAME="${FUNCTION_NAME:-grupo33-card-worker}"
# The academic lab accounts do not allow iam:CreateRole or
# iam:PutRolePolicy, so the 6_lambda stack runs the worker under the
# pre-provisioned LabRole (see terraform/stacks/6_lambda/main.tf).
ROLE_NAME="${ROLE_NAME:-LabRole}"
TOPIC_NAME="${TOPIC_NAME:-grupo33-card-verification-notifications}"

SKIP_INFRA=false
KEEP_CARDS=false
for arg in "$@"; do
  case "$arg" in
    --skip-infra) SKIP_INFRA=true ;;
    --keep) KEEP_CARDS=true ;;
    *) echo "Unknown option: ${arg}" >&2; exit 1 ;;
  esac
done

RUN_START="$(date +%s)"

FAILURES=0
PASS=0
pass() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $1"; FAILURES=$((FAILURES + 1)); }

http_code() { # url curl-extra-args... -> prints the HTTP status code
  local url="$1"; shift
  curl -sk -o /dev/null -w "%{http_code}" --max-time 15 "$@" "$url" 2>/dev/null || echo "000"
}

http_body() { # url curl-extra-args... -> prints the response body
  local url="$1"; shift
  curl -sk --max-time 15 "$@" "$url" 2>/dev/null
}

json_field() { # stdin json, field -> prints the field value
  python3 -c '
import json, sys
data = json.load(sys.stdin)
value = data
for key in sys.argv[1].split("."):
    if not isinstance(value, dict) or key not in value:
        sys.exit(1)
    value = value[key]
print(value)
' "$1"
}

card_field() { # card_id field -> prints the field of the stored card as
  # seen through the listing endpoint GET /credit-cards (the same
  # contract the grader collection uses; the response is the JSON array
  # of the caller's cards). Empty when the card is not in the array or
  # the answer is not a JSON array.
  local body
  body="$(http_body "${BASE}/credit-cards" -H "Authorization: Bearer ${TOKEN}")"
  printf '%s' "${body}" | python3 -c '
import json, sys
try:
    cards = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for card in cards:
    if card.get("id") == sys.argv[1]:
        print(card.get(sys.argv[2], ""))
        break
' "${1}" "${2}"
}

card_status() { # card_id -> prints the stored status (empty when absent)
  card_field "${1}" status
}

card_updated_at() { # card_id -> prints the stored updatedAt (empty when absent)
  card_field "${1}" updatedAt
}

listing_contract_ok() { # card_id -> prints "ok" when the listing endpoint
  # carries the card with exactly the documented contract fields
  # (id, token, userId, lastFourDigits, issuer, status, createdAt,
  # updatedAt, the dates in ISO format)
  local body
  body="$(http_body "${BASE}/credit-cards" -H "Authorization: Bearer ${TOKEN}")"
  printf '%s' "${body}" | python3 -c '
import json, re, sys
try:
    cards = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
expected = {"id", "token", "userId", "lastFourDigits", "issuer", "status", "createdAt", "updatedAt"}
iso = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
for card in cards:
    if card.get("id") == sys.argv[1]:
        if set(card) != expected:
            sys.exit(0)
        if not iso.match(card["createdAt"]) or not iso.match(card["updatedAt"]):
            sys.exit(0)
        print("ok")
        break
' "${1}"
}

card_ruv() { # card_id -> prints the stored TrueNative RUV (read from the
  # table because the documented listing contract does not return it)
  aws dynamodb get-item --region "${REGION}" --table-name "${TABLE_NAME}" \
    --key "{\"id\": {\"S\": \"${1}\"}}" \
    --query 'Item.ruv.S' --output text 2>/dev/null
}

wait_for_status() { # card_id expected_status timeout_seconds -> prints final status
  local card_id="$1" expected="$2" timeout="$3"
  local end=$(( $(date +%s) + timeout ))
  local status
  while [ "$(date +%s)" -lt "${end}" ]; do
    status="$(card_status "${card_id}")"
    if [ "${status}" = "${expected}" ]; then
      echo "${status}"
      return 0
    fi
    sleep 3
  done
  echo "${status:-<missing>}"
  return 1
}

queue_depth() { # queue_url -> prints ApproximateNumberOfMessages
  local url="$1"
  if [ -z "${url}" ] || [ "${url}" = "None" ]; then
    echo "unknown"
    return 0
  fi
  aws sqs get-queue-attributes --region "${REGION}" --queue-url "${url}" \
    --attribute-names ApproximateNumberOfMessages \
    --query 'Attributes.ApproximateNumberOfMessages' --output text 2>/dev/null
}

# ------------------------------------------------------------
# 0. Prerequisites
# ------------------------------------------------------------
echo "==> [0/7] Checking prerequisites"

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: the aws cli is required (https://aws.amazon.com/cli/)" >&2
  exit 1
fi
if ! aws sts get-caller-identity --region "${REGION}" >/dev/null 2>&1; then
  echo "ERROR: AWS credentials for ${REGION} are not configured" >&2
  exit 1
fi
pass "aws credentials work for ${REGION} ($(aws sts get-caller-identity --region "${REGION}" --query Arn --output text | cut -d/ -f2))"

for tool in curl jq python3 kubectl; do
  if command -v "$tool" >/dev/null 2>&1; then
    pass "tool ${tool} is available"
  else
    fail "tool ${tool} is missing"
  fi
done

# ------------------------------------------------------------
# 1. Infrastructure of the asynchronous flow
# ------------------------------------------------------------
QUEUE_URL=""
DLQ_URL=""
BASE=""
if [ "${SKIP_INFRA}" = "false" ]; then
  echo "==> [1/7] Checking the asynchronous flow infrastructure"

  QUEUE_URL="$(aws sqs get-queue-url --region "${REGION}" --queue-name "${QUEUE_NAME}" --query 'QueueUrl' --output text 2>/dev/null)"
  if [ -n "${QUEUE_URL}" ] && [ "${QUEUE_URL}" != "None" ]; then
    pass "queue ${QUEUE_NAME} exists"
  else
    fail "queue ${QUEUE_NAME} does not exist (apply the 5_sqs stack)"
  fi

  DLQ_URL="$(aws sqs get-queue-url --region "${REGION}" --queue-name "${DLQ_NAME}" --query 'QueueUrl' --output text 2>/dev/null)"
  if [ -n "${DLQ_URL}" ] && [ "${DLQ_URL}" != "None" ]; then
    pass "dead letter queue ${DLQ_NAME} exists"
  else
    fail "dead letter queue ${DLQ_NAME} does not exist (apply the 5_sqs stack)"
  fi

  ACCOUNT_ID="$(aws sts get-caller-identity --region "${REGION}" --query Account --output text 2>/dev/null)"
  if aws sns get-topic-attributes --region "${REGION}" \
    --topic-arn "arn:aws:sns:${REGION}:${ACCOUNT_ID}:${TOPIC_NAME}" >/dev/null 2>&1; then
    pass "sns topic ${TOPIC_NAME} exists (email subscription target)"
  else
    fail "sns topic ${TOPIC_NAME} does not exist (apply the 4_sns stack)"
  fi

  TABLE_STATUS="$(aws dynamodb describe-table --region "${REGION}" --table-name "${TABLE_NAME}" --query 'Table.TableStatus' --output text 2>/dev/null)"
  if [ "${TABLE_STATUS}" = "ACTIVE" ]; then
    pass "dynamodb table ${TABLE_NAME} is ACTIVE"
  else
    fail "dynamodb table ${TABLE_NAME} is not ACTIVE (status: ${TABLE_STATUS:-missing}, apply the 3_dynamodb stack)"
  fi

  LAMBDA_STATE="$(aws lambda get-function --region "${REGION}" --function-name "${FUNCTION_NAME}" --query 'Configuration.State' --output text 2>/dev/null)"
  if [ "${LAMBDA_STATE}" = "Active" ]; then
    pass "lambda function ${FUNCTION_NAME} is Active"
  else
    fail "lambda function ${FUNCTION_NAME} is not Active (state: ${LAMBDA_STATE:-missing}, apply the 6_lambda stack)"
  fi

  FUNCTION_ROLE_ARN="$(aws lambda get-function --region "${REGION}" --function-name "${FUNCTION_NAME}" \
    --query 'Configuration.Role' --output text 2>/dev/null)"
  if [ "${FUNCTION_ROLE_ARN:-}" = "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}" ]; then
    pass "lambda function ${FUNCTION_NAME} runs under the role ${ROLE_NAME}"
  else
    fail "lambda function ${FUNCTION_NAME} does not run under the role ${ROLE_NAME} (role: ${FUNCTION_ROLE_ARN:-missing})"
  fi

  if [ -n "${QUEUE_URL}" ] && [ "${QUEUE_URL}" != "None" ]; then
    QUEUE_ARN="arn:aws:sqs:${REGION}:$(aws sts get-caller-identity --region "${REGION}" --query Account --output text):${QUEUE_NAME}"
    MAPPING_STATE="$(aws lambda list-event-source-mappings --region "${REGION}" --function-name "${FUNCTION_NAME}" \
      --query "EventSourceMappings[?EventSourceArn=='${QUEUE_ARN}'].State" --output text 2>/dev/null)"
    if [ "${MAPPING_STATE}" = "Enabled" ]; then
      pass "event source mapping from ${QUEUE_NAME} to ${FUNCTION_NAME} is Enabled"
    else
      fail "event source mapping from ${QUEUE_NAME} to ${FUNCTION_NAME} is not Enabled (state: ${MAPPING_STATE:-missing})"
    fi
  fi

  if kubectl cluster-info >/dev/null 2>&1; then
    for deployment in credit-cards-app truenative; do
      REPLICAS="$(kubectl get deployment "${deployment}" -n default -o jsonpath='{.status.availableReplicas}' 2>/dev/null)"
      if [ -n "${REPLICAS}" ] && [ "${REPLICAS}" -ge 1 ]; then
        pass "deployment ${deployment} has ${REPLICAS} available replica(s)"
      else
        fail "deployment ${deployment} is not available (availableReplicas: ${REPLICAS:-missing})"
      fi
    done
  else
    fail "kubectl cannot reach the cluster (deploy it or fix the kubeconfig)"
  fi

  # Resolve the ingress host. The ingress is an NGINX LoadBalancer (a
  # classic ELB on EKS; the academic account has no ALB, so the elbv2 API
  # finds nothing). Prefer the authoritative kubectl read, fall back to the
  # classic ELB API by tag.
  LB_DNS="$(kubectl -n ingress-nginx get svc ingress-nginx-controller \
    -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)"
  if [ -z "${LB_DNS}" ]; then
    LB_DNS="$(aws elb describe-load-balancers --region "${REGION}" --output json \
      | jq -r '.LoadBalancerDescriptions[] | select(.Tags[]? | .Key=="kubernetes.io/service-name" and .Value=="ingress-nginx/ingress-nginx-controller") | .DNSName' | head -1)"
  fi
  if [ -n "${LB_DNS}" ]; then
    BASE="https://${LB_DNS}"
    pass "ingress load balancer found at ${LB_DNS}"
  else
    fail "ingress load balancer not found (service ingress-nginx/ingress-nginx-controller has no hostname); apply the k8s manifests first"
  fi
fi

if [ -z "${BASE}" ]; then
  echo ""
  echo "Cannot continue: the ingress host was not resolved."
  exit 1
fi
echo "    base path: ${BASE} (self signed certificate: curl -k / newman --insecure)"

CREATED_CARD_IDS=()

# ------------------------------------------------------------
# 2. TrueNative configuration (SUCCESS_RATE 0 -> RECHAZADA first)
# ------------------------------------------------------------
echo "==> [2/7] Configuring TrueNative (SUCCESS_RATE=0, MAX_POLL_DELAY=5)"
CODE="$(http_code "${BASE}/native/env" -X POST -H "Content-Type: application/json" \
  -d '{"SUCCESS_RATE": 0, "MAX_POLL_DELAY": 5, "MAX_WEBHOOK_DELAY": 5}')"
if [ "$CODE" = "200" ]; then
  pass "POST /native/env -> 200"
else
  fail "POST /native/env -> ${CODE} (expected 200)"
fi

# ------------------------------------------------------------
# 3. Caller session (user + bearer token)
# ------------------------------------------------------------
echo "==> [3/7] Creating the caller and obtaining a bearer token"
NOW="$(date +%s)"
USERNAME="rf006_verify_${NOW}"
DNI="$(python3 -c 'import random; print("".join(str(random.randint(0,9)) for _ in range(8)))')"
CARD_NUMBER="$(python3 -c 'import random; print("4" + "".join(str(random.randint(0,9)) for _ in range(15)))')"
CARD_CVV="$(python3 -c 'import random; print(str(random.randint(100,999)))')"
# Relative offset: two years from now, MM/YY (never a hardcoded date)
CARD_EXPIRATION="$(python3 -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) + timedelta(days=730)).strftime("%m/%y"))')"

CARD_BODY="{\"cardNumber\": \"${CARD_NUMBER}\", \"cvv\": \"${CARD_CVV}\", \"expirationDate\": \"${CARD_EXPIRATION}\", \"cardHolderName\": \"RF006 Verify\"}"

CODE="$(http_code "${BASE}/users" -X POST -H "Content-Type: application/json" \
  -d "{\"username\": \"${USERNAME}\", \"password\": \"Secret123!\", \"email\": \"${USERNAME}@example.com\", \"dni\": \"${DNI}\", \"fullName\": \"RF006 Verify\", \"phoneNumber\": \"3001234567\"}")"
if [ "$CODE" = "201" ]; then
  pass "POST /users -> 201 (user ${USERNAME})"
else
  fail "POST /users -> ${CODE} (expected 201)"
fi

# A fresh user is POR_VERIFICAR: the bearer token only exists once the
# TrueNative webhook reaches the in cluster callback (the
# MAX_WEBHOOK_DELAY configured above, 5 seconds, plus the callback round
# trip). Poll the auth endpoint until the loop completes, the same wait
# the graded collection does in its pre request script.
TOKEN=""
AUTH_CODE=""
for i in $(seq 1 15); do
  AUTH_RAW="$(curl -sk -w '\n%{http_code}' --max-time 10 -X POST \
    -H "Content-Type: application/json" \
    "${BASE}/users/auth" \
    -d "{\"username\": \"${USERNAME}\", \"password\": \"Secret123!\"}" 2>/dev/null)"
  AUTH_CODE="$(printf '%s' "${AUTH_RAW}" | tail -n 1)"
  if [ "${AUTH_CODE}" = "200" ]; then
    AUTH_BODY="$(printf '%s' "${AUTH_RAW}" | sed '$d')"
    TOKEN="$(printf '%s' "${AUTH_BODY}" | json_field token 2>/dev/null)"
    if [ -n "${TOKEN}" ] && [ "${TOKEN}" != "None" ]; then
      break
    fi
  fi
  sleep 5
done
if [ -n "${TOKEN}" ] && [ "${TOKEN}" != "None" ]; then
  pass "POST /users/auth -> 200 (token obtained on poll ${i}; the webhook loop completed)"
else
  TOKEN=""
  fail "POST /users/auth did not return a token within 75 s (last code: ${AUTH_CODE:-000}); the webhook path users_app -> TrueNative -> user-verification-callback did not complete"
fi

# ------------------------------------------------------------
# 4. Synchronous contract of POST /credit-cards
# ------------------------------------------------------------
echo "==> [4/7] Checking the synchronous contract of POST /credit-cards"

CODE="$(http_code "${BASE}/credit-cards" -X POST -H "Content-Type: application/json" -d "${CARD_BODY}")"
if [ "$CODE" = "403" ]; then
  pass "POST /credit-cards without token -> 403"
else
  fail "POST /credit-cards without token -> ${CODE} (expected 403)"
fi

CODE="$(http_code "${BASE}/credit-cards" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer FAKETOKEN" -d "${CARD_BODY}")"
if [ "$CODE" = "401" ]; then
  pass "POST /credit-cards with an invalid token -> 401"
else
  fail "POST /credit-cards with an invalid token -> ${CODE} (expected 401)"
fi

CODE="$(http_code "${BASE}/credit-cards" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"cardNumber\": \"${CARD_NUMBER}\", \"cvv\": \"${CARD_CVV}\"}")"
if [ "$CODE" = "400" ]; then
  pass "POST /credit-cards with missing fields -> 400"
else
  fail "POST /credit-cards with missing fields -> ${CODE} (expected 400)"
fi

CODE="$(http_code "${BASE}/credit-cards" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"cardNumber\": \"${CARD_NUMBER}\", \"cvv\": \"${CARD_CVV}\", \"expirationDate\": \"19/01\", \"cardHolderName\": \"RF006 Verify\"}")"
if [ "$CODE" = "412" ]; then
  pass "POST /credit-cards with an expired card -> 412"
else
  fail "POST /credit-cards with an expired card -> ${CODE} (expected 412)"
fi

# The utility endpoints (TASK-025): no bearer token required.
CC_PING_BODY="$(http_body "${BASE}/credit-cards/ping")"
if [ "$CC_PING_BODY" = "pong" ]; then
  pass "GET /credit-cards/ping -> 200 body 'pong' (no auth)"
else
  fail "GET /credit-cards/ping body '${CC_PING_BODY:-<empty>}' (expected 'pong')"
fi

CC_COUNT="$(http_body "${BASE}/credit-cards/count" | json_field count 2>/dev/null)"
if [ -n "${CC_COUNT}" ] && [ "${CC_COUNT}" != "None" ]; then
  pass "GET /credit-cards/count -> 200 with the count field (no auth, value ${CC_COUNT})"
else
  fail "GET /credit-cards/count did not answer {count: n} (no auth)"
fi

# ------------------------------------------------------------
# 5. Asynchronous flow: POR_VERIFICAR -> RECHAZADA -> APROBADA
# ------------------------------------------------------------
echo "==> [5/7] Verifying the asynchronous flow (card_worker bounded polling)"

# When --skip-infra was used the queue URLs were not resolved yet.
if [ -z "${QUEUE_URL}" ] || [ "${QUEUE_URL}" = "None" ]; then
  QUEUE_URL="$(aws sqs get-queue-url --region "${REGION}" --queue-name "${QUEUE_NAME}" --query 'QueueUrl' --output text 2>/dev/null)"
fi
if [ -z "${DLQ_URL}" ] || [ "${DLQ_URL}" = "None" ]; then
  DLQ_URL="$(aws sqs get-queue-url --region "${REGION}" --queue-name "${DLQ_NAME}" --query 'QueueUrl' --output text 2>/dev/null)"
fi

# One curl call captures both the body and the status code (the body is
# everything before the final line, the code the last line).
CREATED1_RAW="$(curl -sk -w '\n%{http_code}' --max-time 15 -X POST \
  -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" \
  "${BASE}/credit-cards" -d "${CARD_BODY}" 2>/dev/null)"
CREATE1_BODY="$(printf '%s' "${CREATED1_RAW}" | sed '$d')"
CREATE1_CODE="$(printf '%s' "${CREATED1_RAW}" | tail -n 1)"
CARD1_ID="$(echo "${CREATE1_BODY}" | json_field id 2>/dev/null)"
CREATED_CARD_IDS+=("${CARD1_ID}")

if [ "$CREATE1_CODE" = "201" ] && [ -n "${CARD1_ID}" ] && [ "${CARD1_ID}" != "None" ]; then
  pass "POST /credit-cards -> 201 (card ${CARD1_ID})"
else
  fail "POST /credit-cards -> ${CREATE1_CODE} (expected 201, body: ${CREATE1_BODY})"
fi

if [ -n "${CARD1_ID}" ] && [ "${CARD1_ID}" != "None" ]; then
  # Second creation of the same card number: the duplicate detection
  # must reject it with 409 (the card is already stored).
  DUP_CODE="$(http_code "${BASE}/credit-cards" -X POST -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" -d "${CARD_BODY}")"
  if [ "$DUP_CODE" = "409" ]; then
    pass "second POST /credit-cards with the same number -> 409 (duplicate rejected)"
  else
    fail "second POST /credit-cards with the same number -> ${DUP_CODE} (expected 409)"
  fi
fi

if [ -n "${CARD1_ID}" ] && [ "${CARD1_ID}" != "None" ]; then

  # Immediately after the creation the card must be POR_VERIFICAR
  # (the worker has no time to finish yet: TrueNative answers after
  # the configured MAX_POLL_DELAY of 5 seconds).
  STATUS_NOW="$(card_status "${CARD1_ID}")"
  if [ "${STATUS_NOW}" = "POR_VERIFICAR" ]; then
    pass "card ${CARD1_ID} stored as POR_VERIFICAR right after creation"
  else
    fail "card ${CARD1_ID} status right after creation is ${STATUS_NOW:-<missing>} (expected POR_VERIFICAR)"
  fi

  # The worker must move the card to RECHAZADA within one minute.
  FINAL_STATUS="$(wait_for_status "${CARD1_ID}" "RECHAZADA" 60 || true)"
  if [ "${FINAL_STATUS}" = "RECHAZADA" ]; then
    UPDATED_AT="$(card_updated_at "${CARD1_ID}")"
    if [ -n "${UPDATED_AT}" ] && [ "${UPDATED_AT}" != "None" ]; then
      pass "card ${CARD1_ID} moved to RECHAZADA by the worker (updatedAt=${UPDATED_AT})"
    else
      fail "card ${CARD1_ID} is RECHAZADA but updatedAt is missing"
    fi
  else
    fail "card ${CARD1_ID} did not reach RECHAZADA within 60 s (last status: ${FINAL_STATUS})"
  fi

  # The listing contract (TASK-024): the caller's array carries the
  # stored card with exactly the documented fields, the dates in ISO
  # format, and no card of any other user (the array is user scoped).
  LIST_CONTRACT="$(listing_contract_ok "${CARD1_ID}")"
  if [ "${LIST_CONTRACT}" = "ok" ]; then
    pass "GET /credit-cards lists card ${CARD1_ID} with the documented contract fields"
  else
    fail "GET /credit-cards does not list card ${CARD1_ID} with the documented contract fields"
  fi

  # The event was consumed by the worker: the queue is empty and the
  # dead letter queue stayed empty (no exhausted attempt).
  DEPTH="$(queue_depth "${QUEUE_URL}")"
  if [ "${DEPTH}" = "0" ]; then
    pass "card verification queue is empty (event consumed by the worker)"
  else
    fail "card verification queue still has ${DEPTH} message(s) (worker did not consume the event)"
  fi
  DLQ_DEPTH="$(queue_depth "${DLQ_URL}")"
  if [ "${DLQ_DEPTH}" = "0" ]; then
    pass "dead letter queue is empty (no exhausted invocation)"
  else
    fail "dead letter queue has ${DLQ_DEPTH} message(s) (the worker invocation failed)"
  fi
fi

# ---- APROBADA: switch TrueNative to SUCCESS_RATE 100 and create a new card
CODE="$(http_code "${BASE}/native/env" -X POST -H "Content-Type: application/json" \
  -d '{"SUCCESS_RATE": 100, "MAX_POLL_DELAY": 5, "MAX_WEBHOOK_DELAY": 5}')"
if [ "$CODE" = "200" ]; then
  pass "POST /native/env (SUCCESS_RATE=100) -> 200"
else
  fail "POST /native/env (SUCCESS_RATE=100) -> ${CODE} (expected 200)"
fi

CARD_NUMBER_2="$(python3 -c 'import random; print("4" + "".join(str(random.randint(0,9)) for _ in range(15)))')"
CARD_BODY_2="{\"cardNumber\": \"${CARD_NUMBER_2}\", \"cvv\": \"${CARD_CVV}\", \"expirationDate\": \"${CARD_EXPIRATION}\", \"cardHolderName\": \"RF006 Verify\"}"
CREATED2_RAW="$(curl -sk -w '\n%{http_code}' --max-time 15 -X POST \
  -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" \
  "${BASE}/credit-cards" -d "${CARD_BODY_2}" 2>/dev/null)"
CREATE2_BODY="$(printf '%s' "${CREATED2_RAW}" | sed '$d')"
CREATE2_CODE="$(printf '%s' "${CREATED2_RAW}" | tail -n 1)"
CARD2_ID="$(echo "${CREATE2_BODY}" | json_field id 2>/dev/null)"
CREATED_CARD_IDS+=("${CARD2_ID}")

if [ "$CREATE2_CODE" = "201" ] && [ -n "${CARD2_ID}" ] && [ "${CARD2_ID}" != "None" ]; then
  pass "POST /credit-cards (new card) -> 201 (card ${CARD2_ID})"

  FINAL_STATUS_2="$(wait_for_status "${CARD2_ID}" "APROBADA" 60 || true)"
  if [ "${FINAL_STATUS_2}" = "APROBADA" ]; then
    UPDATED_AT_2="$(card_updated_at "${CARD2_ID}")"
    if [ -n "${UPDATED_AT_2}" ] && [ "${UPDATED_AT_2}" != "None" ]; then
      pass "card ${CARD2_ID} moved to APROBADA by the worker (updatedAt=${UPDATED_AT_2})"
    else
      fail "card ${CARD2_ID} is APROBADA but updatedAt is missing"
    fi
  else
    fail "card ${CARD2_ID} did not reach APROBADA within 60 s (last status: ${FINAL_STATUS_2})"
  fi

  DLQ_DEPTH="$(queue_depth "${DLQ_URL}")"
  if [ "${DLQ_DEPTH}" = "0" ]; then
    pass "dead letter queue is still empty"
  else
    fail "dead letter queue has ${DLQ_DEPTH} message(s)"
  fi
fi

# ------------------------------------------------------------
# 6. Result email notification (TASK-023): the worker publishes
#    the result to the SNS topic after every terminal state. The
#    publish is observable in the CloudWatch log group of the
#    function (the email itself is delivered by the email protocol
#    subscription of the topic to the EMAIL_TO_NOTIFY address).
# ------------------------------------------------------------
echo "==> [6/7] Checking the result email notification publish (worker -> ${TOPIC_NAME})"

LOG_GROUP="/aws/lambda/${FUNCTION_NAME}"
EMAIL_LOGS="$(aws logs filter-log-events --region "${REGION}" \
  --log-group-name "${LOG_GROUP}" \
  --filter-pattern "Published the card result notification" \
  --start-time "$((RUN_START - 60))" \
  --query 'join("", events[].message)' --output text 2>/dev/null)"

if [ -n "${EMAIL_LOGS}" ] && [ "${EMAIL_LOGS}" != "None" ]; then
  pass "the worker published the result notification to ${TOPIC_NAME} (CloudWatch ${LOG_GROUP})"
else
  fail "no result notification publish found in the CloudWatch log group ${LOG_GROUP} (the worker must publish to ${TOPIC_NAME} after every terminal state)"
fi

if printf '%s' "${EMAIL_LOGS}" | grep -q "status RECHAZADA"; then
  pass "a RECHAZADA email notification was published (first card)"
else
  fail "no RECHAZADA email notification found in the worker logs (the email is mandatory for every outcome)"
fi

if printf '%s' "${EMAIL_LOGS}" | grep -q "status APROBADA"; then
  pass "an APROBADA email notification was published (second card)"
else
  fail "no APROBADA email notification found in the worker logs (the email is mandatory for every outcome)"
fi

# ------------------------------------------------------------
# 7. TrueNative side check (same contract the worker polls)
# ------------------------------------------------------------
echo "==> [7/7] Checking the TrueNative side (GET /native/cards/{ruv})"

SECRET_TOKEN=""
if kubectl cluster-info >/dev/null 2>&1; then
  # Decode with python3 so the check works on macOS (base64 -D) and Linux.
  SECRET_TOKEN="$(kubectl get secret truenative-secret -n default \
    -o jsonpath='{.data.SECRET_TOKEN}' 2>/dev/null \
    | python3 -c 'import base64, sys; print(base64.b64decode(sys.stdin.read().strip()).decode())' 2>/dev/null)"
fi
if [ -n "${SECRET_TOKEN}" ] && [ -n "${CARD1_ID:-}" ]; then
  RUV1="$(card_ruv "${CARD1_ID}")"
  if [ -n "${RUV1}" ] && [ "${RUV1}" != "None" ]; then
    NATIVE_RESPONSE="$(http_body "${BASE}/native/cards/${RUV1}" -H "Authorization: Bearer ${SECRET_TOKEN}")"
    NATIVE_STATUS="$(echo "${NATIVE_RESPONSE}" | json_field status 2>/dev/null)"
    if [ "${NATIVE_STATUS}" = "RECHAZADA" ]; then
      pass "TrueNative GET /native/cards/${RUV1} -> status RECHAZADA (the host the worker polls)"
    else
      fail "TrueNative GET /native/cards/${RUV1} -> status ${NATIVE_STATUS:-<missing>} (expected RECHAZADA, body: ${NATIVE_RESPONSE})"
    fi
  else
    fail "card ${CARD1_ID} has no stored ruv"
  fi
else
  echo "  [SKIP] TrueNative side check (kubectl or truenative-secret unavailable)"
fi

# ------------------------------------------------------------
# Cleanup + summary
# ------------------------------------------------------------
if [ "${KEEP_CARDS}" = "false" ]; then
  # The reset utility endpoint performs the cleanup (the exact
  # documented message confirms it); when it does not answer 200 the
  # script falls back to the item by item table deletion. The guarded
  # expansion keeps the loop working on bash 3.2 (macOS default) when
  # the array is still empty under `set -u`.
  RESET_RAW="$(curl -sk -w '\n%{http_code}' --max-time 15 -X POST "${BASE}/credit-cards/reset" 2>/dev/null)"
  RESET_BODY="$(printf '%s' "${RESET_RAW}" | sed '$d')"
  RESET_CODE="$(printf '%s' "${RESET_RAW}" | tail -n 1)"
  if [ "${RESET_CODE}" = "200" ] && printf '%s' "${RESET_BODY}" | grep -q "Todos los datos fueron eliminados"; then
    COUNT_AFTER="$(http_body "${BASE}/credit-cards/count" | json_field count 2>/dev/null)"
    if [ "${COUNT_AFTER}" = "0" ]; then
      pass "POST /credit-cards/reset -> 200 (cleaned up, the count is back to 0)"
    else
      fail "POST /credit-cards/reset answered 200 but the count is ${COUNT_AFTER:-<missing>} (expected 0)"
    fi
  else
    for card_id in ${CREATED_CARD_IDS[@]+"${CREATED_CARD_IDS[@]}"}; do
      if [ -n "${card_id}" ] && [ "${card_id}" != "None" ]; then
        aws dynamodb delete-item --region "${REGION}" --table-name "${TABLE_NAME}" \
          --key "{\"id\": {\"S\": \"${card_id}\"}}" >/dev/null 2>&1 || true
      fi
    done
    fail "POST /credit-cards/reset -> ${RESET_CODE} body '${RESET_BODY:-<empty>}' (cleaned up from the table instead)"
  fi
  echo "    cleaned up: the created card(s) are deleted from ${TABLE_NAME}"
fi

echo ""
echo "============================================================"
echo "Verification summary: ${PASS} passed, ${FAILURES} failed"
echo "============================================================"
if [ "${FAILURES}" -gt 0 ]; then
  exit 1
fi
echo "All checks passed."
