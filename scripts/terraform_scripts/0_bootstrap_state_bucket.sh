#!/usr/bin/env bash
# bootstrap_state_bucket.sh
# Creates the shared S3 bucket used as the Terraform state backend
# for ALL stacks, and ensures the secrets-pipeline-native-map secret
# exists for the local plan of the 4_sns and eks stacks. Run this
# before any `terraform init`.
# Intentionally does NOT use Terraform, since the bucket must exist
# before any stack's backend can be configured.
set -euo pipefail


BUCKET="${1:-terraform-dann-pe-trujillo}"
  echo ""
  read -r -p "❓ Is this a dev (development environment) bucket for? [y/N] " CONFIRM
  if [[ "${CONFIRM}" =~ ^[Yy]$ ]]; then
    echo "▶️  Creating bucket for development(dev: terraform-dann-pe-trujillo-dev)"
    BUCKET="${1:-terraform-dann-pe-trujillo-dev}"
  else
    echo "⏭️  Creating bucket for production (student1: terraform-dann-pe-trujillo)"
    BUCKET="${1:-terraform-dann-pe-trujillo-prod}"
  fi

REGION="${2:-us-east-1}"

# ------------------------------------------------------------
# Pipeline secret for the local plan of the 4_sns and eks stacks
# The deploy pipeline (ci_entrega2_deploy.yml) creates and populates
# secrets-pipeline-native-map before any stack is applied, so on a
# fresh account those stacks cannot plan until the secret exists.
# This step mirrors scripts/local-deploy.sh: it reads EMAIL_TO_NOTIFY
# from the out-of-repo truenative_secrets/dev.env file and creates
# the secret once. It never updates the secret: the pipeline
# overwrites it on every deploy, and the local account role denies
# secretsmanager:PutSecretValue.
# ------------------------------------------------------------
SECRET_NAME="secrets-pipeline-native-map"
DEV_ENV_DIR="$(cd "$(dirname "$0")/../../../truenative_secrets" 2>/dev/null && pwd || true)"
DEV_ENV_FILE="${DEV_ENV_DIR}/dev.env"

if aws secretsmanager get-secret-value --secret-id "${SECRET_NAME}" --region "${REGION}" >/dev/null 2>&1; then
  echo "✅ Secret ${SECRET_NAME} already exists, leaving it untouched."
else
  EMAIL_TO_NOTIFY="$(grep -E '^EMAIL_TO_NOTIFY=' "${DEV_ENV_FILE}" 2>/dev/null | cut -d= -f2-)"

  if [ -z "${EMAIL_TO_NOTIFY}" ]; then
    echo "⚠️  Secret ${SECRET_NAME} not found, and EMAIL_TO_NOTIFY is missing from ${DEV_ENV_FILE}."
    echo "    Add a line EMAIL_TO_NOTIFY=<address> to that file and re-run this script."
  else
    echo "🚀 Creating local secret ${SECRET_NAME} from ${DEV_ENV_FILE}"
    aws secretsmanager create-secret \
      --name "${SECRET_NAME}" \
      --secret-string "{\"EMAIL_TO_NOTIFY\": \"${EMAIL_TO_NOTIFY}\"}" \
      --region "${REGION}"
  fi
fi

# The local account role is explicitly denied s3:ListBucket, so head-bucket
# answers 403 (Forbidden) even for buckets that exist. Treat that as an
# existing bucket instead of trying to create it again. The output is
# captured first because `set -o pipefail` would fail the pipeline
# `aws ... | grep -q` even when grep matches (aws exits non zero on 403).
if HEAD_OUTPUT="$(aws s3api head-bucket --bucket "${BUCKET}" 2>&1)"; then
  echo "✅ Bucket ${BUCKET} already exists — nothing to do."
  exit 0
elif echo "${HEAD_OUTPUT}" | grep -q "Forbidden"; then
  echo "✅ Bucket ${BUCKET} already exists (the local role is denied s3:ListBucket, so it cannot be verified) — nothing to do."
  exit 0
fi

echo "🚀 Creating state backend bucket: ${BUCKET} (${REGION})"
aws s3api create-bucket \
  --bucket "${BUCKET}" \
  --region "${REGION}" \
  --debug

echo "🔒 Enabling versioning (protects state history / recovery from bad applies)"
aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

echo "🔒 Blocking public access"
aws s3api put-public-access-block \
  --bucket "${BUCKET}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "🔒 Enabling default encryption (AES256)"
aws s3api put-bucket-encryption \
  --bucket "${BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

echo "✅ Bucket ${BUCKET} ready for use as a Terraform state backend."
