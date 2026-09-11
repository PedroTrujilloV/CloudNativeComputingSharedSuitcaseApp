#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STACKS_DIR="${ROOT_DIR}/terraform/stacks"
PLANS_DIR="${ROOT_DIR}/tfplans"

if [ ! -d "${PLANS_DIR}" ] || [ -z "$(ls -A "${PLANS_DIR}" 2>/dev/null)" ]; then
  echo "❌ No saved plans found in ${PLANS_DIR}. Run plan_all.sh first."
  exit 1
fi

for PLAN_FILE in "${PLANS_DIR}"/*.tfplan; do
  PLAN_BASENAME=$(basename "${PLAN_FILE}" .tfplan)
  STACK_NAME="${PLAN_BASENAME%-*}"
  ENV_NAME="${PLAN_BASENAME##*-}"
  TARGET_STACK_DIR="${STACKS_DIR}/${STACK_NAME}"

  echo "-----------------------------------------------------"
  echo "📄 Plan: stack=${STACK_NAME} env=${ENV_NAME}"
  echo "-----------------------------------------------------"

  (cd "${TARGET_STACK_DIR}" && terraform show "${PLAN_FILE}")

  echo ""
  read -r -p "❓ Apply this plan for ${STACK_NAME}/${ENV_NAME}? [y/N] " CONFIRM
  if [[ "${CONFIRM}" =~ ^[Yy]$ ]]; then
    (cd "${TARGET_STACK_DIR}" && terraform apply "${PLAN_FILE}")
    echo "✅ Applied ${STACK_NAME}/${ENV_NAME}"
  else
    echo "⏭️  Skipped ${STACK_NAME}/${ENV_NAME}"
  fi
done

echo "-----------------------------------------------------"
echo "✅ Done reviewing all saved plans."
