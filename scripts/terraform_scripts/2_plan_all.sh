#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENTS_DIR="${ROOT_DIR}/terraform/environments"
STACKS_DIR="${ROOT_DIR}/terraform/stacks"
PLANS_DIR="${ROOT_DIR}/tfplans"

mkdir -p "${PLANS_DIR}"

echo "🔍 Discovering environment/stack combinations..."

for ENV_PATH in "${ENVIRONMENTS_DIR}"/*/; do
  ENV_NAME=$(basename "${ENV_PATH}")

  echo ""
  read -r -p "❓ Should we plan for this environment ${ENV_NAME}? [y/N] " CONFIRM
  if [[ "${CONFIRM}" =~ ^[Yy]$ ]]; then
    echo "▶️  Planning for environment: ${ENV_NAME}"
  else
    echo "⏭️  Skipping environment: ${ENV_NAME}"
    continue
  fi

  for STACK_PATH in "${ENV_PATH}"*/; do
    STACK_NAME=$(basename "${STACK_PATH}")
    BACKEND_TFVARS="${STACK_PATH}backend.tfvars"
    TFVARS="${STACK_PATH}terraform.tfvars"
    TARGET_STACK_DIR="${STACKS_DIR}/${STACK_NAME}"

    if [ ! -d "${TARGET_STACK_DIR}" ]; then
      echo "⚠️  Skipping ${ENV_NAME}/${STACK_NAME}: no matching terraform/stacks/${STACK_NAME}"
      continue
    fi
    if [ ! -f "${BACKEND_TFVARS}" ] || [ ! -f "${TFVARS}" ]; then
      echo "⚠️  Skipping ${ENV_NAME}/${STACK_NAME}: missing backend.tfvars or terraform.tfvars"
      continue
    fi

    echo "-----------------------------------------------------"
    echo "🚀 stack=${STACK_NAME} env=${ENV_NAME}"
    (
      cd "${TARGET_STACK_DIR}"

      # Re-init against THIS environment's backend before planning it —
      # required because each stack dir has only one active backend at a time.
      #terraform init -reconfigure -backend-config="${BACKEND_TFVARS}" >/dev/null
      terraform -chdir="${TARGET_STACK_DIR}" init  -reconfigure  -backend-config="${BACKEND_TFVARS}"  >/dev/null
      terraform -chdir="${TARGET_STACK_DIR}" validate 
      PLAN_FILE="${PLANS_DIR}/${STACK_NAME}-${ENV_NAME}.tfplan"
      terraform -chdir="${TARGET_STACK_DIR}" plan -var-file="${TFVARS}" -out="${PLAN_FILE}"
      echo "✅ Plan saved: ${PLAN_FILE}"
    )
  done
done

echo "-----------------------------------------------------"
echo "✅ Done planning all stack/environment combinations."
echo "📁 Saved plans in: ${PLANS_DIR}"
