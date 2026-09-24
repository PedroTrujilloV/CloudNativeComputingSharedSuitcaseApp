# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased ]

### Added

- Triggered the TrueNative identity verification on user creation in
  `users_app` (T011, branch
  `feature/epic-b-rf007-t011-trigger-identity-verify`):
  - Added the `TrueNativeVerificationPort`
    (`users_app/src/domain/ports/truenative_port.py`) and the
    `TrueNativeVerificationAdapter`
    (`users_app/src/adapters/truenative/verification_adapter.py`), a
    synchronous `httpx` client that calls `POST /native/verify` with the
    `Authorization: Bearer <SECRET_TOKEN>` header, the available user fields,
    the local user id as `userIdentifier`, a unique `transactionIdentifier`
    per request, and the absolute callback URL as `userWebhook`.
  - Rewired `CreateUserUseCase` to store the new user as `POR_VERIFICAR`
    first and then register the verification: on `201` the returned RUV is
    stored through the new `set_ruv` repository method, and on a rejection
    (`400`, `401`, `403`, or `409`, or any other error status) or an
    unreachable platform the user is marked `NO_VERIFICADO` while the
    creation still answers `201` with `{id, createdAt}`. The provider errors
    `TrueNativeRequestError` and `TrueNativeUnreachableError` live in
    `users_app/src/errors.py`.
  - Added the `TRUE_NATIVE_BASE_URL`, `SECRET_TOKEN`, and `USER_WEBHOOK_URL`
    settings (in `users_app/src/config.py`) and promoted `httpx` to a main
    dependency. The AWS users-app Deployment
    (`k8s_entrega2/20-users-app.yml`) declares the three variables, with
    `SECRET_TOKEN` read from the `truenative-secret` Secret created by the
    TrueNative deployment (`k8s_entrega3/k8s-true-native-deployment.yml`).
  - Covered the flow with unit tests (API, use case, adapter with
    `httpx.MockTransport`, and configuration), growing the suite from 58 to
    89 tests at 94.32% coverage, and documented the integration in
    `users_app/README.md` and `docs/development-view.md`.
- Added the public `user_verification_callback` app (T012, branch
  `feature/epic-b-rf007-t012-webhook-for-callback`): the dedicated receiver
  for the TrueNative identity verification callback, separate from
  `users_app` so the users web component stays free of unauthenticated
  routes.
  - `PATCH /users/verify/callback` is public (no platform auth) and answers
    `200` on every well-formed receipt. It verifies `verifyToken` as
    `sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")` (constant-time comparison,
    exact textual form of the JSON score) before trusting the payload, and
    discards the message without any change when the signature does not
    match.
  - On a valid signature the score is mapped to the user status with the
    team threshold (`VERIFICADO` when the score is greater than 60,
    `NO_VERIFICADO` when it is 60 or lower), and the change is applied
    synchronously through the Users service API
    (`PATCH /users/{userIdentifier}`), which refreshes `updatedAt`. A
    structurally malformed body answers `400`. No asyncio, background task,
    thread, or event-loop handling exists in the component.
  - Added the app entry to `config.yaml` `apps`, the workload and service
    manifests (`k8s_entrega2/28-user-verification-callback.yml`, Service
    `user-verification-callback-service`, the target of `USER_WEBHOOK_URL`
    from T011), the ingress rule for the more specific prefix
    `/users/verify/callback` in `k8s_entrega2/zz-ingress.yml`, and a
    `user_verification_callback` job in `ci_evaluador_unit.yml`.
  - Covered the flow with unit tests (router, use case, HTTP adapter with
    `httpx.MockTransport`, and configuration): 47 tests at 95.60% coverage,
    and documented the component in
    `user_verification_callback/README.md`, `docs/development-view.md`, and
    `docs/deployment-view.md`.
- Added the identity verification result email to `user_verification_callback`
  (T013, branch `feature/epic-b-rf007-t013-notify-user-by-email`): right after
  the webhook-driven status update is applied, the use case publishes the
  result email synchronously to the `grupo33-user-verification-notifications`
  SNS topic provisioned by the `4_sns` stack (TASK-003). The email is sent for
  both the `VERIFICADO` and the `NO_VERIFICADO` outcome, contains the final
  status, the RUV, and the user data used in the verification process, and a
  signature mismatch, an unknown user, or a Users service error never
  produces an email (no status change was applied). A rejected notification
  never undoes the applied status change, and the endpoint keeps answering
  `200` to TrueNative in every case.
  - New domain pieces in `user_verification_callback`: the `UpdatedUserData`
    model, the `VerificationEmail` value object, the `EmailNotificationPort`,
    the `EmailNotificationError`, and the `SnsEmailNotification` adapter
    (boto3 `publish` to the topic; the composed email is logged; an empty
    `USER_VERIFICATION_TOPIC_ARN` skips the delivery with a warning, as in
    local runs without the AWS stack). The `UsersServiceClient.update_status`
    now returns the user block of the update answer. `boto3` was added to the
    app dependencies.
  - `users_app`: `PATCH /users/{id}` now answers the updated user (`id`,
    `username`, `email`, `dni`, `fullName`, `phoneNumber`, `status`, `ruv`,
    `updatedAt`) in addition to the confirmation message, so the callback
    builds the email from the data the platform persists (the status stated in
    the email is the status stored in the platform) without touching the
    users database.
  - The workload manifest gains the `USER_VERIFICATION_TOPIC_ARN` env
    (resolved by the pipeline envsubst from the `user_verification_topic_arn`
    output of the `4_sns` stack); the recipient address stays out of the
    repository because the topic email subscription uses the
    `EMAIL_TO_NOTIFY` value read from the `secrets-pipeline-native-map`
    secret.
  - Covered the flow with unit tests (router, use case, HTTP adapter, SNS
    adapter with a fake boto3 client, and configuration): the callback suite
    grew from 47 to 72 tests at 95.59% coverage, and the users_app suite
    keeps 89 tests at 94.42%. Documented in
    `user_verification_callback/README.md` and `docs/development-view.md`.

- Extended the `users_app` User data model for the RF-007 identity
  verification lifecycle (T010, branch
  `feature/epic-b-rf007-t010-user-app-identity-verify`):
  - Added the `ruv` column to the `users` table and the `ruv` field to the
    `User` domain model, so the service stores the unique verification record
    returned by TrueNative for traceability and callback correlation.
  - The existing `status` column already supports the `POR_VERIFICAR`,
    `VERIFICADO`, and `NO_VERIFICADO` values, and `updatedAt` is rewritten
    with the current UTC date on every update, including status transitions.
    No pre-existing user field was renamed or duplicated.

### Changed

- Made the `4_sns` stack pass the local `1_init_all.sh` and `2_plan_all.sh`
  helper scripts (PR #132, T003):
  - Renamed the SNS topics to a flat form (`grupo33-card-verification-notifications`
    and `grupo33-user-verification-notifications`) in the `student1` and `dev`
    environment tfvars, because an SNS topic name cannot contain a slash.
  - Documented the local plan prerequisite of the `secrets-pipeline-native-map`
    secret in `terraform/stacks/4_sns/locals.tf` and the `4_sns` stack README:
    only the deploy pipeline creates the secret, so a local plan on a fresh
    account needs it created once beforehand with the AWS CLI. The Terraform
    configuration keeps the required data source pattern and the pipeline
    behavior is unchanged: the `EMAIL_TO_NOTIFY` value is read at plan time
    and never stored in state.
  - Updated `docs/terraform-deployment.md` and the root `README.md`
    troubleshooting table to document the naming rule and the local plan
    prerequisite.
- Extended `scripts/terraform_scripts/0_bootstrap_state_bucket.sh` to
  create the `secrets-pipeline-native-map` secret once from the out-of-repo
  `truenative_secrets/dev.env` file when it does not exist, following the
  same dev.env convention as `scripts/local-deploy.sh` (PR #132, T003).
  Removed a stray `continue` statement that was not inside a loop and
  could abort the script under `set -e`.

- Fixed old vale error in legacy `*_app/README.md` files [3a8d808f9acda83d4dae7014946f7d5209e29cc9]:
  - `offers_app/README.md`
  - `posts_app/README.md`
  - `routes_app/README.md`
  - `users_app/README.md`
- Gated token generation and token verification in `users_app` on the
  identity verification status, as the Enunciado approved in advance
  for RF-007 (T014, branch
  `feature/epic-b-rf007-t014-no-token-for-unverified-user`):
  - `POST /users/auth` answers `401` when the user is `POR_VERIFICAR`
    or `NO_VERIFICADO` and stores no token. The `AuthenticateUserUseCase`
    raises the new `UserNotVerifiedError` (`users_app/src/errors.py`)
    after the credentials are validated, and the router maps it to
    `401`. Invalid credentials still answer `404`, so the endpoint does
    not reveal whether a username exists or what its status is.
  - `GET /users/me` answers `401` for a valid, unexpired token owned by
    a user that is no longer `VERIFICADO`. The `GetCurrentUserUseCase`
    raises the existing `InvalidTokenError` after the token is resolved.
    Every service that validates tokens (the RF-003, RF-004 and RF-005
    orchestrators, and the RF-006 credit cards component) calls this
    endpoint, so the gate covers token verification as a whole without
    touching those services.
  - Both rejections are logged at `WARNING`. No other `users_app`
    behavior changed.
  - Covered with use case tests for both gates (issuance accepted only
    for `VERIFICADO`, rejected for the other two statuses with no token
    stored, and verification rejected for unknown, expired, and
    unverified user tokens) and router tests for the `401` answers: the
    suite grew from 89 to 102 tests at 94.69% coverage. Documented in
    `users_app/README.md` (with the manual end to end verification) and
    `docs/development-view.md`.
  - Updated `scripts/local-verify.sh` (the smoke test asserts the `401`
    while the user is `POR_VERIFICAR`, applies the verification status
    with the same `PATCH /users/{id}` the callback performs, and then
    authenticates) and the local copies of the Entrega 2 Postman
    collections in `scripts/entrega2/` (a `PATCH /users/{id}` request
    simulates the verification callback after each user creation).

## [Entrega 2]

### Changed

- Updated Kubernetes deployment manifests [d49519f]:
  - `k8s/offers-app.yaml`
  - `k8s/posts-app.yaml`
  - `k8s/routes-app.yaml`
  - `k8s/users-app.yaml`


## [Entrega 1] - 2026-08-30

### Added
- Initial set of files for **Entrega 1** (commit `0cb591c`, PR #33 by `pe.trujillo`),
  covering the microservices, domain docs, Kubernetes manifests, and CI workflows
  (198 files, ~19,700 insertions).

#### Microservices
- **offers_app**: FastAPI service with Clean Architecture layout (`domain` / `adapters` /
  `entrypoints`), offer repository adapter, configuration, error handling, unit + API tests,
  Postman collection, `Dockerfile`, and `pyproject.toml`/`poetry.lock`.
- **posts_app**: FastAPI service for publications with database adapter and repository,
  `create_publication` use case, API router and schemas, unit tests, `Dockerfile`,
  and `pyproject.toml`/`poetry.lock`.
- **routes_app**: FastAPI service for routes with domain models (`route`, `schemas`),
  route validation service, database adapter, API router, extensive unit tests
  (including Postman/pytest suites), `Dockerfile`, and `pyproject.toml`/`poetry.lock`.
- **users_app**: FastAPI service for users with database adapter, security adapters
  (password hashing, token generation), auth/user use cases, API router and schemas,
  unit tests, `Dockerfile`, and `pyproject.toml`/`poetry.lock`.

#### Documentation
- `docs/README.md`, `docs/TeamRules.md`, and the four view documents:
  `deployment-view.md`, `development-view.md`, `functional-view.md`, `information-view.md`.
- PlantUML diagrams and their generated PNGs: `components.puml/png`,
  `deployment.puml/png`, `entities.puml/png`, `networks.puml/png`.
- `plantuml-generator` service (`Dockerfile`, `entrypoint.sh`, `.dockerignore`) for
  rendering the diagrams.
- Root `README.md` updated and `old_README.md` preserved.

#### Kubernetes
- Deployment manifests: `offers-app.yaml`, `posts-app.yaml`, `routes-app.yaml`,
  `users-app.yaml`.
- Network policies: `offers-network-policy.yaml`, `posts-network-policy.yaml`,
  `routes-network-policy.yaml`, `users-network-policy.yaml`.

#### CI / Workflows & Tooling
- Updated GitHub Actions workflows: `ci_evaluador_unit.yml`, `ci_pipeline.yml`,
  and new `pages.yml`.
- Updated `config.yaml`, `makefile`, and `.gitignore` to support the new structure.

[Unreleased]: https://github.com/Uniandes-Is4103/202614-grupo33-proyecto/compare/v0.1.0...HEAD
[Entrega 1]: https://github.com/Uniandes-Is4103/202614-grupo33-proyecto/compare/v0.1.0...0cb591c
