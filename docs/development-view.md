
# Development View

## Table of Contents
- [Development View](#development-view)
  - [Table of Contents](#table-of-contents)
  - [Project Structure](#project-structure)
    - [Application Folders](#application-folders)
    - [k8s Folders](#k8s-folders)
    - [Ingress](#ingress)
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
- [Run Orchestrators](#run-orchestrators)
  - [RF-003 Post Creation](#rf-003-post-creation)
  - [RF-004 Offer Creation](#rf-004-offer-creation)
    - [Run the RF-004 orchestrator locally](#run-the-rf-004-orchestrator-locally)
    - [Run the RF-004 orchestrator with Docker](#run-the-rf-004-orchestrator-with-docker)
    - [Deploy the RF-004 orchestrator (Minikube/EKS)](#deploy-the-rf-004-orchestrator-minikubeeks)
    - [Manual verification of RF-004](#manual-verification-of-rf-004)
  - [RF-005 Post Query](#rf-005-post-query)

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
├── rf003_create_post_app/           # RF-003 orchestrator (Entrega 2)
├── rf004_create_offer_app/          # RF-004 orchestrator (Entrega 2)
├── rf005_query_post_app/            # RF-005 orchestrator (Entrega 2)
├── user_verification_callback/      # RF-007 verification callback receiver + result email (Entrega 3)
│   └── README.md                    # App structure, tests, env vars, config, execution
│
├── k8s/                             # Legacy Entrega 1 manifests (users-app.yaml, etc.)
├── k8s_entrega2/                    # Entrega 2 manifests (secrets, apps, ingress, local-db)
├── scripts/                         # Local deploy/verify scripts + terraform helper scripts
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
│   ├── rf006-sequence-view.md       # RF-006 sequence view (Entrega 3)
│   ├── rf007-sequence-view.md       # RF-007 sequence view (Entrega 3)
│   │
│   └── diagrams/
│       ├── components.puml          # Functional/component model
│       ├── deployment.puml          # Deployment model
│       ├── entities.puml            # Entity model
│       ├── networks.puml            # Network model
│       ├── components_second_iteration.puml   # Entrega 2 component model
│       ├── components_third_iteration.puml    # Entrega 3 component model
│       ├── deployment_second_iteration.puml   # Entrega 2 deployment model
│       ├── deployment_third_iteration.puml    # Entrega 3 deployment model
│       ├── networks_second_iteration.puml     # Entrega 2 network model
│       ├── rf003-sequence.puml      # RF-003 sequence diagram
│       ├── rf004-sequence.puml      # RF-004 sequence diagram
│       ├── rf005-sequence.puml      # RF-005 sequence diagram
│       ├── rf006-sequence.puml      # RF-006 sequence diagram (Entrega 3)
│       └── rf007-sequence.puml      # RF-007 sequence diagram (Entrega 3)
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
- **`k8s/`** contains the original legacy Entrega 1 manifests
  (`.yaml`) for the four original apps (for example `users-app.yaml`,
  `users-network-policy.yaml`), with underscore image names
  (`users_app:v0.0.0`, etc.). The `ci_entrega1_evaluador_k8s.yml` pipeline
  (GitHub) builds those images and applies the whole `k8s/` tree.

**Docker image naming**: The `k8s_entrega2/` manifests use hyphenated image
names matching the `apps:` list in `config.yaml` exactly (for example,
`users-app:v0.0.0`, `scores-app:v0.0.0`). The legacy `k8s/`
manifests use the underscore names from the top-level `config.yaml` keys
(for example, `users_app:v0.0.0`).

**Local automation**: `scripts/local-deploy.sh` and `scripts/local-verify.sh`
deploy and verify the `k8s_entrega2/` stack on Minikube (see the
[README](../README.md#run-with-minikube)). `scripts/local-deploy.sh` builds
the eight images from the real application folders (the four legacy apps,
`scores_app`, and the three orchestrators) and applies the manifests in the
order encoded in their file names.

### Ingress

`k8s_entrega2/zz-ingress.yml` (resource name `microservices-ingress`)
provides a single public entry point routing by path prefix to all the
services (the eight of the previous deliveries, plus the TrueNative service
added in Entrega 3 under `/native`). It is the same resource in both
environments:

- **Local Minikube**: uses `ingressClassName: nginx` with the NGINX ingress addon
- **AWS EKS production**: the same `ingressClassName: nginx`. The course project required an AWS ALB, but the AWS Academy academic accounts do not allow ALB, so the NGINX ingress controller is used in both environments (see the [Deployment View](./deployment-view.md#ingress-deployment-details))

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

### users_app schema change for RF-007 (Entrega 3)

The `users` table gained one column, `ruv`, so the service can store the unique
verification record returned by TrueNative and correlate the asynchronous
verification callback with the user. The existing columns were not renamed or
duplicated: `status` already supports the `POR_VERIFICAR`, `VERIFICADO`, and
`NO_VERIFICADO` values, and `updatedAt` is rewritten with the current UTC date
on every update, including on every status transition.

| Column | Type     | Notes |
| ------ | -------- | ----- |
| `ruv`  | string   | Optional. Unique verification record returned by TrueNative, stored for traceability and callback correlation |

The schema is created on application startup through the SQLAlchemy model
(`init_db()` in `users_app/src/adapters/database/connection.py`), so a fresh
database picks the new column up automatically.

### TrueNative verification trigger in users_app (RF-007, T011)

User creation now triggers the TrueNative identity verification. The flow
follows the RF-007 sequence view: the user is persisted first with status
`POR_VERIFICAR`, and then the service calls TrueNative `POST /native/verify`
as a normal synchronous request response call while the creation request is
still open.

The integration follows the usual port and adapter pattern:

| Piece | Location |
| ----- | -------- |
| Port | `users_app/src/domain/ports/truenative_port.py` (`TrueNativeVerificationPort`) |
| Adapter | `users_app/src/adapters/truenative/verification_adapter.py` (`TrueNativeVerificationAdapter`) |
| Use case | `users_app/src/domain/use_cases/create_user_use_case.py` |
| Wiring | `users_app/src/entrypoints/api/deps.py` (`get_truenative_verification_provider`) |

The adapter sends every user field that has a value (`email`, `dni`,
`fullName`, and `phone` for the domain `phoneNumber`), the value that
identifies the user locally (`userIdentifier`), a fresh UUID per request as
`transactionIdentifier`, and the absolute callback URL (`userWebhook`,
`USER_WEBHOOK_URL`). The request carries the `Authorization: Bearer
<SECRET_TOKEN>` header and answers with `201` plus the RUV, which the use
case stores on the user record through `set_ruv` without touching `status`
or `updatedAt`.

Provider failures are explicit and never swallowed. A rejection status
(`400`, `401`, `403`, or `409`, or any other error status) raises
`TrueNativeRequestError`; a connection failure, a timeout, or a malformed
success body raises `TrueNativeUnreachableError` (both in
`users_app/src/errors.py`). In every failure case the use case marks the
user `NO_VERIFICADO` (refreshing `updatedAt`), the rejection is logged with
the transaction identifier and the status code, and the creation still
answers `201` with `{id, createdAt}`: the user exists, and the outcome can
be fixed later. The webhook callback that applies the final status is
handled by the `user_verification_callback` component (described in the
next section).

The integration is configured through environment variables (see
`users_app/README.md`): `TRUE_NATIVE_BASE_URL` (defaults to the in-cluster
service `http://truenative-service`), `SECRET_TOKEN` (provided through the
`truenative-secret` Secret, never hardcoded), and `USER_WEBHOOK_URL`. The
AWS users-app Deployment (`k8s_entrega2/20-users-app.yml`) declares the three
variables; the legacy Minikube manifest under `k8s/` keeps working without
them because the defaults point at the same service names and the defined
failure behavior keeps creation answering `201` when TrueNative is absent.

### User verification callback receiver (RF-007, T012)

The verification result arrives later, when TrueNative calls the
`userWebhook` URL with a `PATCH` carrying `{RUV, userIdentifier,
transactionIdentifier, createdAt, status, score, verifyToken}`. The receiver
is a dedicated app (`user_verification_callback/`), separate from
`users_app`, for two reasons: `users_app` stays free of unauthenticated
routes, and the receiver owns no data store (it updates the user through the
Users service API, so the user data stays in the shared RDS instance under
the `users` schema).

The public endpoint is `PATCH /users/verify/callback` (reachable through the
single ingress host under the more specific prefix `/users/verify/callback`,
so the existing `/users/*` behavior is unchanged). It is unauthenticated by
design (TrueNative cannot supply a platform token), and its only protection
is the signature check: `verifyToken` must equal
`sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")`, computed over the exact textual
form of the JSON `score` value (integer or float, never coerced) and
compared in constant time. The secret is the same `SECRET_TOKEN` that
TrueNative uses (both deployments read the `truenative-secret` Secret).

After a valid signature, the status is computed from the score with the
team threshold: `VERIFICADO` when the score is greater than 60,
`NO_VERIFICADO` when it is 60 or lower (the `status` field carried by the
provider is never trusted). The change is applied with a normal synchronous
`PATCH /users/{userIdentifier}` call to the Users service, which refreshes
`updatedAt` and answers the updated user record. The receiver then publishes
the result email synchronously to the RF-007 SNS topic from that persisted
record (the email notification of T013, described below). Whatever the
outcome (applied, signature mismatch, unknown user, or Users service error),
the endpoint answers `200` to TrueNative on a well-formed receipt, and only a
structurally malformed body answers `400`. The receiver runs no background
task, thread, or asyncio construct: the whole flow (update and email
publish) is a synchronous request/response inside the callback request,
which keeps the web component within the course restriction on
asynchronous execution.

Deployment: the image is built and published like the other apps (the
`user_verification_callback` entry in `config.yaml` `apps`), the workload
lives in `k8s_entrega2/28-user-verification-callback.yml` (Deployment
`user-verification-callback` + ClusterIP Service
`user-verification-callback-service`, which is exactly the target of
`USER_WEBHOOK_URL` in `20-users-app.yml`), and the ingress rule is in
`k8s_entrega2/zz-ingress.yml`. The unit-test pipeline gains a
`user_verification_callback` job in `ci_evaluador_unit.yml`.

### Identity verification result email (RF-007, T013)

The RF-007 acceptance criteria mandate an email for every finished
verification, regardless of the outcome: the target address must receive
a message with the final status, the RUV generated by TrueNative, and the
user data used in the verification process, and the content must be
consistent with what the platform persists.

The producer is the `user_verification_callback` service, as the team
docs define it: right after the status update is applied inside the
callback request, the use case publishes the result email to the
`grupo33-user-verification-notifications` SNS topic (provisioned by the
`4_sns` Terraform stack, one topic per requirement of Entrega 3). The
publish is a plain synchronous boto3 call inside the callback request, so
the component stays free of the forbidden asynchronous patterns. The
recipient is never in the code: the topic has a single email
subscription whose endpoint is the `EMAIL_TO_NOTIFY` value read from the
`secrets-pipeline-native-map` secret at plan time, and a rejected or
unconfigured notification never undoes the already applied status change
(the endpoint keeps answering `200` to TrueNative).

The email content comes from the user record the platform persists: the
`PATCH /users/{id}` endpoint of `users_app` now answers the updated user
in addition to the confirmation message (the `user` block with `id`,
`username`, `email`, `dni`, `fullName`, `phoneNumber`, `status`, `ruv`
and `updatedAt`), so the callback builds the email from the exact data
the status update stored, and the status stated in the email is the
status persisted in the platform. Absent profile fields are shown as
`Not provided`. The topic ARN reaches the workload through the
`${USER_VERIFICATION_TOPIC_ARN}` envsubst placeholder in
`k8s_entrega2/28-user-verification-callback.yml` (the deploy pipeline
exports the `user_verification_topic_arn` output of the `4_sns` stack),
and the publish uses the cluster node role credentials through the
default boto3 chain. When the topic ARN is empty (local runs without the
AWS stack) the composed email is logged and the delivery is skipped with
a warning, so the flow keeps working end to end locally.

### Token gating by verification status (RF-007, T014)

The Enunciado approves, in advance, exactly one additional change to
`users_app` beyond the RF-007 flow: the service must not generate or
verify tokens for a user that is not `VERIFICADO`. Because `users_app`
is the only component that issues and validates session tokens, two
checks cover the whole platform:

| Check | Location | Behavior |
| ----- | -------- | -------- |
| Token generation | `users_app/src/domain/use_cases/authenticate_user_use_case.py` | Once the credentials are validated, the status must be `VERIFICADO`. A `POR_VERIFICAR` or `NO_VERIFICADO` user raises the new `UserNotVerifiedError` (`users_app/src/errors.py`), and `POST /users/auth` answers `401` without storing a token |
| Token verification | `users_app/src/domain/use_cases/get_current_user_use_case.py` | Once the token is resolved and its expiration is checked, the owner must still be `VERIFICADO`. Otherwise the existing `InvalidTokenError` is raised and `GET /users/me` answers `401` |

The verification check is the one every other service relies on: the
RF-003, RF-004 and RF-005 orchestrators, and the RF-006 credit cards
component, validate the caller token by calling `GET /users/me`, so a
token owned by a user that is not `VERIFICADO` stops resolving
everywhere without touching those services. Both rejections are logged
at `WARNING` with the username and the status that caused them. The
rest of the API is unchanged: invalid credentials still answer `404`,
so the login endpoint does not reveal whether a username exists or
what its status is, and every other endpoint behaves as before.

The `users_app` unit suite covers both gates at the use case level (a
token is only issued for a `VERIFICADO` user, no token is stored for
the other two statuses, and verification rejects unknown, expired, and
unverified user tokens) and at the router level (the `401` answers of
`POST /users/auth` and `GET /users/me`), growing the suite from 89 to
102 tests at 94.69% coverage. The manual end to end verification
against the real TrueNative platform (both outcomes, plus the token
rejection after a status change) is documented in `users_app/README.md`,
in the "Token gating by verification status (RF-007, T014)" section.
The local verification scripts were updated for the new rule: the
`scripts/local-verify.sh` smoke test now asserts the `401` while the
user is `POR_VERIFICAR`, applies the verification status with the same
`PATCH /users/{id}` the callback component performs, and then
authenticates, and the local copies of the Entrega 2 Postman
collections in `scripts/entrega2/` simulate the verification callback
with a `PATCH /users/{id}` request after each user creation, so the
RF-003, RF-004 and RF-005 flows keep running with verified users.

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
* `ci_entrega1_evaluador_k8s.yml`: validates the Minikube deployment, database configuration, and API contract of each application. **This file must not be modified.**
* `ci_evaluador_unit.yml`: runs the unit tests and validates the minimum 70% coverage for each application. **This is the only pipeline file the team should modify**, by adding one job for each application.
* `ci_entrega2_deploy.yml` (Entrega 2): builds the images declared under `apps:` in `config.yaml` (including `scores-app:v0.0.0`), pushes them to ECR, deploys the Terraform stacks, and applies the `k8s_entrega2/` manifests (listed in `k8s_manifests`).
* `ci_entrega2_deploy.yml` (Entrega 2): builds the images declared under `apps:` in `config.yaml` (including `scores-app:v0.0.0`), pushes them to ECR, deploys the Terraform stacks, and applies the `k8s_entrega2/` manifests (listed in `k8s_manifests`).
* `ci_entrega2_destroy.yml` (Entrega 2): manually destroys the Terraform stacks in reverse order.
* `ci_pipeline.yml`: runs the Vale documentation checker on `docs/` for every push/PR to `main`.


# Run Orchestrators

## RF-003 Post Creation

The `rf003_create_post_app` orchestrator exposes the client facing endpoint
`POST /rf003/posts`. A request carries a Bearer token (validated against the
Users service) and a JSON body with the post details (`flightId`, airport
codes, countries, `bagCost`, planned dates, and `expireAt`). The orchestrator
then:

1. Validates the caller token (403 without a token, 401 with an invalid one).
2. Resolves the route by `flightId` in the Routes service: it reuses an
   existing route, or creates it and marks it as created by this request.
3. Creates the post in the Posts service, referencing the route.

Consistency (saga compensation, documented in
[solution-patterns.md](./solution-patterns.md#rf-003)): the flow performs two
writes on two independently owned stores (Routes, Posts) with no distributed
transaction, and the team's definition of consistency is **either both writes
exist or neither does**. When the post stage fails with an integration error
(Posts unreachable) and the route was created by this same request, the
orchestrator runs the compensating action (deletes the route through
`DELETE /routes/{id}`) and answers `503` with the message `El servicio está
temporalmente fuera de servicio.`, so no orphaned route remains. Pre-existing
routes (reused by `flightId`) are never compensated, and business rejections
(400/412) pass through unchanged and never trigger compensation. The full
contract, status code table, and environment variables are documented in the
[RF-003 app README](../rf003_create_post_app/README.md).

### Run the RF-003 orchestrator locally

```bash
cd rf003_create_post_app
poetry install
USERS_SERVICE_URL=http://localhost:8000 \
ROUTES_SERVICE_URL=http://localhost:8002 \
POSTS_SERVICE_URL=http://localhost:8003 \
poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8001
```

All three downstream services must be running for the happy path (Users on
`8000`, Routes on `8002`, Posts on `8003`; any ports work if you export the
matching `*_SERVICE_URL` values).

### Run the RF-003 orchestrator with Docker

```bash
cd rf003_create_post_app
docker build -t rf003-create-post-app:v0.0.0 .
docker run --rm -p 8001:8000 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e ROUTES_SERVICE_URL=http://routes-app-service:8000 \
  -e POSTS_SERVICE_URL=http://posts-app-service:8000 \
  rf003-create-post-app:v0.0.0
```

### Deploy the RF-003 orchestrator (Minikube/EKS)

Build and push the image to ECR, then create the Deployment and Service
(name `rf003-create-post-service`, port `8000`) with the
`USERS_SERVICE_URL`, `ROUTES_SERVICE_URL`, and `POSTS_SERVICE_URL`
environment variables pointing at the cluster DNS names of each downstream
service, and expose it through the ingress path `/rf003/posts` (see the
[Deployment View](./deployment-view.md)).

### Manual verification of RF-003

The Postman collection in `scripts/entrega2/evaluate_rf003.json` covers the
full flow (the same files the grader runs, also kept under
`rf003_create_post_app/tests/api/`): the **Setup** folder creates the user
and the token, then the remaining requests cover the 403/401/400/412
scenarios and the 201 happy path (route created or reused plus post
created).

The consistency acceptance criteria are covered by
`scripts/entrega2/evaluate_rf003_consistency.json` (stop the Posts service
first, then run its **Consistency** folder): the post request answers `503`
with the standard message, the follow up request verifies that no orphaned
route remains (the compensating deletion ran), and a final request after
restarting the Posts service confirms the `201` happy path again. The curl
equivalent is in the
[RF-003 app README](../rf003_create_post_app/README.md#manual-verification-curl).

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

## RF-005 Post Query

The `rf005_query_post_app` orchestrator exposes the client facing endpoint
`GET /rf005/posts/{id}`. A request carries a Bearer token (validated against
the Users service). The orchestrator then:

1. Validates the caller token (401 with an invalid one).
2. Fetches the post from the Posts service (404 if unknown) and rejects the
   request with 403 if the caller is not the post owner.
3. Fetches the route from the Routes service.
4. Fetches all offers for the post from the Offers service.
5. Looks up the score for each offer in the Scores service. A missing or
   unreachable score for one offer sets that offer's score to `null` and the
   loop continues; the whole request does not fail.
6. Sorts the offers descending by score (nulls last, with a documented
   tie-breaking rule) and returns the post, its route, and its sorted offers.

This is a read-side composition, not a write-side saga: there is no state to
roll back, so no compensating action exists in this flow (documented in
[solution-patterns.md](./solution-patterns.md#rf-005)). The per-offer
fallback is an explicit resilience requirement from the project document: a
missing or unavailable score for one offer never fails the whole response.
Posts, Routes, and Offers are hard dependencies here: if any of them is down,
the whole request fails with `503`. The full contract, status code table, and
environment variables are documented in the
[RF-005 app README](../rf005_query_post_app/README.md).

### Run the RF-005 orchestrator locally

```bash
cd rf005_query_post_app
poetry install
USERS_SERVICE_URL=http://localhost:8000 \
POSTS_SERVICE_URL=http://localhost:8002 \
ROUTES_SERVICE_URL=http://localhost:8006 \
OFFERS_SERVICE_URL=http://localhost:8003 \
SCORES_SERVICE_URL=http://localhost:8004 \
poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8005
```

All five downstream services must be running for the happy path (Users on
`8000`, Posts on `8002`, Routes on `8006`, Offers on `8003`, Scores on
`8004`; any ports work if you export the matching `*_SERVICE_URL` values).

### Run the RF-005 orchestrator with Docker

```bash
cd rf005_query_post_app
docker build -t rf005-query-post-app:v0.0.0 .
docker run --rm -p 8005:8005 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e POSTS_SERVICE_URL=http://posts-app-service:8002 \
  -e ROUTES_SERVICE_URL=http://routes-app-service:8006 \
  -e OFFERS_SERVICE_URL=http://offers-app-service:8003 \
  -e SCORES_SERVICE_URL=http://scores-app-service:8004 \
  rf005-query-post-app:v0.0.0
```

### Deploy the RF-005 orchestrator (Minikube/EKS)

Build and push the image to ECR, then create the Deployment and Service
(name `rf005-query-post-service`, port `8005`) with the
`USERS_SERVICE_URL`, `POSTS_SERVICE_URL`, `ROUTES_SERVICE_URL`,
`OFFERS_SERVICE_URL`, and `SCORES_SERVICE_URL` environment variables
pointing at the cluster DNS names of each downstream service, and expose it
through the ingress path `/rf005/posts/{id}` (see the
[Deployment View](./deployment-view.md)).

### Manual verification of RF-005

The automated manual verification script in
`scripts/rf005_automations/rf005_manual_verification.sh` runs the whole flow
against the real services and asserts every documented status code and body
(empty bodies for 403/401/404, the exact `503` message, and the full `200`
payload with the score-descending / nulls-last ordering). The graded Postman
collections live in `scripts/entrega2/evaluate_rf005.json` and
`scripts/entrega2/evaluate_rf005_consistency.json` (the consistency
collection stops the Scores service first and verifies the `200` with
`"score": null` per offer instead of a failure). See the
[RF-005 app README](../rf005_query_post_app/README.md#manual-verification-curl)
for the curl equivalent.