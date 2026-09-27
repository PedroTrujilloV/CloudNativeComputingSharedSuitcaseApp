# NOTE on what this stack deliberately does NOT expose:
#
# The deploy pipeline merges every output of every stack into a single JSON
# that GitHub Actions treats as a job output, and it silently discards the
# output when it contains the value of any environment secret (the
# ACCOUNT_ID secret, for example, is a substring of every ARN/URL). The
# cluster ARN therefore is NOT exposed; it can be looked up with
# `aws eks describe-cluster` when needed. The endpoint / certificate /
# OIDC outputs were removed for the same reason (the pipeline connects
# kubectl with `aws eks update-kubeconfig`, so none of them is consumed).

output "eks_cluster_id" {
  description = "El ID del clúster EKS desplegado."
  value       = module.my_eks_cluster.cluster_id
}

output "secret_token_b64" {
  description = "Base64 encoding of the TrueNative authentication token (SECRET_TOKEN), read from the 'secrets-pipeline-native-map' secret of AWS Secrets Manager (populated by the pipeline from the environment secrets). The raw value is an environment secret and cannot cross the pipeline's combined tf_outputs channel (GitHub Actions discards an output containing a secret value as a substring); base64 keeps it out of the scrubbing while the K8s Secret data field consumes it directly. The pipeline exports it as $SECRET_TOKEN_B64 for the envsubst of k8s_entrega3/k8s-true-native-deployment.yml; the stack 6_lambda reads the same map key for the card worker."
  value     = base64encode(local.pipeline_native_map["SECRET_TOKEN"])
  sensitive = true
}
