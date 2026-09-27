#!/usr/bin/env bash
# Verifica que las herramientas necesarias para correr los scripts de esta
# carpeta estén instaladas. Uso: check-prerequisites.sh [deploy|destroy|test|all]
#
# No usa "set -e": se recolectan todos los problemas encontrados antes de
# reportar, en vez de detenerse en el primero.
set -uo pipefail

mode="${1:-all}"
missing=()
warnings=()

case "$(uname -s)" in
  Darwin) os="mac" ;;
  MINGW*|MSYS*|CYGWIN*) os="windows" ;;
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then os="wsl"; else os="linux"; fi
    ;;
  *) os="desconocido" ;;
esac

hint() {
  case "$1" in
    git) echo "https://git-scm.com/downloads" ;;
    aws)
      case "$os" in
        mac) echo "brew install awscli" ;;
        windows) echo "choco install awscli" ;;
        *) echo "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" ;;
      esac ;;
    curl)
      case "$os" in
        windows) echo "incluido en Git for Windows; si falta: choco install curl" ;;
        *) echo "instale curl con el gestor de paquetes del sistema" ;;
      esac ;;
    terraform)
      case "$os" in
        mac) echo "brew install terraform" ;;
        windows) echo "choco install terraform" ;;
        *) echo "https://developer.hashicorp.com/terraform/install" ;;
      esac ;;
    docker)
      case "$os" in
        mac|windows) echo "https://www.docker.com/products/docker-desktop" ;;
        *) echo "https://docs.docker.com/engine/install/" ;;
      esac ;;
    kubectl)
      case "$os" in
        mac) echo "brew install kubectl" ;;
        windows) echo "choco install kubernetes-cli" ;;
        *) echo "https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/" ;;
      esac ;;
    helm)
      case "$os" in
        mac) echo "brew install helm" ;;
        windows) echo "choco install kubernetes-helm" ;;
        *) echo "https://helm.sh/docs/intro/install/" ;;
      esac ;;
    jq)
      case "$os" in
        mac) echo "brew install jq" ;;
        windows) echo "choco install jq" ;;
        *) echo "sudo apt-get install jq" ;;
      esac ;;
    yq)
      case "$os" in
        mac) echo "brew install yq" ;;
        windows) echo "choco install yq" ;;
        *) echo "https://github.com/mikefarah/yq#install (binario oficial, no el paquete 'yq' de pip/apt)" ;;
      esac ;;
    envsubst)
      case "$os" in
        mac) echo "brew install gettext && brew link --force gettext" ;;
        windows) echo "choco install gettext" ;;
        *) echo "sudo apt-get install gettext-base" ;;
      esac ;;
    node)
      case "$os" in
        mac) echo "brew install node" ;;
        windows) echo "choco install nodejs-lts" ;;
        *) echo "https://nodejs.org/en/download" ;;
      esac ;;
    npm) echo "se instala junto con node" ;;
    newman) echo "npm install -g newman" ;;
  esac
}

check() {
  local tool="$1"
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  ✅ $tool"
  else
    echo "  ❌ $tool (falta)"
    missing+=("$tool")
  fi
}

case "$mode" in
  deploy)  tools=(git aws curl jq yq terraform docker kubectl helm envsubst) ;;
  destroy) tools=(git aws curl jq yq terraform kubectl helm) ;;
  test)    tools=(git aws curl node npm newman kubectl) ;;
  all)     tools=(git aws curl jq yq terraform docker kubectl helm envsubst node npm newman) ;;
  *)
    echo "Uso: $0 [deploy|destroy|test|all]" >&2
    exit 2
    ;;
esac

echo "Verificando herramientas requeridas (modo: ${mode}, sistema: ${os})"
echo

for t in "${tools[@]}"; do
  check "$t"
done

# yq: en varias distribuciones "yq" es la versión en Python (incompatible con
# la sintaxis usada en estos scripts, que requieren mikefarah/yq v4).
if printf '%s\n' "${tools[@]}" | grep -qx yq && command -v yq >/dev/null 2>&1; then
  if ! yq --version 2>&1 | grep -qi mikefarah; then
    warnings+=("El 'yq' instalado no parece ser mikefarah/yq v4 (requerido). Ver: https://github.com/mikefarah/yq")
  fi
fi

# docker --version no verifica que el daemon esté corriendo.
if printf '%s\n' "${tools[@]}" | grep -qx docker && command -v docker >/dev/null 2>&1; then
  if ! docker info >/dev/null 2>&1; then
    warnings+=("Docker está instalado pero el daemon no responde. Abra Docker Desktop y espere a que inicie.")
  fi
fi

echo
if [ ${#missing[@]} -gt 0 ]; then
  echo "❌ Faltan las siguientes herramientas:"
  for t in "${missing[@]}"; do
    echo "   - ${t}: $(hint "$t")"
  done
fi

if [ ${#warnings[@]} -gt 0 ]; then
  echo "⚠️  Advertencias:"
  for w in "${warnings[@]}"; do
    echo "   - ${w}"
  done
fi

if [ ${#missing[@]} -gt 0 ]; then
  exit 1
fi

echo "✅ Todas las herramientas requeridas están instaladas."
