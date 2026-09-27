# Card Verification Queue Stack (5_sqs)

## Overview

The **5_sqs** stack provisions the asynchronous seam of the RF-006 flow:
the Amazon SQS queue that carries the card verification events from
`credit_cards_app` to the `card_worker` Lambda function, plus its dead
letter queue and redrive policy.

The queue name follows the team naming convention with the `grupo33`
prefix (the same prefix the DynamoDB table of `3_dynamodb` and the SNS
topics of `4_sns` use).

## Why this stack is in tf_stacks and not post_k8s_stacks

The deploy pipeline exports to the `envsubst` step of the k8s manifests
only the outputs of the `tf_stacks` stacks. The credit cards manifest
needs the queue URL as an environment variable
(`CARD_VERIFICATION_QUEUE_URL`), so the queue must exist before the k8s
manifests are applied. The consuming side of the seam, the Lambda
function, is provisioned by the `6_lambda` stack in
`post_k8s_stacks`, because its `TRUENATIVE_URL` points to the ingress
load balancer that only exists once the k8s manifests are deployed.

## Components

| Resource | Description |
|---|---|
| **SQS queue: card verification** | Receives the `CARD_VERIFICATION_REQUESTED` events published by `credit_cards_app` right after storing a card as `POR_VERIFICAR`. Visibility timeout 45 s (larger than the worst case worker invocation). |
| **SQS queue: dead letter** | Receives the events that fail `maxReceiveCount` times (5) while being processed by the worker. Retention 4 days (the service default) for operator inspection. |
| **Redrive policy** | Moves a message to the dead letter queue after 5 failed receives, so a permanently failing event does not block the queue. |

## Delivery model and fallback

* **At least once delivery**: the worker is idempotent by card id, so a
  redelivered event only rewrites the same terminal state.
* **Fallback (no terminal state)**: when the worker exhausts its bounded
  polling attempts the invocation fails on purpose, the queue redelivers
  the event, and the card stays `POR_VERIFICAR` (a valid state). After the
  maximum number of receives the event is moved to the dead letter queue
  and the card remains `POR_VERIFICAR`. This is the documented fallback of
  the RF-006 pattern (solution patterns view); the card never ends in an
  inconsistent state and the event is never lost.

## Who accesses the queue

| Component | Access |
|---|---|
| `credit_cards_app` | Sends the verification events (producer). |
| `card_worker` | Receives and deletes the events (consumer, through the SQS event source mapping created by `6_lambda`). |

## Variables

| Variable | Description |
|---|---|
| `aws_region` | AWS region of the resources (`us-east-1`). |
| `owner` | Owner tag of the resources. |
| `queue_name` | Name of the card verification queue (`grupo33-card-verification`). |
| `dead_letter_queue_name` | Name of the dead letter queue (`grupo33-card-verification-dlq`). |
| `max_receive_count` | Failed receives before the message moves to the dead letter queue (5). |
| `visibility_timeout_seconds` | Visibility timeout of the queue (45). |
| `db_username`, `db_password` | Unused; declared only because the course evaluation workflow always passes them via `-var`. |

## Outputs

| Output | Description |
|---|---|
| `card_verification_queue_name` | Name of the queue; exposed to the k8s manifest step as `CARD_VERIFICATION_QUEUE_NAME`, from which the manifest reconstructs the full URL. |

The queue URL/ARN are deliberately not exposed: they embed the AWS
account id (the value of the `ACCOUNT_ID` environment secret), and the
deploy pipeline merges every stack output into a single JSON that GitHub
Actions silently discards when it contains a secret value. The URLs
remain available via `aws sqs list-queues`.

## Local plan prerequisite

The stack uses the shared S3 state backend like the rest of the stacks.
The state bucket must exist before the first `terraform init` (see the
`0_storage` stack and `scripts/terraform_scripts/0_bootstrap_state_bucket.sh`
for the bootstrap). No pipeline secret is required for a local plan.
