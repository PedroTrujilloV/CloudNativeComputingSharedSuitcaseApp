#!/usr/bin/env bash
# ============================================================
# Local deployment of the Entrega 2 k8s_entrega2/ manifests on Minikube.
#
# This script automates the manual steps documented in
# docs/README.md ("Run with Minikube") and is also used by the
# ci_local_manual_test.yml workflow. It:
#   1. Removes old Minikube clusters, Docker images and containers.
#   2. Starts a fresh Minikube cluster with the ingress addon.
#   3. Builds all application images into the Minikube Docker daemon.
#   4. Applies the k8s_entrega2/ manifests in the documented deployment order.
#   5. Waits until every Deployment is ready.
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

# ------------------------------------------------------------
# 1. Clean: remove old clusters, images and containers
# ------------------------------------------------------------
echo "==> [1/5] Removing old Minikube clusters, Docker images and containers"
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
MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-7g}"
echo "==> [2/5] Starting Minikube (cpus=${MINIKUBE_CPUS}, memory=${MINIKUBE_MEMORY}) and enabling the ingress addon"
minikube start --cpus="${MINIKUBE_CPUS}" --memory="${MINIKUBE_MEMORY}"
minikube addons enable ingress
eval "$(minikube docker-env)"

# ------------------------------------------------------------
# 3. Build all images into the Minikube Docker daemon
#    (image names must match k8s_entrega2/*.yml and config.yaml exactly)
# ------------------------------------------------------------
echo "==> [3/5] Building application images"

build_app() {
  local folder="$1" image="$2"
  if [ ! -f "${folder}/Dockerfile" ]; then
    echo "ERROR: ${folder}/Dockerfile not found" >&2
    exit 1
  fi
  echo "    building ${image} from ${folder}/"
  docker build -t "${image}" -f "${folder}/Dockerfile" "${folder}" >/dev/null
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

# ------------------------------------------------------------
# 4. Apply the k8s_entrega2/ manifests in deployment order.
#    The file names encode the order (00 secrets -> 10 network
#    policies -> 20 apps -> zz ingress last) and match the
#    alphabetical order used by the AWS pipeline.
# ------------------------------------------------------------
echo "==> [4/5] Applying k8s_entrega2/ manifests in order"
for f in \
  k8s_entrega2/local-only/00-secrets.yml \
  k8s_entrega2/local-only/15-shared-db.yml \
  k8s_entrega2/20-users-app.yml \
  k8s_entrega2/21-posts-app.yml \
  k8s_entrega2/22-offers-app.yml \
  k8s_entrega2/23-routes-app.yml \
  k8s_entrega2/24-scores-app.yml \
  k8s_entrega2/25-rf003-create-post-app.yml \
  k8s_entrega2/26-rf004-create-offer-app.yml \
  k8s_entrega2/27-rf005-query-post-app.yml \
  k8s_entrega2/zz-ingress.yml
do
  echo "    applying ${f}"
  kubectl apply -f "${f}"
done
echo "    waiting for shared-db pod"
kubectl wait --for=condition=ready pod -l app=shared-db --timeout=300s

# ------------------------------------------------------------
# 5. Wait for every Deployment to become ready
# ------------------------------------------------------------
echo "==> [5/5] Waiting for Deployments to be ready"
for d in users-app posts-app offers-app routes-app scores-app \
  rf003-create-post-app rf004-create-offer-app rf005-query-post-app; do
  kubectl wait --for=condition=available deployment "$d" --timeout=300s
done

echo ""
echo "Deployment finished. Run 'bash scripts/local-verify.sh' to verify."
