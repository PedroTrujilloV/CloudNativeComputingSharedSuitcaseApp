#!/usr/bin/env bash
# ============================================================
# Local deployment of the k8s_entrega2/ and k8s_entrega3/ manifests
# on Minikube.
#
# This script automates the manual steps documented in
# docs/README.md ("Run with Minikube") and is also used by the
# ci_local_manual_test.yml workflow. It:
#   1. Removes old Minikube clusters, Docker images and containers.
#   2. Starts a fresh Minikube cluster with the ingress addon.
#   3. Builds all application images into the Minikube Docker daemon
#      (the eight legacy and Entrega 2 apps plus credit-cards-app).
#   4. Applies the k8s_entrega2/ manifests in the documented deployment order.
#   5. Deploys the k8s_entrega3/ workloads (TrueNative with the
#      SECRET_TOKEN loaded from the out of repo
#      truenative_secrets/dev.env file, one level above the repo root,
#      and the credit cards Deployment + Service) with the Ingress last,
#      and waits until every Deployment is ready.
#
# NOTE about the credit cards app on Minikube: Minikube has no DynamoDB
# table, no SQS queue and no Lambda function, so the synchronous creation
# flow (POST /credit-cards with a valid body) fails at the DynamoDB step
# and the asynchronous verification worker never runs locally. The
# deployment itself starts and answers the token and validation errors
# (403, 401, 400, 412); the full RF-006 flow is verified on the AWS dev
# environment (see scripts/terraform_scripts/verify-aws-rf006.sh).
#
# Usage (from the repository root):
#   bash scripts/local-deploy.sh
#
# The legacy Entrega 1 deployment (k8s/entrega1_k8s/) is NOT deployed by
# this script: it is evaluated separately by the
# ci_entrega1_evaluador_k8s.yml pipeline on GitHub, and the two
# deployments define the same resource names with different image tags,
# so they must not run in the same cluster at the same time.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

ACCOUNT_ID="000000000000" #"$(aws sts get-caller-identity --query Account --output text)"
AWS_REGION="us-east-1"
# ------------------------------------------------------------
# 1. Clean: remove old clusters, images and containers
# ------------------------------------------------------------
echo "==> [1/7] Removing old Minikube clusters, Docker images and containers"
minikube stop >/dev/null 2>&1 || true
minikube delete >/dev/null 2>&1 || true
docker rm -f $(docker ps -aq) >/dev/null 2>&1 || true
docker rmi $(docker images -q) >/dev/null 2>&1 || true
docker system prune -f >/dev/null 2>&1 || true

# ------------------------------------------------------------
# 2. Fresh cluster with the ingress addon
#    Sizes can be overridden: MINIKUBE_CPUS=4 MINIKUBE_MEMORY=7g
#    (defaults fit a Docker Desktop with 8 GB allocated)
# ------------------------------------------------------------
MINIKUBE_CPUS="${MINIKUBE_CPUS:-2}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-4g}"
echo "==> [2/7] Starting Minikube (cpus=${MINIKUBE_CPUS}, memory=${MINIKUBE_MEMORY}) and enabling the ingress addon"
minikube start --cpus="${MINIKUBE_CPUS}" --memory="${MINIKUBE_MEMORY}"
minikube addons enable ingress
eval "$(minikube docker-env)"

# ------------------------------------------------------------
# 3. Build all images into the Minikube Docker daemon
#    (image names must match k8s_entrega2/*.yml and config.yaml exactly)
# ------------------------------------------------------------
echo "==> [3/7] Building application images"

build_app() {
  local folder="$1" image="$2"
  if [ ! -f "${folder}/Dockerfile" ]; then
    echo "ERROR: ${folder}/Dockerfile not found" >&2
    exit 1
  fi
  echo "    building ${image} from ${folder}/"
  local uri="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${image}"
  docker build -t "${uri}" -f "${folder}/Dockerfile" "${folder}" >/dev/null
}

# Legacy apps (Entrega 1, hyphenated image names for the k8s_entrega2/ deployment)
build_app users_app  users-app:v0.0.0
build_app posts_app  posts-app:v0.0.0
build_app offers_app offers-app:v0.0.0
build_app routes_app routes-app:v0.0.0
# Entrega 2 apps
build_app scores_app scores-app:v0.0.0
build_app rf003_create_post_app rf003-create-post-app:v0.0.0
build_app rf004_create_offer_app rf004-create-offer-app:v0.0.0
build_app rf005_query_post_app rf005-query-post-app:v0.0.0
# Entrega 3 apps
build_app credit_cards_app credit-cards-app:v0.0.0

# ------------------------------------------------------------
# 3.b Replace image placeholders in Kubernetes manifests
#     Note: the k8s_entrega2/ manifests use the ECR image URIs, not Docker Hub.
# ------------------------------------------------------------

DEPLOY_DIR="k8s_temp_local_deploy"
cp -R k8s_entrega2/. "${DEPLOY_DIR}/"

replace_image_placeholder() {
  local manifest="$1"
  local image="$2"

  if [ ! -f "${manifest}" ]; then
    echo "ERROR: ${manifest} not found" >&2
    exit 1
  fi

  local image_uri="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${image}"

  echo "    updating ${manifest}"
  echo "      ${image_uri}"

  # Replace the literal placeholder with the ACCOUNT_ID, AWS_REGION image URI.
  sed -i '' "s|\${ACCOUNT_ID}|${ACCOUNT_ID}|g" "${manifest}"
  sed -i '' "s|\${AWS_REGION}|${AWS_REGION}|g" "${manifest}"

  # Make sure no placeholder remains.
  if grep -q '${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}' "${manifest}"; then
    echo "ERROR: Image placeholder was not fully replaced in ${manifest}" >&2
    exit 1
  fi
}

echo "==> [4/7] Replacing Kubernetes image placeholders"

replace_image_placeholder "${DEPLOY_DIR}/20-users-app.yml" "users-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/21-posts-app.yml" "posts-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/22-offers-app.yml" "offers-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/23-routes-app.yml" "routes-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/24-scores-app.yml" "scores-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/25-rf003-create-post-app.yml" "rf003-create-post-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/26-rf004-create-offer-app.yml" "rf004-create-offer-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/27-rf005-query-post-app.yml" "rf005-query-post-app:v0.0.0"


# ------------------------------------------------------------
# 4. Apply the k8s_entrega2/ manifests in deployment order.
#    The file names encode the order (00 secrets -> 10 network
#    policies -> 20 apps -> zz ingress last) and match the
#    alphabetical order used by the AWS pipeline.
# ------------------------------------------------------------
echo "==> [5/7] Applying k8s_entrega2/ manifests in order"
for f in \
  "${DEPLOY_DIR}/local-only/00-secrets.yml" \
  "${DEPLOY_DIR}/local-only/15-shared-db.yml" \
  "${DEPLOY_DIR}/20-users-app.yml" \
  "${DEPLOY_DIR}/21-posts-app.yml" \
  "${DEPLOY_DIR}/22-offers-app.yml" \
  "${DEPLOY_DIR}/23-routes-app.yml" \
  "${DEPLOY_DIR}/24-scores-app.yml" \
  "${DEPLOY_DIR}/25-rf003-create-post-app.yml" \
  "${DEPLOY_DIR}/26-rf004-create-offer-app.yml" \
  "${DEPLOY_DIR}/27-rf005-query-post-app.yml" \
  # "${DEPLOY_DIR}/zz-ingress.yml"
do
  echo "    applying ${f}"
  kubectl apply -f "${f}"
done
echo "    waiting for shared-db pod"
kubectl wait --for=condition=ready pod -l app=shared-db --timeout=300s

# ------------------------------------------------------------
# 5. Wait for every Deployment to become ready
# ------------------------------------------------------------
echo "==> [6/7] Waiting for Deployments to be ready"
for d in users-app posts-app offers-app routes-app scores-app \
  rf003-create-post-app rf004-create-offer-app rf005-query-post-app; do
  kubectl wait --for=condition=available deployment "$d" --timeout=300s
done



# ------------------------------------------------------------
# 6. k8s_entrega3/ workloads: TrueNative (the SECRET_TOKEN comes from
#    the out of repo dev.env file) and the credit cards Deployment +
#    Service. Both are applied BEFORE the Ingress (the /native and
#    /credit-cards rules route to their services).
#    The dev.env file lives OUTSIDE the repository, one level above the
#    repo root: <parent-of-repo>/truenative_secrets/dev.env, with a
#    single line SECRET_TOKEN=<random string>. It is never committed.
#    The credit cards placeholders are local values: Minikube has no
#    DynamoDB table nor SQS queue, the table name is a placeholder and
#    the empty queue URL makes the app skip the publish and log it.
# ------------------------------------------------------------

echo "==> [7/7] Deploying the k8s_entrega3/ workloads"

get_dev_env_vars() {
  local env_file="$1/dev.env"
  # Load secrets locally if the .env file exists
  if [ -f "$env_file" ]; then
      # Safely export variables from the .env file for this process only
      set -a
      . "$env_file"
      set +a
  else
      echo "Error: .env file not found in $env_file" >&2
      exit 1
  fi

  # verify if SECRET_TOKEN exists
  if [ -z "${SECRET_TOKEN:-}" ]; then
      echo "ERROR: SECRET_TOKEN is not available." >&2
      echo "Either create <parent-of-repo>/truenative_secrets/dev.env with one line (SECRET_TOKEN=<random string>), or export SECRET_TOKEN (the local manual test workflow reads it from the repository secret)." >&2
      exit 1
  fi

}
if [ -z "${SECRET_TOKEN:-}" ]; then
    echo "- Loading secrets from dev.env" >&2
    SCRIPT_DIR="$(cd $(dirname $0)/../../truenative_secrets && pwd )"
    get_dev_env_vars "$SCRIPT_DIR" 
fi

envsubst < "k8s_entrega3/k8s-true-native-deployment.yml" | kubectl apply -f -

ACCOUNT_ID="${ACCOUNT_ID}" AWS_REGION="${AWS_REGION}" \
CREDIT_CARDS_TABLE_NAME="credit_cards" CARD_VERIFICATION_QUEUE_URL="" \
envsubst '${ACCOUNT_ID} ${AWS_REGION} ${CREDIT_CARDS_TABLE_NAME} ${CARD_VERIFICATION_QUEUE_URL}' \
  < "k8s_entrega3/k8s-credit-cards-deployment.yml" | kubectl apply -f -

kubectl apply -f "k8s_entrega2/zz-ingress.yml"

for d in truenative credit-cards-app; do
  kubectl wait --for=condition=available deployment "$d" --timeout=300s
done

echo ""
echo "Deployment finished. Run 'bash scripts/local-verify.sh' to verify."
