
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
├── k8s/                             # Kubernetes deployment files (placeholder)
│
├── docs/                            # Technical documentation
│   ├── README.md                    # Documentation home + team + technologies + TOC
│   ├── TeamRules.md                 # Team development rules
│   │
│   ├── architecture/
│   ├── information.md           # Information view
│   ├── functional.md            # Functional view
│   ├── deployment.md            # Deployment view
│   ├── development.md           # Development view
│   │
│   └── diagrams/
│       ├── components.puml          # Functional/component model
│       ├── deployment.puml          # Deployment model
│       ├── entities.puml            # Entity model
│       └── networks.puml            # Network model
│
└── README.md                         # Project overview + deployment instructions
```

### Application Folders

Each application (`users_app`, `routes_app`, `posts_app`, `offers_app`) is an independent component with its own source code, unit tests, `Dockerfile`, and `README.md` file describing its structure, environment variables, execution, and testing.

Each application has exclusive ownership of its own data: no application directly accesses another application's database.

### k8s Folder

Contains the declarative manifests required to deploy the four applications and their databases on Minikube: Deployments, Services (ClusterIP for databases and NodePort for applications), `emptyDir` volumes, and Network Policies for isolation.

### docs Folder

Contains the system's technical documentation in Markdown, following the Documentation as Code approach.

It includes the home page, information, functional, deployment, and development views, along with their respective PlantUML diagrams located in `docs/diagrams/`.

### config.yaml File

Configuration file located at the repository root that describes the team, the work board, the link to the published documentation, and the information for each application (folder, image name, tag, and authors).

This file is used by the pipelines to evaluate the project delivery.

---

## API Endpoints

| Application | Resource  | Main Endpoints                                                                                                                          |
| ----------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Users       | `/users`  | `POST /users`, `PATCH /users/{id}`, `POST /users/auth`, `GET /users/me`, `GET /users/count`, `GET /users/ping`, `POST /users/reset`     |
| Routes      | `/routes` | `POST /routes`, `GET /routes`, `GET /routes/{id}`, `DELETE /routes/{id}`, `GET /routes/count`, `GET /routes/ping`, `POST /routes/reset` |
| Posts       | `/posts`  | `POST /posts`, `GET /posts`, `GET /posts/{id}`, `DELETE /posts/{id}`, `GET /posts/count`, `GET /posts/ping`, `POST /posts/reset`        |
| Offers      | `/offers` | `POST /offers`, `GET /offers`, `GET /offers/{id}`, `DELETE /offers/{id}`, `GET /offers/count`, `GET /offers/ping`, `POST /offers/reset` |

Refer to the `README.md` of each application for the complete details of parameters, request bodies, and responses.

## Data Models

The system manages four main entities: User, Route, Post, and Offer.

The complete details of their attributes and data types are documented in the Information View (`docs/`), with the corresponding model located at:

`docs/diagrams/entities.puml`

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

* `ci_evaluador_docs.yml`: validates the technical documentation and PlantUML diagrams. **This file must not be modified.**
* `ci_evaluador_entrega1_k8s.yml`: validates the Minikube deployment, network policies, and API contract of each application. **This file must not be modified.**
* `ci_evaluador_unit.yml`: runs the unit tests and validates the minimum 70% coverage for each application. **This is the only pipeline file the team should modify**, by adding one job for each application.

