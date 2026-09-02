

## Project Structure

```text
.
├── users_app/          # User management application
├── routes_app/         # Route management application
├── posts_app/          # Post management application
├── offers_app/         # Offer management application
├── scores_app/         # Scores management application
├── k8s/                # Kubernetes deployment manifests
├── docs/               # Technical documentation as code
│   └── diagrams/       # PlantUML diagrams (entities, components, deployment, networks)
├── config.yaml         # Team and application configuration
└── README.md           # This file
```

More detailed information in the [Development View](./docs/development-view.md)
and [Technical Documentation](./docs/README.md)


# Deployment Guide

This guide describes, step by step, how to fully deploy the project: the applications (users, posts, routes, offers, scores), their databases, the generation of the technical documentation (PlantUML diagrams), and the final validation on Minikube.

## Table of Contents

- [Deployment Guide](#deployment-guide)
  - [Table of Contents](#table-of-contents)
  - [Delivery 2 (Entrega 2) Changes](#delivery-2-entrega-2-changes)
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
  - [Step 10: Obtain the URLs for Each Application](#step-10-obtain-the-urls-for-each-application)
  - [Step 11: Test the API with Postman](#step-11-test-the-api-with-postman)
  - [Step 12: Verify Network Isolation](#step-12-verify-network-isolation)
  - [Step 13: Run the Validation Pipelines](#step-13-run-the-validation-pipelines)
  - [Step 14: Cleanup (Optional)](#step-14-cleanup-optional)
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
* **Shared database:** in the cloud deployment (Terraform stacks) all
  applications share a single PostgreSQL instance, with per-app schema and
  role isolation. The local Minikube model in this guide keeps one database
  per application for isolation.

The rest of the guide below documents the Delivery 1 local deployment model;
the `scores_app` build/run steps follow the same pattern as the other
applications (see its [README](./scores_app/README.md)).

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

Verify that all five images were built successfully:

```bash
docker images | grep -E "users|posts|routes|offers|scores"
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
```

Verify that the images are available inside Minikube:

```bash
minikube image ls | grep -E "users|posts|routes|offers|scores"
```

## Step 8: Deploy the Kubernetes Manifests

Apply all declarative manifests located in `k8s/` (Deployments, Services, `emptyDir` volumes, and Network Policies):

```bash
kubectl apply -f k8s/
```

> Note: the `k8s/` folder currently contains the manifests of the four
> Delivery 1 applications. The `scores_app` manifest is added in a follow-up
> task of Epic B; until then the local deployment covers the four
> applications above.

## Step 9: Verify the Deployment

Confirm that the eight workloads (4 applications + 4 databases) are running correctly in the `default` namespace:

```bash
kubectl get pods
kubectl get services
kubectl get networkpolicies
```

All pods should show `Running` status and `READY 1/1`. If any pod fails, check the logs:

```bash
kubectl logs <pod-name>
kubectl describe pod <pod-name>
```

## Step 10: Obtain the URLs for Each Application

Each application is exposed through a NodePort Service. Obtain the URL assigned by Minikube for each one:

```bash
minikube service users-app-service --url
minikube service posts-app-service --url
minikube service routes-app-service --url
minikube service offers-app-service --url
```

## Step 11: Test the API with Postman

Import the corresponding Postman collections for each application and update the `baseUrl` environment variable (**Current value**, not Initial value) with the URL obtained in the previous step. Run each collection (`Run collection`) and confirm that all tests pass successfully.

Also verify the health endpoints for each application:

```bash
curl <url-users>/users/ping
curl <url-posts>/posts/ping
curl <url-routes>/routes/ping
curl <url-offers>/offers/ping
# Each one should respond: pong
```

## Step 12: Verify Network Isolation

Confirm that each application can communicate only with its own database and not with the databases of the other applications. You can validate this by executing a command inside an application pod and attempting to reach another application's database:

```bash
kubectl exec -it <users-app-pod-name> -- sh -c "nc -zv posts-db-service 5432"
# Should fail / timeout, confirming isolation
```

## Step 13: Run the Validation Pipelines

Before creating the release, manually run the provided pipelines (without modifying them) from the **Actions** tab of the repository on GitHub. For Entrega 1:

* `Entrega 1 - Evaluador Documentación` (`ci_entrega1_evaluador_docs.yml`)
* `Entrega 1 - Evaluador Implementación` (`ci_entrega1_evaluador_k8s.yml`)

For Entrega 2 (cloud deployment via Terraform stacks and ECR images):

* `Entrega 2 - Deploy` (`ci_entrega2_deploy.yml`)
* `Entrega 2 - Destroy` (`ci_entrega2_destroy.yml`, manual and destructive)

Confirm that they finish successfully (passed ✅) before continuing.

Additionally, confirm that the unit testing pipeline (`ci_evaluador_unit.yml`) passes correctly on every push/PR to `main`, with a minimum coverage of 70% per application.

## Step 14: Cleanup (Optional)

To remove the deployment and stop Minikube after testing:

```bash
kubectl delete -f k8s/
minikube stop
# To completely remove the cluster:
minikube delete
```

## Troubleshooting Common Issues

| Problem                                                  | Possible Cause                                                                      | Solution                                                                                                              |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Pod in `ImagePullBackOff` state                          | The image was not loaded into Minikube, or the name/tag does not match the manifest | Run `minikube image load` with the exact `image_name:image_tag` used in the manifest and `config.yaml`                |
| Pod in `CrashLoopBackOff` state                          | Error starting the application (database connection, missing environment variable)  | Check `kubectl logs <pod>` and verify the environment variables defined in the Deployment                             |
| `minikube service --url` does not respond                | The Service is not correctly linked to the Deployment, or the pod is not `Running`  | Run `kubectl get endpoints <service-name>`                                                                            |
| Postman receives a connection error                      | The `baseUrl` variable (Current value) was not updated, or Minikube is not running  | Repeat Step 10 and update the variable in Postman                                                                     |
| An application can access another application's database | Network Policy is incorrectly configured or was not applied                         | Run `kubectl get networkpolicies` and compare against `networks.puml`                                                 |
| PlantUML diagrams are not generated                      | Incorrect mount path or `.puml` syntax errors                                       | Verify that `docs/diagrams/` contains the `.puml` files and review the output from the `plantuml-generator` container |

````
