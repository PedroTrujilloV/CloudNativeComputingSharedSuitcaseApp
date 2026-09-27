aws_region = "us-east-1"
owner      = "pe.trujillo"

lambda_function_name = "grupo33-card-worker"
lambda_role_name = "grupo33-card-worker-role"

image_repository_name = "card-worker"
image_tag = "v0.0.0"

# Names of the resources created by the other stacks (to resolve ARNs).
credit_cards_table_name = "grupo33-credit-cards"
card_verification_topic_name = "grupo33-card-verification-notifications"
queue_name = "grupo33-card-verification"

# Bounded polling budget of a single invocation: worst case 5 attempts x
# 3 s HTTP timeout + 4 waits x 2 s = 23 s, under the 30 s timeout.
poll_max_attempts = 5
poll_interval_seconds = 2
http_timeout_seconds = 3

# Must mirror max_receive_count of the 5_sqs stack: on that last receive
# the worker publishes the POR_VERIFICAR fallback email before the event
# moves to the dead letter queue.
max_receive_count = 5

lambda_timeout_seconds = 30
lambda_memory_mb = 256
