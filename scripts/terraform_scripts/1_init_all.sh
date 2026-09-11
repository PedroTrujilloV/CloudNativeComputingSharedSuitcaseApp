#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENVIRONMENTS_DIR="${ROOT_DIR}/terraform/environments"
STACKS_DIR="${ROOT_DIR}/terraform/stacks"

echo "🔍 Discovering environment/stack combinations..."

for ENV_PATH in "${ENVIRONMENTS_DIR}"/*/; do
  ENV_NAME=$(basename "${ENV_PATH}")

  echo ""
  read -r -p "❓ Should init with this environment ${ENV_NAME}? [y/N] " CONFIRM
  if [[ "${CONFIRM}" =~ ^[Yy]$ ]]; then
    echo "▶️  Initializing environment: ${ENV_NAME}"
  else
    echo "⏭️  Skipping environment: ${ENV_NAME}"
    continue
  fi

  for STACK_PATH in "${ENV_PATH}"*/; do
    STACK_NAME=$(basename "${STACK_PATH}")
    BACKEND_TFVARS="${STACK_PATH}backend.tfvars"
    TARGET_STACK_DIR="${STACKS_DIR}/${STACK_NAME}"

    if [ ! -d "${TARGET_STACK_DIR}" ]; then
      echo "⚠️  Skipping ${ENV_NAME}/${STACK_NAME}: no matching terraform/stacks/${STACK_NAME}"
      continue
    fi

    if [ ! -f "${BACKEND_TFVARS}" ]; then
      echo "⚠️  Skipping ${ENV_NAME}/${STACK_NAME}: no backend.tfvars found"
      continue
    fi

    echo "-----------------------------------------------------"
    echo "🚀 terraform init: stack=${STACK_NAME} env=${ENV_NAME}"
    (
      # cd "${TARGET_STACK_DIR}"
      # cd "${STACK_PATH}"
      terraform -chdir="${TARGET_STACK_DIR}" init  -reconfigure  -backend-config="${BACKEND_TFVARS}"
      terraform -chdir="${TARGET_STACK_DIR}" validate
    )
  done
done

echo "-----------------------------------------------------"
echo "✅ Done initializing all stack/environment combinations."
