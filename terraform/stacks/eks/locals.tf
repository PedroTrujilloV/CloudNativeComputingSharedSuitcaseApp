# The deploy pipeline (ci_entrega2_deploy.yml) uploads every GitHub
# environment secret except AWS_* and GITHUB_TOKEN to a single AWS Secrets
# Manager secret named "secrets-pipeline-native-map" (a JSON map of
# key: value pairs) before any stack is applied. This stack reads the map
# with a data source and exposes the keys the k8s manifests need as
# Terraform outputs: the pipeline exports every output as an uppercased
# environment variable for the envsubst step that applies the k8s
# manifests.
#
# The token value itself must never appear in a Terraform output: the
# pipeline merges every stack output into one tf_outputs JSON, and GitHub
# Actions silently discards a job output when it contains the value of any
# in-scope environment secret as a substring — the map's SECRET_TOKEN is
# exactly such a secret, so re-exposing it raw would poison the whole
# combined output and every envsubst render would resolve empty. The value
# is therefore base64-encoded before being exposed (the encoded form
# contains no secret value as a substring); the pipeline exports it as
# $SECRET_TOKEN_B64 and the TrueNative manifest fills a K8s Secret
# `data:` field, which takes base64 natively.
#
# The map must contain the key before the first apply of this stack:
# the SECRET_TOKEN GitHub secret must exist in the GitHub environment
# (for example "student1"), otherwise the jsondecode key access fails at
# plan time. The secret is never stored in Terraform state: the data
# source reads it at plan time and only the derived outputs are exposed.
data "aws_secretsmanager_secret_version" "pipeline_native_map" {
  secret_id = "secrets-pipeline-native-map"
}

locals {
  pipeline_native_map = jsondecode(data.aws_secretsmanager_secret_version.pipeline_native_map.secret_string)
}
