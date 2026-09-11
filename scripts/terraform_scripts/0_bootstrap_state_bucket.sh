#!/usr/bin/env bash
# bootstrap_state_bucket.sh
# Creates the shared S3 bucket used as the Terraform state backend
# for ALL stacks. Run this ONCE, before any `terraform init`.
# Intentionally does NOT use Terraform, since this bucket must exist
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
    continue
  fi

REGION="${2:-us-east-1}"

if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "✅ Bucket ${BUCKET} already exists — nothing to do."
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
