# The deploy pipeline (ci_entrega2_deploy.yml) uploads every GitHub
# environment secret except AWS_* and GITHUB_TOKEN to a single AWS Secrets
# Manager secret named "secrets-pipeline-native-map" (a JSON map of
# key: value pairs) before any stack is applied. This stack reads the map
# with a data source and exposes the keys the k8s manifests need as
# Terraform outputs: the pipeline exports every output as an uppercased
# environment variable for the envsubst step that applies the k8s
# manifests (for example, the output "secret_token" becomes $SECRET_TOKEN).
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
