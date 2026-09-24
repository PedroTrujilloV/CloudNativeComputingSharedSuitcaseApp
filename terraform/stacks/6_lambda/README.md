# Card Worker Lambda Stack (6_lambda)

## Overview

The **6_lambda** stack provisions the consuming side of the asynchronous
seam of RF-006: the `card_worker` Lambda function (image based, built from
the `card_worker` folder per `config.yaml`), its least privilege execution
role, and the SQS event source mapping that connects it to the card
verification queue created by the `5_sqs` stack.

The worker consumes the `CARD_VERIFICATION_REQUESTED` events, polls
TrueNative `GET /native/cards/{ruv}` a bounded number of times per
invocation, and updates the terminal status and `updatedAt` of the card in
the DynamoDB table owned by `credit_cards_app`.

## Why this stack is in post_k8s_stacks

The `TRUENATIVE_URL` environment variable of the function points to the
load balancer of the ingress-nginx controller, which only exists once the
k8s manifests are deployed. That is why this stack is applied after the
kubernetes step (`post_k8s_stacks` in `config.yaml`): the stack discovers
the balancer with an `aws_lb` data source filtered by the
standard service name tag
(`kubernetes.io/service-name = ingress-nginx/ingress-nginx-controller`),
the same tag the destroy pipeline uses to wait for the balancer to be
deleted. The queue itself lives in the `5_sqs` stack (in `tf_stacks`)
because the credit cards manifest needs the queue URL at envsubst time.

## Components

| Resource | Description |
|---|---|
| **Lambda function: card worker** | Image based function (`card-worker` repository of ECR, tag per `config.yaml`). Timeout 30 s, memory 256 MB. Environment: table name, `TRUENATIVE_URL` (ingress host), `TRUENATIVE_SECRET_TOKEN` (from the `secrets-pipeline-native-map` secret, never committed), card topic ARN, and the bounded polling settings. |
| **IAM role: card worker** | Execution role of the function with least privilege, exactly the three integrations of the flow plus the function logs (see below). |
| **SQS event source mapping** | Invokes the function on the card verification queue with `batch_size` 1 (one card per invocation, clean idempotency) and no batching window (the event is delivered as soon as it is visible). |

## Least privilege role

The role assumes only `lambda.amazonaws.com` and its inline policy allows,
each on a single resource ARN:

* `dynamodb:GetItem` and `dynamodb:PutItem` on the credit cards table.
* `sqs:ReceiveMessage`, `sqs:DeleteMessage`, and `sqs:GetQueueAttributes`
  on the card verification queue.
* `sns:Publish` on the card verification topic (the result notification of
  the epic; the permission is granted now so the next task only adds the
  publish call in the code).
* `logs:CreateLogGroup`, `logs:CreateLogStream`, and `logs:PutLogEvents`
  on the log group of this function only.

The `SECRET_TOKEN` value is read at plan time from the
`secrets-pipeline-native-map` secret in AWS Secrets Manager (the deploy
pipeline populates it from the GitHub environment secrets) and injected as
an environment variable; it never appears in this repository.

## Timing model

One invocation polls up to `poll_max_attempts` times (5) with
`poll_interval_seconds` (2 s) between attempts and `http_timeout_seconds`
(3 s) per request, so the worst case invocation is under the 30 s timeout.
When the attempts are exhausted the invocation fails on purpose, the queue
redelivers the event (visibility timeout 45 s in `5_sqs`), and the card
stays `POR_VERIFICAR`; after `maxReceiveCount` receives the event is moved
to the dead letter queue (documented fallback of the RF-006 pattern).

## Variables

| Variable | Description |
|---|---|
| `aws_region` | AWS region of the resources (`us-east-1`). |
| `owner` | Owner of the resources. |
| `lambda_function_name` | Name of the function (`grupo33-card-worker`). |
| `lambda_role_name` | Name of the execution role (`grupo33-card-worker-role`). |
| `image_repository_name` | ECR repository of the worker image (`card-worker`). |
| `image_tag` | Image tag (`v0.0.0`, per `config.yaml`). |
| `credit_cards_table_name` | Credit cards table name (to resolve its ARN). |
| `card_verification_topic_name` | Card verification topic name (to resolve its ARN). |
| `queue_name` | Card verification queue name (to resolve its ARN). |
| `poll_max_attempts` | Bounded attempts per invocation (5). |
| `poll_interval_seconds` | Wait between two attempts (2). |
| `http_timeout_seconds` | Timeout per polling request (3). |
| `lambda_timeout_seconds` | Function timeout (30). |
| `lambda_memory_mb` | Function memory (256). |
| `db_username`, `db_password` | Unused; declared only because the course evaluation workflow always passes them via `-var`. |

## Outputs

| Output | Description |
|---|---|
| `card_worker_function_name` | Name of the function. |
| `card_worker_function_arn` | ARN of the function. |
| `card_worker_role_arn` | ARN of the execution role. |
| `card_worker_truenative_url` | Base URL used by the worker to reach TrueNative (ingress host). |

## Plan prerequisites

* The k8s manifests must be deployed (the ingress load balancer must
  exist); otherwise the data source precondition fails.
* The `5_sqs` and `4_sns` stacks must be applied (the queue and the topic
  must exist to resolve their ARNs).
* The `secrets-pipeline-native-map` secret must exist with the
  `SECRET_TOKEN` key (created by the deploy pipeline from the GitHub
  environment secrets).
