# The ingress load balancer is created by the EKS cloud controller manager
# when the deploy pipeline installs the ingress-nginx controller (helm,
# LoadBalancer service) during the k8s manifests step. It carries the
# standard kubernetes service name tag, the same tag the destroy pipeline
# filters on to wait for the balancer to be deleted. This stack is in
# post_k8s_stacks precisely so that the balancer already exists at plan
# time: the worker needs its host as TRUENATIVE_URL, and the rest of the
# system (including the evaluator) reaches TrueNative through this single
# external host. If the balancer is not found (for example a local plan
# before the k8s manifests exist), the data source fails the plan with a
# clear error.
data "aws_lb" "ingress" {
  tags = {
    "kubernetes.io/service-name" = "ingress-nginx/ingress-nginx-controller"
  }
}

# The credit cards table is owned by the 3_dynamodb stack; the worker only
# needs its ARN for the least privilege policy.
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
# mapping and the least privilege policy reference its ARN.
data "aws_sqs_queue" "card_verification" {
  name = var.queue_name
}

# The deploy pipeline uploads every GitHub environment secret except AWS_*
# and GITHUB_TOKEN to this secret before any stack is applied; the worker
# reads the SECRET_TOKEN key from the map (same pattern as the eks stack).
# The secret must exist before the first apply of this stack: the
# SECRET_TOKEN GitHub secret must be configured in the environment.
data "aws_secretsmanager_secret_version" "pipeline_native_map" {
  secret_id = "secrets-pipeline-native-map"
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}
