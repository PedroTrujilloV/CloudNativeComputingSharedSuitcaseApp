#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENTS_DIR="${ROOT_DIR}/terraform/environments"
STACKS_DIR="${ROOT_DIR}/terraform/stacks"

DESTROY_ALL=false
if [ "${1:-}" = "--all" ]; then
  DESTROY_ALL=true
fi

# Detect the AWS account of the current session so we never try to touch
# state buckets owned by a different account.
CURRENT_ACCOUNT=""
if command -v aws >/dev/null 2>&1; then
  CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)
fi
if [ -z "${CURRENT_ACCOUNT}" ]; then
  echo "⚠️  Could not detect the current AWS account."
  echo "    Continuing, but please verify which environment you are destroying."
else
  echo "👤 Current AWS account: ${CURRENT_ACCOUNT}"
fi

# Extract an AWS account ID (arn:aws:iam::<ACCOUNT>:...) from a tfvars file.
extract_account() {
  local file="$1"
  grep -o 'arn:aws:iam::[0-9]\{12\}:' "${file}" 2>/dev/null | head -1 | grep -o '[0-9]\{12\}' || true
}

# Account for an environment = first account found across any stack's tfvars.
env_account() {
  local env_dir="$1"
  local f acct
  for f in "${env_dir}"/*/*.tfvars; do
    [ -f "${f}" ] || continue
    acct=$(extract_account "${f}")
    if [ -n "${acct}" ]; then
      echo "${acct}"
      return 0
    fi
  done
  echo ""
}

echo "🔍 Discovering environment/stack combinations..."

# Collect valid combos first, then reverse the order before destroying —
# per config.yaml: destruction should happen in reverse of deployment order.
COMBOS=()
for ENV_PATH in "${ENVIRONMENTS_DIR}"/*/; do
  ENV_NAME=$(basename "${ENV_PATH}")
  ENV_ACCT="$(env_account "${ENV_PATH%/}")"

  if [ -n "${CURRENT_ACCOUNT}" ] && [ -n "${ENV_ACCT}" ] && [ "${ENV_ACCT}" != "${CURRENT_ACCOUNT}" ] && ! ${DESTROY_ALL}; then
    echo "⏭️  Skipping environment '${ENV_NAME}': belongs to AWS account ${ENV_ACCT}, but current session is ${CURRENT_ACCOUNT}."
    echo "    (Use --all to force destroying every environment.)"
    continue
  fi

  for STACK_PATH in "${ENV_PATH}"*/; do
    STACK_NAME=$(basename "${STACK_PATH}")
    BACKEND_TFVARS="${STACK_PATH}backend.tfvars"
    TFVARS="${STACK_PATH}terraform.tfvars"
    TARGET_STACK_DIR="${STACKS_DIR}/${STACK_NAME}"

    if [ ! -d "${TARGET_STACK_DIR}" ] || [ ! -f "${BACKEND_TFVARS}" ] || [ ! -f "${TFVARS}" ]; then
      echo "⚠️  Skipping ${ENV_NAME}/${STACK_NAME}: missing stack dir, backend.tfvars, or terraform.tfvars"
      continue
    fi
    COMBOS+=("${ENV_NAME}|${STACK_NAME}|${BACKEND_TFVARS}|${TFVARS}|${TARGET_STACK_DIR}")
  done
done

if [ ${#COMBOS[@]} -eq 0 ]; then
  echo "❌ No environment/stack combinations to destroy for the current AWS session."
  exit 1
fi

PROCESSED=0
DESTROYED=0

# Reverse the array
for ((i=${#COMBOS[@]}-1; i>=0; i--)); do
  IFS='|' read -r ENV_NAME STACK_NAME BACKEND_TFVARS TFVARS TARGET_STACK_DIR <<< "${COMBOS[$i]}"

  echo "-----------------------------------------------------"
  echo "🔎 Reviewing destroy plan: stack=${STACK_NAME} env=${ENV_NAME}"
  echo "-----------------------------------------------------"

  # Stacks with an S3 backend need -backend-config; stacks with a local
  # backend reject unknown S3 keys, so only pass it when declared.
  if grep -rq 'backend "s3"' "${TARGET_STACK_DIR}" --include="*.tf" 2>/dev/null; then
    BACKEND_ARGS=(-backend-config="${BACKEND_TFVARS}")
  else
    BACKEND_ARGS=()
  fi

  # A failed plan (e.g. no access to the state bucket) must not abort the
  # whole script — skip this combo and move on to the next.
  if ! (
    cd "${TARGET_STACK_DIR}"
    terraform init -reconfigure "${BACKEND_ARGS[@]}" >/dev/null
    terraform plan -destroy -var-file="${TFVARS}"
  ); then
    echo "⚠️  Destroy plan failed for ${STACK_NAME}/${ENV_NAME}. Skipping it."
    continue
  fi

  PROCESSED=$((PROCESSED + 1))

  echo ""
  echo "⚠️  This will PERMANENTLY DESTROY real resources for ${STACK_NAME}/${ENV_NAME}."
  read -r -p "❓ Type the environment name (${ENV_NAME}) to confirm, or anything else to skip: " CONFIRM_ENV

  if [ "${CONFIRM_ENV}" != "${ENV_NAME}" ]; then
    echo "⏭️  Skipped ${STACK_NAME}/${ENV_NAME} (confirmation did not match)."
    continue
  fi

  read -r -p "❓ Final confirmation — type DESTROY (all caps) to proceed: " CONFIRM_WORD
  if [ "${CONFIRM_WORD}" != "DESTROY" ]; then
    echo "⏭️  Skipped ${STACK_NAME}/${ENV_NAME} (final confirmation did not match)."
    continue
  fi

  (
    cd "${TARGET_STACK_DIR}"
    terraform destroy -var-file="${TFVARS}"
  )
  DESTROYED=$((DESTROYED + 1))
  echo "✅ Destroyed ${STACK_NAME}/${ENV_NAME}"
done

echo "-----------------------------------------------------"
echo "✅ Done. Plans reviewed: ${PROCESSED}, destroyed: ${DESTROYED}."
