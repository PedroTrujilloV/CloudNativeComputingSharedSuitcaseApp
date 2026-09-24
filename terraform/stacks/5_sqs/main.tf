# SQS stack of the card verification events (Entrega 3, RF-006).
#
# This stack is part of tf_stacks (applied before the k8s manifests) because
# the credit_cards_app manifest needs the queue URL as an environment
# variable at envsubst time, and only the tf_stacks outputs are exported to
# that step of the deploy pipeline. The Lambda function that consumes this
# queue lives in the 6_lambda stack (post_k8s_stacks), because its
# TRUENATIVE_URL points to the ingress load balancer that only exists once
# the k8s manifests are deployed.
#
# Delivery model:
#   * at least once delivery: the consumer (card_worker) must be idempotent,
#     and it is, because it updates the card by id;
#   * dead letter policy: an event that fails the maximum number of
#     receives is moved to the DLQ instead of blocking the queue, so the
#     card stays POR_VERIFICAR (documented fallback of the pattern);
#   * visibility timeout: larger than the worst case invocation of the
#     worker (bounded polling of a few seconds), so a failed invocation
#     redelivers the message right after the visibility window.

resource "aws_sqs_queue" "card_verification_dead_letter" {
  name                       = var.dead_letter_queue_name
  message_retention_seconds  = 345600 # 4 days, the service default
  visibility_timeout_seconds = 30
}

resource "aws_sqs_queue" "card_verification" {
  name                       = var.queue_name
  message_retention_seconds  = 345600 # 4 days, the service default
  visibility_timeout_seconds = var.visibility_timeout_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.card_verification_dead_letter.arn
    maxReceiveCount     = var.max_receive_count
  })
}
