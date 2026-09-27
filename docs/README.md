
# Project Delivery 3 - Shared Suitcase Package Delivery Platform (P2P Broker)

This project implements a brokerage platform (broker) for collaborative package delivery. Delivery 1 consisted of four independent applications (users, routes, posts, and offers), each with its own PostgreSQL database, deployed in containers and locally orchestrated using Kubernetes (Minikube). Delivery 2 (Entrega 2) extended the system with the `scores_app` microservice, three orchestrator services (RF-003, RF-004, and RF-005), a Kubernetes Ingress as the single public entry point, and a shared PostgreSQL instance in the cloud deployment. Delivery 3 (Entrega 3) adds the two new requirements on top of the same cluster and the same single external host:

* **`credit_cards_app`** a new microservice (RF-006) that owns the CreditCard entity in its own DynamoDB table and exposes the `/credit-cards/*` API: it validates the request, tokenizes the card at TrueNative, stores it with status `POR_VERIFICAR`, publishes the verification event to the SQS queue, and answers the client in less than five seconds.
* **`card_worker`** a serverless component (RF-006) implemented as an AWS Lambda function packaged as a container image: it consumes the card verification queue, polls TrueNative until the card reaches a terminal state (`APROBADA` or `RECHAZADA`), updates the card status in the DynamoDB table, and publishes the result email to the SNS topics.
* **`user_verification_callback`** a new service (RF-007) that receives the asynchronous identity verification callback from TrueNative, validates the SHA256 integrity token, updates the user status (`VERIFICADO` or `NO_VERIFICADO`) through the `users_app` API, and publishes the result email to the SNS topics.
* **`truenative`** the provided external verification and tokenization platform, deployed on the cluster and reachable at `/native/*`.
* **The serverless infrastructure** of the new Terraform stacks (`3_dynamodb` for the CreditCard table, `4_sns` for the email topics, `5_sqs` for the card verification queue and its dead letter queue, and `6_lambda` for the worker function, its least privilege role, and the event source mapping).
* **The `users_app` modification** (RF-007) that forbids token generation and verification while the user is not `VERIFICADO`, the only change applied to a component from the previous deliveries.

## Page

Project Delivery 3 Github web page: https://miniature-disco-ee8nm6p.pages.github.io

The published documentation site is the GitHub Pages site for this repository (see `config.yaml` `docs` for the URL).

By using this project, you will find:

* Five independent REST microservices (users, routes, posts, offers, scores) plus the new credit cards microservice, each exclusively responsible for its own data.
* Three orchestrator services (RF-003, RF-004, RF-005) that coordinate the microservices behind a single client-facing endpoint per requirement. Each orchestrator handles consistency (for example, RF-003 uses saga compensation to avoid orphaned routes when a downstream service fails mid-flow) and error propagation (integration failures return 503; business rejections pass through 412 unchanged).
* A shared PostgreSQL instance for the applications of the previous deliveries, with per-app database and role isolation enforced at the PostgreSQL level, and a dedicated DynamoDB table for the CreditCard entity of RF-006.
* An asynchronous, event driven verification flow for RF-006 (SQS queue, Lambda worker, and SNS email) and for RF-007 (TrueNative webhook, callback service, and SNS email), both behind the single external host.
* Authentication based on random tokens (not JWT) for user management, with token issuance and verification blocked while the user is not verified.
* Technical documentation as code, with architecture views modeled in PlantUML and published through GitHub Pages.
* GitHub Actions pipelines to validate deployment, database configuration, API contracts, and unit test coverage.

## Table of Contents

- [Project Delivery 3 - Shared Suitcase Package Delivery Platform (P2P Broker)](#project-delivery-3---shared-suitcase-package-delivery-platform-p2p-broker)
  - [Page](#page)
  - [Table of Contents](#table-of-contents)
  - [Team](#team)
  - [Architectural Views](#architectural-views)
    - [Information View](#information-view)
    - [Functional View](#functional-view)
    - [Deployment View](#deployment-view)
    - [Development View](#development-view)
    - [Consistency patterns for orchestrators](#consistency-patterns-for-orchestrators)
  - [Requirements](#requirements)
    - [Requirement RF-003](#requirement-rf-003)
      - [RF-003 Sequence View](#rf-003-sequence-view)
      - [RF-003 Solution Pattern](#rf-003-solution-pattern)
    - [Requirement RF-004](#requirement-rf-004)
      - [RF-004 Sequence View](#rf-004-sequence-view)
      - [RF-004 Solution Pattern](#rf-004-solution-pattern)
    - [Requirement RF-005](#requirement-rf-005)
      - [RF-005 Sequence View](#rf-005-sequence-view)
      - [RF-005 Solution Pattern](#rf-005-solution-pattern)
    - [Requirement RF-006](#requirement-rf-006)
      - [RF-006 Sequence View](#rf-006-sequence-view)
      - [RF-006 Solution Pattern](#rf-006-solution-pattern)
    - [Requirement RF-007](#requirement-rf-007)
      - [RF-007 Sequence View](#rf-007-sequence-view)
      - [RF-007 Solution Pattern](#rf-007-solution-pattern)
  - [Development and Deployment Technologies](#development-and-deployment-technologies)
    - [Postman](#postman)
    - [Git](#git)
    - [Python 3.11](#python-311)
    - [Poetry](#poetry)
    - [Pyenv](#pyenv)
    - [IDE](#ide)
    - [Docker](#docker)
    - [Minikube](#minikube)
    - [Kubectl](#kubectl)
  - [Application Execution](#application-execution)
    - [1. Install Dependencies](#1-install-dependencies)
    - [2. Run Each Application Locally](#2-run-each-application-locally)
  - [Deployment](#deployment)
    - [Run with Docker](#run-with-docker)
    - [Run with Minikube](#run-with-minikube)
      - [Automated local deployment and verification (recommended)](#automated-local-deployment-and-verification-recommended)
      - [Local deployment (Ingress-required)](#local-deployment-ingress-required)
      - [Testing saga consistency with Postman + kubectl](#testing-saga-consistency-with-postman--kubectl)
      - [Local deployment with Ingress (manual steps, reference)](#local-deployment-with-ingress-manual-steps-reference)
        - [Step 1 - Remove old images and containers](#step-1---remove-old-images-and-containers)
        - [Step 2 - Start a fresh Minikube cluster with the Ingress addon enabled](#step-2---start-a-fresh-minikube-cluster-with-the-ingress-addon-enabled)
        - [Step 3 - Build all Docker images into Minikube](#step-3---build-all-docker-images-into-minikube)
        - [Step 4 - Apply Kubernetes manifests in order](#step-4---apply-kubernetes-manifests-in-order)
        - [Step 5 - Verify pods and services are running](#step-5---verify-pods-and-services-are-running)
        - [Step 6 - Access services through the Ingress](#step-6---access-services-through-the-ingress)
      - [Troubleshooting local deployment](#troubleshooting-local-deployment)
      - [Ingress configurations (two environments)](#ingress-configurations-two-environments)
        - [Local Minikube - NGINX Ingress](#local-minikube---nginx-ingress)
        - [AWS EKS production - NGINX Ingress (ALB not available)](#aws-eks-production---nginx-ingress-alb-not-available)
    - [Deployment (AWS)](#deployment-aws)
  - [Running PlantUML Generator](#running-plantuml-generator)
  - [Terraform](#terraform)
    - [Terraform Deployment Guide](#terraform-deployment-guide)
    - [Stack READMEs](#stack-readmes)
  - [Kubernetes Resources](#kubernetes-resources)
    - [Entrega 2 manifests (`k8s_entrega2/`)](#entrega-2-manifests-k8s_entrega2)
    - [Entrega 3 manifests (`k8s_entrega3/`)](#entrega-3-manifests-k8s_entrega3)
    - [Legacy Entrega 1 manifests (`k8s/`)](#legacy-entrega-1-manifests-k8s)
    - [Secrets Management](#secrets-management)
      - [Local Minikube (shared database instance)](#local-minikube-shared-database-instance)
      - [AWS Production (shared RDS instance)](#aws-production-shared-rds-instance)
      - [Production notes](#production-notes)
  - [Contributing](#contributing)
  - [Team Rules](#team-rules)
  - [License](#license)
  - [Authors](#authors)

## Team

- Pedro Trujillo:  pe.trujillo@uniandes.edu.co

## Architectural Views

### Information View

The [Information View](./information-view.md) documents the domain entities
(User, Route, Post, Offer, and Score) with their attributes and data types,
plus the entity relationship diagram.

### Functional View

The [Functional View](./functional-view.md) presents the runtime components
(the five microservices, the three orchestrators, the shared database, the
Ingress, and the Entrega 3 components: the credit cards service, the card
worker, the card verification queue, the user verification callback,
TrueNative, and the SNS email topics) with their responsibilities, design
considerations, and integrations.

### Deployment View

The [Deployment View](./deployment-view.md) describes how the components are
deployed in both environments: local Minikube and AWS EKS, including the
network model, the Ingress deployment details, the Terraform
infrastructure deployment, and the Entrega 3 deployment model (the new
runtimes, data stores, messaging, and email mechanism on the same single
entry point).

### Development View

The [Development View](./development-view.md) documents the project structure
(app folders, k8s folders, docs folder, `config.yaml`), the API endpoints,
the data models, the testing strategy, and the pipelines.

### Consistency patterns for orchestrators

Each orchestrator has a documented consistency strategy (see [Solution Patterns](./solution-patterns.md)):

* **RF-003** uses saga compensation to guarantee that a failed request never leaves an orphaned route. If the post creation fails with an integration error and the route was created in this flow, the orchestrator deletes it via `DELETE /routes/{id}`. Business rejections (412) are passed through unchanged.
* **RF-004** writes a score after creating an offer (documented consistency rules for that requirement).
* **RF-005** reads data from multiple services and handles null values safely (for example, missing scores do not cause failures).

## Requirements

### Requirement RF-003

Create a post (with route find or create) as a single client facing request.

#### RF-003 Sequence View

[RF-003 Sequence View](./rf003-sequence-view.md)

#### RF-003 Solution Pattern

[RF-003 Solution Pattern](./solution-patterns.md#rf-003)

### Requirement RF-004

Create an offer and persist its computed score as a single client facing request.

#### RF-004 Sequence View

[RF-004 Sequence View](./rf004-sequence-view.md)

#### RF-004 Solution Pattern

[RF-004 Solution Pattern](./solution-patterns.md#rf-004)

### Requirement RF-005

Query a post with its route and its offers sorted by score (null safe) as a single client facing request.

#### RF-005 Sequence View

[RF-005 Sequence View](./rf005-sequence-view.md)

#### RF-005 Solution Pattern

[RF-005 Solution Pattern](./solution-patterns.md#rf-005)

### Requirement RF-006

Store a credit card and notify its owner of the verification result as a single client facing request, with the verification performed asynchronously.

#### RF-006 Sequence View

[RF-006 Sequence View](./rf006-sequence-view.md)

#### RF-006 Solution Pattern

[RF-006 Solution Pattern](./solution-patterns.md#rf-006)

### Requirement RF-007

Verify the identity of a user when the user is created, so that only verified users can use the platform, with the result delivered by an asynchronous callback.

#### RF-007 Sequence View

[RF-007 Sequence View](./rf007-sequence-view.md)

#### RF-007 Solution Pattern

[RF-007 Solution Pattern](./solution-patterns.md#rf-007)

## Development and Deployment Technologies

This section describes the main technologies and tools used for development, testing, dependency management, containerization, and local deployment.

### Postman

**Postman** is an API development and testing platform used to send HTTP requests to the application's REST endpoints.

In this project, Postman is used to:

* Test REST API endpoints.
* Validate request and response behavior.
* Execute API integration test collections.
* Verify the deployed applications running on Minikube.

The collections live in `scripts/entrega2/` (three functional collections,
`evaluate_rf00X.json`, and three consistency collections,
`evaluate_rf00X_consistency.json`). They can be imported in the Postman UI or
executed headless with Newman (`npm i -g newman`), which is what `scripts/local-verify.sh` and the CI
workflows use including the saga-consistency runs that scale a deployment
to zero replicas between requests (see
[Testing saga consistency with Postman + kubectl](#testing-saga-consistency-with-postman--kubectl)).

For Entrega 3, the graded collection is `scripts/entrega3/entrega3.json`
(three folders, executed in order: "Reset," "RF-007 Verificar identidad,"
and "RF-006 Tarjetas"; it declares the environment variables `BASE_PATH`
and `EMAIL`). The script `scripts/test-entrega3.sh` replicates the evaluator
pipeline locally: it connects to the EKS cluster, resolves the ingress host,
downloads the collection from the course repository, and runs the three
folders with Newman (see the
[Development View](./development-view.md#manual-verification-of-rf-006) for
the expected results per environment).

### Git

**Git** is a distributed version control system used to track changes to the source code and collaborate as a development team.

In this project, Git is used for:

* Version control.
* Branch and merge management.
* Collaboration between team members.
* Tracking project history.
* Integrating changes through Pull Requests.

Before making commits, configure your Git identity:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Verify the configuration with:

```bash
git config --global --list
```

Configuring the Git user ensures that commits and project submissions are correctly associated with the corresponding team member.

### Python 3.11

**Python 3.11** is a general-purpose programming language used to develop the applications in this project when Python is selected as the application language.

Python is used for:

* Application development.
* Implementing REST APIs.
* Writing automated tests.
* Running development and execution scripts.

Verify the installed version with:

```bash
python3 --version
```

The expected version is:

```text
Python 3.11.x
```

### Poetry

**Poetry** is a dependency management and packaging tool for Python projects. It also manages isolated virtual environments for project dependencies.

In this project, Poetry is used to:

* Install project dependencies.
* Manage dependency versions.
* Create and manage virtual environments.
* Execute Python applications and tests within the project environment.

Common commands include:

```bash
poetry install
poetry run <command>
poetry shell
```

The project's dependencies and configuration are defined in:

```text
pyproject.toml
```

### Pyenv

**Pyenv** is a Python version management tool that allows developers to install and switch between multiple Python versions on the same machine.

It is useful when different projects require different Python versions.

For example:

```bash
pyenv install 3.11.9
pyenv local 3.11.9
```

Verify the active version with:

```bash
python --version
```

Pyenv and Poetry can be used together to ensure that the project runs with the required Python version.

### IDE

The team selected the IDE that best fits its workflow. The IDE is not required for deployment, but it facilitates development, debugging, code navigation, and integration with Git.

### Docker

**Docker** is a containerization platform used to package applications together with their dependencies and runtime environment.

In this project, each application has its own Docker image.

Docker is used to:

* Build application images.
* Provide consistent execution environments.
* Isolate applications and their dependencies.
* Prepare applications for deployment to Kubernetes.

Common commands include:

```bash
docker build -t <image_name>:<image_tag> .
docker images
docker run <image_name>:<image_tag>
```

### Minikube

**Minikube** is a tool that runs a local Kubernetes cluster, allowing Kubernetes applications to be developed and tested locally.

In this project, Minikube is used to deploy and validate the complete system locally, including:

* Eleven workloads: the four legacy microservices, scores_app, rf003_create_post_app, rf004_create_offer_app, rf005_query_post_app, and the three Entrega 3 workloads (credit-cards-app, user-verification-callback, and truenative). The card worker is a Lambda function and is never deployed on Minikube.
* One shared PostgreSQL instance with per-app database and role isolation (five databases: users_db, posts_db, offers_db, routes_db, scores_db).
* Kubernetes Services.
* Application-to-database communication through PostgreSQL-level role grants.

Start the cluster with:

```bash
minikube start
```

Check its status with:

```bash
minikube status
```

### Kubectl

**kubectl** is the command-line client used to interact with Kubernetes clusters.

In this project, `kubectl` is used to:

* Deploy Kubernetes manifests.
* Inspect Pods and Services.
* View application logs.
* Debug Kubernetes workloads.

For example:

```bash
kubectl apply -f k8s_entrega2/
kubectl apply -f k8s_entrega2/
kubectl get pods
kubectl get services
kubectl logs <pod-name>
```

`kubectl` communicates with the Kubernetes cluster running through Minikube and provides the primary command-line interface for managing the deployment.



## Application Execution

### 1. Install Dependencies

Navigate to the folder of the application you want to run (for example, `users_app`) and follow the instructions in its local `README.md` to install the dependencies.

```bash
cd users_app
poetry install
```

### 2. Run Each Application Locally

Each application runs independently. Refer to the `README.md` in each folder for the exact execution command and required environment variables, including the connection to its PostgreSQL database on port `5432`:

- [Users App](apps/users_app.md)
- [Routes App](apps/routes_app.md)
- [Posts App](apps/posts_app.md)
- [Offers App](apps/offers_app.md)
- [Scores App](apps/scores_app.md)
- [RF-003 Orchestration App](apps/rf003_create_post_app.md)
- [RF-004 Orchestration App](apps/rf004_create_offer_app.md)
- [RF-005 Orchestration App](apps/rf005_query_post_app.md)
- [Credit Cards App](apps/credit_cards_app.md)
- [Card Worker](apps/card_worker.md)
- [User Verification Callback App](apps/user_verification_callback.md)

## Deployment

### Run with Docker

Each application has its own `Dockerfile`. Build and run each application independently:

```bash
cd <app_folder>
docker build -t <image_name>:<image_tag> .
docker run -p <port>:<port> <image_name>:<image_tag>
```

The values of `image_name` and `image_tag` must exactly match those defined in `config.yaml` and in the manifests under `k8s_entrega2/`. For example, for the users app:

```bash
cd users_app
docker build -t users-app:v0.0.0 .
```

### Run with Minikube

#### Automated local deployment and verification (recommended)

Two scripts in `scripts/` automate the full local sequence. They are also
used by the `ci_local_manual_test.yml` workflow, so running them locally is
exactly the same sequence that runs on GitHub Actions:

```bash
# 1. Deploy: cleans old clusters/images, starts Minikube with the ingress
#    addon, builds all images (the legacy and Entrega 2 apps plus
#    credit-cards-app and user-verification-callback), applies the
#    k8s_entrega2/ manifests in order, deploys the k8s_entrega3/ workloads
#    (TrueNative and the credit cards Deployment + Service, with local
#    placeholder values for the DynamoDB table and the SQS queue), and
#    waits until every Deployment is ready.
bash scripts/local-deploy.sh

# 2. Verify: checks pods, services and the ingress; verifies all app
#    Services are ClusterIP; pings every app through the Ingress paths
#    only; runs a functional smoke test (user -> login rejected while
#    not VERIFICADO -> apply the verification status -> auth ->
#    RF-003 create post -> read post back. Also the credit cards app 
#    through the liveness probe /credit-cards/ping, body "pong"); 
#    runs a functional smoke test
#    (user -> auth -> RF-003 create post -> read post back, plus the
#    credit cards error responses that do not need the AWS stacks: 403,
#    401, 400 and 412 on the creation endpoint, and 403 plus 401 on the
#    listing endpoint); and runs the
#    full Postman collections
#    (functional + consistency) against http://localhost:80, taking the
#    relevant deployment down with `kubectl scale` for each consistency
#    scenario (see "Testing saga consistency with Postman + kubectl").
bash scripts/local-verify.sh
```

The RF-006 happy path (a `201` creation plus the asynchronous terminal
state) is not verifiable on Minikube, because the cluster has no DynamoDB
table, no SQS queue, and no Lambda function. It is verified on the AWS dev
environment with `scripts/terraform_scripts/verify-aws-rf006.sh` (see
"Manual verification of RF-006" in
[development-view.md](./development-view.md#manual-verification-of-rf-006)).

Sizes can be tuned with environment variables, for example
`MINIKUBE_MEMORY=6g bash scripts/local-deploy.sh` on machines with a smaller
Docker Desktop memory allocation.

The legacy Entrega 1 deployment (`k8s/`) is not deployed by these scripts:
it is evaluated separately by the `ci_entrega1_evaluador_k8s.yml` pipeline
on GitHub, and the two deployments define the same resource names with
different images, so they must not run in the same cluster at the same time.

#### Local deployment (Ingress-required)

All app Services are **ClusterIP**, and they are reachable only from inside
the cluster. The single external entry point is the NGINX ingress controller
(Service `ingress-nginx-controller` in namespace `ingress-nginx`). You must
deploy with Ingress:

```bash
minikube start --cpus=2 --memory=4g
minikube addons enable ingress
eval $(minikube docker-env)

# Build all images into Minikube
# (see scripts/local-deploy.sh for the full build sequence)

# Deploy all components (Entrega 2 manifests, in apply order)
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
kubectl apply -f k8s_entrega2/zz-ingress.yml

# Check the status of pods, services and Ingress
kubectl get pods
kubectl get services
kubectl get ingress
```

#### Testing saga consistency with Postman + kubectl

The orchestrators (RF-003, RF-004, RF-005) are designed so that, when one of
their downstream microservices is unavailable mid-flow, they propagate the
integration failure (HTTP 503) and leave the other services' state
**consistent** (no orphans). The Postman collections in
`scripts/entrega2/` test exactly this: each `*_consistency.json` collection
contains a `Reset` folder, one scenario folder per downstream app, and a
`Verificar Consistencia` folder that asserts the post-compensation state.

The scenario only produces a 503 if the downstream app is actually **down**
while the requests are sent. With Kubernetes, the cleanest way to take an app
down is to scale its Deployment to zero replicas the Ingress then answers
503 for its path prefix, exactly like a dead pod in production:

```bash
# 0. Prerequisites: cluster deployed (local-deploy.sh) and `minikube tunnel`
#    running so the Ingress is reachable at http://localhost:80.
#    newman must be installed:  npm i -g newman

# 1. Reset state (deletes the test users/routes/posts/offers)
newman run scripts/entrega2/evaluate_rf003_consistency.json --folder "Reset" \
  --env-var BASE_PATH=http://localhost:80

# 2. Take the downstream app down (users in this example)
kubectl scale deployment users-app -n default --replicas=0
sleep 5   # let the Ingress drop the dead endpoints

# 3. Run the scenario folder: the orchestrator call must fail with 503
newman run scripts/entrega2/evaluate_rf003_consistency.json --folder "RF-003 Crear publicacion" \
  --env-var BASE_PATH=http://localhost:80

# 4. Bring the app back and wait for its pod to be ready
kubectl scale deployment users-app -n default --replicas=1
kubectl wait --for=condition=ready pod -l app=users-app -n default --timeout=120s

# 5. Verify consistency: no orphaned routes/posts were left behind
newman run scripts/entrega2/evaluate_rf003_consistency.json --folder "Verificar Consistencia" \
  --env-var BASE_PATH=http://localhost:80
```

The full matrix (mirrored in `scripts/local-verify.sh`, section `[4/5]`, and
in the `ci_evaluador_entrega2.yml` GitHub workflow):

| Collection | Down deployment | Scenario folder | Verify folder | Extra env vars |
|---|---|---|---|---|
| `evaluate_rf003_consistency.json` | `users-app` | `RF-003 Crear publicacion` | `Verificar Consistencia` | — |
| `evaluate_rf003_consistency.json` | `routes-app` | `RF-003 Crear publicacion` | `Verificar Consistencia` | — |
| `evaluate_rf003_consistency.json` | `posts-app` | `RF-003 Crear publicacion` | `Verificar Consistencia` | — |
| `evaluate_rf004_consistency.json` | `users-app` | `RF-004 Crear oferta` → `Sesion & RF-004` → `Test RF-004` | `Verificar Consistencia` | `USER_TOKEN=FAKETOKEN`, `POST_ID=<uuid>` |
| `evaluate_rf004_consistency.json` | `offers-app` | `RF-004 Crear oferta` | `Verificar Consistencia` | — |
| `evaluate_rf004_consistency.json` | `posts-app` | `Sesion & RF-004` | `Verificar Consistencia` | `POST_ID=<uuid>` |
| `evaluate_rf005_consistency.json` | `users-app` | `Post & Sesion & RF-005` → `Sesion & RF-005` | — (no verify folder) | `USER_TOKEN=FAKETOKEN`, `POST_ID=<uuid>` |
| `evaluate_rf005_consistency.json` | `posts-app` | `Post & Sesion & RF-005` | — (no verify folder) | `POST_ID=<uuid>` |
| `evaluate_rf005_consistency.json` | `offers-app` | `Post & Sesion & RF-005` | — (no verify folder) | — |

Notes:

* **Always run the `Reset` folder first** in each scenario: the collections
  create users with fixed usernames, and a leftover user from a previous run
  makes the `Reset`/`Crear Recursos` requests fail with 412.
* For the RF-004/RF-005 scenarios that start with `Crear Recursos`, run that
  folder **before** scaling the app down (with all apps up), so the post and
  session exist before the failure is injected.
* `POST_ID` can be any UUID (for example `bf8792d2-3097-11ee-be56-0242ac120002`):
  the request must fail at the integration layer before the post is ever
  read. `USER_TOKEN=FAKETOKEN` makes the users service reject the token.
* RF-005 has no `Verificar Consistencia` folder: its query flow is read-only,
  so a 503 mid-flow cannot leave orphaned data behind.
* Scaling to zero (instead of deleting pods) is preferred: it is
  deterministic, does not trigger crash-loop backoff, and the restore step
  (`kubectl wait ... ready`) guarantees the app is back before the
  verification runs.

#### Local deployment with Ingress (manual steps, reference)

The steps below are the manual equivalent of `scripts/local-deploy.sh` and
`scripts/local-verify.sh`. Use the scripts for day-to-day work; keep these
steps here to understand (and debug) what the scripts do.

##### Step 1 - Remove old images and containers

```bash
# Stop and remove any running Minikube cluster
minikube stop
minikube delete

# Remove leftover containers and images from previous deployments
docker rm -f $(docker ps -aq) 2>/dev/null
docker rmi $(docker images -q) 2>/dev/null
docker system prune -f
```

##### Step 2 - Start a fresh Minikube cluster with the Ingress addon enabled

```bash
minikube start --cpus=4 --memory=7g
minikube start --cpus=4 --memory=7g
minikube addons enable ingress
eval $(minikube docker-env)
eval $(minikube docker-env)
```

##### Step 3 - Build all Docker images into Minikube

With `eval $(minikube docker-env)` active, `docker build` writes directly
into the Minikube container runtime:
With `eval $(minikube docker-env)` active, `docker build` writes directly
into the Minikube container runtime:

```bash
# Remember to set ACCOUNT_ID and AWS_REGION. For local development can be anything. 
ACCOUNT_ID="1234567890"
AWS_REGION="us-east-1"
ECR="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/"

# Legacy apps (Entrega 1, hyphenated image names for the k8s_entrega2/ deployment)
docker build -t "${ECR}users-app:v0.0.0" users_app
docker build -t "${ECR}posts-app:v0.0.0" posts_app
docker build -t "${ECR}offers-app:v0.0.0" offers_app
docker build -t "${ECR}routes-app:v0.0.0" routes_app

# Entrega 2 apps (each one is built from its own folder, the same way
# scripts/local-deploy.sh does it)

docker build -t "${ECR}scores-app:v0.0.0" scores_app
docker build -t "${ECR}rf003-create-post-app:v0.0.0" rf003_create_post_app
docker build -t "${ECR}rf004-create-offer-app:v0.0.0" rf004_create_offer_app
docker build -t "${ECR}rf005-query-post-app:v0.0.0" rf005_query_post_app
```

##### Step 4 - Apply Kubernetes manifests in order

```bash
# 0. Modify manually the variables placeholders for each image for each app k8s manifest .yml file
# for example:
# sed -i '' "s|\${ACCOUNT_ID}|123456789|g" "k8s_entrega2/22-offers-app.yml"
# sed -i '' "s|\${AWS_REGION}|us-east-1|g" "k8s_entrega2/22-offers-app.yml"
sed -i '' "s|\${ACCOUNT_ID}|${ACCOUNT_ID}|g" "${manifest}"
sed -i '' "s|\${AWS_REGION}|${AWS_REGION}|g" "${manifest}"

# 1. Local secrets first (required by Deployments)
kubectl apply -f k8s_entrega2/local-only/00-secrets.yml

# 2. Shared database instance (local Minikube only)
kubectl apply -f k8s_entrega2/local-only/15-shared-db.yml

# 3. All app Deployments and Services
kubectl apply -f k8s_entrega2/20-users-app.yml
kubectl apply -f k8s_entrega2/21-posts-app.yml
kubectl apply -f k8s_entrega2/22-offers-app.yml
kubectl apply -f k8s_entrega2/23-routes-app.yml
kubectl apply -f k8s_entrega2/24-scores-app.yml
kubectl apply -f k8s_entrega2/25-rf003-create-post-app.yml
kubectl apply -f k8s_entrega2/26-rf004-create-offer-app.yml
kubectl apply -f k8s_entrega2/27-rf005-query-post-app.yml
# 3. All app Deployments and Services
kubectl apply -f k8s_entrega2/20-users-app.yml
kubectl apply -f k8s_entrega2/21-posts-app.yml
kubectl apply -f k8s_entrega2/22-offers-app.yml
kubectl apply -f k8s_entrega2/23-routes-app.yml
kubectl apply -f k8s_entrega2/24-scores-app.yml
kubectl apply -f k8s_entrega2/25-rf003-create-post-app.yml
kubectl apply -f k8s_entrega2/26-rf004-create-offer-app.yml
kubectl apply -f k8s_entrega2/27-rf005-query-post-app.yml

# 4. Ingress (applied last, routes to all above services)
kubectl apply -f k8s_entrega2/zz-ingress.yml
kubectl apply -f k8s_entrega2/zz-ingress.yml
```

> The file names encode the apply order (00 secrets, 15 shared db, 20 apps,
> zz ingress last), which is the same alphabetical order the AWS pipeline
> uses. There are no NetworkPolicy files in `k8s_entrega2/`: data isolation
> is enforced at the PostgreSQL level (per app databases and roles) in both
> environments.

##### Step 5 - Verify pods and services are running

```bash
kubectl get pods -o wide
kubectl get services
kubectl get ingress
```

All pods should show `STATUS: Running`. The Ingress should show an ADDRESS (provided by the minikube ingress addon); with `minikube tunnel` running, the entry point is `http://localhost:80`.

##### Step 6 - Access services through the Ingress

Start `minikube tunnel` in a separate terminal (the same procedure
`scripts/local-verify.sh` uses); with the tunnel running, all external
traffic enters through `http://localhost:80` and is routed by path:

```bash
INGRESS="http://localhost:80"

# Legacy apps (Entrega 1) - routed to /users/*, /posts/*, /offers/*, /routes/*
curl ${INGRESS}/users/ping
curl ${INGRESS}/posts/ping
curl ${INGRESS}/offers/ping
curl ${INGRESS}/routes/ping

# Orchestrator apps (Entrega 2) - routed to /rf003/*, /rf004/*, /rf005/*
curl ${INGRESS}/rf003/ping
curl ${INGRESS}/rf004/ping
curl ${INGRESS}/rf005/ping

# Credit cards app (Entrega 3) - routed to /credit-cards/*
curl ${INGRESS}/credit-cards/ping
```

All endpoints should return a `pong` response. The same checks, plus a
functional smoke test (create user, check that the login is rejected
while the user is not VERIFICADO, apply the verification status,
authenticate, create a post through RF-003, read the post back), are
automated in `scripts/local-verify.sh`.

#### Troubleshooting local deployment

* Pods stuck in `Pending` - check with `kubectl describe pod <pod-name>` for resource constraints or scheduling errors.
* Pods in `CrashLoopBackOff` - check logs: `kubectl logs <pod-name>`. Verify image is correctly tagged and the app code exists.
* Ingress shows `<pending>` address - ensure `minikube addons enable ingress` was run, then reapply `kubectl apply -f k8s_entrega2/zz-ingress.yml`.
* No endpoints reachable through Ingress - confirm the ingress addon is enabled (`minikube addons enable ingress`), that `minikube tunnel` is running (the entry point is `http://localhost:80`), and check `kubectl get service ingress-nginx-controller -n ingress-nginx` for the controller's status.

#### Ingress configurations (two environments)

The single Ingress resource is defined in `k8s_entrega2/zz-ingress.yml`
(name: `microservices-ingress`). The same resource is used in both
environments: the course project required an AWS ALB for the cloud
deployment, but the AWS Academy academic accounts do not allow ALB, so the
NGINX ingress controller is used everywhere. The rule set grows with each
delivery; the current rules include the `/native` prefix added in Entrega 3.

##### Local Minikube - NGINX Ingress

Use this configuration for local development. The manifest is pre-configured with:

- `ingressClassName: nginx` routes to the Minikube NGINX ingress addon
- `kubernetes.io/ingress.class: nginx` annotation for NGINX compatibility
- No ALB annotations keeps the manifest clean for local use

Steps:
1. `minikube addons enable ingress`
2. Apply the local secrets, the shared database, the app manifests, and the
   ingress (in that order, see the
   [Local deployment (Ingress-required)](#local-deployment-ingress-required)
   section)
3. Start `minikube tunnel` in a separate terminal, then
   `curl http://localhost:80/users/ping`

##### AWS EKS production - NGINX Ingress (ALB not available)

The course project required an AWS ALB for the cloud deployment, but the
AWS Academy academic accounts do not allow ALB, so this project uses the
NGINX ingress controller in both environments. The same
`k8s_entrega2/zz-ingress.yml` resource (`ingressClassName: nginx`) is applied
unchanged on EKS; the NGINX controller runs as a Deployment inside the
cluster and its Service is exposed as a LoadBalancer (AWS provisions the
elastic load balancer for the Service), which serves as the single entry
point. See the header comment in `k8s_entrega2/zz-ingress.yml` and the
[Deployment View](./deployment-view.md) for the rationale and evidence.

Steps for cloud deployment:

1. Deploy the NGINX ingress controller into the EKS cluster (the same addon
   used locally, packaged as a standard Deployment).
2. Apply `k8s_entrega2/zz-ingress.yml` unchanged (`ingressClassName: nginx`).
3. Install the **External Secrets Operator (ESO)** to populate K8s Secrets from **AWS Secrets Manager** at runtime. Secret objects are created by ESO; you do not need to manage base64 values manually.
4. Deploy with `kubectl apply -f k8s_entrega2/`. The LoadBalancer in front of the NGINX controller serves as the single entry point.

### Deployment (AWS)

For the full Terraform and CI pipeline workflow (ECR image build, EKS
deployment, and infrastructure provisioning), use the `ci_entrega2_deploy.yml`
pipeline with a manual workflow dispatch. Refer to the pipeline file at
`.github/workflows/ci_entrega2_deploy.yml`. The pipeline reads `config.yaml`
and performs, in a single run: the Terraform apply in `tf_stacks` order
(`1_database` → `2_registry` → `3_dynamodb` → `eks` → `4_sns` → `5_sqs`),
the Docker image build and push to ECR for every entry of `apps`, the
`k8s_entrega2/` and `k8s_entrega3/` manifest apply, and finally the
`post_k8s_stacks` apply (`6_lambda`, which needs the host of the ingress
load balancer that only exists once the k8s step finished).

After the deploy finishes and before the evaluator, the manual step of the
email mechanism applies: the deploy pipeline creates the SNS topics and their
email subscriptions with the `EMAIL_TO_NOTIFY` address, and Amazon SNS sends
a confirmation email to that address. Open the email and click the
confirmation link once; while the subscription is not confirmed, SNS discards
the notifications and the evaluator fails the email validation.

The evaluation runs with `ci_entrega3_evaluador.yml` (which calls the
course reusable workflow `ci_evaluador_entrega3.yml`, the API tests of
RF-006 and RF-007 against the deployed platform), and the teardown runs
with `ci_entrega2_destroy.yml`, which destroys the `post_k8s_stacks`
first, then the k8s manifests, and then the `tf_stacks` in reverse order.
The pipelines must run in that exact order, and none of them must be
modified.

The database of the previous deliveries is a single shared RDS PostgreSQL
instance with per app schema and role isolation (provisioned by the
`1_database` Terraform stack), and the K8s Secrets are populated from AWS
Secrets Manager by the External Secrets Operator (ESO). The Ingress uses the
NGINX controller in AWS as well, because the AWS Academy academic accounts
do not allow an ALB (see the ingress section above and the
[Deployment View](./deployment-view.md)).

For the stack by stack infrastructure guide, see the [Terraform Deployment
Guide](./terraform-deployment.md).

## Running PlantUML Generator

Run from the repo root dir:

```bash
cd plantuml-generator && docker build -t plantuml/plantuml:latest .
cd ../
docker run --rm -e PLANTUML_LIMIT_SIZE=8192 -v "$(pwd)/docs/diagrams:/workspace" -w /workspace plantuml/plantuml:latest "**.puml"
```

## Terraform

The project uses Terraform to provision the cloud infrastructure (S3 state
bucket, RDS PostgreSQL, ECR repositories, the DynamoDB table of the CreditCard
entity, EKS cluster, the SNS email topics, the SQS card verification queue,
and the Lambda card worker) on AWS Academy. The active stacks, in
`config.yaml` `tf_stacks` deploy order, are `1_database`, `2_registry`,
`3_dynamodb`, `eks`, `4_sns`, and `5_sqs`; after the k8s manifests are
deployed the pipeline applies the `post_k8s_stacks` list, currently
`6_lambda`. `0_storage` is commented out because its bucket must exist
before any stack can initialize its S3 state backend (see the
[Terraform Deployment Guide](./terraform-deployment.md) for the storage
bootstrap prerequisite).

### Terraform Deployment Guide

The [Terraform Deployment Guide](./terraform-deployment.md) documents the
stack model, the deployment and destroy order, the local deployment steps,
and the verification commands.

### Stack READMEs

Each stack folder under `terraform/stacks/` contains its own README with the
components, variables, outputs, and cross stack relationships:

- [0_storage Stack README](../terraform/stacks/0_storage/README.md)
- [1_database Stack README](../terraform/stacks/1_database/README.md)
- [2_registry Stack README](../terraform/stacks/2_registry/README.md)
- [3_dynamodb Stack README](../terraform/stacks/3_dynamodb/README.md)
- [eks Stack README](../terraform/stacks/eks/README.md)
- [4_sns Stack README](../terraform/stacks/4_sns/README.md)
- [5_sqs Stack README](../terraform/stacks/5_sqs/README.md)
- [6_lambda Stack README](../terraform/stacks/6_lambda/README.md)

For CI/CD deployment details, refer to the `ci_entrega2_deploy.yml` and
`ci_entrega2_destroy.yml` pipelines in `.github/workflows/`.

## Kubernetes Resources

The Kubernetes manifests are organized in two folders, one per delivery.
They must not be applied together: both deployments define resources with
the same names (for example `users-app`, `users-app-service`) but with
different images.

### Entrega 2 manifests (`k8s_entrega2/`)

Applied by the `ci_entrega2_deploy.yml` pipeline (AWS/EKS) and by
`scripts/local-deploy.sh` (local Minikube). File names encode the apply
order, which matches the alphabetical order the pipeline uses. All
application Deployments and Services are ClusterIP; the only external entry
point is the Ingress.

| File | Components | Purpose |
|---|---|---|
| `k8s_entrega2/local-only/00-secrets.yml` | 5 K8s Secret objects | DB credentials for local Minikube, pointing at the shared Postgres instance (`shared-db-service`) |
| `k8s_entrega2/local-only/15-shared-db.yml` | Deployment + Service (shared-db) | Single shared PostgreSQL instance for local Minikube, with per app databases and roles |
| `k8s_entrega2/20-users-app.yml` | Deployment + Service (users-app) | users service, ClusterIP |
| `k8s_entrega2/21-posts-app.yml` | Deployment + Service (posts-app) | posts service, ClusterIP |
| `k8s_entrega2/22-offers-app.yml` | Deployment + Service (offers-app) | offers service, ClusterIP |
| `k8s_entrega2/23-routes-app.yml` | Deployment + Service (routes-app) | routes service, ClusterIP |
| `k8s_entrega2/24-scores-app.yml` | Deployment + Service (scores-app) | scores service, ClusterIP |
| `k8s_entrega2/25-rf003-create-post-app.yml` | Deployment + Service (rf003-create-post-app) | RF-003 orchestrator (stateless, no DB), ClusterIP |
| `k8s_entrega2/26-rf004-create-offer-app.yml` | Deployment + Service (rf004-create-offer-app) | RF-004 orchestrator (stateless, no DB), ClusterIP |
| `k8s_entrega2/27-rf005-query-post-app.yml` | Deployment + Service (rf005-query-post-app) | RF-005 orchestrator (stateless, no DB), ClusterIP |
| `k8s_entrega2/zz-ingress.yml` | Ingress resource (`microservices-ingress`) | Single entry point routing to all 8 services |

The `k8s_entrega2/00-secrets.yml` file is the AWS shaped template (it uses
`${RDS_ADDRESS}` style placeholders and is rendered by the pipeline), and
`k8s_entrega2/00-secrets.yml.tpl` documents the per app secret shape. The
`local-only/` folder is excluded from `config.yaml` `k8s_manifests`, so the
AWS EKS pipeline never applies the local shared DB (production uses real
RDS). The RF-007 callback receiver lives in this folder too
(`28-user-verification-callback.yml`), because it is deployed like any other
web workload.

### Entrega 3 manifests (`k8s_entrega3/`)

Applied by the `ci_entrega2_deploy.yml` pipeline after `k8s_entrega2/` (both
folders are listed in `config.yaml` `k8s_manifests`), and by
`scripts/local-deploy.sh` for the local Minikube deployment. The two files
use `${...}` placeholders that the deploy step renders with envsubst before
the apply.

| File | Components | Purpose |
|---|---|---|
| `k8s_entrega3/k8s-true-native-deployment.yml` | K8s Secret (`truenative-secret`) + Deployment + Service (`truenative`, `truenative-service`) | The external TrueNative platform (provided image `true-native:2.0.0`); the `SECRET_TOKEN` value is the base64 form of the `SECRET_TOKEN_B64` environment variable that the pipeline exports from the `eks` stack output, and the manifest never carries the raw token |
| `k8s_entrega3/k8s-credit-cards-deployment.yml` | K8s Secret (`lab-aws-credentials`) + Deployment + Service (`credit-cards-app`, `credit-cards-service`) | The credit cards microservice; the DynamoDB table name and the SQS queue name come from the `3_dynamodb` and `5_sqs` stack outputs, the queue URL is reconstructed from the queue name plus the account id and region at render time, and the pod authenticates to AWS with the session credentials of the deployer |

The `truenative-secret` created by the first manifest is consumed by both
the TrueNative container and the credit cards Deployment (the
`TRUENATIVE_SECRET_TOKEN` environment variable), so every client of the
platform uses the same token.

### Legacy Entrega 1 manifests (`k8s/`)

The legacy manifests live directly in `k8s/` (one file per app, plus one
NetworkPolicy per app pair):

| File | Components | Purpose |
|---|---|---|
| `k8s/users-app.yaml` | Deployment + Service (users-app, image `users_app:v0.0.0`), Deployment + Service (users-db) | Legacy users service with PostgreSQL, NodePort 30000 |
| `k8s/posts-app.yaml` | Deployment + Service (posts-app, image `posts_app:v0.0.0`), Deployment + Service (posts-db) | Legacy posts service with PostgreSQL, NodePort 30001 |
| `k8s/offers-app.yaml` | Deployment + Service (offers-app, image `offers_app:v0.0.0`), Deployment + Service (offers-db) | Legacy offers service with PostgreSQL, NodePort 30003 |
| `k8s/routes-app.yaml` | Deployment + Service (routes-app, image `routes_app:v0.0.0`), Deployment + Service (routes-db) | Legacy routes service with PostgreSQL, NodePort 30002 |
| `k8s/*-network-policy.yaml` | NetworkPolicy resources | Database isolation per app pair |

The `ci_entrega1_evaluador_k8s.yml` pipeline (GitHub) builds the
underscore images (`users_app:v0.0.0`, etc.) from the top-level
`users_app` / `posts_app` / `offers_app` / `routes_app` keys in
`config.yaml` and applies the whole `k8s/` tree. The top-level `config.yaml`
keys exist precisely so that `yq '.users_app.folder'` and friends resolve;
the `apps:` list (hyphenated image names) feeds the `ci_entrega2_deploy.yml`
pipeline instead.

### Secrets Management

All database credentials reference K8s Secrets via `secretKeyRef`. There are two deployment environments with different secrets strategies:

#### Local Minikube (shared database instance)

All five apps share a single PostgreSQL instance: the `shared-db` Deployment
in `k8s_entrega2/local-only/15-shared-db.yml`. Each app uses its own
database and role within that instance, and reads DB_HOST, DB_PORT, DB_NAME,
DB_USER, DB_PASSWORD from its own per app Secret in
`k8s_entrega2/local-only/00-secrets.yml` (DB_HOST is `shared-db-service`).

```bash
# Deploy local secrets and the shared database instance
kubectl apply -f k8s_entrega2/local-only/00-secrets.yml
kubectl apply -f k8s_entrega2/local-only/15-shared-db.yml
```

#### AWS Production (shared RDS instance)

All five apps connect to the **same** RDS PostgreSQL instance (`shared_db`). Data isolation is achieved at the PostgreSQL level through:

1. **Schema-level isolation**: Each app uses a different schema (`users`, `posts`, `offers`, `routes`, `scores`) within the shared database.
2. **Role-level isolation**: Each app has its own database role with privileges scoped to its own schema only no cross-schema queries are possible.

The credential model in production:

1. The `1_database` Terraform stack creates the AWS Secrets Manager secret
   with the RDS endpoint and credentials.
2. The `k8s_entrega2/00-secrets.yml` template (one Secret per app, for
   example `users-app-secrets`) holds the `DB_HOST`, `DB_PORT`, `DB_NAME`,
   `DB_USER`, and `DB_PASSWORD` keys; the pipeline renders the `${...}`
   placeholders and the **External Secrets Operator (ESO)** keeps the values
   in sync with AWS Secrets Manager at runtime.
3. Each app connects to the shared RDS instance using its own schema and
   role for data isolation.

**To switch an app Deployment for AWS:** Update each app's env block so
DB_HOST and DB_PORT read from the rendered secret values, and add
SCHEMA_NAME and DB_ROLE for the per app schema isolation. See the header
comment in `k8s_entrega2/20-users-app.yml` for the full instructions.

#### Production notes

1. The **External Secrets Operator (ESO)** watches these Secret objects and populates them from **AWS Secrets Manager** at runtime.
2. No base64 values need to be stored in the repository for production.
3. For local development, placeholder values are stored in `k8s_entrega2/local-only/00-secrets.yml` for testing purposes only.

To encode or decode credentials:

```bash
# Encode a value for K8s Secret data field
echo -n "my-secret-value" | base64

# Decode a base64 value back to plaintext
echo "bXktc2VjcmV0LXZhbHVl" | base64 -d
```

## Contributing

Work is managed through the team's project board (see `config.yaml` `board` for the URL).

Each team member is responsible for an application, including its code, tests, `Dockerfile`, `k8s/` manifests, and associated documentation.

Changes must be integrated through small, focused Pull Requests targeting the `main` branch.

## Team Rules

The project development team rules can be found in the following link:

- [Team Rules](./TeamRules.md)

## License

This project is for academic use in the context of the Cloud Application Development course.

## Authors

Refer to the `config.yaml` file for the list of team members and their participation percentage.




