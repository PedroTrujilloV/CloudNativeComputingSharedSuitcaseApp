#!/usr/bin/env bash
# Replica localmente ci_evaluador_entrega3.yml: descarga la colección de
# Postman de la entrega 3, conecta con el cluster EKS y corre las pruebas de
# Reset, RF-007 y RF-006 con newman.
#
# Uso: bash scripts/test-entrega3.sh
# Configuración: scripts/.env (ver scripts/.env.example)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$SCRIPT_DIR/check-prerequisites.sh" test

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

required_secrets=(AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN EMAIL_TO_NOTIFY)
missing=()
for var in "${required_secrets[@]}"; do
  [ -z "${!var:-}" ] && missing+=("$var")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "❌ Faltan las siguientes variables en scripts/.env:"
  printf '   - %s\n' "${missing[@]}"
  exit 1
fi
echo "✅ Variables requeridas presentes."

# El pipeline de GitHub no recibe la región como input para este workflow, así
# que connect-eks-cluster siempre usa us-east-1 por defecto.
export AWS_DEFAULT_REGION="us-east-1"

evaluator_dir="$SCRIPT_DIR/.evaluator"
mkdir -p "$evaluator_dir"
echo "== Descargando colección de la entrega 3 =="
curl -sSL -o "$evaluator_dir/entrega3.json" \
  https://raw.githubusercontent.com/MISW-4301-Desarrollo-Apps-en-la-Nube/recursos-evaluador/main/entrega3/entrega3.json

echo "== Conectando al cluster EKS =="
aws sts get-caller-identity >/dev/null

cluster_count=$(aws eks list-clusters --query 'length(clusters)' --output text)
if [ "$cluster_count" != "1" ]; then
  echo "❌ Se esperaba exactamente 1 cluster EKS en la cuenta, se encontraron ${cluster_count}." >&2
  exit 1
fi
cluster_name=$(aws eks list-clusters --query 'clusters[0]' --output text)
echo "Cluster detectado: ${cluster_name}"
aws eks update-kubeconfig --region "$AWS_DEFAULT_REGION" --name "$cluster_name"

hostname=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
if [ -z "$hostname" ]; then
  echo "❌ No se pudo obtener el hostname del load balancer de ingress-nginx." >&2
  exit 1
fi
base_path="https://${hostname}"
echo "BASE_PATH: ${base_path}"

# Cada folder corre aunque el anterior haya fallado (igual que "if: always()"
# en el workflow); el resultado final refleja si alguno falló.
overall_status=0

run_folder() {
  local folder="$1"
  shift
  echo "== newman: ${folder} =="
  if ! newman run "$evaluator_dir/entrega3.json" --env-var "BASE_PATH=${base_path}" "$@" --verbose --folder "$folder" --insecure; then
    overall_status=1
  fi
}

run_folder "Reset"
run_folder "RF-007 Verificar identidad" --env-var "EMAIL=${EMAIL_TO_NOTIFY}"
run_folder "RF-006 Tarjetas" --env-var "EMAIL=${EMAIL_TO_NOTIFY}"

if [ "$overall_status" -eq 0 ]; then
  echo "✅ Pruebas de entrega 3 completadas sin errores."
else
  echo "❌ Al menos una prueba de entrega 3 falló (ver detalle arriba)." >&2
fi
exit "$overall_status"
