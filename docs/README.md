
# Project Delivery 2 - Shared Suitcase Package Delivery Platform (P2P Broker)

This project implements a brokerage platform (broker) for collaborative package delivery. Delivery 1 consisted of four independent applications (users, routes, posts, and offers), each with its own PostgreSQL database, deployed in containers and locally orchestrated using Kubernetes (Minikube). Delivery 2 (Entrega 2) extends the system with:

* **`scores_app`** a fifth microservice that persists a Score (Utilidad) value per offer (written by RF-004, read null-safely by RF-005).
* **Three orchestrator services** (`rf003_create_post_app`, `rf004_create_offer_app`, and `rf005_query_post_app`) that expose the client-facing endpoints for requirements RF-003, RF-004, and RF-005. Each orchestrator coordinates calls to the existing microservices while handling consistency (for example, RF-003 uses saga compensation to avoid orphaned routes when a downstream service fails mid-flow) and error propagation (integration failures return 503; business rejections pass through 412 unchanged).
* **A Kubernetes Ingress** that serves as the single public entry point for all eight services, routing by path prefix (`/users`, `/posts`, `/offers`, `/routes`, `/rf003`, `/rf004`, `/rf005`).
* **AWS Secrets Manager integration** (via Kubernetes External Secrets Operator) for database credentials in production deployments. Local development uses K8s Secrets with placeholder values stored in `k8s/secrets.yaml`.
* **A shared PostgreSQL instance** in the cloud deployment (single RDS with per-app schema and role isolation), provisioned through Terraform stacks and deployed via the `ci_entrega2_deploy.yml` pipeline, which builds and pushes the images to ECR.

## Page

- [Shared Suitcase App](https://ubiquitous-journey-4zq6j6o.pages.github.io/)

By using this project, you will find:

* Five independent REST microservices (users, routes, posts, offers, scores), each exclusively responsible for its own data.
* Three orchestrator services (RF-003, RF-004, RF-005) that coordinate the microservices behind a single client-facing endpoint per requirement. Each orchestrator handles consistency (for example, RF-003 uses saga compensation to avoid orphaned routes when a downstream service fails mid-flow) and error propagation (integration failures return 503; business rejections pass through 412 unchanged).
* Network isolation between each application and its database through Kubernetes Network Policies.
* Authentication based on random tokens (not JWT) for user management.
* A shared PostgreSQL instance in the cloud deployment, with per-app schema and role isolation.
* Technical documentation as code, with architecture views modeled in PlantUML and published through GitHub Pages.
* GitHub Actions pipelines to validate deployment, network policies, API contracts, and unit test coverage.

## Table of Contents

- [Project Delivery 2 - Shared Suitcase Package Delivery Platform (P2P Broker)](#project-delivery-2---shared-suitcase-package-delivery-platform-p2p-broker)
  - [Page](#page)
  - [Table of Contents](#table-of-contents)
  - [Team](#team)
  - [Architectural Views](#architectural-views)
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
    - [Local deployment (without Ingress)](#local-deployment-without-ingress)
    - [Local deployment with Ingress (recommended for Entrega 2)](#local-deployment-with-ingress-recommended-for-entrega-2)
    - [Troubleshooting local deployment](#troubleshooting-local-deployment)
    - [AWS production deployment notes](#aws-production-deployment-notes)
  - [Runing plantuml-generator](#runing-plantuml-generator)
  - [Technical Documentation](#technical-documentation)
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
* Five PostgreSQL databases in the local model (one per database-owning app: users_db, posts_db, offers_db, routes_db, scores_db).
* Kubernetes Services.
* Network Policies.
* Application-to-database communication.

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
* Check Network Policies.
* View application logs.
* Debug Kubernetes workloads.

For example:

```bash
kubectl apply -f k8s/
kubectl get pods
kubectl get services
kubectl get networkpolicies
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

For `rf004_create_offer_app` and `rf005_query_post_app`, source folders do not yet exist in this repository. Their Kubernetes manifests (`k8s/rf004-create-offer-app.yaml` and `k8s/rf005-query-post-app.yaml`) are provided for the deployment pipeline. When source code is added, follow the same Dockerfile pattern as `rf003_create_post_app/Dockerfile`.

## Run with Docker

Each application has its own `Dockerfile`. Build and run each application independently:

```bash
cd <app_folder>
docker build -t <image_name>:<image_tag> .
docker run -p <port>:<port> <image_name>:<image_tag>
```

The values of `image_name` and `image_tag` must exactly match those defined in `config.yaml` and in the manifests under `k8s/`.

## Run with Minikube

### Local deployment (without Ingress)

```bash
minikube start --cpus=2 --memory=4g

# Build and load each image into Minikube
minikube image load <image_name>:<image_tag>

# Deploy all components
kubectl apply -f k8s/

# Check the status of pods, services, and network policies
kubectl get pods
kubectl get services
kubectl get networkpolicies
```

Minikube will assign a NodePort to each application. You can retrieve it using:

```bash
minikube service <service-name> --url
```

This URL can then be used to access the application from your browser or Postman.

### Local deployment with Ingress (recommended for Entrega 2)

In Entrega 2 a single Ingress resource routes all traffic through one entry point. Follow these manual steps to deploy locally:

#### Step 1 - Remove old images and containers

```bash
# Stop and remove any running Minikube cluster
minikube stop
minikube delete

# Remove leftover pods or services from previous deployments
kubectl delete namespace default --ignore-not-found=true
kubectl delete ingress --all --all-namespaces --ignore-not-found=true
```

#### Step 2 - Start a fresh Minikube cluster with the Ingress addon enabled

```bash
minikube start --cpus=4 --memory=8g
minikube addons enable ingress
```

#### Step 3 - Build and load all Docker images into Minikube

For each app listed in `config.yaml`:

```bash
# Legacy apps (Entrega 1)
cd users_app && minikube image build -t users-app:v0.0.0 . && cd ..
cd posts_app && minikube image build -t posts-app:v0.0.0 . && cd ..
cd offers_app && minikube image build -t offers-app:v0.0.0 . && cd ..
cd routes_app && minikube image build -t routes-app:v0.0.0 . && cd ..

# Entrega 2 apps
cd scores_app && minikube image build -t scores-app:v0.0.0 . && cd ..
cd rf003_create_post_app && minikube image build -t rf003-create-post-app:v0.0.0 . && cd ..
# For apps without source folders yet (rf004, rf005) use placeholder images:
# docker build with a stub Dockerfile, then:
minikube image load users-app:v0.0.0 --name rf004-create-offer-app:v0.0.0
minikube image load users-app:v0.0.0 --name rf005-query-post-app:v0.0.0
```

#### Step 4 - Apply Kubernetes manifests in order

```bash
# 1. Secrets first (required by Deployments)
kubectl apply -f k8s/secrets.yaml

# 2. Network policies for database isolation
kubectl apply -f k8s/users-network-policy.yaml
kubectl apply -f k8s/posts-network-policy.yaml
kubectl apply -f k8s/offers-network-policy.yaml
kubectl apply -f k8s/routes-network-policy.yaml
kubectl apply -f k8s/scores-network-policy.yaml

# 3. All app Deployments and Services (order does not matter)
kubectl apply -f k8s/users-app.yaml
kubectl apply -f k8s/posts-app.yaml
kubectl apply -f k8s/offers-app.yaml
kubectl apply -f k8s/routes-app.yaml
kubectl apply -f k8s/scores-app.yaml
kubectl apply -f k8s/rf003-create-post-app.yaml
kubectl apply -f k8s/rf004-create-offer-app.yaml
kubectl apply -f k8s/rf005-query-post-app.yaml

# 4. Ingress (applied last, routes to all above services)
kubectl apply -f k8s/ingress.yaml
```

#### Step 5 - Verify pods and services are running

```bash
kubectl get pods -o wide
kubectl get services
kubectl get ingress
```

All pods should show `STATUS: Running`. The Ingress should show an ADDRESS (provided by the minikube ingress addon).

#### Step 6 - Access services through the Ingress

Start a tunnel to expose the Ingress load balancer:

```bash
minikube tunnel
# Enter your system password when prompted
```

In another terminal, verify all endpoints are reachable:

```bash
# Legacy apps (Entrega 1)
curl http://localhost/users/ping
curl http://localhost/posts/ping
curl http://localhost/offers/ping
curl http://localhost/routes/ping

# Orchestrator apps (Entrega 2)
curl http://localhost/rf003/ping
curl http://localhost/rf004/ping
curl http://localhost/rf005/ping
```

All endpoints should return `{"status": "ok"}` or a similar pong response.

### Troubleshooting local deployment

* Pods stuck in `Pending` - check with `kubectl describe pod <pod-name>` for resource constraints or scheduling errors.
* Pods in `CrashLoopBackOff` - check logs: `kubectl logs <pod-name>`. Verify image is correctly tagged and the app code exists.
* Ingress shows `<pending>` address - ensure `minikube addons enable ingress` was run, then reapply `kubectl apply -f k8s/ingress.yaml`.
* `curl` to localhost fails after tunnel starts - confirm you have `kubectl proxy` or `minikube tunnel` running with the correct addon enabled.

### AWS production deployment notes

In production on AWS EKS:

1. Install the **AWS Load Balancer Controller** (replaces the minikube ingress addon).
2. Install the **External Secrets Operator (ESO)** to populate K8s Secrets from **AWS Secrets Manager** at runtime. Set `type: Opaque` Secret objects are created by ESO; you do not need to manage base64 values manually.
3. Update the Ingress annotation `ingressClassName: nginx` to `ingressClassName: alb` in `k8s/ingress.yaml`.
4. Deploy with `kubectl apply -f k8s/` as above. The ALB provisioned by the controller serves as the single entry point.

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

## Kubernetes Resources

All Kubernetes manifests are in the `k8s/` directory:

| File | Components | Purpose |
|---|---|---|
| `k8s/users-app.yaml` | Deployment + Service (users-app), Deployment + Service (users-db) | Legacy users service with PostgreSQL |
| `k8s/posts-app.yaml` | Deployment + Service (posts-app), Deployment + Service (posts-db) | Legacy posts service with PostgreSQL |
| `k8s/offers-app.yaml` | Deployment + Service (offers-app), Deployment + Service (offers-db) | Legacy offers service with PostgreSQL |
| `k8s/routes-app.yaml` | Deployment + Service (routes-app), Deployment + Service (routes-db) | Legacy routes service with PostgreSQL |
| `k8s/scores-app.yaml` | Deployment + Service (scores-app), Deployment + Service (scores-db) | New scoring service with PostgreSQL |
| `k8s/rf003-create-post-app.yaml` | Deployment + Service (rf003-create-post-app) | RF-003 orchestrator (stateless, no DB) |
| `k8s/rf004-create-offer-app.yaml` | Deployment + Service (rf004-create-offer-app) | RF-004 orchestrator (stateless, no DB) |
| `k8s/rf005-query-post-app.yaml` | Deployment + Service (rf005-query-post-app) | RF-005 orchestrator (stateless, no DB) |
| `k8s/ingress.yaml` | Ingress resource | Single entry point routing to all 8 services |
| `k8s/secrets.yaml` | 5 K8s Secret objects (local) | DB credentials for **local minikube**—each app has its own separate Postgres pod in local mode |
| `k8s/secrets-aws-shared-db.yaml` | 6 K8s Secrets (AWS) | Shared RDS connection (`shared-db-secrets`) + per-app schema/role credentials for **AWS production** where all apps share one database instance |
| `k8s/*-network-policy.yaml` | NetworkPolicy resources | Database isolation per app pair |

### Secrets Management

All database credentials reference K8s Secrets via `secretKeyRef`. There are two deployment environments with different secrets strategies:

#### Local Minikube (Entrega 1 model)—per-app databases

Each app has its own separate PostgreSQL pod. Each app reads DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD from its own per-app Secret in `k8s/secrets.yaml`.

```bash
# Deploy local secrets
kubectl apply -f k8s/secrets.yaml
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
kubectl apply -f k8s/secrets-aws-shared-db.yaml
```

**To switch an app Deployment for AWS:** Update each app's env block so DB_HOST and DB_PORT read from `shared-db-secrets` (instead of the per-app local secret), and add SCHEMA_NAME and DB_ROLE from the per-app credentials. See the header comment in `k8s/users-app.yaml` for the full instructions.

#### Production notes

1. The **External Secrets Operator (ESO)** watches these Secret objects and populates them from **AWS Secrets Manager** at runtime.
2. No base64 values need to be stored in the repository for production.
3. For local development, placeholder values are stored in `k8s/secrets.yaml` and `k8s/secrets-aws-shared-db.yaml` for testing purposes only.

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




