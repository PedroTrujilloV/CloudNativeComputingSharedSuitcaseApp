# The deploy pipeline (ci_entrega2_deploy.yml) uploads every GitHub
# environment secret except AWS_* and GITHUB_TOKEN to a single AWS Secrets
# Manager secret named "secrets-pipeline-native-map" (a JSON map of
# key: value pairs) before any stack is applied. This stack reads the map
# with a data source and uses the EMAIL_TO_NOTIFY key as the endpoint of
# the email subscriptions, so no email address is ever hardcoded in this
# repository.
#
# The pipeline creates and populates the secret before any stack is applied,
# so during a real pipeline run the data source reads the EMAIL_TO_NOTIFY
# value at plan time. On a fresh local account the secret does not exist
# yet (only the pipeline creates it), so a local plan needs the secret to
# be present first. The 0_bootstrap_state_bucket.sh script creates it once
# from the EMAIL_TO_NOTIFY line of the out-of-repo truenative_secrets/dev.env
# file; alternatively, create it manually with the aws cli:
#   aws secretsmanager create-secret --name secrets-pipeline-native-map
#     --secret-string '{"EMAIL_TO_NOTIFY": "local-test@example.com"}'
# The pipeline overwrites the secret on every deploy, so a local test value
# is safe. The secret value is never stored in Terraform state: the data
# source reads it at plan time and only the subscription resources are
# created from it.
data "aws_secretsmanager_secret_version" "pipeline_native_map" {
  secret_id = "secrets-pipeline-native-map"
}

locals {
  pipeline_native_map = jsondecode(data.aws_secretsmanager_secret_version.pipeline_native_map.secret_string)
  email_to_notify     = local.pipeline_native_map["EMAIL_TO_NOTIFY"]
}
