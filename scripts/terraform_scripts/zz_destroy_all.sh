#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENTS_DIR="${ROOT_DIR}/terraform/environments"
STACKS_DIR="${ROOT_DIR}/terraform/stacks"

echo "🔍 Discovering environment/stack combinations..."

# Collect valid combos first, then reverse the order before destroying —
# per config.yaml: destruction should happen in reverse of deployment order.
COMBOS=()
for ENV_PATH in "${ENVIRONMENTS_DIR}"/*/; do
  ENV_NAME=$(basename "${ENV_PATH}")
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
  echo "❌ No valid environment/stack combinations found."
  exit 1
fi

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

  (
    cd "${TARGET_STACK_DIR}"
    terraform init -reconfigure "${BACKEND_ARGS[@]}" >/dev/null
    terraform plan -destroy -var-file="${TFVARS}"
  )

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
  echo "✅ Destroyed ${STACK_NAME}/${ENV_NAME}"
done

echo "-----------------------------------------------------"
echo "✅ Done processing all destroy candidates."
