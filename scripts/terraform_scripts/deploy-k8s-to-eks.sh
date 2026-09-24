#!/usr/bin/env bash
# deploy-k8s-to-eks.sh
# Deploys the k8s_entrega2/ manifests to the real AWS EKS cluster.
set -euo pipefail

cd "$(dirname "$0")/../.."

# ------------------------------------------------------------
# 0. Configuration — override any of these via env vars, e.g.:
#    TF_STACK_DIR=terraform/stacks/eks ./scripts/terraform_scripts/deploy-k8s-to-eks.sh
# ------------------------------------------------------------
REGION="${REGION:-us-east-1}"
TF_STACK_DIR="${TF_STACK_DIR:-terraform/stacks/eks}"   # <-- CONFIRM: adjust to whichever stack provisions the EKS cluster

echo "==> [0/6] Resolving account, cluster name and region"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

# CONFIRM: these output names must exist in ${TF_STACK_DIR}/outputs.tf.
# If your outputs are named differently, change the two lines below.
# CLUSTER_NAME="$(terraform -chdir="${TF_STACK_DIR}" output -raw cluster_name)" # Didn't work for  now
# REGION="$(terraform -chdir="${TF_STACK_DIR}" output -raw region 2>/dev/null || echo "${REGION}")"

CLUSTER_NAME="$(grep -E '^cluster_name' terraform/environments/student1/eks/terraform.tfvars | cut -d'"' -f2)"
REGION="$(grep -E '^region' terraform/environments/student1/eks/terraform.tfvars | cut -d'"' -f2)"

echo "    account: ${ACCOUNT_ID}"
echo "    cluster: ${CLUSTER_NAME}"
echo "    region:  ${REGION}"

ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# ------------------------------------------------------------
# 1. Authenticate Docker against ECR
# ------------------------------------------------------------
echo "==> [1/6] Logging in to ECR"
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# ------------------------------------------------------------
# 2.a Build, tag and push every app image
#    (image names must match k8s_entrega2/*.yml and config.yaml exactly)
# ------------------------------------------------------------
ensure_ecr_repo() {
  local repo="$1"
  if ! aws ecr describe-repositories --repository-names "${repo}" --region "${REGION}" >/dev/null 2>&1; then
    echo "    creating missing ECR repository: ${repo}"
    aws ecr create-repository --repository-name "${repo}" --region "${REGION}" >/dev/null
  fi
}

image_exists_in_ecr() {
  local image="$1"

  local repo="${image%%:*}"
  local tag="${image##*:}"

  aws ecr describe-images \
    --repository-name "${repo}" \
    --image-ids "imageTag=${tag}" \
    --region "${REGION}" \
    >/dev/null 2>&1
}

build_app() {
  local folder="$1" image="$2"          # image, e.g. "users-app:v0.0.0"
  local repo="${image%%:*}"             # "users-app"

  if [ ! -f "${folder}/Dockerfile" ]; then
    echo "ERROR: ${folder}/Dockerfile not found" >&2
    exit 1
  fi

  # Check whether the exact image:tag already exists in ECR.
  if image_exists_in_ecr "${image}"; then
    echo
    echo "Image already exists:"
    echo "  ${ECR_REGISTRY}/${image}"

    read -r -p "Rebuild and replace it? [y/N] " answer

    if [[ "$answer" =~ ^[Yy]$ ]]; then
      echo "    rebuilding ${image}"
    else
      echo "    skipping ${image}"
      return 0
    fi

  fi
  ensure_ecr_repo "${repo}"

  echo "    building ${image} from ${folder}/"
  docker build -t "${image}" -f "${folder}/Dockerfile" "${folder}"
  docker tag "${image}" "${ECR_REGISTRY}/${image}"
  docker push "${ECR_REGISTRY}/${image}"
}

echo "==> [2/6] a) Building and pushing images"
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
# Entrega 3 apps (the card_worker image is NOT deployed on the cluster:
# the 6_lambda stack consumes it from ECR as the Lambda function image)
build_app credit_cards_app credit-cards-app:v0.0.0

# ------------------------------------------------------------
# 2.b Replace image placeholders in Kubernetes manifests
#     Note: the k8s_entrega2/ manifests use the ECR image URIs, not Docker Hub.
# ------------------------------------------------------------

DEPLOY_DIR="k8s_temp_deploy"
cp -R k8s_entrega2/. "${DEPLOY_DIR}/"

replace_image_placeholder() {
  local manifest="$1"
  local image="$2"

  if [ ! -f "${manifest}" ]; then
    echo "ERROR: ${manifest} not found" >&2
    exit 1
  fi

  local image_uri="${ECR_REGISTRY}/${image}"

  echo "    updating ${manifest}"
  echo "      <image_uri>:<tag> -> ${image_uri}"

  # Replace the literal placeholder with the ECR image URI.
  sed -i '' "s|<image_uri>:<tag>|${image_uri}|g" "${manifest}"

  # Make sure no placeholder remains.
  if grep -q '<image_uri>:<tag>' "${manifest}"; then
    echo "ERROR: Image placeholder was not fully replaced in ${manifest}" >&2
    exit 1
  fi
}

echo "==> [2/6] b) Replacing Kubernetes image placeholders"

replace_image_placeholder "${DEPLOY_DIR}/20-users-app.yml" "users-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/21-posts-app.yml" "posts-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/22-offers-app.yml" "offers-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/23-routes-app.yml" "routes-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/24-scores-app.yml" "scores-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/25-rf003-create-post-app.yml" "rf003-create-post-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/26-rf004-create-offer-app.yml" "rf004-create-offer-app:v0.0.0"
replace_image_placeholder "${DEPLOY_DIR}/27-rf005-query-post-app.yml" "rf005-query-post-app:v0.0.0"



# ------------------------------------------------------------
# 3. Point kubectl at the real EKS cluster
# ------------------------------------------------------------
echo "==> [3/6] Configuring kubectl for EKS cluster ${CLUSTER_NAME}"
aws eks update-kubeconfig --region "${REGION}" --name "${CLUSTER_NAME}"
kubectl config current-context   # sanity check — should print the EKS cluster ARN, not "minikube"

echo "    clearing prior deployment state (deployments, services, secrets, network policies)"
kubectl delete deploy,svc,secret,networkpolicy --all -n default --ignore-not-found

# ------------------------------------------------------------
# 4. Ensure the AWS Load Balancer Controller is installed
#    (EKS equivalent of `minikube addons enable ingress`)
#    CONFIRM: requires an IRSA service account already provisioned by
#    Terraform — set SKIP_ALB_INSTALL=true if that's handled elsewhere.
#     --set serviceAccount.create=false this  If Terraform already creates the IRSA ServiceAccount
#    https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html
# ------------------------------------------------------------

SKIP_ALB_INSTALL=true
if [ "${SKIP_ALB_INSTALL:-false}" != "true" ]; then
  # ----------------------------------------------------------
  # 4.2 Create IAM policy if it does not already exist
  # ----------------------------------------------------------
  POLICY_NAME="AWSLoadBalancerControllerIAMPolicy"
  POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

  if aws iam get-policy \
      --policy-arn "${POLICY_ARN}" \
      >/dev/null 2>&1; then

    echo "    IAM policy already exists:"
    echo "      ${POLICY_ARN}"

  else

    echo "    IAM policy does not exist; creating it"

    POLICY_FILE="$(mktemp)"

    curl -fsSL \
      "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.14.1/docs/install/iam_policy.json" \
      -o "${POLICY_FILE}"

    aws iam create-policy \
      --policy-name "${POLICY_NAME}" \
      --policy-document "file://${POLICY_FILE}"

    rm -f "${POLICY_FILE}"

    echo "    IAM policy created:"
    echo "      ${POLICY_ARN}"
  fi

  # ----------------------------------------------------------
  # 4.3 Ensure IAM OIDC provider exists for the EKS cluster
  # ----------------------------------------------------------
  if ! eksctl version &> /dev/null; then
    echo "eksctl version could not be found. Installing..."
    brew install eksctl
  fi

  echo "    ensuring IAM OIDC provider exists"
  
  eksctl utils associate-iam-oidc-provider \
    --region="${REGION}" \
    --cluster="${CLUSTER_NAME}" \
    --approve
  # ----------------------------------------------------------
  # 4.3 Create/ensure IRSA ServiceAccount
  # ----------------------------------------------------------
  echo "    ensuring IRSA ServiceAccount exists"

  eksctl create iamserviceaccount \
    --cluster="${CLUSTER_NAME}" \
    --namespace=kube-system \
    --name=aws-load-balancer-controller \
    --attach-policy-arn="${POLICY_ARN}" \
    --override-existing-serviceaccounts \
    --region="${REGION}" \
    --approve

  eksctl utils associate-iam-oidc-provider --region=us-east-1 --cluster=grupo33-dann-cluster
  
  echo "==> [4/6] Ensuring AWS Load Balancer Controller is installed"
  helm repo add eks https://aws.github.io/eks-charts >/dev/null
  helm repo update >/dev/null
  helm upgrade --install aws-load-balancer-controller \
    eks/aws-load-balancer-controller \
    --namespace kube-system \
    --set clusterName="${CLUSTER_NAME}" \
    --set serviceAccount.create=false \
    --set serviceAccount.name=aws-load-balancer-controller \
    --version 1.14.0

  # ----------------------------------------------------------
  # 4.5 Wait for controller
  # ----------------------------------------------------------
  echo "    waiting for AWS Load Balancer Controller to be ready before applying manifests"

  kubectl -n kube-system rollout status deployment/aws-load-balancer-controller --timeout=180s
  kubectl -n kube-system wait --for=condition=ready pod \
    -l app.kubernetes.io/name=aws-load-balancer-controller --timeout=180s
else
  echo "==> [4/6] Skipping ALB controller install (SKIP_ALB_INSTALL=true)"
  echo "==> [4/6] Installing NGINX Ingress Controller instead"
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null
  helm repo update >/dev/null
  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace --set controller.service.type=LoadBalancer 
  # ----------------------------------------------------------
  # 4.5 Wait for ingress nginx controller
  # ----------------------------------------------------------
  echo "    waiting for ingress nginx and LoadBalancer external hostname"

  kubectl -n ingress-nginx wait --for=jsonpath='{.status.loadBalancer.ingress}' \
    service/ingress-nginx-controller --timeout=180s
fi

# ------------------------------------------------------------
# 4.6 Fetch real DB credentials from AWS Secrets Manager and
#     render them into the K8s Secrets applied in step 5.
# ------------------------------------------------------------
echo "==> Fetching DB credentials from Secrets Manager"
SECRET_ARN="$(terraform -chdir=terraform/stacks/1_database output -raw secrets_manager_secret_arn)"

DB_SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_ARN}" \
  --region "${REGION}" \
  --query SecretString --output text)"

export DB_HOST="$(echo "${DB_SECRET_JSON}" | jq -r .host)"
export DB_PORT="$(echo "${DB_SECRET_JSON}" | jq -r .port)"
export DB_NAME="$(echo "${DB_SECRET_JSON}" | jq -r .dbname)"
export DB_ENGINE="$(echo "${DB_SECRET_JSON}" | jq -r .engine)"
export DB_USERNAME="$(echo "${DB_SECRET_JSON}" | jq -r .username)"
export DB_PASSWORD="$(echo "${DB_SECRET_JSON}" | jq -r .password)"

if [ -z "${DB_HOST}" ] || [ "${DB_HOST}" == "null" ]; then
  echo "ERROR: DB_HOST came back empty — check the jq keys above against the actual secret JSON." >&2
  exit 1
fi

# ------------------------------------------------------------
# 4.7 Fetch the pipeline secret map (secrets-pipeline-native-map).
#     The pipeline ci_entrega2_deploy.yml uploads every GitHub
#     environment secret (except AWS_* and GITHUB_TOKEN) into this
#     JSON map before running terraform. The 4_sns stack reads
#     EMAIL_TO_NOTIFY from it, and the TrueNative manifest needs
#     SECRET_TOKEN for its K8s Secret.
# ------------------------------------------------------------
echo "==> Fetching pipeline secret map (EMAIL_TO_NOTIFY, SECRET_TOKEN)"
PIPELINE_SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id "secrets-pipeline-native-map" \
  --region "${REGION}" \
  --query SecretString --output text)"

export EMAIL_TO_NOTIFY="$(echo "${PIPELINE_SECRET_JSON}" | jq -r '.EMAIL_TO_NOTIFY')"
export SECRET_TOKEN="$(echo "${PIPELINE_SECRET_JSON}" | jq -r '.SECRET_TOKEN')"

if [ -z "${EMAIL_TO_NOTIFY}" ] || [ "${EMAIL_TO_NOTIFY}" == "null" ]; then
  echo "ERROR: EMAIL_TO_NOTIFY came back empty: make sure the GitHub environment" >&2
  echo "       secret EMAIL_TO_NOTIFY exists before the pipeline runs." >&2
  exit 1
fi

if [ -z "${SECRET_TOKEN}" ] || [ "${SECRET_TOKEN}" == "null" ]; then
  echo "ERROR: SECRET_TOKEN came back empty: make sure the GitHub environment" >&2
  echo "       secret SECRET_TOKEN exists before the pipeline runs." >&2
  exit 1
fi

envsubst < "${DEPLOY_DIR}/00-secrets.yml.tpl" > "${DEPLOY_DIR}/00-secrets.yml"
echo "    rendered ${DEPLOY_DIR}/00-secrets.yml with real DB credentials"

# ------------------------------------------------------------
# 4.8 Render the TrueNative manifest (k8s_entrega3/). It needs
#     SECRET_TOKEN, which comes from the pipeline secret map
#     (never hardcoded, same pattern as the local deploy script).
#     It is applied BEFORE the Ingress, because the /native rule
#     routes to truenative-service.
# ------------------------------------------------------------
echo "==> Rendering TrueNative manifest (k8s_entrega3/)"
envsubst < "k8s_entrega3/k8s-true-native-deployment.yml" > "${DEPLOY_DIR}/k8s-true-native-deployment.yml"
echo "    rendered ${DEPLOY_DIR}/k8s-true-native-deployment.yml with SECRET_TOKEN"

# ------------------------------------------------------------
# 4.9 Render the credit cards manifest (k8s_entrega3/). The table
#     name and the queue URL come from the 3_dynamodb and 5_sqs
#     stack outputs (the stacks must be applied before this step,
#     which the pipeline order guarantees); the token itself comes
#     from the truenative-secret created by the TrueNative manifest,
#     so this manifest only references the secret by name.
# ------------------------------------------------------------
echo "==> Rendering credit cards manifest (k8s_entrega3/)"
CREDIT_CARDS_TABLE_NAME="$(terraform -chdir=terraform/stacks/3_dynamodb output -raw credit_cards_table_name)"
CARD_VERIFICATION_QUEUE_URL="$(terraform -chdir=terraform/stacks/5_sqs output -raw card_verification_queue_url)"

if [ -z "${CREDIT_CARDS_TABLE_NAME}" ] || [ -z "${CARD_VERIFICATION_QUEUE_URL}" ]; then
  echo "ERROR: the 3_dynamodb or 5_sqs stack output came back empty." >&2
  echo "       Apply both stacks (config.yaml tf_stacks order) before this step." >&2
  exit 1
fi

ACCOUNT_ID="${ACCOUNT_ID}" AWS_REGION="${REGION}" \
CREDIT_CARDS_TABLE_NAME="${CREDIT_CARDS_TABLE_NAME}" \
CARD_VERIFICATION_QUEUE_URL="${CARD_VERIFICATION_QUEUE_URL}" \
envsubst '${ACCOUNT_ID} ${AWS_REGION} ${CREDIT_CARDS_TABLE_NAME} ${CARD_VERIFICATION_QUEUE_URL}' \
  < "k8s_entrega3/k8s-credit-cards-deployment.yml" > "${DEPLOY_DIR}/k8s-credit-cards-deployment.yml"
echo "    rendered ${DEPLOY_DIR}/k8s-credit-cards-deployment.yml (table=${CREDIT_CARDS_TABLE_NAME})"

# ------------------------------------------------------------
# 5. Apply the k8s_entrega2/ and k8s_entrega3/ manifests in
#    deployment order. The TrueNative manifest goes BEFORE the
#    Ingress, because the /native rule routes to truenative-service.
#    Note: local-only/15-shared-db.yml is intentionally excluded —
#    AWS uses the managed RDS instance from the `1_database` stack
#    instead.
# ------------------------------------------------------------
echo "==> [5/6] Applying k8s_entrega2/ and k8s_entrega3/ manifests in order"
for f in \
  "${DEPLOY_DIR}/00-secrets.yml" \
  "${DEPLOY_DIR}/20-users-app.yml" \
  "${DEPLOY_DIR}/21-posts-app.yml" \
  "${DEPLOY_DIR}/22-offers-app.yml" \
  "${DEPLOY_DIR}/23-routes-app.yml" \
  "${DEPLOY_DIR}/24-scores-app.yml" \
  "${DEPLOY_DIR}/25-rf003-create-post-app.yml" \
  "${DEPLOY_DIR}/26-rf004-create-offer-app.yml" \
  "${DEPLOY_DIR}/27-rf005-query-post-app.yml" \
  "${DEPLOY_DIR}/k8s-true-native-deployment.yml" \
  "${DEPLOY_DIR}/k8s-credit-cards-deployment.yml" \
  "${DEPLOY_DIR}/zz-ingress.yml"
do
  echo "    applying ${f}"
  kubectl apply -f "${f}"
done

# ------------------------------------------------------------
# 6. Wait for every Deployment to become ready and roll out
# ------------------------------------------------------------
echo "==> [6/6] Waiting for Deployments to be ready"
APPS=(users-app posts-app offers-app routes-app scores-app \
  rf003-create-post-app rf004-create-offer-app rf005-query-post-app \
  truenative credit-cards-app)

for d in "${APPS[@]}"; do
  kubectl wait --for=condition=available deployment "$d" --timeout=300s
done

for d in "${APPS[@]}"; do
  kubectl rollout status deployment/"$d" --timeout=300s
done

kubectl get endpoints \
  users-app-service posts-app-service offers-app-service routes-app-service \
  scores-app-service rf003-create-post-app-service \
  rf004-create-offer-app-service rf005-query-post-app-service \
  credit-cards-service truenative-service

echo ""
echo "Deployment finished."
echo "Verify the RF-006 asynchronous flow with:"
echo "  bash scripts/terraform_scripts/verify-aws-rf006.sh"
