locals {
  pipeline_native_map = jsondecode(data.aws_secretsmanager_secret_version.pipeline_native_map.secret_string)

  # The worker reaches TrueNative through the single external host of the
  # platform (the ingress load balancer), with the same URL scheme the
  # evaluator uses (https, self signed certificate, verification disabled
  # in the worker HTTP client).
  truenative_url = "https://${data.aws_lb.ingress.dns_name}"

  # Image based Lambda: the image is built by the deploy pipeline from the
  # card_worker folder and pushed to the ECR repository of the 2_registry
  # stack (same name and tag as the config.yaml entry of card_worker).
  ecr_image_uri = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.image_repository_name}:${var.image_tag}"
}

# IAM execution role of the card worker (least privilege: exactly the three
# integrations of the flow, nothing else).
resource "aws_iam_role" "card_worker" {
  name               = var.lambda_role_name
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "card_worker" {
  name = "${var.lambda_role_name}-policy"
  role = aws_iam_role.card_worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Read and update the card by id in the credit cards table.
      {
        Sid      = "CreditCardsTable"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = [data.aws_dynamodb_table.credit_cards.arn]
      },
      # Consume the verification events (the event source mapping invokes
      # the function on the queue).
      {
        Sid      = "CardVerificationQueue"
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [data.aws_sqs_queue.card_verification.arn]
      },
      # Publish the card result notification to the card topic.
      {
        Sid      = "CardResultTopic"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [data.aws_sns_topic.card_verification.arn]
      },
      # Write the invocation logs to the function log group only.
      {
        Sid    = "WorkerLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_function_name}:*"
        ]
      },
    ]
  })
}

resource "aws_lambda_function" "card_worker" {
  function_name = var.lambda_function_name
  image_uri     = local.ecr_image_uri
  role          = aws_iam_role.card_worker.arn
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  environment {
    variables = {
      APP_NAME                = "card_worker"
      LOG_LEVEL               = "INFO"
      AWS_REGION              = var.aws_region
      DYNAMODB_TABLE_NAME     = data.aws_dynamodb_table.credit_cards.name
      TRUENATIVE_URL          = local.truenative_url
      TRUENATIVE_SECRET_TOKEN = local.pipeline_native_map["SECRET_TOKEN"]
      CARD_RESULT_TOPIC_ARN   = data.aws_sns_topic.card_verification.arn
      POLL_MAX_ATTEMPTS       = var.poll_max_attempts
      POLL_INTERVAL_SECONDS   = var.poll_interval_seconds
      HTTP_TIMEOUT_SECONDS    = var.http_timeout_seconds
      MAX_RECEIVE_COUNT       = var.max_receive_count
    }
  }
}

# One card per invocation: clean idempotency semantics (a failure affects
# only its own message) and no batching window, so the event is delivered
# as soon as the queue polling finds it.
resource "aws_lambda_event_source_mapping" "card_verification" {
  function_name                      = aws_lambda_function.card_worker.function_name
  event_source_arn                   = data.aws_sqs_queue.card_verification.arn
  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
}
