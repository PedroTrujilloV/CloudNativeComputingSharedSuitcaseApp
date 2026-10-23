

## Project Structure

```text
.
├── users_app/                     # User management application (modified in Entrega 3: no token generation or verification while the user is not VERIFICADO)
├── routes_app/                    # Route management application
├── posts_app/                     # Post management application
├── offers_app/                    # Offer management application
├── scores_app/                    # Scores management application (Entrega 2)
├── rf003_create_post_app/         # RF-003 orchestrator (Entrega 2)
├── rf004_create_offer_app/        # RF-004 orchestrator (Entrega 2)
├── rf005_query_post_app/          # RF-005 orchestrator (Entrega 2)
├── credit_cards_app/              # Credit cards service (Entrega 3, RF-006): owns the CreditCard entity and its DynamoDB table
├── card_worker/                   # Card verification worker (Entrega 3, RF-006): AWS Lambda function that polls TrueNative until the card reaches a terminal state
├── user_verification_callback/    # User verification callback (Entrega 3, RF-007): receives the TrueNative identity verification callback and updates the user status
├── k8s/                           # Legacy Entrega 1 Kubernetes manifests
├── k8s_entrega2/                  # Kubernetes manifests (secrets, apps, ingress, local-only shared DB); in Entrega 3 it gains the RF-007 callback manifest (28-user-verification-callback.yml)
├── k8s_entrega3/                  # Entrega 3 manifests (TrueNative deployment and the credit cards Deployment + Service, rendered with envsubst at apply time)
├── terraform/                     # Terraform stacks and environments for the AWS infrastructure
│   ├── stacks/                    # One folder per stack: 0_storage, 1_database, 2_registry, 3_dynamodb, eks, 4_sns, 5_sqs, 6_lambda
│   ├── modules/                   # Shared modules used by the stacks (rds, eks, repository, secrets_manager, storage)
│   └── environments/              # One folder per environment (dev, student1), each holding the tfvars of every stack
├── scripts/                       # Local deploy/verify scripts, Postman collections, Terraform helper scripts
├── plantuml-generator/            # Docker image that renders the PlantUML diagrams
├── styles/                        # Vale style packages for the documentation checks
├── docs/                          # Technical documentation as code
│   └── diagrams/                  # PlantUML diagrams (entities, components, deployment, networks, sequences)
├── config.yaml                    # Team and application configuration
└── README.md                      # This file
```

More detailed information in the [Development View](./docs/development-view.md)
and [Technical Documentation](./docs/README.md)






# Deployment Guide

This guide describes, step by step, how to fully deploy the project: the applications (the five microservices, the three orchestrators, and the new components of Entrega 3), their databases, the generation of the technical documentation (PlantUML diagrams), the cloud deployment with the provided pipelines, and the final validation on Minikube.

## Table of Contents

- [Deployment Guide](#deployment-guide)
  - [Table of Contents](#table-of-contents)
  - [Delivery 2 (Entrega 2) Changes](#delivery-2-entrega-2-changes)
  - [Delivery 3 (Entrega 3) Changes](#delivery-3-entrega-3-changes)
  - [Terraform Stacks](#terraform-stacks)
  - [How to run](#how-to-run)
  - [Cloud Deployment (AWS)](#cloud-deployment-aws)
  - [Cloud Deployment Procedure (Entrega 3)](#cloud-deployment-procedure-entrega-3)
    - [Prerequisites for the Cloud Deployment](#prerequisites-for-the-cloud-deployment)
    - [Step 1: Verify the config.yaml and the GitHub secret](#step-1-verify-the-configyaml-and-the-github-secret)
    - [Step 2: Run the Deploy Pipeline](#step-2-run-the-deploy-pipeline)
    - [Step 3: Confirm the SNS Email Subscriptions (manual step)](#step-3-confirm-the-sns-email-subscriptions-manual-step)
    - [Step 4: Run the Evaluator Pipeline](#step-4-run-the-evaluator-pipeline)
    - [Step 5: Run the Destroy Pipeline](#step-5-run-the-destroy-pipeline)
  - [Testing Toolchain](#testing-toolchain)
  - [Prerequisites](#prerequisites)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Verify config.yaml](#step-2-verify-configyaml)
  - [Step 3: Generate Technical Documentation (PlantUML)](#step-3-generate-technical-documentation-plantuml)
  - [Step 4: Run Each Application Locally (Optional, for Development)](#step-4-run-each-application-locally-optional-for-development)
  - [Step 5: Build the Docker Images](#step-5-build-the-docker-images)
  - [Step 6: Start Minikube](#step-6-start-minikube)
  - [Step 7: Load the Images into Minikube](#step-7-load-the-images-into-minikube)
  - [Step 8: Deploy the Kubernetes Manifests](#step-8-deploy-the-kubernetes-manifests)
  - [Step 9: Verify the Deployment](#step-9-verify-the-deployment)
  - [Step 10: Access the Applications via Ingress](#step-10-access-the-applications-via-ingress)
  - [Step 11: Test the API with Postman](#step-11-test-the-api-with-postman)
  - [Step 12: Run the Validation Pipelines](#step-12-run-the-validation-pipelines)
  - [Step 13: Cleanup (Optional)](#step-13-cleanup-optional)
  - [Troubleshooting Common Issues](#troubleshooting-common-issues)

## Delivery 2 (Entrega 2) Changes

Entrega 2 extends the Delivery 1 system with three new elements:

* **`scores_app`:** a new microservice that persists a Score (Utilidad) value
  per offer. It is written by the RF-004 orchestrator and read (null-safely)
  by the RF-005 orchestrator. Its image is `scores-app:v0.0.0` per
  `config.yaml`.
* **Orchestrators:** `rf003_create_post_app`, `rf004_create_offer_app`, and
  `rf005_query_post_app` expose the client-facing endpoints for requirements
  RF-003, RF-004, and RF-005, coordinating calls to the existing services.
  Each orchestrator is stateless (no database of its own), uses Clean
  Architecture internally, and handles downstream failures: integration errors
  return HTTP 503 with a standard Spanish message; business rejections from
  downstream services pass through unchanged (HTTP 412 for example invalid
  dates or duplicate posts). The RF-003 orchestrator additionally implements
  saga compensation to avoid orphaned data when the post creation fails mid-flow.
* **Shared database:** both cloud and local deployments use a single PostgreSQL instance. In production (Terraform stacks) all applications share an AWS RDS instance with per-app schema and role isolation. The local Minikube model mirrors this architecture via `k8s_entrega2/local-only/15-shared-db.yml` a single shared Postgres Deployment with per-app databases and PostgreSQL-level role isolation applied by `local-deploy.sh` (this folder is excluded from `config.yaml k8s_manifests`).

The rest of the guide below documents the Delivery 1 local deployment model;
the `scores_app` build/run steps follow the same pattern as the other
applications (see its [README](./scores_app/README.md)).


## Delivery 3 (Entrega 3) Changes

Entrega 3 adds the two new requirements (RF-006, credit card registration, and
RF-007, user identity verification) on top of the same cluster and the same
single external host. The new units are:

* **`credit_cards_app`:** the CreditCardsApp service, a new microservice that
  owns the CreditCard entity in its own DynamoDB table and exposes the
  `/credit-cards/*` API. The initial response returns in less than 5 seconds:
  the synchronous path validates the request, calls TrueNative to tokenize the
  card, stores the card with status `POR_VERIFICAR`, and publishes the
  verification event to the queue.
* **`card_worker`:** an AWS Lambda function (packaged as a container image)
  that consumes the card verification queue (SQS), polls TrueNative until the
  card reaches a terminal state (`APROBADA` or `RECHAZADA`), updates the card
  status and `updatedAt`, and publishes the email notification to the SNS
  topics.
* **`user_verification_callback`:** a FastAPI service that receives the
  asynchronous callback from TrueNative with the identity verification result,
  validates the SHA256 integrity token, updates the user status
  (`VERIFICADO` or `NO_VERIFICADO`) through the `users_app` API, and
  publishes the email notification to the SNS topics.
* **`truenative`:** the provided external platform
  (`ghcr.io/misw-4301-desarrollo-apps-en-la-nube/true-native:2.0.0`), deployed
  on the cluster with the `k8s_entrega3/k8s-true-native-deployment.yml`
  manifest and reachable at `/native/*`. It is configured with the mandatory
  `SECRET_TOKEN` environment variable, which the manifest reads from the
  `truenative-secret` Kubernetes Secret; the secret value is substituted at
  apply time in both environments and is never committed in plaintext. The
  manifest declares no `namespace`, so the workload runs in the default
  namespace, as the course requires.
* **Serverless resources:** the DynamoDB table, the SQS queue, the SNS email
  topics, and the Lambda function are provisioned by the new Terraform
  stacks (`3_dynamodb`, `5_sqs`, `4_sns`, and `6_lambda`). The queue lives
  in `tf_stacks` because the credit cards manifest needs its URL at
  envsubst time; the Lambda function lives in `post_k8s_stacks` because it
  needs the host of the ingress load balancer, which only exists once the
  k8s manifests are deployed.
* **`users_app` modification:** limited to the rule defined by the project
  document: the service no longer generates or verifies tokens while the user
  is not in the `VERIFICADO` status, so a user in the `POR_VERIFICAR` or
  `NO_VERIFICADO` status cannot authenticate or use the platform. It also
  exposes the internal endpoint that `user_verification_callback` uses to
  update the user status after the identity verification finishes.
* **Email mechanism:** the notifications use the SNS email topics. The
  subscription address comes from the `EMAIL_TO_NOTIFY` key of the
  `secrets-pipeline-native-map` secret in AWS Secrets Manager, which the
  deploy pipeline populates from the GitHub secret of the same name. This
  mechanism requires a manual confirmation step after the deploy (see the
  [Cloud Deployment Procedure (Entrega 3)](#cloud-deployment-procedure-entrega-3)).

The full description of every new component (responsibilities, design
considerations, and integrations) is in the [Functional View](./docs/functional-view.md)
and the [Deployment View](./docs/deployment-view.md).


## Terraform Stacks

The infrastructure is defined as Terraform stacks under `terraform/stacks/`, each with its own stack-specific README:

| Stack | Description | Stack README |
|-------|-------------|--------------|
| **0_storage** | S3 bucket for shared object storage across all apps | [terraform/stacks/0_storage/README.md](./terraform/stacks/0_storage/README.md) |
| **1_database** | Shared PostgreSQL RDS instance + Secrets Manager | [terraform/stacks/1_database/README.md](./terraform/stacks/1_database/README.md) |
| **2_registry** | ECR repositories for Docker images | [terraform/stacks/2_registry/README.md](./terraform/stacks/2_registry/README.md) |
| **3_dynamodb** | Dedicated DynamoDB table for the CreditCard entity (`credit_cards_app`, Entrega 3) | [terraform/stacks/3_dynamodb/README.md](./terraform/stacks/3_dynamodb/README.md) |
| **eks** | EKS cluster + managed node groups for workloads | [terraform/stacks/eks/README.md](./terraform/stacks/eks/README.md) |
| **4_sns** | SNS email topics + email subscriptions for RF-006 and RF-007 | [terraform/stacks/4_sns/README.md](./terraform/stacks/4_sns/README.md) |
| **5_sqs** | Card verification queue + dead letter queue (RF-006, in `tf_stacks`) | [terraform/stacks/5_sqs/README.md](./terraform/stacks/5_sqs/README.md) |
| **6_lambda** | Card worker Lambda function + least privilege role + event source mapping (RF-006, in `post_k8s_stacks`) | [terraform/stacks/6_lambda/README.md](./terraform/stacks/6_lambda/README.md) |

The serverless resources of RF-006 are provisioned by the two stacks above:
`5_sqs` (in `tf_stacks`) creates the queue and the dead letter queue, and
`6_lambda` (in `post_k8s_stacks`) creates the worker function, its least
privilege role, and the event source mapping that connects both sides. Every
stack follows the same folder rule (both `terraform/stacks/<name>/` and
`terraform/environments/<environment>/<name>/` must exist).

The `config.yaml` `tf_stacks` list defines the deploy order used by the
`ci_entrega2_deploy.yml` pipeline: `1_database` → `2_registry` →
`3_dynamodb` → `eks` → `4_sns` → `5_sqs`. After the k8s manifests are
deployed, the pipeline applies the `post_k8s_stacks` list (currently
`6_lambda`).
(`0_storage` is commented out in `config.yaml`; see
[Terraform Cloud Infrastructure](./docs/terraform-deployment.md) for the
storage bootstrap prerequisite and why it is not part of the pipeline order).
Destroy always runs in reverse order.

## How to run

Run each of the following from the repo root dir (the `0_bootstrap_state_bucket.sh`
script creates the S3 state bucket once, before any `terraform init`):

```bash
bash scripts/terraform_scripts/0_bootstrap_state_bucket.sh  # create the shared S3 state bucket (once)
bash scripts/terraform_scripts/1_init_all.sh               # terraform init for every stack/env combo
bash scripts/terraform_scripts/2_plan_all.sh               # terraform plan for every stack/env combo -> tfplans/
bash scripts/terraform_scripts/3_apply_reviewed.sh         # terraform apply reviewed plans only, you can skip plans if needed
bash scripts/terraform_scripts/zz_destroy_all.sh           # terraform destroy for every stack/env combo (manual and destructive)
```

## Cloud Deployment (AWS)

The cloud deployment is driven by the `ci_entrega2_deploy.yml` pipeline
(manual `workflow_dispatch`, one run per environment: `student1` to `student4`
or `tutor`). It reads `config.yaml` and performs the following steps in order:

1. **Terraform apply** for each stack in the `tf_stacks` list, in list order
   (`1_database` → `2_registry` → `3_dynamodb` → `eks` → `4_sns` → `5_sqs`).
   Each stack uses the `terraform/environments/<environment>/<stack>/` tfvars
   and stores its state in the shared S3 bucket (see `backend.tfvars`).
2. **Docker image build and push**: one image per entry in the `apps:` list
   (the five microservices, the three orchestrators, and, in Entrega 3, the
   credit cards service, the card verification worker, and the user
   verification callback), pushed to the ECR repositories created by the
   `2_registry` stack.
3. **Kubernetes manifests apply**: the `k8s_entrega2/` and `k8s_entrega3/`
   manifests are applied to the EKS cluster in alphabetical file name order
   (00 secrets, 20 apps, zz ingress last), including the new workloads of
   Entrega 3 and the TrueNative deployment
   (`k8s_entrega3/k8s-true-native-deployment.yml`). The `SECRET_TOKEN` that
   the TrueNative manifest references is exported by the pipeline from the
   `secret_token` output of the `eks` stack (see the Terraform Stacks
   section), so the envsubst step of the pipeline resolves it before the
   manifests reach the cluster.
4. **Terraform apply of the `post_k8s_stacks`** list (currently `6_lambda`),
   applied after the k8s manifests so the worker can discover the host of the
   ingress load balancer and wire the queue, the role, and the function.

Database model: all five data owning applications share a single RDS
PostgreSQL instance (the `1_database` stack). Data isolation is enforced at
the PostgreSQL level: each application owns its own schema and a dedicated
login role with grants scoped to that schema only. The `1_database` stack
also creates the AWS Secrets Manager secret with the database credentials.

Secrets: in production the K8s Secrets are populated from AWS Secrets
Manager by the External Secrets Operator (ESO). The `k8s_entrega2/00-secrets.yml`
file holds placeholder values for local testing only; the
`k8s_entrega2/00-secrets.yml.tpl` template shows the per app secret shape.

Ingress: the same `microservices-ingress` resource is used in both
environments. The course project required an AWS ALB, but the AWS Academy
academic accounts do not allow ALB, so the deployment uses the NGINX ingress
controller in both local Minikube and AWS EKS (see the header comment in
`k8s_entrega2/zz-ingress.yml` and the [Deployment View](./docs/deployment-view.md)).

Notes:

* The `0_storage` stack is commented out in `config.yaml`: the S3 bucket it
  creates must exist before any stack can initialize its S3 state backend, so
  it cannot be part of the pipeline order. It is provisioned manually in
  `dev` environments with the custom automation scripts above; in the student
  evaluation environment ("Entrega 2 Deploy") the state bucket already exists.
* To tear down the infrastructure, run the `ci_entrega2_destroy.yml` pipeline
  (manual and destructive): it destroys the stacks in reverse order.
* For the full stack by stack guide, variable tables, and verification steps,
  see the [Terraform Deployment Guide](./docs/terraform-deployment.md).

## Cloud Deployment Procedure (Entrega 3)

The cloud validation of the delivery runs the provided pipelines in this exact
order, without modifying them, from the **Actions** tab of the repository:

1. `ci_entrega2_deploy.yml` (Entrega 2 - Deploy)
2. the manual email confirmation step (it applies to this solution, see Step 3)
3. `ci_evaluador_entrega3.yml` (Entrega 3 - Evaluador Implementación)
4. `ci_entrega2_destroy.yml` (Entrega 2 - Destroy)

### Prerequisites for the Cloud Deployment

* The GitHub secret `EMAIL_TO_NOTIFY` is configured in the selected environment.
  The deploy pipeline copies it, together with the rest of the environment
  secrets, to the AWS Secrets Manager secret `secrets-pipeline-native-map`,
  which the Terraform stacks read to create the email subscriptions.
* `config.yaml` lists every component in the `tf_stacks`, `k8s_manifests`,
  and `apps` keys, including the new stacks and applications of Entrega 3.
* No credentials, secret values, or email addresses are stored in this
  repository: they live in the GitHub secrets and in AWS Secrets Manager.

### Step 1: Verify the config.yaml and the GitHub secret

Confirm that `config.yaml` lists all the applications and stacks, and that the
`EMAIL_TO_NOTIFY` secret exists in the environment that will be used for the
deployment. Without that secret the deploy pipeline cannot populate
`secrets-pipeline-native-map` and the email mechanism cannot be configured.

### Step 2: Run the Deploy Pipeline

Run the **Entrega 2 - Deploy** workflow (`ci_entrega2_deploy.yml`) from the
Actions tab, select the environment (for example `student1`), and wait until
the run finishes successfully. The pipeline applies the Terraform stacks in
`tf_stacks` order (including the new stacks that create the DynamoDB table,
the SQS queue, and the SNS topics with the email subscriptions), builds and
pushes the images, applies the Kubernetes manifests (the new workloads and
the TrueNative deployment), and finally applies the `post_k8s_stacks` list
(the `6_lambda` stack with the card worker function, its least privilege
role, and the queue event source mapping).

### Step 3: Confirm the SNS Email Subscriptions (manual step)

**This step applies to this solution.** The email mechanism is Amazon SNS:
during the deploy, the new Terraform stack creates the SNS topics and the
email subscriptions, and Amazon SNS sends a subscription confirmation email to
the address stored in `EMAIL_TO_NOTIFY`. Before running the evaluator, open
that inbox and click the confirmation link of each subscription. While a
subscription is not confirmed, SNS discards the messages and the evaluator
pipeline will fail on the email validation. The address is never written in
this repository; it comes from the secret.

### Step 4: Run the Evaluator Pipeline

Run the **Entrega 3 - Evaluador Implementación** workflow
(`ci_evaluador_entrega3.yml`) with the same environment. It executes the API
tests of RF-006 (credit cards) and RF-007 (user identity verification) against
the deployed system, including the validation of the email notification. If
the deploy pipeline did not finish successfully, this pipeline will fail
because there is no functional infrastructure to test.

### Step 5: Run the Destroy Pipeline

Only after the evaluator has finished (or after the evaluation is complete),
run the **Entrega 2 - Destroy** workflow (`ci_entrega2_destroy.yml`). It
destroys the infrastructure in the reverse order of the deploy. While it has
not been run, the cluster, the databases, and the serverless resources keep
consuming the AWS Academy budget.

## Testing Toolchain

All the applications are written in Python with Poetry, and the web
applications use FastAPI. They are tested with pytest. Each application runs its unit tests with the
`unittest` target of the root `makefile` (pytest with pytest-cov and a minimum
coverage of 70% enforced with `--cov-fail-under=70`). The unit testing pipeline
`ci_evaluador_unit.yml` (Evaluador Pruebas Unitarias) runs on every push and
pull request to `main` and validates the coverage of each application job,
including `card_worker`. No
language other than Python and no testing framework other than pytest are used
in this project, so no additional toolchain section is required. Manual and
integration verification is documented per requirement in the
[Development View](./docs/development-view.md); in particular,
[Manual verification of RF-006](./docs/development-view.md#manual-verification-of-rf-006)
documents the runs of the graded collection `scripts/entrega3/entrega3.json`
on local Minikube and on the AWS dev environment, with the expected result
of each run.

## Prerequisites

Before starting, make sure you have installed:

* [ ] Docker
* [ ] Minikube
* [ ] kubectl
* [ ] Postman
* [ ] Git
* [ ] Python 3.11 + Poetry (or another stack, depending on the language selected by the team)

Verify the installed versions:

```bash
docker --version
minikube version
kubectl version --client
git --version
```

## Step 1: Clone the Repository

```bash
git clone <team-repository-url>
cd <repository-name>
```

## Step 2: Verify config.yaml

Confirm that the `config.yaml` file at the repository root has been properly completed: team name, members, board link, documentation link, the `tf_stacks` list (including the new Entrega 3 stacks), and the data (`folder`, `image_name`, `image_tag`, `authors`) for each of the five applications (`users_app`, `posts_app`, `routes_app`, `offers_app`, `scores_app`), the three orchestrators, and the three new components of Entrega 3 (`credit_cards_app`, `card_worker`, `user_verification_callback`).

```bash
cat config.yaml
```

> This file is used by the pipelines to grade the delivery. If it is not configured correctly, the delivery cannot be evaluated.

## Step 3: Generate Technical Documentation (PlantUML)

Build the PlantUML generator image and run it to render all `.puml` diagrams located in `docs/diagrams/` as `.png` files.

```bash
cd plantuml-generator
docker build -t plantuml/plantuml:latest .
cd ../

docker run --rm -e PLANTUML_LIMIT_SIZE=8192 \
  -v "$(pwd)/docs/diagrams:/workspace" \
  -w /workspace \
  plantuml/plantuml:latest "**.puml"
```

Verify that the diagrams were generated:

```bash
ls docs/diagrams/*.png
# Should show at least: entities.png, components.png, deployment.png, networks.png
# plus the Entrega 2 diagrams: components/deployment/networks_second_iteration.png
# and rf003/rf004/rf005-sequence.png
# and the Entrega 3 diagrams: components_third_iteration.png, deployment_third_iteration.png,
# rf006-sequence.png, and rf007-sequence.png
```

## Step 4: Run Each Application Locally (Optional, for Development)

For development and quick testing before containerization, each application can be run independently. Refer to the `README.md` in each folder for the exact command and required environment variables:

* [Users README](./users_app/README.md)
* [Posts README](./posts_app/README.md)
* [Routes README](./routes_app/README.md)
* [Offers README](./offers_app/README.md)
* [Scores README](./scores_app/README.md)
* [RF-003 README](./rf003_create_post_app/README.md)
* [RF-004 README](./rf004_create_offer_app/README.md)
* [RF-005 README](./rf005_query_post_app/README.md)
* The new components of Entrega 3 (`credit_cards_app`, `card_worker`, and
  `user_verification_callback`) follow the same pattern: each folder contains
  its own `README.md` with the exact command and the required environment
  variables. `credit_cards_app` uses its own DynamoDB table instead of the
  shared PostgreSQL instance.

Each application requires a PostgreSQL database available on port `5432` (you can start it independently with Docker during development).

## Step 5: Build the Docker Images

Repeat this step for each of the five applications, using the `image_name` and `image_tag` values defined in `config.yaml`:

```bash
cd users_app
docker build -t <users_image_name>:<users_image_tag> .
cd ..

cd posts_app
docker build -t <posts_image_name>:<posts_image_tag> .
cd ..

cd routes_app
docker build -t <routes_image_name>:<routes_image_tag> .
cd ..

cd offers_app
docker build -t <offers_image_name>:<offers_image_tag> .
cd ..

cd scores_app
docker build -t scores-app:v0.0.0 .
cd ..
```

Repeat the same step for the three orchestrators, building each one from its
own folder (the same folders `scripts/local-deploy.sh` uses):

```bash
cd rf003_create_post_app
docker build -t rf003-create-post-app:v0.0.0 .
cd ..

cd rf004_create_offer_app
docker build -t rf004-create-offer-app:v0.0.0 .
cd ..

cd rf005_query_post_app
docker build -t rf005-query-post-app:v0.0.0 .
cd ..
```

In Entrega 3 the same step applies to the new components: the
`credit_cards_app` and `user_verification_callback` images are built from
their own folders, and the `card_worker` image is the container image of the
Lambda function. TrueNative is not built locally: it uses the provided image
`ghcr.io/misw-4301-desarrollo-apps-en-la-nube/true-native:2.0.0`.

Verify that all the images were built successfully:

```bash
docker images | grep -E "users|posts|routes|offers|scores|rf003|rf004|rf005|credit|card|verification"
```

## Step 6: Start Minikube

```bash
minikube start --cpus=2 --memory=4g
```

Confirm that the cluster is active:

```bash
minikube status
kubectl get nodes
```

## Step 7: Load the Images into Minikube

Minikube runs its own internal Docker daemon; locally built images must be explicitly loaded:

```bash
minikube image load <users_image_name>:<users_image_tag>
minikube image load <posts_image_name>:<posts_image_tag>
minikube image load <routes_image_name>:<routes_image_tag>
minikube image load <offers_image_name>:<offers_image_tag>
minikube image load scores-app:v0.0.0
minikube image load rf003-create-post-app:v0.0.0
minikube image load rf004-create-offer-app:v0.0.0
minikube image load rf005-query-post-app:v0.0.0
```

Verify that the images are available inside Minikube:

```bash
minikube image ls | grep -E "users|posts|routes|offers|scores|rf003|rf004|rf005"
```

## Step 8: Deploy the Kubernetes Manifests

Apply the declarative manifests located in `k8s_entrega2/` (Deployments, Services, Secrets, and Ingress) in the same order `scripts/local-deploy.sh` uses: the local secrets and the shared Postgres instance first (both in `k8s_entrega2/local-only/`), then the application Deployments and Services (the eight of the previous deliveries, plus the RF-007 callback receiver and the RF-006 credit cards service of Entrega 3), the TrueNative deployment of `k8s_entrega3/`, and the Ingress last:

```bash
kubectl apply -f k8s_entrega2/local-only/00-secrets.yml
kubectl apply -f k8s_entrega2/local-only/15-shared-db.yml
kubectl apply -f k8s_entrega2/20-users-app.yml
kubectl apply -f k8s_entrega2/21-posts-app.yml
kubectl apply -f k8s_entrega2/22-offers-app.yml
kubectl apply -f k8s_entrega2/23-routes-app.yml
kubectl apply -f k8s_entrega2/24-scores-app.yml
kubectl apply -f k8s_entrega2/25-rf003-create-post-app.yml
kubectl apply -f k8s_entrega2/26-rf004-create-offer-app.yml
kubectl apply -f k8s_entrega2/27-rf005-query-post-app.yml
kubectl apply -f k8s_entrega2/28-user-verification-callback.yml
kubectl apply -f k8s_entrega3/k8s-true-native-deployment.yml
kubectl apply -f k8s_entrega3/k8s-credit-cards-deployment.yml
kubectl apply -f k8s_entrega2/zz-ingress.yml
```

> **Note:** The `k8s_entrega2/local-only/` folder contains the local secrets and the shared Postgres instance used only for local Minikube testing. It is excluded from `config.yaml k8s_manifests` so the AWS EKS pipeline never applies it (production uses real RDS and the ESO populated secrets).
>
> **Note:** TrueNative is not built locally: it uses the provided image. `scripts/local-deploy.sh` reads the `SECRET_TOKEN` value from `truenative_secrets/dev.env`, a file that lives OUTSIDE the repository, one level above the repo root (that is, `<parent-of-repo>/truenative_secrets/dev.env`), and is therefore never committed. A fresh developer creates that folder once and writes a single line in it: `SECRET_TOKEN=<any random string>`. The script then substitutes the value into the `truenative-secret` Kubernetes Secret and applies `k8s_entrega3/k8s-true-native-deployment.yml` before the Ingress. The manifest declares only the mandatory `SECRET_TOKEN`; the optional testing variables (`SUCCESS_RATE`, `MAX_WEBHOOK_DELAY`, and `MAX_POLL_DELAY`) keep their platform defaults in the cluster, and the evaluation collection reconfigures them at runtime through `POST /native/env`, so no dev override is needed in the manifest.

The RF-007 callback receiver is added to `k8s_entrega2/` with the same
numbered naming convention (`28-user-verification-callback.yml`), so it is
applied in order by the pipeline. The RF-006 credit cards Deployment and
Service live in `k8s_entrega3/k8s-credit-cards-deployment.yml` (the DynamoDB
table name and the SQS queue URL come from the Terraform outputs, and the
local run uses placeholder values), and the TrueNative deployment lives in
`k8s_entrega3/k8s-true-native-deployment.yml`. Both are applied by
`scripts/local-deploy.sh` after the `k8s_entrega2/` workloads and before the
Ingress, with the `SECRET_TOKEN` value substituted from the out of repo
`truenative_secrets/dev.env` file (see the note above).

## Step 9: Verify the Deployment

Confirm that all twelve workloads (5 applications + 3 orchestrators + shared-db + the three workloads of Entrega 3: credit-cards-app, user-verification-callback, and truenative) are running correctly in the `default` namespace:

```bash
kubectl get pods
kubectl get services
kubectl get ingress
```

All pods should show `Running` status and `READY 1/1`. If any pod fails, check the logs:

```bash
kubectl logs <pod-name>
kubectl describe pod <pod-name>
```

## Step 10: Access the Applications via Ingress

All applications are reachable through a single Ingress resource that routes by path prefix. Start `minikube tunnel` in a separate terminal (this is the same procedure `scripts/local-verify.sh` uses): with the tunnel running, the Ingress is reachable at `http://localhost:80`:

```bash
minikube tunnel
```

Example health checks:
```bash
curl http://localhost:80/users/ping
curl http://localhost:80/posts/ping
curl http://localhost:80/rf003/ping
curl http://localhost:80/credit-cards/ping
curl http://localhost:80/native/ping
# Each should respond: pong
```

## Step 11: Test the API with Postman

Import the corresponding Postman collections for each application and update the `baseUrl` environment variable (**Current value**, not Initial value) with the URL obtained in the previous step. Run each collection (`Run collection`) and confirm that all tests pass successfully.

For Entrega 3, use the graded collection `scripts/entrega3/entrega3.json`
(its folders are "Reset," "RF-007 Verificar identidad," and "RF-006 Tarjetas,"
and it declares the environment variables `BASE_PATH` and `EMAIL`). The
script `scripts/test-entrega3.sh` runs the same collection against the AWS
deployment (it reads `scripts/.env`, connects to the cluster with the
active AWS session, and resolves the ingress host automatically).

## Step 12: Run the Validation Pipelines

Before creating the release, manually run the provided pipelines (without modifying them) from the **Actions** tab of the repository on GitHub. For Entrega 1:

* `Entrega 1 - Evaluador Implementación` (`ci_entrega1_evaluador_k8s.yml`)

For Entrega 2 (cloud deployment via Terraform stacks and ECR images):

* `Entrega 2 - Deploy` (`ci_entrega2_deploy.yml`)
* `Entrega 2 - Destroy` (`ci_entrega2_destroy.yml`, manual and destructive)

For Entrega 3, run the full sequence documented in the
[Cloud Deployment Procedure (Entrega 3)](#cloud-deployment-procedure-entrega-3):
the deploy pipeline, the manual SNS confirmation step, the evaluator workflow
(`ci_entrega3_evaluador.yml`, which calls the course reusable workflow
`ci_evaluador_entrega3.yml`), and the destroy pipeline, in that order.

Confirm that they finish successfully (passed ✅) before continuing.

The documentation pipeline `Entrega 1 - Evaluador Documentación`
(`ci_entrega1_evaluador_docs.yml`) is `workflow_dispatch` only and calls an
external reusable workflow from the course organization repository, so it must
be run manually from the Actions tab. Its status for the Entrega 2
documentation is unconfirmed, so do not rely on it as the only validation:
also run the local checks below (Vale on `docs/` and a manual review of the
published Pages site) before releasing.

Additionally, confirm that the unit testing pipeline (`ci_evaluador_unit.yml`) passes correctly on every push/PR to `main`, with a minimum coverage of 70% per application.

## Step 13: Cleanup (Optional)

To remove the deployment and stop Minikube after testing:

```bash
kubectl delete -f k8s_entrega2/
kubectl delete -f k8s_entrega3/
kubectl delete -f k8s_entrega2/local-only/15-shared-db.yml  # local minikube only
minikube stop
# To completely remove the cluster:
minikube delete
```

For the cloud infrastructure, the cleanup is the `ci_entrega2_destroy.yml`
pipeline (see the [Cloud Deployment Procedure (Entrega 3)](#cloud-deployment-procedure-entrega-3),
Step 5), not the `kubectl` commands above.

## Troubleshooting Common Issues

| Problem                                                  | Possible Cause                                                                      | Solution                                                                                                              |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Pod in `ImagePullBackOff` state                          | The image was not loaded into Minikube, or the name/tag does not match the manifest | Run `minikube image load` with the exact `image_name:image_tag` used in the manifest and `config.yaml`                |
| Pod in `CrashLoopBackOff` state                          | Error starting the application (database connection, missing environment variable)  | Check `kubectl logs <pod>` and verify the environment variables defined in the Deployment                             |
| Application not reachable via Ingress                    | The ingress-nginx-controller is not running, or routing is misconfigured            | Run `kubectl get pods -n ingress-nginx` and verify the microservices-ingress resource                                 |
| Postman receives a connection error                      | The `baseUrl` variable (Current value) was not updated, or Minikube is not running  | Repeat Step 10 and update the variable in Postman                                                                     |
| Application cannot connect to the database               | shared-db pod not ready, or DB credentials in secrets are incorrect                 | Run `kubectl get pods -l app=shared-db` and `kubectl logs <shared-db-pod>`                                            |
| PlantUML diagrams are not generated                      | Incorrect mount path or `.puml` syntax errors                                       | Verify that `docs/diagrams/` contains the `.puml` files and review the output from the `plantuml-generator` container |
| `minikube service --url` does not respond                | The Service is not correctly linked to the Deployment, or the pod is not `Running`  | Run `kubectl get endpoints <service-name>`                                                                            |
| An application can access another application's database | Network Policy is incorrectly configured or was not applied (legacy `k8s/` deployment) | Run `kubectl get networkpolicies` and compare against `networks.puml`                                                 |
| No email arrives after a verification process             | The SNS subscription is not confirmed, or the `EMAIL_TO_NOTIFY` secret is missing in the environment                                   | Confirm the subscription (see the Cloud Deployment Procedure, Step 3) and verify that the deploy pipeline populated `secrets-pipeline-native-map` |
| A local plan of `4_sns` reports the pipeline secret missing | The `secrets-pipeline-native-map` secret only exists after a deploy pipeline run, so a local plan on a fresh account finds no secret | Expected on a fresh account: create the secret once beforehand with the AWS CLI so the local plan can read it (see the `4_sns` stack README); the deploy pipeline overwrites the secret on every run |
| Cards stay `POR_VERIFICAR` and the worker logs "TrueNative could not be reached" | An orphaned classic load balancer from a previous lab session still carries the ingress-nginx tags, and the card worker discovery picks it instead of the live balancer (or the live balancer has no registered instance yet) | List the classic load balancers with `aws elb describe-load-balancers`, check each one with `aws elb describe-instance-health`, and delete the orphaned balancer that registers no instance (`aws elb delete-load-balancer --load-balancer-name <name>`); on a fresh cluster, wait for the node to be registered and the health check to pass before rerunning the flow |


## Demo Third Iteration:



https://github.com/user-attachments/assets/f9c6d26d-f27c-4a24-8ecc-b627cc3f6197






