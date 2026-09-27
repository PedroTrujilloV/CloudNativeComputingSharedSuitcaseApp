# Credit Cards DynamoDB Stack (3_dynamodb)

## Overview

The **3_dynamodb** stack provisions the dedicated storage of the
`credit_cards_app` (Entrega 3, RF-006): one Amazon DynamoDB table that holds
the `CreditCard` entity. The table is exclusive to the credit cards
application, so the new requirement keeps its data isolated from the shared
PostgreSQL instance of the legacy applications, as the course data ownership
rule requires.

The table name comes from the environment tfvars
(`credit_cards_table_name`), and it follows the team naming convention with
the `grupo33` prefix (the same prefix the SNS topics of `4_sns` use).

## Components

| Resource | Description |
|---|---|
| **DynamoDB table: credit cards** | Stores the `CreditCard` entity with partition key `id` (the card UUID) and the global secondary index `userId-index` (partition key `userId`, projection `ALL`), which turns the per owner listing into a single DynamoDB query. |

Key design decisions:

* **Partition key `id`**: the card worker updates the status by card id, so
  the update path never touches the index.
* **GSI `userId-index`**: the `GET /credit-cards` endpoint lists the cards of
  the caller, and the duplicate check of `POST /credit-cards` needs the cards
  of one user. Both read through the index instead of scanning the table.
* **PAY_PER_REQUEST billing**: the traffic is small and spiky, so on demand
  billing avoids any capacity planning.
* **Flat string items**: every attribute is stored as a string (dates in ISO
  `yyyy-mm-ddTHH:MM:SS`, UTC 0), so the application maps the entity to items
  without any DynamoDB type conversion.
* **Server side encryption**: enabled at the table level, no extra
  configuration on the application side.

## Who accesses the table

| Component | Access |
|---|---|
| `credit_cards_app` | Reads and writes the cards it owns (the data owner). |
| `card_worker` | Updates the status and `updatedAt` by card id while completing the asynchronous verification. |

No other component of the platform is allowed to read or write this table.
The legacy applications keep using the shared RDS PostgreSQL instance of the
`1_database` stack and never touch DynamoDB.

## Variables

| Variable | Description |
|---|---|
| `aws_region` | AWS region of the resources (`us-east-1`). |
| `owner` | Owner tag of the resources. |
| `credit_cards_table_name` | Name of the table (environment specific, `grupo33-credit-cards` in the committed environments). |

## Outputs

| Output | Description |
|---|---|
| `credit_cards_table_name` | Name of the table. |

The output is exposed to the Kubernetes manifest step of the deploy
pipeline as the environment variable `CREDIT_CARDS_TABLE_NAME`, so the
`credit_cards_app` manifest can read the table name without hardcoding
it. The table ARN is deliberately not exposed: it embeds the AWS account
id (the value of the `ACCOUNT_ID` environment secret), and the pipeline
merges every stack output into a single JSON that GitHub Actions
silently discards when it contains a secret value. The ARN remains
available via `aws dynamodb describe-table`.

## Local plan prerequisite

The stack uses the shared S3 state backend like the rest of the stacks. The
state bucket must exist before the first `terraform init` (see the
`0_storage` stack and `scripts/terraform_scripts/0_bootstrap_state_bucket.sh`
for the bootstrap). No pipeline secret is required for a local plan.
