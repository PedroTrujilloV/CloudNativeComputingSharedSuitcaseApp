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
# The Terraform environment to deploy (dev or student1). The cluster name
# and region come from its eks tfvars, and the stack outputs read below
# (1_database, 3_dynamodb, 4_sns, 5_sqs) must have been planned and
# applied against that same environment first (the helper scripts
# re-init each stack dir against the environment of the last run).
TF_ENV="${TF_ENV:-student1}"
TF_STACK_DIR="${TF_STACK_DIR:-terraform/stacks/eks}"   # <-- CONFIRM: adjust to whichever stack provisions the EKS cluster

echo "==> [0/6] Resolving account, cluster name and region"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

# CONFIRM: these output names must exist in ${TF_STACK_DIR}/outputs.tf.
# If your outputs are named differently, change the two lines below.
# CLUSTER_NAME="$(terraform -chdir="${TF_STACK_DIR}" output -raw cluster_name)" # Didn't work for  now
# REGION="$(terraform -chdir="${TF_STACK_DIR}" output -raw region 2>/dev/null || echo "${REGION}")"

CLUSTER_NAME="$(grep -E '^cluster_name' "terraform/environments/${TF_ENV}/eks/terraform.tfvars" | cut -d'"' -f2)"
REGION="$(grep -E '^region' "terraform/environments/${TF_ENV}/eks/terraform.tfvars" | cut -d'"' -f2)"

echo "    environment: ${TF_ENV}"
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
# the 6_lambda stack consumes it from ECR as the Lambda function image;
# the user-verification-callback image is the RF-007 webhook receiver)
build_app credit_cards_app credit-cards-app:v0.0.0
build_app user_verification_callback user-verification-callback:v0.0.0
build_app card_worker card-worker:v0.0.0

# ------------------------------------------------------------
# 2.b Replace image placeholders in Kubernetes manifests
#     Note: the k8s_entrega2/ manifests use the ECR image URIs, not Docker Hub.
# ------------------------------------------------------------

DEPLOY_DIR="k8s_temp_deploy"
cp -R k8s_entrega2/. "${DEPLOY_DIR}/"

replace_image_placeholder() {
  local manifest="$1"
  local image="$2"          # image, e.g. "users-app:v0.0.0" (logged only)

  if [ ! -f "${manifest}" ]; then
    echo "ERROR: ${manifest} not found" >&2
    exit 1
  fi

  echo "    updating ${manifest} (${image})"
  echo "      \${ACCOUNT_ID}.dkr.ecr.\${REGION} -> ${ECR_REGISTRY}"

  # The manifests carry the placeholders
  # ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/<image>:<tag>;
  # replace them with the real account and region of this deployment.
  sed -i '' "s|\${ACCOUNT_ID}|${ACCOUNT_ID}|g" "${manifest}"
  sed -i '' "s|\${REGION}|${REGION}|g" "${manifest}"

  # Make sure no placeholder remains.
  if grep -q '${ACCOUNT_ID}.dkr.ecr.${REGION}' "${manifest}"; then
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
replace_image_placeholder "${DEPLOY_DIR}/28-user-verification-callback.yml" "user-verification-callback:v0.0.0"



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
SECRET_NAME="$(terraform -chdir=terraform/stacks/1_database output -raw secrets_manager_secret_name)"

DB_SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_NAME}" \
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
#     SECRET_TOKEN for its K8s Secret. The K8s Secret uses a
#     `data:` field, so the manifest placeholder is the base64
#     encoding of the token (SECRET_TOKEN_B64), computed here from
#     the map value — exactly the same base64 channel the pipeline
#     uses on AWS through the safe eks output "secret_token_b64".
# ------------------------------------------------------------
echo "==> Fetching pipeline secret map (EMAIL_TO_NOTIFY, SECRET_TOKEN)"
PIPELINE_SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id "secrets-pipeline-native-map" \
  --region "${REGION}" \
  --query SecretString --output text)"

export EMAIL_TO_NOTIFY="$(echo "${PIPELINE_SECRET_JSON}" | jq -r '.EMAIL_TO_NOTIFY')"
export SECRET_TOKEN="$(echo "${PIPELINE_SECRET_JSON}" | jq -r '.SECRET_TOKEN')"
export SECRET_TOKEN_B64="$(printf '%s' "${SECRET_TOKEN}" | base64 | tr -d '\n')"

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
#     SECRET_TOKEN_B64 (the base64 encoding of the map's
#     SECRET_TOKEN, computed above; never hardcoded). It is
#     applied BEFORE the Ingress, because the /native rule
#     routes to truenative-service.
# ------------------------------------------------------------
echo "==> Rendering TrueNative manifest (k8s_entrega3/)"
envsubst < "k8s_entrega3/k8s-true-native-deployment.yml" > "${DEPLOY_DIR}/k8s-true-native-deployment.yml"
echo "    rendered ${DEPLOY_DIR}/k8s-true-native-deployment.yml with SECRET_TOKEN_B64"

# ------------------------------------------------------------
# 4.9 Render the credit cards manifest (k8s_entrega3/). The table
#     name and the queue name come from the 3_dynamodb and 5_sqs
#     stack outputs (the stacks must be applied before this step,
#     which the pipeline order guarantees); the full queue URL is
#     reconstructed inside the manifest from the safe queue name
#     plus $ACCOUNT_ID and $REGION (the full URL embeds the
#     account id, so it cannot be a terraform output). The token
#     itself comes from the truenative-secret created by the
#     TrueNative manifest, so this manifest only references the
#     secret by name.
#
#     The lab-aws-credentials secret of the manifest is filled from
#     the active AWS session of this deployer (the pipeline export
#     or the default profile of ~/.aws/credentials): the EKS node
#     role of the lab account carries no DynamoDB policy and the
#     account forbids creating IAM roles or enabling IRSA, so the
#     credit cards pod authenticates with the session that deploys
#     it. The values are validated against the table before the
#     render (fail fast with a clear message) and never printed.
# ------------------------------------------------------------
echo "==> Rendering credit cards manifest (k8s_entrega3/)"
CREDIT_CARDS_TABLE_NAME="$(terraform -chdir=terraform/stacks/3_dynamodb output -raw credit_cards_table_name)"
CARD_VERIFICATION_QUEUE_NAME="$(terraform -chdir=terraform/stacks/5_sqs output -raw card_verification_queue_name)"

if [ -z "${CREDIT_CARDS_TABLE_NAME}" ] || [ -z "${CARD_VERIFICATION_QUEUE_NAME}" ]; then
  echo "ERROR: the 3_dynamodb or 5_sqs stack output came back empty." >&2
  echo "       Apply both stacks (config.yaml tf_stacks order) before this step." >&2
  exit 1
fi

# Resolve the active session credentials (environment first, then the
# default profile of the AWS CLI credentials file) without printing them.
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ] || [ -z "${AWS_SESSION_TOKEN:-}" ]; then
  CRED_FILE="${HOME}/.aws/credentials"
  if [ -f "${CRED_FILE}" ]; then
    echo "    resolving the AWS session from ${CRED_FILE} (default profile)"
    AWS_ACCESS_KEY_ID="$(awk -F'=' '/^aws_access_key_id/ {print $2; exit}' "${CRED_FILE}")"
    AWS_SECRET_ACCESS_KEY="$(awk -F'=' '/^aws_secret_access_key/ {print $2; exit}' "${CRED_FILE}")"
    AWS_SESSION_TOKEN="$(awk -F'=' '/^aws_session_token/ {print $2; exit}' "${CRED_FILE}")"
  fi
fi

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ] || [ -z "${AWS_SESSION_TOKEN:-}" ]; then
  echo "ERROR: the active AWS session (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY," >&2
  echo "       AWS_SESSION_TOKEN) is incomplete: the credit cards pod authenticates" >&2
  echo "       with the session that deploys it, and the lab account has no node" >&2
  echo "       role or IRSA path with DynamoDB access. Refresh the lab session and" >&2
  echo "       re-run this script." >&2
  exit 1
fi

if ! aws dynamodb describe-table --table-name "${CREDIT_CARDS_TABLE_NAME}" >/dev/null 2>&1; then
  echo "ERROR: the active AWS session cannot describe the table ${CREDIT_CARDS_TABLE_NAME}." >&2
  echo "       Refresh the lab session (the credentials are injected into the" >&2
  echo "       lab-aws-credentials secret at apply time) and re-run this script." >&2
  exit 1
fi
echo "    the active session can access the table ${CREDIT_CARDS_TABLE_NAME}"

export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

ACCOUNT_ID="${ACCOUNT_ID}" REGION="${REGION}" \
CREDIT_CARDS_TABLE_NAME="${CREDIT_CARDS_TABLE_NAME}" \
CARD_VERIFICATION_QUEUE_NAME="${CARD_VERIFICATION_QUEUE_NAME}" \
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN}" \
envsubst '${ACCOUNT_ID} ${REGION} ${CREDIT_CARDS_TABLE_NAME} ${CARD_VERIFICATION_QUEUE_NAME} ${AWS_ACCESS_KEY_ID} ${AWS_SECRET_ACCESS_KEY} ${AWS_SESSION_TOKEN}' \
  < "k8s_entrega3/k8s-credit-cards-deployment.yml" > "${DEPLOY_DIR}/k8s-credit-cards-deployment.yml"
echo "    rendered ${DEPLOY_DIR}/k8s-credit-cards-deployment.yml (table=${CREDIT_CARDS_TABLE_NAME}, queue=${CARD_VERIFICATION_QUEUE_NAME})"

# ------------------------------------------------------------
# 4.10 Render the RF-007 callback manifest (k8s_entrega2/28). The
#      full topic ARN is reconstructed inside the manifest from the
#      safe user_verification_topic_name output of the 4_sns stack
#      (the topic that carries the email subscription to
#      EMAIL_TO_NOTIFY) plus $ACCOUNT_ID and $REGION (the ARN
#      embeds the account id, so it cannot be a terraform output);
#      the account/region parts were already replaced by the image
#      placeholder pass above. The SECRET_TOKEN comes from the
#      truenative-secret created by the TrueNative manifest, so the
#      manifest only references it by name.
# ------------------------------------------------------------
echo "==> Rendering user verification callback manifest (k8s_entrega2/28)"
USER_VERIFICATION_TOPIC_NAME="$(terraform -chdir=terraform/stacks/4_sns output -raw user_verification_topic_name)"

if [ -z "${USER_VERIFICATION_TOPIC_NAME}" ] || [ "${USER_VERIFICATION_TOPIC_NAME}" = "None" ]; then
  echo "ERROR: the 4_sns stack output user_verification_topic_name came back empty." >&2
  echo "       Apply the 4_sns stack (config.yaml tf_stacks order) before this step." >&2
  exit 1
fi

envsubst '${USER_VERIFICATION_TOPIC_NAME}' \
  < "${DEPLOY_DIR}/28-user-verification-callback.yml" > "${DEPLOY_DIR}/28-user-verification-callback.rendered.yml"
echo "    rendered ${DEPLOY_DIR}/28-user-verification-callback.rendered.yml (topic=${USER_VERIFICATION_TOPIC_NAME})"

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
  "${DEPLOY_DIR}/28-user-verification-callback.rendered.yml" \
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
  user-verification-callback truenative credit-cards-app)

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
  user-verification-callback-service \
  credit-cards-service truenative-service

echo ""
echo "Deployment finished."
echo "Verify the RF-006 asynchronous flow with:"
echo "  bash scripts/terraform_scripts/verify-aws-rf006.sh"
