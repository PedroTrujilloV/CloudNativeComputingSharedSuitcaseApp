
# Development View

## Table of Contents
- [Development View](#development-view)
  - [Table of Contents](#table-of-contents)
  - [Project Structure](#project-structure)
    - [Application Folders](#application-folders)
    - [k8s Folder](#k8s-folder)
    - [docs Folder](#docs-folder)
    - [config.yaml File](#configyaml-file)
  - [API Endpoints](#api-endpoints)
  - [Data Models](#data-models)
  - [Testing](#testing)
    - [Unit Tests](#unit-tests)
    - [Integration Tests](#integration-tests)
  - [Pipelines](#pipelines)

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
├── k8s/                             # Kubernetes deployment manifests
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

### k8s Folder

Contains the declarative manifests required to deploy the applications and their databases on Minikube: Deployments, Services (ClusterIP for databases and NodePort for applications), `emptyDir` volumes, and Network Policies for isolation. The current manifests cover the four Delivery 1 applications (`users-app`, `posts-app`, `routes-app`, `offers-app`); the `scores_app` manifest is added in a follow-up task of Epic B.

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
* `ci_entrega1_evaluador_k8s.yml`: validates the Minikube deployment, network policies, and API contract of each application. **This file must not be modified.**
* `ci_evaluador_unit.yml`: runs the unit tests and validates the minimum 70% coverage for each application. **This is the only pipeline file the team should modify**, by adding one job for each application.
* `ci_entrega2_deploy.yml` (Entrega 2): builds the images declared under `apps:` in `config.yaml` (including `scores-app:v0.0.0`), pushes them to ECR, deploys the Terraform stacks, and applies the `k8s/` manifests.
* `ci_entrega2_destroy.yml` (Entrega 2): manually destroys the Terraform stacks in reverse order.
* `ci_pipeline.yml`: runs the Vale documentation checker on `docs/` for every push/PR to `main`.

