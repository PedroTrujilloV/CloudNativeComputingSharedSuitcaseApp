#!/usr/bin/env bash
set -e

echo "🔍 Searching block traffic NetworkPolicies"

# List all the policies with prefix 'block-'
BLOCK_POLICIES=$(kubectl get networkpolicy -n default --no-headers | awk '/^block-/ {print $1}')

if [ -z "$BLOCK_POLICIES" ]; then
  echo "✅ No blocking NetworkPolicies."
  exit 0
fi

echo "🗑️ Removing NetworkPolicies:"
echo "$BLOCK_POLICIES"

# Delete each blocking NetworkPolicy
for POLICY in $BLOCK_POLICIES; do
  kubectl delete networkpolicy "$POLICY" -n default
done

echo "✅ All the block NetworkPolicies were removed."
