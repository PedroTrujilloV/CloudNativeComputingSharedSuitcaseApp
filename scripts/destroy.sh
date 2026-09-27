#!/usr/bin/env bash
# Replica localmente ci_entrega2_destroy.yml: destruye post_k8s_stacks, borra
# los manifiestos de k8s y destruye tf_stacks, en orden inverso al deploy.
# Debe correrse desde una copia local del repositorio del estudiante, con
# esta carpeta ("scripts") en su raíz.
#
# Uso: bash scripts/destroy.sh
# Configuración: scripts/.env (ver scripts/.env.example)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

bash "$SCRIPT_DIR/check-prerequisites.sh" destroy

ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ No existe ${ENV_FILE}. Copie scripts/.env.example a scripts/.env y complete los valores." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${ENVIRONMENT:?Defina ENVIRONMENT en scripts/.env}"
case "$ENVIRONMENT" in
  student1|student2|student3|student4|tutor) ;;
  *) echo "❌ ENVIRONMENT inválido: '${ENVIRONMENT}' (debe ser student1, student2, student3, student4 o tutor)." >&2; exit 1 ;;
esac

cd "$REPO_ROOT"

# -----------------------------------------------------------------------
# 0. Validar secrets/variables requeridos (equivalente al job "config").
# -----------------------------------------------------------------------
required_secrets=(AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN)
missing=()
for var in "${required_secrets[@]}"; do
  [ -z "${!var:-}" ] && missing+=("$var")
done
if [ "$ENVIRONMENT" = "tutor" ] && [ -z "${TF_STATE_BUCKET_NAME:-}" ]; then
  missing+=("TF_STATE_BUCKET_NAME")
fi
if [ ${#missing[@]} -gt 0 ]; then
  echo "❌ Faltan las siguientes variables en scripts/.env:"
  printf '   - %s\n' "${missing[@]}"
  exit 1
fi

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
repo_name="${REPO_NAME:-$(basename "$REPO_ROOT")}"
echo "✅ Variables requeridas presentes."

if [ ! -d terraform/stacks ] || [ ! -d terraform/environments ]; then
  echo "❌ Este repositorio debe tener terraform/stacks/ y terraform/environments/ en la raíz." >&2
  exit 1
fi

# -----------------------------------------------------------------------
# 1. Leer config.yaml
# -----------------------------------------------------------------------
tf_stacks=$(yq -o=json -I=0 '.tf_stacks // []' config.yaml)
post_k8s_stacks=$(yq -o=json -I=0 '.post_k8s_stacks // []' config.yaml)
k8s_manifests=$(yq -o=json -I=0 '.k8s_manifests // []' config.yaml)
default_env=$(yq -r '.default_env // ""' config.yaml)

[ "$(echo "$tf_stacks" | jq 'length')" -gt 0 ] || { echo "❌ config.yaml no define 'tf_stacks'." >&2; exit 1; }
[ "$(echo "$k8s_manifests" | jq 'length')" -gt 0 ] || { echo "❌ config.yaml no define 'k8s_manifests'." >&2; exit 1; }
[ -n "$default_env" ] || { echo "❌ config.yaml no define 'default_env'." >&2; exit 1; }
[ "$default_env" != "tutor" ] || { echo "❌ 'default_env' no puede ser 'tutor'." >&2; exit 1; }

if [ "$ENVIRONMENT" = "tutor" ]; then
  env_environment="$default_env"
else
  env_environment="$ENVIRONMENT"
fi

# -----------------------------------------------------------------------
# Descubrir región / cluster_name a partir de tf_stacks
# -----------------------------------------------------------------------
region=""
cluster_name=""
for stack_name in $(echo "$tf_stacks" | jq -r '.[]'); do
  stack_dir="terraform/stacks/${stack_name}"
  env_dir="terraform/environments/${env_environment}/${stack_name}"
  backend_file="${env_dir}/backend.tfvars"
  tfvars_file="${env_dir}/terraform.tfvars"

  [ -d "$stack_dir" ] || { echo "❌ No existe ${stack_dir}." >&2; exit 1; }
  [ -f "$backend_file" ] || { echo "❌ No existe ${backend_file}." >&2; exit 1; }

  if [ "$ENVIRONMENT" = "tutor" ]; then
    stack_region="us-east-1"
  else
    stack_region=$(grep '^region' "$backend_file" | cut -d'"' -f2)
  fi
  region="${region:-$stack_region}"

  if [ -z "$cluster_name" ] && [ -f "$tfvars_file" ]; then
    found=$(grep '^cluster_name' "$tfvars_file" | cut -d'"' -f2 || true)
    cluster_name="${cluster_name:-$found}"
  fi
done
[ -n "$cluster_name" ] || { echo "❌ Ningún stack de tf_stacks define 'cluster_name' en su terraform.tfvars." >&2; exit 1; }

echo "Región: ${region} | Cluster: ${cluster_name} | Ambiente base: ${env_environment}"

db_vars=()
[ -n "${DB_USERNAME:-}" ] && db_vars+=("-var=db_username=${DB_USERNAME}")
[ -n "${DB_PASSWORD:-}" ] && db_vars+=("-var=db_password=${DB_PASSWORD}")

destroy_stacks() {
  local stacks_json="$1"
  echo "$stacks_json" | jq -r 'reverse | .[]' | while read -r stack_name; do
    stack_dir="terraform/stacks/${stack_name}"
    env_dir="../../../terraform/environments/${env_environment}/${stack_name}"

    echo "== terraform destroy: ${stack_name} =="
    pushd "$stack_dir" >/dev/null

    if [ "$ENVIRONMENT" = "tutor" ]; then
      terraform init -reconfigure \
        -backend-config="${env_dir}/backend.tfvars" \
        -backend-config="bucket=${TF_STATE_BUCKET_NAME}" \
        -backend-config="key=${repo_name}/${stack_name}/terraform.tfstate" \
        -backend-config="region=us-east-1"
    else
      terraform init -reconfigure -backend-config="${env_dir}/backend.tfvars"
    fi

    terraform destroy "${db_vars[@]}" -var-file="${env_dir}/terraform.tfvars" -auto-approve

    popd >/dev/null
  done
}

# -----------------------------------------------------------------------
# 1. Destruir post_k8s_stacks (si existen), antes de tocar k8s.
# -----------------------------------------------------------------------
if [ "$(echo "$post_k8s_stacks" | jq 'length')" -gt 0 ]; then
  echo "== terraform destroy: post_k8s_stacks =="
  destroy_stacks "$post_k8s_stacks"
else
  echo "-- post_k8s_stacks vacío, se omite --"
fi

# -----------------------------------------------------------------------
# 2. Desinstalar ingress-nginx y borrar manifiestos de k8s. El Service tipo
#    LoadBalancer crea un ELB real en AWS que terraform nunca gestionó; hay
#    que esperar a que desaparezca antes de destruir la VPC/el cluster.
# -----------------------------------------------------------------------
echo "== Verificando si el cluster EKS existe =="
if aws eks describe-cluster --name "$cluster_name" --region "$region" >/dev/null 2>&1; then
  cluster_exists=true
else
  cluster_exists=false
  echo "-- El cluster ${cluster_name} no existe (o ya fue borrado); se omite la limpieza de k8s. --"
fi

if [ "$cluster_exists" = true ]; then
  aws eks update-kubeconfig --region "$region" --name "$cluster_name"

  if helm status ingress-nginx -n ingress-nginx >/dev/null 2>&1; then
    helm uninstall ingress-nginx -n ingress-nginx --wait --timeout 5m
  else
    echo "-- El release ingress-nginx no existe, no hay nada que desinstalar. --"
  fi

  echo "== Esperando a que AWS elimine el load balancer de ingress-nginx =="
  lb_deleted=false
  for i in $(seq 1 30); do
    remaining=$(aws resourcegroupstaggingapi get-resources \
      --resource-type-filters elasticloadbalancing \
      --tag-filters Key=kubernetes.io/service-name,Values=ingress-nginx/ingress-nginx-controller \
      --query 'length(ResourceTagMappingList)' --output text)
    if [ "$remaining" = "0" ]; then
      echo "✅ Load balancer eliminado."
      lb_deleted=true
      break
    fi
    echo "   Todavía existe (intento ${i}/30), esperando 20s..."
    sleep 20
  done
  if [ "$lb_deleted" != true ]; then
    echo "❌ El load balancer de ingress-nginx sigue existiendo después de ~10 min. Revise la consola de AWS (EC2 → Load Balancers) antes de continuar con terraform destroy." >&2
    exit 1
  fi

  echo "== Borrando manifiestos de k8s restantes =="
  echo "$k8s_manifests" | jq -r 'reverse | .[]' | while read -r dir; do
    echo "-- kubectl delete (${dir}) --"
    kubectl delete -f "$dir" --ignore-not-found
  done
fi

# -----------------------------------------------------------------------
# 3. Destruir tf_stacks, en orden inverso al deploy.
# -----------------------------------------------------------------------
echo "== terraform destroy: tf_stacks =="
destroy_stacks "$tf_stacks"

echo "✅ Destroy de '${ENVIRONMENT}' completado."
