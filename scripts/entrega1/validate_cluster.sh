#!/usr/bin/env bash

set -e

# Expected pods to be present in the cluster
EXPECTED_PODS=("users-db" "offers-db" "posts-db" "routes-db" "users-app" "offers-app" "posts-app" "routes-app")

# Services expected to be present in the cluster with their target pods
declare -A EXPECTED_SERVICES
EXPECTED_SERVICES=(
    ["users-db-service"]="users-db"
    ["offers-db-service"]="offers-db"
    ["posts-db-service"]="posts-db"
    ["routes-db-service"]="routes-db"
    ["users-app-service"]="users-app"
    ["offers-app-service"]="offers-app"
    ["posts-app-service"]="posts-app"
    ["routes-app-service"]="routes-app"
)

# Database deployments expected to have volumes defined and mounted
DB_DEPLOYMENTS=("users-db" "offers-db" "posts-db" "routes-db")

echo "✅ Checking expected pods..."
TOTAL_PODS=${#EXPECTED_PODS[@]}
FOUND_PODS=0

for POD in "${EXPECTED_PODS[@]}"; do
    if kubectl get pods | grep -q "$POD"; then
        echo "✔️ $POD found"
        FOUND_PODS=$((FOUND_PODS+1))
    else
        echo "❌ $POD NOT found"
    fi
done

echo "✅ Checking expected services and their targets..."
TOTAL_SERVICES=${#EXPECTED_SERVICES[@]}
FOUND_SERVICES=0

for SERVICE in "${!EXPECTED_SERVICES[@]}"; do
    TARGET_POD=${EXPECTED_SERVICES[$SERVICE]}
    if kubectl get svc | grep -q "$SERVICE"; then
        echo "✔️ $SERVICE exists"
        SELECTOR=$(kubectl get svc "$SERVICE" -o jsonpath='{.spec.selector.app}')
        if [ "$SELECTOR" == "$TARGET_POD" ]; then
            echo "✔️ $SERVICE points to $TARGET_POD"
            FOUND_SERVICES=$((FOUND_SERVICES+1))
        else
            echo "❌ $SERVICE does not point to $TARGET_POD (found selector: $SELECTOR)"
        fi
    else
        echo "❌ Service $SERVICE NOT found"
    fi
done

echo "✅ Checking DB deployments for volumes..."
TOTAL_DB_DEPLOYMENTS=${#DB_DEPLOYMENTS[@]}
FOUND_DB_DEPLOYMENTS=0

for DB in "${DB_DEPLOYMENTS[@]}"; do
    DEPLOYMENT_NAME="$(kubectl get deployment -l "app=$DB" -n "default" -o name --ignore-not-found | head -n1)"
    if [ -n "$DEPLOYMENT_NAME" ]; then
        DEPLOYMENT_NAME=$(kubectl get deployment -l app="$DB" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        echo "✔️ $DEPLOYMENT_NAME exists"

        VOLUMES=$(kubectl get deployment "$DEPLOYMENT_NAME" -o jsonpath='{.spec.template.spec.volumes[*].name}' 2>/dev/null || echo "")
        VOLUME_MOUNTS=$(kubectl get deployment "$DEPLOYMENT_NAME" -o jsonpath='{.spec.template.spec.containers[*].volumeMounts[*].name}' 2>/dev/null || echo "")

        if [ -n "$VOLUMES" ] && [ -n "$VOLUME_MOUNTS" ]; then
            echo "✔️ $DEPLOYMENT_NAME has volumes defined and mounted"
            FOUND_DB_DEPLOYMENTS=$((FOUND_DB_DEPLOYMENTS+1))
        else
            echo "❌ $DEPLOYMENT_NAME is missing volumes or volume mounts"
        fi
    else
        echo "❌ Deployment for $DB NOT found"
    fi
done

# Final summary
TOTAL_FOUND=$(( FOUND_PODS + FOUND_SERVICES + FOUND_DB_DEPLOYMENTS ))
TOTAL_COMPONENTS=$(( TOTAL_PODS + TOTAL_SERVICES + TOTAL_DB_DEPLOYMENTS ))

COMPONENTS_PERCENT=$(( TOTAL_FOUND * 100 / TOTAL_COMPONENTS ))
echo "-----------------------------------------------------"
echo "✅ Summary of checks:"
echo "🚀 Components correctly configured: ${COMPONENTS_PERCENT}%"

if [ $TOTAL_FOUND -lt $TOTAL_COMPONENTS ]; then
    echo "❌ Not all components are correctly configured."
    exit 1
fi
echo "✔️ All components are correctly configured."
exit 0
