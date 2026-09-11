
# Development View

## Table of Contents
- [Development View](#development-view)
  - [Table of Contents](#table-of-contents)
  - [Project Structure](#project-structure)
    - [Application Folders](#application-folders)
    - [k8s Folders](#k8s-folders)
    - [Ingress](#ingress)
    - [docs Folder](#docs-folder)
    - [config.yaml File](#configyaml-file)
  - [API Endpoints](#api-endpoints)
  - [Data Models](#data-models)
  - [Testing](#testing)
    - [Unit Tests](#unit-tests)
    - [Integration Tests](#integration-tests)
  - [Pipelines](#pipelines)
- [Run Orchestators](#run-orchestators)
  - [RF-004 Offer Creation](#rf-004-offer-creation)
    - [Run the RF-004 orchestrator locally](#run-the-rf-004-orchestrator-locally)
    - [Run the RF-004 orchestrator with Docker](#run-the-rf-004-orchestrator-with-docker)
    - [Deploy the RF-004 orchestrator (Minikube/EKS)](#deploy-the-rf-004-orchestrator-minikubeeks)
    - [Manual verification of RF-004](#manual-verification-of-rf-004)

## Project Structure

```
├── .github/                         # CI/CD pipelines
│
├── users_app/                       # Users application
│   └── README.md                    # App structure, tests, env vars, config, execution
│
├── routes_app/                      # Routes application
│   └── README.md                    # App structure, tests, env vars, config, execution
│
├── posts_app/                       # Posts application
│   └── README.md                    # App structure, tests, env vars, config, execution
│
├── offers_app/                      # Offers application
│   └── README.md                    # App structure, tests, env vars, config, execution
│
├── scores_app/                      # Scores application (Entrega 2)
│   └── README.md                    # App structure, tests, env vars, config, execution
│
├── k8s/                             # Legacy Entrega 1 manifests (k8s/entrega1_k8s/)
├── k8s_entrega2/                    # Entrega 2 manifests (secrets, apps, ingress, local-db)
├── scripts/                         # Local deploy/verify scripts + rf004/rf005 stub image
│
├── docs/                            # Technical documentation
│   ├── README.md                    # Documentation home + team + technologies + TOC
│   ├── TeamRules.md                 # Team development rules
│   ├── information-view.md          # Information view
│   ├── functional-view.md           # Functional view
│   ├── deployment-view.md           # Deployment view
│   ├── development-view.md          # Development view
│   ├── solution-patterns.md         # RF-003/RF-004/RF-005 solution patterns
│   ├── rf003-sequence-view.md       # RF-003 sequence view
│   ├── rf004-sequence-view.md       # RF-004 sequence view
│   ├── rf005-sequence-view.md       # RF-005 sequence view
│   │
│   └── diagrams/
│       ├── components.puml          # Functional/component model
│       ├── deployment.puml          # Deployment model
│       ├── entities.puml            # Entity model
│       ├── networks.puml            # Network model
│       ├── components_second_iteration.puml   # Entrega 2 component model
│       ├── deployment_second_iteration.puml   # Entrega 2 deployment model
│       ├── networks_second_iteration.puml     # Entrega 2 network model
│       ├── rf003-sequence.puml      # RF-003 sequence diagram
│       ├── rf004-sequence.puml      # RF-004 sequence diagram
│       └── rf005-sequence.puml      # RF-005 sequence diagram
│
└── README.md                         # Project overview + deployment instructions
```

### Application Folders

Each application (`users_app`, `routes_app`, `posts_app`, `offers_app`, and `scores_app`) is an independent component with its own source code, unit tests, `Dockerfile`, and `README.md` file describing its structure, environment variables, execution, and testing.

`scores_app` is new in Entrega 2: it owns the Score (Utilidad) entity and persists one current score per offer (idempotent upsert by `offerId`), exposing a null-safe API (a missing score reads as `score: null`, never an error).

Each application has exclusive ownership of its own data: no application directly accesses another application's database.

### k8s Folders

The manifests are split into two folders, one per delivery, because both
deployments define resources with the same names (for example
`users-app`, `users-app-service`, `users-db`) but with different images,
and they must not be applied to the same cluster at the same time.

- **`k8s_entrega2/`** contains the declarative manifests for the Entrega 2
  deployment: Secrets, Deployments + Services (ClusterIP for applications)
  for the five data-owning microservices (`users-app`, `posts-app`,
  `offers-app`, `routes-app`, `scores-app`) and the three orchestrators,
  plus the Ingress. Data isolation between apps uses a single shared Postgres
  instance (per-app databases and roles) local Minikube uses the file in
  `k8s_entrega2/local-only/15-shared-db.yml`; production uses AWS RDS.
  File names encode the apply order (00 secrets, 15 shared db, 20 apps, zz
  ingress), which matches the alphabetical order used by the
  `ci_entrega2_deploy.yml` pipeline.
- **`k8s/entrega1_k8s/`** contains the original legacy Entrega 1 manifests
  (`.yaml`) for the four original apps, with underscore image names
  (`users_app:v0.0.0`, etc.). The `ci_entrega1_evaluador_k8s.yml` pipeline
  (GitHub) builds those images and applies the whole `k8s/` tree.

**Docker image naming**: The `k8s_entrega2/` manifests use hyphenated image
names matching the `apps:` list in `config.yaml` exactly (for example,
`users-app:v0.0.0`, `scores-app:v0.0.0`). The legacy `k8s/entrega1_k8s/`
manifests use the underscore names from the top-level `config.yaml` keys
(for example, `users_app:v0.0.0`).

**Local automation**: `scripts/local-deploy.sh` and `scripts/local-verify.sh`
deploy and verify the `k8s_entrega2/` stack on Minikube (see the
[README](../README.md#run-with-minikube)). `scripts/stubs/` provides a
ping-only image for `rf004`/`rf005`, whose real code lives in separate
branches.

### Ingress

`k8s_entrega2/zz-ingress.yml` (resource name `microservices-ingress`)
provides a single public entry point routing by path prefix to all eight
services. It supports two deployment environments:

- **Local Minikube**: pre-configured with `ingressClassName: nginx` for the NGINX ingress addon
- **AWS EKS production**: change to `ingressClassName: alb` and add ALB annotations per the [README documentation](../README.md#ingress-configurations-two-environments)

### docs Folder

Contains the system's technical documentation in Markdown, following the Documentation as Code approach.

It includes the home page, information, functional, deployment, and development views, along with their respective PlantUML diagrams located in `docs/diagrams/`.

### config.yaml File

Configuration file located at the repository root that describes the team, the work board, the link to the published documentation, and the information for each application (folder, image name, tag, and authors).

This file is used by the pipelines to evaluate the project delivery.

---

## API Endpoints

| Application | Resource    | Main Endpoints                                                                                                                          |
| ----------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Users       | `/users`    | `POST /users`, `PATCH /users/{id}`, `POST /users/auth`, `GET /users/me`, `GET /users/count`, `GET /users/ping`, `POST /users/reset`     |
| Routes      | `/routes`   | `POST /routes`, `GET /routes`, `GET /routes/{id}`, `DELETE /routes/{id}`, `GET /routes/count`, `GET /routes/ping`, `POST /routes/reset` |
| Posts       | `/posts`    | `POST /posts`, `GET /posts`, `GET /posts/{id}`, `DELETE /posts/{id}`, `GET /posts/count`, `GET /posts/ping`, `POST /posts/reset`        |
| Offers      | `/offers`   | `POST /offers`, `GET /offers`, `GET /offers/{id}`, `DELETE /offers/{id}`, `GET /offers/count`, `GET /offers/ping`, `POST /offers/reset` |
| Scores      | `/scores`   | `POST /scores`, `GET /scores?offerId={offerId}`, `GET /scores/{id}`, `GET /scores/count`, `GET /scores/ping`, `POST /scores/reset`       |

Entrega 2 orchestrator endpoints (client-facing, see the [Functional View](./functional-view.md)):

| Orchestrator         | Endpoint                                | Description                                                              |
| -------------------- | --------------------------------------- | ------------------------------------------------------------------------ |
| `rf003_create_post_app`  | `POST /rf003/posts`                     | Create a post (with route find-or-create) as a single operation          |
| `rf004_create_offer_app` | `POST /rf004/posts/{id}/offers`         | Create an offer and persist its computed score (RF-004)                  |
| `rf005_query_post_app`   | `GET /rf005/posts/{id}`                 | Query a post with its route and offers sorted by score (null-safe)       |

Refer to the `README.md` of each application for the complete details of parameters, request bodies, and responses.

## Data Models

The system manages five main entities: User, Route, Post, Offer, and Score (Entrega 2).

The complete details of their attributes and data types are documented in the Information View (`docs/`), with the corresponding model located at:

`docs/diagrams/entities.puml`

The `Score` (Utilidad) entity persists one current score per offer:

| Column      | Type     | Notes                                                        |
| ----------- | -------- | ------------------------------------------------------------ |
| `id`        | string   | Primary key (UUID)                                           |
| `offerId`   | string   | The offer this score belongs to (unique, indexed)            |
| `value`     | float    | The computed utility value (API field: `score`)              |
| `createdAt` | datetime | Creation timestamp (UTC)                                     |
| `updatedAt` | datetime | Last update timestamp (UTC)                                  |

A missing score for an offer is represented by the absence of a row, which the API reads as `score: null` (null-safe, never an error).

## Testing

### Unit Tests

Each application has its own unit test suite, with a minimum required coverage of 70%.

Coverage validation is performed exclusively through the `ci_evaluador_unit.yml` pipeline; results from local executions are not accepted as evidence.

```bash
cd <app_folder>
poetry run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing
```

### Integration Tests

Integration tests (API) are executed through Postman collections, one for each application.

Import the corresponding collection into your Postman application, configure the environment variable with the URL of the deployed application, and run the collection.

These same collections are used by the `ci_evaluador_entrega1_k8s.yml` pipeline to validate the Minikube deployment, including network isolation between applications.

## Pipelines

The `.github/workflows/` folder contains the following pipelines:

* `ci_entrega1_evaluador_docs.yml`: validates the technical documentation and PlantUML diagrams. **This file must not be modified.**
* `ci_entrega1_evaluador_k8s.yml`: validates the Minikube deployment, database configuration, and API contract of each application. **This file must not be modified.**
* `ci_evaluador_unit.yml`: runs the unit tests and validates the minimum 70% coverage for each application. **This is the only pipeline file the team should modify**, by adding one job for each application.
* `ci_entrega2_deploy.yml` (Entrega 2): builds the images declared under `apps:` in `config.yaml` (including `scores-app:v0.0.0`), pushes them to ECR, deploys the Terraform stacks, and applies the `k8s_entrega2/` manifests (listed in `k8s_manifests`).
* `ci_entrega2_destroy.yml` (Entrega 2): manually destroys the Terraform stacks in reverse order.
* `ci_pipeline.yml`: runs the Vale documentation checker on `docs/` for every push/PR to `main`.


# Run Orchestators

## RF-004 Offer Creation

The `rf004_create_offer_app` orchestrator exposes the client facing endpoint
`POST /rf004/posts/{id}/offers`. A request carries a Bearer token (validated
against the Users service) and a JSON body with the offer details
(`description`, `size` LARGE/MEDIUM/SMALL, `fragile`, and `offer` in COP).
The orchestrator then:

1. Validates the caller token (403 without a token, 401 with an invalid one).
2. Fetches the post from the Posts service (404 if unknown).
3. Applies the business rules: the caller cannot offer on their own post and
   the post must not be expired (both return 412).
4. Fetches the route from the Routes service and calculates the score as
   `offer - (bag occupancy % * bagCost)`, where the occupancy is 100% for
   LARGE, 50% for MEDIUM, and 25% for SMALL bags.
5. Creates the offer in the Offers service.
6. Persists the score in the Scores service.

Consistency (saga compensation, documented in
[solution-patterns.md](./solution-patterns.md#rf-004)): the flow performs
two writes on two independently owned stores (Offers, Scores) with no
distributed transaction, and the team's definition of consistency is
**either both writes exist or neither does**. Steps 5 and 6 are therefore
a saga: when the score stage fails with an integration error (Scores
unreachable) after the offer was already created, the orchestrator runs
the compensating action (deletes the just created offer through
`DELETE /offers/{id}`) and answers `503` with the message `El servicio
está temporalmente fuera de servicio.`, so no orphaned offer remains.
Hard failures at any stage (Users, Posts, Routes, Offers, or Scores
unreachable) return `503`; business rejections (400/404/412) pass
through unchanged and never trigger compensation. The full contract,
status code table, and environment variables are documented in the
[RF-004 app README](../rf004_create_offer_app/README.md).

### Run the RF-004 orchestrator locally

```bash
cd rf004_create_offer_app
poetry install
USERS_SERVICE_URL=http://localhost:8000 \
POSTS_SERVICE_URL=http://localhost:8003 \
ROUTES_SERVICE_URL=http://localhost:8002 \
OFFERS_SERVICE_URL=http://localhost:8004 \
SCORES_SERVICE_URL=http://localhost:8005 \
poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8001
```

All five downstream services must be running for the happy path (Users on
`8000`, Routes on `8002`, Posts on `8003`, Offers on `8004`, Scores on
`8005`; any ports work if you export the matching `*_SERVICE_URL` values).

### Run the RF-004 orchestrator with Docker

```bash
cd rf004_create_offer_app
docker build -t rf004-create-offer-app:v0.0.0 .
docker run --rm -p 8001:8000 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e POSTS_SERVICE_URL=http://posts-app-service:8000 \
  -e ROUTES_SERVICE_URL=http://routes-app-service:8002 \
  -e OFFERS_SERVICE_URL=http://offers-app-service:8004 \
  -e SCORES_SERVICE_URL=http://scores-app-service:8005 \
  rf004-create-offer-app:v0.0.0
```

### Deploy the RF-004 orchestrator (Minikube/EKS)

Build and push the image to ECR, then create the Deployment and Service
(name `rf004-create-offer-service`, port `8000`) with the
`USERS_SERVICE_URL`, `POSTS_SERVICE_URL`, `ROUTES_SERVICE_URL`,
`OFFERS_SERVICE_URL`, and `SCORES_SERVICE_URL` environment variables
pointing at the cluster DNS names of each downstream service, and expose it
through the ingress path `/rf004/posts/{id}/offers` (see the
[Deployment View](./deployment-view.md)). Verify after deploying:

```bash
kubectl get pods -l app=rf004-create-offer-app
# -> 1/1 Running (the HEALTHCHECK on /rf004/ping gates readiness)

kubectl logs -l app=rf004-create-offer-app --tail=20
# -> uvicorn startup lines, no import or configuration errors

curl -s http://<INGRESS_HOST>/rf004/ping
# -> pong
```

### Manual verification of RF-004

The full step by step curl walkthrough (user and token creation, route
creation, post creation, the 403/401/400/404/412/503 scenarios, and the 201
happy path with the score persisted) is in the
[RF-004 app README](../rf004_create_offer_app/README.md#manual-verification-curl).

The Postman collection in `rf004_create_offer_app/tests/api/evaluate_rf004.json`
covers the same flow: its **Setup** folder creates the owner and the caller,
stores both tokens, creates a route, and creates a valid owner post plus a
short lived one. Run the remaining requests in order: the **Expired post**
request runs after the short lived post has expired, and the last request
(**Valid request -> 201**) asserts the `201` status and the `data` body with
the new offer id, the caller id, the creation timestamp, and the post id.

The consistency acceptance criteria are covered by
`rf004_create_offer_app/tests/api/evaluate_rf004_consistency.json` (stop
the Scores service first, then run its **Consistency** folder): the offer
request answers `503` with the standard message, the follow up request
verifies that no orphaned offer remains for the post (the compensating
deletion ran), and a final request after restarting the Scores service
confirms the `201` happy path again. See the
[RF-004 app README](../rf004_create_offer_app/README.md#manual-verification-consistency-rollback-on-a-mid-flow-outage)
for the curl equivalent.