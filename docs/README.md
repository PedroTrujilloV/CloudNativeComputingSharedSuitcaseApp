
# Project Delivery 2 - Shared Suitcase Package Delivery Platform (P2P Broker)

This project implements a brokerage platform (broker) for collaborative package delivery. Delivery 1 consisted of four independent applications (users, routes, posts, and offers), each with its own PostgreSQL database, deployed in containers and locally orchestrated using Kubernetes (Minikube). Delivery 2 (Entrega 2) extends the system with:

* **`scores_app`** a fifth microservice that persists a Score (Utilidad) value per offer (written by RF-004, read null-safely by RF-005).
* **Three orchestrator services** (`rf003_create_post_app`, `rf004_create_offer_app`, and `rf005_query_post_app`) that expose the client-facing endpoints for requirements RF-003, RF-004, and RF-005. Each orchestrator coordinates calls to the existing microservices while handling consistency (for example, RF-003 uses saga compensation to avoid orphaned routes when a downstream service fails mid-flow) and error propagation (integration failures return 503; business rejections pass through 412 unchanged).
* **A Kubernetes Ingress** that serves as the single public entry point for all eight services, routing by path prefix (`/users`, `/posts`, `/offers`, `/routes`, `/rf003`, `/rf004`, `/rf005`).
* **AWS Secrets Manager integration** (via Kubernetes External Secrets Operator) for database credentials in production deployments. Local development uses K8s Secrets with placeholder values stored in `k8s_entrega2/00-secrets.yml`.
* **A shared PostgreSQL instance** in the cloud deployment (single RDS with per-app schema and role isolation), provisioned through Terraform stacks and deployed via the `ci_entrega2_deploy.yml` pipeline, which builds and pushes the images to ECR.

## Page

- [Shared Suitcase App](https://miniature-disco-ee8nm6p.pages.github.io/)

By using this project, you will find:

* Five independent REST microservices (users, routes, posts, offers, scores), each exclusively responsible for its own data.
* Three orchestrator services (RF-003, RF-004, RF-005) that coordinate the microservices behind a single client-facing endpoint per requirement. Each orchestrator handles consistency (for example, RF-003 uses saga compensation to avoid orphaned routes when a downstream service fails mid-flow) and error propagation (integration failures return 503; business rejections pass through 412 unchanged).
* A shared PostgreSQL instance for all applications, with per-app database and role isolation enforced at the PostgreSQL level.
* Authentication based on random tokens (not JWT) for user management.
* Technical documentation as code, with architecture views modeled in PlantUML and published through GitHub Pages.
* GitHub Actions pipelines to validate deployment, database configuration, API contracts, and unit test coverage.

## Table of Contents

- [Project Delivery 2 - Shared Suitcase Package Delivery Platform (P2P Broker)](#project-delivery-2---shared-suitcase-package-delivery-platform-p2p-broker)
  - [Page](#page)
  - [Table of Contents](#table-of-contents)
  - [Team](#team)
  - [Architectural Views](#architectural-views)
    - [Consistency patterns for orchestrators](#consistency-patterns-for-orchestrators)
    - [Requirements](#requirements)
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
      - [AWS EKS production - ALB Ingress](#aws-eks-production---alb-ingress)
    - [AWS production deployment notes](#aws-production-deployment-notes)
  - [Running PlantUML Generator](#running-plantuml-generator)
  - [Technical Documentation](#technical-documentation)
  - [Terraform Cloud Infrastructure](#terraform-cloud-infrastructure)
    - [Stack READMEs](#stack-readmes)
  - [Kubernetes Resources](#kubernetes-resources)
    - [Entrega 2 manifests (`k8s_entrega2/`)](#entrega-2-manifests-k8s_entrega2)
    - [Legacy Entrega 1 manifests (`k8s/entrega1_k8s/`)](#legacy-entrega-1-manifests-k8sentrega1_k8s)
    - [Secrets Management](#secrets-management)
      - [Local Minikube (Entrega 1 model) per-app databases](#local-minikube-entrega-1-model-per-app-databases)
      - [AWS Production (Entrega 2 model) shared RDS instance](#aws-production-entrega-2-model-shared-rds-instance)
      - [Production notes](#production-notes)
  - [Contributing](#contributing)
  - [Team Rules](#team-rules)
  - [License](#license)
  - [Authors](#authors)

## Team

- Pedro Trujillo:  pe.trujillo@uniandes.edu.co

## Architectural Views

System architecture documentation can be found at:

- [Information View](./information-view.md)
- [Functional View](./functional-view.md)
- [Deployment View](./deployment-view.md)

### Consistency patterns for orchestrators

Each orchestrator has a documented consistency strategy (see [Solution Patterns](./solution-patterns.md)):

* **RF-003** uses saga compensation to guarantee that a failed request never leaves an orphaned route. If the post creation fails with an integration error and the route was created in this flow, the orchestrator deletes it via `DELETE /routes/{id}`. Business rejections (412) are passed through unchanged.
* **RF-004** writes a score after creating an offer (documented consistency rules for that requirement).
* **RF-005** reads data from multiple services and handles null values safely (for example, missing scores do not cause failures).

### Requirements
  * Requirement RF-003
    * [Solution pattern](./solution-patterns.md#rf-003). 
    * [Sequence View](./rf003-sequence-view.md). 
  * Requirement RF-004
    * [Solution pattern](./solution-patterns.md#rf-004). 
    * [Sequence View](./rf004-sequence-view.md). 
  * Requirement RF-005
    * [Solution pattern](./solution-patterns.md#rf-005). 
    * [Sequence View](./rf005-sequence-view.md). 

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
executed headless with [Newman](https://github.com/postmanlabs/newman)
(`npm i -g newman`), which is what `scripts/local-verify.sh` and the CI
workflows use including the saga-consistency runs that scale a deployment
to zero replicas between requests (see
[Testing saga consistency with Postman + kubectl](#testing-saga-consistency-with-postman--kubectl)).

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

* Eight services (four legacy microservices plus scores_app, rf003_create_post_app, rf004_create_offer_app, and rf005_query_post_app).
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
- [RF-003 Orchestation App](apps/rf003_create_post_app.md)
- [RF-004 Orchestation App](apps/rf004_create_offer_app.md)
- [RF-005 Orchestation App](apps/rf005_query_post_app.md)

## Run with Docker

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

## Run with Minikube

### Automated local deployment and verification (recommended)

Two scripts in `scripts/` automate the full local sequence. They are also
used by the `ci_local_manual_test.yml` workflow, so running them locally is
exactly the same sequence that runs on GitHub Actions:

```bash
# 1. Deploy: cleans old clusters/images, starts Minikube with the ingress
#    addon, builds all images, applies the k8s_entrega2/ manifests in order
#    and waits until every Deployment is ready.
bash scripts/local-deploy.sh

# 2. Verify: checks pods, services and the ingress; verifies all app
#    Services are ClusterIP; pings every app through the Ingress paths
#    only; runs a functional smoke test (user -> auth -> RF-003 create
#    post -> read post back); and runs the full Postman collections
#    (functional + consistency) against http://localhost:80, taking the
#    relevant deployment down with `kubectl scale` for each consistency
#    scenario (see "Testing saga consistency with Postman + kubectl").
bash scripts/local-verify.sh
```

Sizes can be tuned with environment variables, for example
`MINIKUBE_MEMORY=6g bash scripts/local-deploy.sh` on machines with a smaller
Docker Desktop memory allocation.

The legacy Entrega 1 deployment (`k8s/entrega1_k8s/`) is not deployed by
these scripts: it is evaluated separately by the
`ci_entrega1_evaluador_k8s.yml` pipeline on GitHub, and the two deployments
define the same resource names with different images, so they must not run
in the same cluster at the same time.

### Local deployment (Ingress-required)

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

# Deploy all components (Entrega 2 manifests)
kubectl apply -f k8s_entrega2/

# Check the status of pods, services, network policies and Ingress
kubectl get pods
kubectl get services
kubectl get networkpolicies
kubectl get ingress
```

### Testing saga consistency with Postman + kubectl

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

### Local deployment with Ingress (manual steps, reference)

The steps below are the manual equivalent of `scripts/local-deploy.sh` and
`scripts/local-verify.sh`. Use the scripts for day-to-day work; keep these
steps here to understand (and debug) what the scripts do.

#### Step 1 - Remove old images and containers

```bash
# Stop and remove any running Minikube cluster
minikube stop
minikube delete

# Remove leftover containers and images from previous deployments
docker rm -f $(docker ps -aq) 2>/dev/null
docker rmi $(docker images -q) 2>/dev/null
docker system prune -f
```

#### Step 2 - Start a fresh Minikube cluster with the Ingress addon enabled

```bash
minikube start --cpus=4 --memory=7g
minikube addons enable ingress
eval $(minikube docker-env)
```

#### Step 3 - Build all Docker images into Minikube

With `eval $(minikube docker-env)` active, `docker build` writes directly
into the Minikube container runtime:

```bash
# Legacy apps (Entrega 1, hyphenated image names for the k8s_entrega2/ deployment)
docker build -t users-app:v0.0.0 users_app
docker build -t posts-app:v0.0.0 posts_app
docker build -t offers-app:v0.0.0 offers_app
docker build -t routes-app:v0.0.0 routes_app

# Entrega 2 apps
docker build -t scores-app:v0.0.0 scores_app
docker build -t rf003-create-post-app:v0.0.0 rf003_create_post_app

# rf004/rf005 live in separate branches: build the ping-only stub image
docker build -t rf004-create-offer-app:v0.0.0 scripts/stubs
docker build -t rf005-query-post-app:v0.0.0 scripts/stubs
```

#### Step 4 - Apply Kubernetes manifests in order

The file names encode the apply order (00 secrets, 10 network policies,
20 apps, zz ingress last), which is the same alphabetical order the AWS
pipeline uses:

```bash
# 1. Secrets first (required by Deployments)
kubectl apply -f k8s_entrega2/00-secrets.yml

# 2. Network policies for database isolation
kubectl apply -f k8s_entrega2/10-users-network-policy.yml
kubectl apply -f k8s_entrega2/11-posts-network-policy.yml
kubectl apply -f k8s_entrega2/12-offers-network-policy.yml
kubectl apply -f k8s_entrega2/13-routes-network-policy.yml
kubectl apply -f k8s_entrega2/14-scores-network-policy.yml

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
```

#### Step 5 - Verify pods and services are running

```bash
kubectl get pods -o wide
kubectl get services
kubectl get ingress
```

All pods should show `STATUS: Running`. The Ingress should show an ADDRESS (provided by the minikube ingress addon).

#### Step 6 - Access services through the Ingress

The NGINX ingress controller exposes a NodePort on the Minikube node;
all external traffic enters through this single port and is routed by path:

```bash
NODE_IP=$(minikube ip)
INGRESS_PORT=$(kubectl get service ingress-nginx-controller \
  -n ingress-nginx -o jsonpath='{.spec.ports[0].nodePort}')
INGRESS="http://${NODE_IP}:${INGRESS_PORT}"

# Legacy apps (Entrega 1) - routed to /users/*, /posts/*, /offers/*, /routes/*
curl ${INGRESS}/users/ping
curl ${INGRESS}/posts/ping
curl ${INGRESS}/offers/ping
curl ${INGRESS}/routes/ping

# Orchestrator apps (Entrega 2) - routed to /rf003/*, /rf004/*, /rf005/*
curl ${INGRESS}/rf003/ping
curl ${INGRESS}/rf004/ping
curl ${INGRESS}/rf005/ping
```

All endpoints should return a `pong` response. The same checks, plus a
functional smoke test (create user, authenticate, create a post through
RF-003, read the post back), are automated in `scripts/local-verify.sh`.

### Troubleshooting local deployment

* Pods stuck in `Pending` - check with `kubectl describe pod <pod-name>` for resource constraints or scheduling errors.
* Pods in `CrashLoopBackOff` - check logs: `kubectl logs <pod-name>`. Verify image is correctly tagged and the app code exists.
* Ingress shows `<pending>` address - ensure `minikube addons enable ingress` was run, then reapply `kubectl apply -f k8s_entrega2/zz-ingress.yml`.
* No endpoints reachable through Ingress - confirm the ingress addon is enabled (`minikube addons enable ingress`) and check `kubectl get service ingress-nginx-controller -n ingress-nginx` for the controller's NodePort (dynamic, not hardcoded).

### Ingress configurations (two environments)

The single Ingress resource is defined in `k8s_entrega2/zz-ingress.yml`
(name: `microservices-ingress`). It is the same resource in both
environments; only the controller class and annotations differ.

#### Local Minikube - NGINX Ingress

Use this configuration for local development. The manifest is pre-configured with:

- `ingressClassName: nginx` routes to the Minikube NGINX ingress addon
- `kubernetes.io/ingress.class: nginx` annotation for NGINX compatibility
- No ALB annotations keeps the manifest clean for local use

Steps:
1. `minikube addons enable ingress`
2. `kubectl apply -f k8s_entrega2/00-secrets.yml -f k8s_entrega2/zz-ingress.yml`
3. `curl ${INGRESS}/users/ping` (replace with dynamic ingress URL from Step 6)

#### AWS EKS production - ALB Ingress

Use this configuration for cloud deployment. Steps to switch:

1. Install the **AWS Load Balancer Controller** (replaces the minikube ingress addon).
2. Change `ingressClassName: nginx` to `ingressClassName: alb` in `k8s_entrega2/zz-ingress.yml`.
3. Remove the `kubernetes.io/ingress.class` annotation and keep only ALB annotations:
   - `alb.ingress.kubernetes.io/scheme: internet-facing`
   - `alb.ingress.kubernetes.io/target-type: ip`
   - `alb.ingress.kubernetes.io/listen-ports: '[{\"HTTPS\":443}]'`
   - `alb.ingress.kubernetes.io/ip-address-type: ipv4`
4. Install the **External Secrets Operator (ESO)** to populate K8s Secrets from **AWS Secrets Manager** at runtime. Secret objects are created by ESO; you do not need to manage base64 values manually.
5. Deploy with `kubectl apply -f k8s_entrega2/`. The ALB provisioned by the controller serves as the single entry point.

### AWS production deployment notes

For the full Terraform and CI pipeline workflow (ECR image build, EKS deployment, infrastructure provisioning), use the `ci_entrega2_deploy.yml` pipeline with a manual workflow dispatch. Refer to the pipeline file at `.github/workflows/ci_entrega2_deploy.yml`.

## Running PlantUML Generator

run from the repo root dir:
```
cd plantuml-generator && docker build -t plantuml/plantuml:latest .
cd ../
docker run --rm -e PLANTUML_LIMIT_SIZE=8192 -v "$(pwd)/docs/diagrams:/workspace" -w /workspace plantuml/plantuml:latest "**.puml"
```

## Technical Documentation

Development documentation can be found at:

- [Development View](./development-view.md)
- [Information View](./information-view.md)
- [Functional View](./functional-view.md)
- [Deployment View](./deployment-view.md)
- [Solution Patterns (RF-003, RF-004, RF-005)](./solution-patterns.md)

## Terraform Cloud Infrastructure

The project uses Terraform to provision cloud infrastructure (EKS, RDS PostgreSQL, ECR) on AWS Academy. The stacks are deployed in order: network, data, compute.

### Stack READMEs

- [Terraform Deployment Guide](./terraform-deployment.md)
- [Network Stack README](./terraform/network-README.md)
- [Data Stack README](./terraform/data-README.md)
- [Compute Stack README](./terraform/compute-README.md)

For local deployment steps, see the Terraform Deployment Guide above. For CI/CD deployment details, refer to the `ci_entrega2_deploy.yml` pipeline in `.github/workflows/`.
## Kubernetes Resources

The Kubernetes manifests are organized in two folders, one per delivery.
They must not be applied together: both deployments define resources with
the same names (for example `users-app`, `users-app-service`, `users-db`)
but with different images.

### Entrega 2 manifests (`k8s_entrega2/`)

Applied by the `ci_entrega2_deploy.yml` pipeline (AWS/EKS) and by
`scripts/local-deploy.sh` (local Minikube). File names encode the apply
order, which matches the alphabetical order the pipeline uses:

| File | Components | Purpose |
|---|---|---|
| `k8s_entrega2/00-secrets.yml` | 5 K8s Secret objects (local) | DB credentials for **local minikube**; each app has its own separate Postgres pod in local mode |
| `k8s_entrega2/00-aws-secrets-shared-db.yml` | 6 K8s Secrets (AWS) | Shared RDS connection (`shared-db-secrets`) + per-app schema/role credentials for **AWS production** where all apps share one database instance |
| `k8s_entrega2/10-users-network-policy.yml` | NetworkPolicy (users-network) | users-app can only talk to users-db |
| `k8s_entrega2/11-posts-network-policy.yml` | NetworkPolicy (posts-network) | posts-app can only talk to posts-db |
| `k8s_entrega2/12-offers-network-policy.yml` | NetworkPolicy (offers-network) | offers-app can only talk to offers-db |
| `k8s_entrega2/13-routes-network-policy.yml` | NetworkPolicy (routes-network) | routes-app can only talk to routes-db |
| `k8s_entrega2/14-scores-network-policy.yml` | NetworkPolicy (scores-network) | scores-app can only talk to scores-db |
| `k8s_entrega2/20-users-app.yml` | Deployment + Service (users-app), Deployment + Service (users-db) | users service with PostgreSQL, ClusterIP |
| `k8s_entrega2/21-posts-app.yml` | Deployment + Service (posts-app), Deployment + Service (posts-db) | posts service with PostgreSQL, ClusterIP |
| `k8s_entrega2/22-offers-app.yml` | Deployment + Service (offers-app), Deployment + Service (offers-db) | offers service with PostgreSQL, ClusterIP |
| `k8s_entrega2/23-routes-app.yml` | Deployment + Service (routes-app), Deployment + Service (routes-db) | routes service with PostgreSQL, ClusterIP |
| `k8s_entrega2/24-scores-app.yml` | Deployment + Service (scores-app), Deployment + Service (scores-db) | scores service with PostgreSQL, ClusterIP |
| `k8s_entrega2/25-rf003-create-post-app.yml` | Deployment + Service (rf003-create-post-app) | RF-003 orchestrator (stateless, no DB), ClusterIP |
| `k8s_entrega2/26-rf004-create-offer-app.yml` | Deployment + Service (rf004-create-offer-app) | RF-004 orchestrator (stateless, no DB), ClusterIP |
| `k8s_entrega2/27-rf005-query-post-app.yml` | Deployment + Service (rf005-query-post-app) | RF-005 orchestrator (stateless, no DB), ClusterIP |
| `k8s_entrega2/zz-ingress.yml` | Ingress resource (`microservices-ingress`) | Single entry point routing to all 8 services |

### Legacy Entrega 1 manifests (`k8s/entrega1_k8s/`)

| File | Components | Purpose |
|---|---|---|
| `k8s/entrega1_k8s/users-app.yaml` | Deployment + Service (users-app, image `users_app:v0.0.0`), Deployment + Service (users-db) | Legacy users service with PostgreSQL, NodePort 30000 |
| `k8s/entrega1_k8s/posts-app.yaml` | Deployment + Service (posts-app, image `posts_app:v0.0.0`), Deployment + Service (posts-db) | Legacy posts service with PostgreSQL, NodePort 30001 |
| `k8s/entrega1_k8s/offers-app.yaml` | Deployment + Service (offers-app, image `offers_app:v0.0.0`), Deployment + Service (offers-db) | Legacy offers service with PostgreSQL, NodePort 30003 |
| `k8s/entrega1_k8s/routes-app.yaml` | Deployment + Service (routes-app, image `routes_app:v0.0.0`), Deployment + Service (routes-db) | Legacy routes service with PostgreSQL, NodePort 30002 |
| `k8s/entrega1_k8s/*-network-policy.yaml` | NetworkPolicy resources | Database isolation per app pair |

The `ci_entrega1_evaluador_k8s.yml` pipeline (GitHub) builds the
underscore images (`users_app:v0.0.0`, etc.) from the top-level
`users_app` / `posts_app` / `offers_app` / `routes_app` keys in
`config.yaml` and applies the whole `k8s/` tree (which only contains this
subfolder). The top-level `config.yaml` keys exist precisely so that
`yq '.users_app.folder'` and friends resolve; the `apps:` list (hyphenated
image names) feeds the `ci_entrega2_deploy.yml` pipeline instead.

### Secrets Management

All database credentials reference K8s Secrets via `secretKeyRef`. There are two deployment environments with different secrets strategies:

#### Local Minikube (Entrega 1 model) per-app databases

Each app has its own separate PostgreSQL pod. Each app reads DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD from its own per-app Secret in `k8s_entrega2/00-secrets.yml`.

```bash
# Deploy local secrets
kubectl apply -f k8s_entrega2/00-secrets.yml
```

#### AWS Production (Entrega 2 model) shared RDS instance

All five apps connect to the **same** RDS PostgreSQL instance (`shared_db`). Data isolation is achieved at the PostgreSQL level through:

1. **Schema-level isolation**: Each app uses a different schema (`users`, `posts`, `offers`, `routes`, `scores`) within the shared database.
2. **Role-level isolation**: Each app has its own database role with privileges scoped to its own schema only no cross-schema queries are possible.

The two-step credential model:

1. `shared-db-secrets` (shared by all apps) provides `DB_HOST`, `DB_PORT`, and `DB_NAME` (the shared RDS endpoint). Populated by ESO from a single AWS Secrets Manager entry (for example, `aws-secrets-manager/shared-db`).
2. Per-app credentials (for example, `users-app-db-creds`) provide `SCHEMA_NAME`, `DB_ROLE`, `DB_USER`, and `DB_PASSWORD`. Each app's deployment sets `DB_HOST` and `DB_PORT` from `shared-db-secrets`, and connects to the shared database using its own schema/role for data isolation.

```bash
# Deploy AWS production secrets (ESO will populate values from Secrets Manager)
kubectl apply -f k8s_entrega2/00-aws-secrets-shared-db.yml
```

**To switch an app Deployment for AWS:** Update each app's env block so DB_HOST and DB_PORT read from `shared-db-secrets` (instead of the per-app local secret), and add SCHEMA_NAME and DB_ROLE from the per-app credentials. See the header comment in `k8s_entrega2/20-users-app.yml` for the full instructions.

#### Production notes

1. The **External Secrets Operator (ESO)** watches these Secret objects and populates them from **AWS Secrets Manager** at runtime.
2. No base64 values need to be stored in the repository for production.
3. For local development, placeholder values are stored in `k8s_entrega2/00-secrets.yml` and `k8s_entrega2/00-aws-secrets-shared-db.yml` for testing purposes only.

To encode or decode credentials:

```bash
# Encode a value for K8s Secret data field
echo -n "my-secret-value" | base64

# Decode a base64 value back to plaintext
echo "bXktc2VjcmV0LXZhbHVl" | base64 -d
```

## Contributing

Work is managed through the team's repository [Kanban board](https://github.com/orgs/MISW-4301-Desarrollo-Apps-en-la-Nube/projects/370/views/1).

Each team member is responsible for an application, including its code, tests, `Dockerfile`, `k8s/` manifests, and associated documentation.

Changes must be integrated through small, focused Pull Requests targeting the `main` branch.

## Team Rules

The project development team rules can be found in the following link:

- [Team Rules](./TeamRules.md)

## License

This project is for academic use in the context of the Cloud Application Development course.

## Authors

Refer to the `config.yaml` file for the list of team members and their participation percentage.




