# SNS Email Stack (4_sns)

## Overview

The **4_sns** stack provisions the base infrastructure of the email
notification mechanism of Entrega 3: two Amazon SNS topics with email
protocol subscriptions. The project document recommends SNS for the
mandatory email notification, and this stack is the home of that
mechanism: one topic per requirement, so each producer publishes to the
topic that matches its own result.

The subscription address is never hardcoded: it is read at plan time from
the `EMAIL_TO_NOTIFY` key of the `secrets-pipeline-native-map` secret in
AWS Secrets Manager, which the deploy pipeline
(`ci_entrega2_deploy.yml`) populates from the GitHub environment secrets
before any stack is applied.

## Components

| Resource | Description |
|---|---|
| **SNS topic: card verification** | Receives the card registration result of RF-006, published by the `card_worker` Lambda function. One email protocol subscription. |
| **SNS topic: user verification** | Receives the identity verification result of RF-007, published by the `user_verification_callback` service. One email protocol subscription. |
| **Email subscriptions** | One per topic. The endpoint is the `EMAIL_TO_NOTIFY` value from the `secrets-pipeline-native-map` secret. While the subscription is pending, SNS discards the messages. |

## Pipeline secrets (EMAIL_TO_NOTIFY)

The deploy pipeline uploads every GitHub environment secret except `AWS_*`
and `GITHUB_TOKEN` to the AWS Secrets Manager secret
`secrets-pipeline-native-map` (a JSON map) before any stack is applied.
This stack reads the map with a data source and takes the
`EMAIL_TO_NOTIFY` key:

```hcl
data "aws_secretsmanager_secret_version" "pipeline_native_map" {
  secret_id = "secrets-pipeline-native-map"
}

locals {
  pipeline_native_map = jsondecode(data.aws_secretsmanager_secret_version.pipeline_native_map.secret_string)
  email_to_notify     = local.pipeline_native_map["EMAIL_TO_NOTIFY"]
}
```

The `EMAIL_TO_NOTIFY` GitHub secret must exist in the GitHub environment
(for example `student1`) before the first apply of this stack: if the key
is missing from the secret, the `jsondecode` key access fails at plan
time. The value is never stored in Terraform state, and no email address
appears in this repository.

The secret itself is created and populated only by the deploy pipeline,
so a local plan on a fresh account (the helper scripts
`1_init_all.sh` and `2_plan_all.sh` in `scripts/terraform_scripts/`) runs
before the secret exists and the data source cannot read it. The
`0_bootstrap_state_bucket.sh` script handles this step for you: it reads
`EMAIL_TO_NOTIFY` from the out-of-repo `truenative_secrets/dev.env` file
(the same file that `scripts/local-deploy.sh` uses for `SECRET_TOKEN`)
and creates the secret once. Alternatively, create the secret manually
with the AWS CLI:

```bash
aws secretsmanager create-secret \
  --name secrets-pipeline-native-map \
  --secret-string '{"EMAIL_TO_NOTIFY": "local-test@example.com"}' \
  --region us-east-1
```

A local test value is safe: the deploy pipeline overwrites the secret on
every run, so the pipeline always plans with the real `EMAIL_TO_NOTIFY`
value. The local value is only a plan input: it is not part of the
deployed infrastructure, and no real email address is stored in this
repository.

## Manual confirmation step

**A manual step is required after every deploy.** When the stack creates
(or recreates) a subscription, Amazon SNS sends a subscription
confirmation email to the `EMAIL_TO_NOTIFY` address. The link in that
email must be clicked once per subscription before any message is
delivered; while a subscription is pending, SNS discards the messages.
This is documented in the repository `README.md` (Cloud Deployment
Procedure, Step 3) and it runs between the deploy pipeline and the
evaluator pipeline.

## Variables

| Variable | Type | Description |
|---|---|---|
| `aws_region` | `string` | AWS region (always `us-east-1`). |
| `owner` | `string` | Owner tag for the resources. |
| `card_verification_topic_name` | `string` | Name of the RF-006 card verification topic. |
| `user_verification_topic_name` | `string` | Name of the RF-007 identity verification topic. |

## Outputs

| Output | Description |
|---|---|
| `card_verification_topic_arn` | ARN of the RF-006 card verification topic. |
| `user_verification_topic_arn` | ARN of the RF-007 identity verification topic. |
| `email_endpoint` | The subscription address, read from the secret (sensitive). |

## Deployment Order

The stack is listed in the `tf_stacks` key of `config.yaml`, after the
`eks` stack. The deploy pipeline applies the stacks in that order, and
the destroy pipeline destroys them in reverse order. The helper scripts
in `scripts/terraform_scripts/` (`1_init_all.sh`, `2_plan_all.sh`,
`3_apply_reviewed.sh`, `zz_destroy_all.sh`) discover the stack
automatically from the `terraform/environments/<environment>/4_sns/`
folder.

## Manual Verification

```bash
# From repo root, after the deploy:
aws sns list-topics --region us-east-1
aws sns list-subscriptions --region us-east-1
# Check the EMAIL_TO_NOTIFY inbox for the confirmation emails and click
# the link of each subscription.
```

## Important Notes

* The topics use the default naming given in the environment tfvars. The
  names keep the `grupo33` prefix of the other AWS resources of this
  project, but use a flat form (for example
  `grupo33-card-verification-notifications`) because an SNS topic name
  cannot contain a slash: only letters, digits, hyphens, and underscores
  are allowed.
* The producers of the messages (the `card_worker` function and the
  `user_verification_callback` service) receive the topic ARNs from the
  pipeline: the pipeline exports every stack output as an uppercased
  environment variable, so `card_verification_topic_arn` becomes
  `$CARD_VERIFICATION_TOPIC_ARN` and `user_verification_topic_arn`
  becomes `$USER_VERIFICATION_TOPIC_ARN` for the envsubst step that
  applies the Kubernetes manifests.
* No email address, credential, or secret value is stored in this
  repository or in the Terraform state.
