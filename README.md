

## Project Structure

```text
.
├── users_app/                # User management application
├── routes_app/               # Route management application
├── posts_app/                # Post management application
├── offers_app/               # Offer management application
├── scores_app/               # Scores management application (Entrega 2)
├── rf003_create_post_app/    # RF-003 orchestrator (Entrega 2)
├── rf004_create_offer_app/   # RF-004 orchestrator (Entrega 2)
├── rf005_query_post_app/     # RF-005 orchestrator (Entrega 2)
├── k8s/                      # Legacy Entrega 1 Kubernetes manifests
├── k8s_entrega2/             # Entrega 2 Kubernetes manifests (secrets, apps, ingress, local-only shared DB)
├── terraform/                # Terraform stacks and environments for the AWS infrastructure
├── scripts/                  # Local deploy/verify scripts, Postman collections, Terraform helper scripts
├── plantuml-generator/       # Docker image that renders the PlantUML diagrams
├── styles/                   # Vale style packages for the documentation checks
├── docs/                     # Technical documentation as code
│   └── diagrams/             # PlantUML diagrams (entities, components, deployment, networks, sequences)
├── config.yaml               # Team and application configuration
└── README.md                 # This file
```

More detailed information in the [Development View](./docs/development-view.md)
and [Technical Documentation](./docs/README.md)






# Deployment Guide

This guide describes, step by step, how to fully deploy the project: the applications (users, posts, routes, offers, scores), their databases, the generation of the technical documentation (PlantUML diagrams), and the final validation on Minikube.

## Table of Contents

- [Deployment Guide](#deployment-guide)
  - [Table of Contents](#table-of-contents)
  - [Delivery 2 (Entrega 2) Changes](#delivery-2-entrega-2-changes)
  - [Terraform Stacks](#terraform-stacks)
  - [How to run](#how-to-run)
  - [Cloud Deployment (AWS)](#cloud-deployment-aws)
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
  - [Step 10: Access the Applications via Ingress](#step-10-access-the-applications-via-ingress)
  - [Step 11: Test the API with Postman](#step-11-test-the-api-with-postman)
  - [Step 12: Run the Validation Pipelines](#step-12-run-the-validation-pipelines)
  - [Step 13: Cleanup (Optional)](#step-13-cleanup-optional)
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
* **Shared database:** both cloud and local deployments use a single PostgreSQL instance. In production (Terraform stacks) all applications share an AWS RDS instance with per-app schema and role isolation. The local Minikube model mirrors this architecture via `k8s_entrega2/local-only/15-shared-db.yml` a single shared Postgres Deployment with per-app databases and PostgreSQL-level role isolation applied by `local-deploy.sh` (this folder is excluded from `config.yaml k8s_manifests`).

The rest of the guide below documents the Delivery 1 local deployment model;
the `scores_app` build/run steps follow the same pattern as the other
applications (see its [README](./scores_app/README.md)).


## Terraform Stacks

The infrastructure is defined as four Terraform stacks under `terraform/stacks/`, each with its own stack-specific README:

| Stack | Description | Stack README |
|-------|-------------|--------------|
| **0_storage** | S3 bucket for shared object storage across all apps | [terraform/stacks/0_storage/README.md](./terraform/stacks/0_storage/README.md) |
| **1_database** | Shared PostgreSQL RDS instance + Secrets Manager | [terraform/stacks/1_database/README.md](./terraform/stacks/1_database/README.md) |
| **2_registry** | ECR repositories for Docker images (8 repos) | [terraform/stacks/2_registry/README.md](./terraform/stacks/2_registry/README.md) |
| **eks** | EKS cluster + managed node groups for workloads | [terraform/stacks/eks/README.md](./terraform/stacks/eks/README.md) |

The `config.yaml` `tf_stacks` list defines the deploy order used by the
`ci_entrega2_deploy.yml` pipeline: `1_database` → `2_registry` → `eks`
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
   (`1_database` → `2_registry` → `eks`). Each stack uses the
   `terraform/environments/<environment>/<stack>/` tfvars and stores its state
   in the shared S3 bucket (see `backend.tfvars`).
2. **Docker image build and push**: one image per entry in the `apps:` list
   (the five microservices plus the three orchestrators), pushed to the ECR
   repositories created by the `2_registry` stack.
3. **Kubernetes manifests apply**: the `k8s_entrega2/` manifests are applied
   to the EKS cluster in alphabetical file name order (00 secrets, 20 apps,
   zz ingress last).

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

Confirm that the `config.yaml` file at the repository root has been properly completed: team name, members, board link, documentation link, and the data (`folder`, `image_name`, `image_tag`, `authors`) for each of the five applications (`users_app`, `posts_app`, `routes_app`, `offers_app`, `scores_app`) and the three orchestrators.

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

Verify that all eight images were built successfully:

```bash
docker images | grep -E "users|posts|routes|offers|scores|rf003|rf004|rf005"
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

Apply the declarative manifests located in `k8s_entrega2/` (Deployments, Services, Secrets, and Ingress) in the same order `scripts/local-deploy.sh` uses: the local secrets and the shared Postgres instance first (both in `k8s_entrega2/local-only/`), then the eight application Deployments and Services, and the Ingress last:

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
kubectl apply -f k8s_entrega2/zz-ingress.yml
```

> **Note:** The `k8s_entrega2/local-only/` folder contains the local secrets and the shared Postgres instance used only for local Minikube testing. It is excluded from `config.yaml k8s_manifests` so the AWS EKS pipeline never applies it (production uses real RDS and the ESO populated secrets).

## Step 9: Verify the Deployment

Confirm that all nine workloads (5 applications + 3 orchestrators + shared-db) are running correctly in the `default` namespace:
Confirm that all nine workloads (5 applications + 3 orchestrators + shared-db) are running correctly in the `default` namespace:

```bash
kubectl get pods
kubectl get services
kubectl get ingress
kubectl get ingress
```

All pods should show `Running` status and `READY 1/1`. If any pod fails, check the logs:

```bash
kubectl logs <pod-name>
kubectl describe pod <pod-name>
```

## Step 10: Access the Applications via Ingress
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
# Each should respond: pong
```

## Step 11: Test the API with Postman

Import the corresponding Postman collections for each application and update the `baseUrl` environment variable (**Current value**, not Initial value) with the URL obtained in the previous step. Run each collection (`Run collection`) and confirm that all tests pass successfully.

## Step 12: Run the Validation Pipelines
## Step 12: Run the Validation Pipelines

Before creating the release, manually run the provided pipelines (without modifying them) from the **Actions** tab of the repository on GitHub. For Entrega 1:

* `Entrega 1 - Evaluador Implementación` (`ci_entrega1_evaluador_k8s.yml`)

For Entrega 2 (cloud deployment via Terraform stacks and ECR images):

* `Entrega 2 - Deploy` (`ci_entrega2_deploy.yml`)
* `Entrega 2 - Destroy` (`ci_entrega2_destroy.yml`, manual and destructive)

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
## Step 13: Cleanup (Optional)

To remove the deployment and stop Minikube after testing:

```bash
kubectl delete -f k8s_entrega2/
kubectl delete -f k8s_entrega2/local-only/15-shared-db.yml  # local minikube only
kubectl delete -f k8s_entrega2/
kubectl delete -f k8s_entrega2/local-only/15-shared-db.yml  # local minikube only
minikube stop
# To completely remove the cluster:
minikube delete
```

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

````
