#!/usr/bin/env bash
set -e

echo "------------------ Validating NetworkPolicies ------------------"

EXPECTED_NP=("users-network" "posts-network" "routes-network" "offers-network")
EXPECTED_RULES=(
  "users-network:users-app:users-db"
  "posts-network:posts-app:posts-db"
  "routes-network:routes-app:routes-db"
  "offers-network:offers-app:offers-db"
)

ALL_OK=true

# 1️⃣ Veryfing that all expected NetworkPolicies exist and are correct
for RULE in "${EXPECTED_RULES[@]}"; do
  IFS=':' read -r POLICY FROM TO <<< "$RULE"

  echo "-----------------------------------------------------"
  echo "🔍 NetworkPolicy: $POLICY"

  if kubectl get networkpolicy "$POLICY" >/dev/null 2>&1; then
    echo "✅ Exists: $POLICY"
  else
    echo "❌ Missing: $POLICY"
    ALL_OK=false
    continue
  fi

  # Check destiny selector
  DEST_LABEL=$(kubectl get networkpolicy "$POLICY" -o jsonpath='{.spec.podSelector.matchLabels.app}')
  if [[ "$DEST_LABEL" == "$TO" ]]; then
    echo "✅ Destiny is correct: $DEST_LABEL"
  else
    echo "❌ Destiny mismatch: expected $TO, got $DEST_LABEL"
    ALL_OK=false
  fi

  # Check from selector
  FROM_LABEL=$(kubectl get networkpolicy "$POLICY" -o jsonpath='{.spec.ingress[0].from[0].podSelector.matchLabels.app}')
  if [[ "$FROM_LABEL" == "$FROM" ]]; then
    echo "✅ From is correct: $FROM_LABEL"
  else
    echo "❌ From mismatch: expected $FROM, got $FROM_LABEL"
    ALL_OK=false
  fi

  # Check port
  PORT=$(kubectl get networkpolicy "$POLICY" -o jsonpath='{.spec.ingress[0].ports[0].port}')
  if [[ "$PORT" == "5432" ]]; then
    echo "✅ Port is correct: $PORT"
  else
    echo "❌ Port mismatch: expected 5432, got $PORT"
    ALL_OK=false
  fi

done

echo "-----------------------------------------------------"

# 2️⃣ Verificar que no existan políticas inesperadas
echo "🔍 Checking for unexpected NetworkPolicies..."
EXISTING_NP=$(kubectl get networkpolicy -o jsonpath='{.items[*].metadata.name}')
UNEXPECTED_FOUND=false

for NP in $EXISTING_NP; do
  FOUND=false
  for EXPECTED in "${EXPECTED_NP[@]}"; do
    if [[ "$NP" == "$EXPECTED" ]]; then
      FOUND=true
      break
    fi
  done

  if [ "$FOUND" = false ]; then
    echo "❌ Unexpected NetworkPolicy found: $NP"
    UNEXPECTED_FOUND=true
    ALL_OK=false
  fi
done

if [ "$UNEXPECTED_FOUND" = false ]; then
  echo "✅ No unexpected NetworkPolicies found."
fi

echo "-----------------------------------------------------"

# Resultado final
if [ "$ALL_OK" = true ]; then
  echo "✅✅✅ All NetworkPolicies are correct!"
else
  echo "❌ One or more NetworkPolicies are invalid!"
  exit 1
fi
