# deploy-k8s-to-eks
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"





# Initially to get as parameter the aws ACCOUNT_ID from github actions, or you can use the following command to get the account ID from the AWS CLI:
aws sts get-caller-identity --query Account --output text   

# Loging to aws
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com


# ------------------------------------------------------------
#  Build all images into the Minikube Docker daemon and tag them with the ECR repository URL and push them to ECR
#    (image names must match k8s_entrega2/*.yml and config.yaml exactly)
# ------------------------------------------------------------

build_app() {
  local folder="$1" image="$2"
  if [ ! -f "${folder}/Dockerfile" ]; then
    echo "ERROR: ${folder}/Dockerfile not found" >&2
    exit 1
  fi
  echo "    building ${image} from ${folder}/"
  docker build -t "${image}" -f "${folder}/Dockerfile" "${folder}" >/dev/null
  docker tag "${image}" <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/${image}
  docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/${image}
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




#Need to get the cluster name and region from the terraform output. You can do this by running the following command:
terraform output -json | jq -r '.cluster_name.value, .region.value'


# Connecting the environment
# To enable the kubectl client to communicate with the newly created EKS cluster, 
# you must update the local configuration file (~/.kube/config), which stores connection contexts. 
#This is done using the following command:

aws eks update-kubeconfig --region us-east-1 --name <cluster_name>

# For the following steps, it is recommended to work in an environment with no running containers.
# You can do this by deleting deployments and services using the command:

kubectl delete all --all -n default


#####

# From here Should be the process to instald or configure ALB Ingress Controller in the EKS cluster. You can do this by following the steps in the AWS documentation: https://docs.aws.amazon.com/eks/latest/userguide/alb-ingress.html 

# ------------------------------------------------------------
#  Fresh cluster with the ingress addon
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
#   Apply the k8s_entrega2/ manifests in deployment order.
#    The file names encode the order (00 secrets -> 10 network
#    policies -> 20 apps -> zz ingress last) and match the
#    alphabetical order used by the AWS pipeline.
# ------------------------------------------------------------
echo "==> [4/5] Applying k8s_entrega2/ manifests in order"
for f in \
  k8s_entrega2/00-secrets.yml \
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

kubectl rollout status deploy/20-users-app.yml
kubectl rollout status deploy/21-posts-app.yml
kubectl rollout status deploy/22-offers-app.yml
kubectl rollout status deploy/23-routes-app.yml
kubectl rollout status deploy/24-scores-app.yml
kubectl rollout status deploy/25-rf003-create-post-app.yml
kubectl rollout status deploy/26-rf004-create-offer-app.yml
kubectl rollout status deploy/27-rf005-query-post-app.yml
kubectl get endpoints rf005-query-post-app-service rf004-create-offer-app-service rf003-create-post-app-service scores-app-service routes-app-service offers-app-service posts-app-service users-app-service


echo ""
echo "Deployment finished. Run 'bash scripts/local-verify.sh' to verify."
