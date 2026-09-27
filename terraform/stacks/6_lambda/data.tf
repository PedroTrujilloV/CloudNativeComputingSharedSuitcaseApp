# The credit cards table is owned by the 3_dynamodb stack; the worker
# resolves its name for the DYNAMODB_TABLE_NAME environment variable.
data "aws_dynamodb_table" "credit_cards" {
  name = var.credit_cards_table_name
}

# The card verification topic is owned by the 4_sns stack; the worker
# publishes the card result notification there (the email task of the epic
# that follows).
data "aws_sns_topic" "card_verification" {
  name = var.card_verification_topic_name
}

# The card verification queue is owned by the 5_sqs stack; the event source
# mapping references its ARN.
data "aws_sqs_queue" "card_verification" {
  name = var.queue_name
}

# TrueNative token: the deploy pipeline uploads every GitHub environment
# secret except AWS_* and GITHUB_TOKEN to the 'secrets-pipeline-native-map'
# secret before any stack is applied; the worker reads the SECRET_TOKEN key
# from the map (same pattern as the eks stack). The secret is never stored
# in Terraform state: the data source reads it at plan time.
data "aws_secretsmanager_secret_version" "pipeline_native_map" {
  secret_id = "secrets-pipeline-native-map"
}

data "aws_caller_identity" "current" {}
