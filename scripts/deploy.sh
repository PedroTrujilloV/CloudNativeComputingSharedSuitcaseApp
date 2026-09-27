#!/usr/bin/env bash
# Replica localmente ci_entrega2_deploy.yml: aplica los stacks de terraform,
# construye y publica las imágenes en ECR, despliega los manifiestos de k8s y
# finalmente aplica post_k8s_stacks. Debe correrse desde una copia local del
# repositorio del estudiante, con esta carpeta ("scripts") en su raíz.
#
# Uso: bash scripts/deploy.sh
# Configuración: scripts/.env (ver scripts/.env.example)
set -euo pipefail
shopt -s nullglob

# jq.exe / yq.exe en Windows escriben CRLF. Command substitution y
# `for x in $(jq -r ...)` dejan el \r pegado al nombre, y [ -d ] falla
# aunque la carpeta exista.
jq() { command jq "$@" | tr -d '\r'; }
yq() { command yq "$@" | tr -d '\r'; }
echo "after jq and yq"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

bash "$SCRIPT_DIR/check-prerequisites.sh" deploy

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

if [ -n "${DB_PASSWORD:-}" ]; then
  len=${#DB_PASSWORD}
  if [ "$len" -lt 8 ] || [ "$len" -gt 128 ]; then
    echo "❌ DB_PASSWORD debe tener entre 8 y 128 caracteres (tiene ${len})." >&2
    exit 1
  fi
  case "$DB_PASSWORD" in
    */*|*'"'*|*@*)
      echo "❌ DB_PASSWORD no puede contener '/', '\"' ni '@' (restricción de RDS)." >&2
      exit 1
      ;;
  esac
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
apps=$(yq -o=json -I=0 '.apps // []' config.yaml | jq -c '[.[] | to_entries[0] | {name: .key} + .value]')
default_env=$(yq -r '.default_env // ""' config.yaml)

[ "$(echo "$tf_stacks" | jq 'length')" -gt 0 ] || { echo "❌ config.yaml no define 'tf_stacks'." >&2; exit 1; }
[ "$(echo "$k8s_manifests" | jq 'length')" -gt 0 ] || { echo "❌ config.yaml no define 'k8s_manifests'." >&2; exit 1; }
[ "$(echo "$apps" | jq 'length')" -gt 0 ] || { echo "❌ config.yaml no define 'apps'." >&2; exit 1; }
if [ "$(echo "$apps" | jq '[.[] | select(has("folder") and has("image_name") and has("image_tag"))] | length')" != "$(echo "$apps" | jq 'length')" ]; then
  echo "❌ Cada entrada de 'apps' debe tener 'folder', 'image_name' e 'image_tag'." >&2
  exit 1
fi
[ -n "$default_env" ] || { echo "❌ config.yaml no define 'default_env'." >&2; exit 1; }
[ "$default_env" != "tutor" ] || { echo "❌ 'default_env' no puede ser 'tutor'." >&2; exit 1; }
for stack_name in $(echo "$post_k8s_stacks" | jq -r '.[]'); do
  [ -d "terraform/stacks/${stack_name}" ] || { echo "❌ No existe terraform/stacks/${stack_name} (listado en post_k8s_stacks)." >&2; exit 1; }
done

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

# -----------------------------------------------------------------------
# Terraform: versión requerida (informativo, no se instala automáticamente)
# -----------------------------------------------------------------------
if [ -f terraform/.terraform-version ]; then
  required_tf_version=$(cat terraform/.terraform-version)
else
  required_tf_version="1.12.0"
fi
installed_tf_version=$(terraform version -json | jq -r .terraform_version)
if [ "$installed_tf_version" != "$required_tf_version" ]; then
  echo "⚠️  Este repositorio espera Terraform ${required_tf_version}; tiene instalado ${installed_tf_version}."
fi

db_vars=()
[ -n "${DB_USERNAME:-}" ] && db_vars+=("-var=db_username=${DB_USERNAME}")
[ -n "${DB_PASSWORD:-}" ] && db_vars+=("-var=db_password=${DB_PASSWORD}")

# -----------------------------------------------------------------------
# 2. Subir a Secrets Manager todo lo definido en scripts/.env que no sea
#    AWS_*/ENVIRONMENT/TF_STATE_BUCKET_NAME/REPO_NAME (igual que el paso
#    "Store non-AWS secrets in Secrets Manager" del pipeline de GitHub).
# -----------------------------------------------------------------------
echo "== Subiendo secrets a Secrets Manager =="
secrets_json="{}"
while IFS= read -r line; do
  [ -z "$line" ] && continue
  case "$line" in \#*) continue ;; esac
  key="${line%%=*}"
  case "$key" in AWS_*|ENVIRONMENT|TF_STATE_BUCKET_NAME|REPO_NAME) continue ;; esac
  value="${!key-}"
  secrets_json=$(jq --arg k "$key" --arg v "$value" '. + {($k): $v}' <<< "$secrets_json")
done < "$ENV_FILE"

secret_name="secrets-pipeline-native-map"
if aws secretsmanager describe-secret --secret-id "$secret_name" >/dev/null 2>&1; then
  aws secretsmanager put-secret-value --secret-id "$secret_name" --secret-string "$secrets_json" >/dev/null
else
  aws secretsmanager create-secret --name "$secret_name" --secret-string "$secrets_json" >/dev/null
fi

# -----------------------------------------------------------------------
# 3. Terraform init/plan/apply, en orden, combinando outputs en un solo mapa.
# -----------------------------------------------------------------------
tf_outputs_file="$(mktemp)"
echo '{}' > "$tf_outputs_file"

apply_stacks() {
  local stacks_json="$1"
  local stack_outputs_tmp
  stack_outputs_tmp="$(mktemp)"

  echo "$stacks_json" | jq -r '.[]' | while read -r stack_name; do
    stack_dir="terraform/stacks/${stack_name}"
    env_dir="../../../terraform/environments/${env_environment}/${stack_name}"

    echo "== terraform apply: ${stack_name} =="
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

    terraform plan "${db_vars[@]}" -var-file="${env_dir}/terraform.tfvars" -out=.tfplan
    terraform apply .tfplan
    terraform output -json > "$stack_outputs_tmp"

    popd >/dev/null

    jq -s '.[0] * (.[1] | map_values(.value))' "$tf_outputs_file" "$stack_outputs_tmp" > "${tf_outputs_file}.new"
    mv "${tf_outputs_file}.new" "$tf_outputs_file"
  done
}

apply_stacks "$tf_stacks"

# -----------------------------------------------------------------------
# 4. Build + push de imágenes a ECR (secuencial; en CI corre en paralelo
#    por matrix, localmente se hace una por una).
# -----------------------------------------------------------------------
account_id=$(aws sts get-caller-identity --query Account --output text)
ecr_registry="${account_id}.dkr.ecr.${region}.amazonaws.com"
# Tras terraform (lambdas) el login a ECR suele existir ya. En macOS un
# segundo login puede fallar con Keychain -25299; en Windows/Linux no.
login_err="$(mktemp)"
if ! aws ecr get-login-password --region "$region" \
  | docker login --username AWS --password-stdin "$ecr_registry" 2>"$login_err"
then
  if grep -qE 'already exists in the keychain|-25299' "$login_err"; then
    echo "ECR login already present; continuing"
  else
    cat "$login_err" >&2
    rm -f "$login_err"
    exit 1
  fi
fi
rm -f "$login_err"

echo "$apps" | jq -c '.[]' | while read -r app; do
  name=$(echo "$app" | jq -r '.name')
  folder=$(echo "$app" | jq -r '.folder')
  image_name=$(echo "$app" | jq -r '.image_name')
  image_tag=$(echo "$app" | jq -r '.image_tag')

  echo "== build+push: ${name} =="
  docker build --platform linux/amd64 --provenance=false -t "${image_name}:${image_tag}" --label version="${image_tag}" -f "${folder}/Dockerfile" "$folder"
  docker tag "${image_name}:${image_tag}" "${ecr_registry}/${image_name}:${image_tag}"
  docker push "${ecr_registry}/${image_name}:${image_tag}"
done

# -----------------------------------------------------------------------
# 5. Desplegar manifiestos de k8s
# -----------------------------------------------------------------------
echo "== Actualizando kubeconfig =="
aws eks update-kubeconfig --region "$region" --name "$cluster_name"

echo "== Instalando/actualizando ingress-nginx =="
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null
helm repo update >/dev/null
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --wait --timeout 5m

# Los outputs de terraform quedan disponibles como variables de entorno en
# mayúscula (ej. output "db_host" -> $DB_HOST) para el envsubst de abajo.
while IFS= read -r line; do
  key="${line%%=*}"
  value="${line#*=}"
  export "$key"="$value"
done < <(jq -r 'to_entries[] | "\(.key | ascii_upcase)=\(.value)"' "$tf_outputs_file")
export ACCOUNT_ID="$account_id"

echo "== Aplicando manifiestos de k8s =="
applied_resources_file="$(mktemp)"
: > "$applied_resources_file"

echo "$k8s_manifests" | jq -r '.[]' | while read -r dir; do
  echo "-- kubectl apply (${dir}) --"
  files=("$dir"/*.yml)
  if [ ${#files[@]} -eq 0 ]; then
    echo "❌ No se encontraron archivos *.yml en '${dir}' (listado en k8s_manifests)." >&2
    exit 1
  fi
  # El "\n" antes de "---" evita que un archivo sin salto de línea final
  # corrompa el stream al concatenarlo con el siguiente documento YAML.
  {
    for f in "${files[@]}"; do
      envsubst < "$f"
      printf '\n---\n'
    done
  } | kubectl apply -f - -o name | tee -a "$applied_resources_file"
done

echo "== Esperando a que los Deployments queden listos =="
deployments_file="$(mktemp)"
grep '^deployment\.apps/' "$applied_resources_file" | sort -u > "$deployments_file" || true
while read -r res; do
  kubectl rollout status "$res" --timeout=180s
done < "$deployments_file"

# -----------------------------------------------------------------------
# 6. Terraform apply de post_k8s_stacks (opcional), sobre los mismos outputs.
# -----------------------------------------------------------------------
if [ "$(echo "$post_k8s_stacks" | jq 'length')" -gt 0 ]; then
  echo "== terraform apply: post_k8s_stacks =="
  apply_stacks "$post_k8s_stacks"
else
  echo "-- post_k8s_stacks vacío, se omite --"
fi

echo "✅ Deploy de '${ENVIRONMENT}' completado."
