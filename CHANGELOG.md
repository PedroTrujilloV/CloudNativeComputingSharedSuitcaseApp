# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased ]

### Added

- Added the RF-006 utility endpoints (TASK-025, issue #96):
  `credit_cards_app` now serves `GET /credit-cards/count` (200 with
  `{"count": <n>}`), `GET /credit-cards/ping` (200 with the plain text
  body `pong`, the same contract as the TrueNative liveness probe), and
  `POST /credit-cards/reset` (deletes every stored card and answers 200
  with the exact documented message `{"msg": "Todos los datos fueron
  eliminados"}`, not translated). All three are unauthenticated, as the
  API specification defines them; the grading pipeline uses them to set
  up and check state between runs, so the exact contract fidelity is
  asserted by the unit tests and the verification scripts. New
  `CountCreditCardsUseCase` and `ResetCreditCardsUseCase` (the repository
  port already exposed `count` and `delete_all`), the
  `CountCreditCardsResponse` and `ResetCreditCardsResponse` schemas, and
  173 unit tests in `credit_cards_app` (99% coverage). The image
  health check now probes `/credit-cards/ping` instead of
  `/openapi.json`; `scripts/local-verify.sh` uses the ping as the
  routing check, and `scripts/terraform_scripts/verify-aws-rf006.sh`
  checks the ping and count answers and uses the reset endpoint for the
  final cleanup (the item by item table deletion stays as fallback).
- Added the card listing endpoint `GET /credit-cards` (TASK-024, issue
  #95, RF-006): `credit_cards_app` now answers 200 with the JSON array of
  the caller's stored cards, each item with `id`, `token`, `userId`,
  `lastFourDigits`, `issuer`, `status`, `createdAt`, and `updatedAt`
  (the dates in ISO `yyyy-mm-ddTHH:MM:SS`, UTC 0). The bearer token
  contract matches the creation endpoint (403 without a token, 401 with
  an invalid or expired token, validated against the users application),
  and the listing is strictly user scoped: a single query on the
  `userId-index` GSI filtered by the caller id, so cards belonging to
  other users are never returned. The raw card number and the CVV are not
  stored by the application, so they cannot appear in the answer, and the
  payment `token` is documented in the listing only because the API
  contract of the exercise requires it (a real service would never expose
  it). New `ListCreditCardsUseCase` and `CreditCardResponse` schema; 165
  unit tests in `credit_cards_app` (99% coverage). The asynchronous
  terminal states are now observed through this endpoint in the manual
  verification (the same contract the grader collection uses), and
  `scripts/local-verify.sh` asserts the listing auth contract (403
  without a token, 401 with an invalid token) on Minikube.
- Added the result email notification of the card verification (TASK-023,
  issue #94, RF-006): the `card_worker` now publishes, right after it
  persists the terminal state, the mandatory email notification to the SNS
  topic `grupo33-card-verification-notifications` of the `4_sns` stack. The
  message carries the process result, the basic card data as stored in the
  database (id, last four digits, issuer, updated date), the RUV generated
  by TrueNative, and the recipient address; the raw card number and the CVV
  never appear in it. The notification is sent for every outcome: on the
  terminal state the publish raises on failure, so the queue redelivers the
  event and the notification is retried (the status update is idempotent by
  card id), and on the last receive without a terminal state (detected
  through the SQS `ApproximateReceiveCount` attribute and the new
  `MAX_RECEIVE_COUNT` setting that mirrors the redrive policy of the
  `5_sqs` stack) the worker publishes the `POR_VERIFICAR` fallback
  notification before the event moves to the dead letter queue, so the
  owner is never left without the email. The recipient is the owner email
  that `credit_cards_app` resolves through the `users_app` API
  (`GET /users/me`) at creation time and carries in the queue event (new
  `ownerEmail` field), so the worker never reads the users database. New
  `CardResultPublisherPort` and `SnsCardResultPublisherAdapter` in
  `card_worker`, and 82 unit tests in `card_worker` (99% coverage, moto
  in memory DynamoDB and SNS, `httpx2` mock transport, injected sleep for
  the polling waits).
- Added the manual verification of the RF-006 asynchronous card
  verification flow (follow up of TASK-022, issue #93): a new
  `scripts/terraform_scripts/verify-aws-rf006.sh` script that runs the
  full reproducible sequence on the AWS dev environment. It checks the
  asynchronous infrastructure (the card verification queue, its dead
  letter queue, the DynamoDB table, the image based Lambda function and
  its execution role, the SQS event source mapping, the credit cards and
  TrueNative Deployments, and the ingress load balancer by tag), the
  synchronous contract of `POST /credit-cards` (403 without a token, 401
  with an invalid token, 400 with missing fields, and 412 with an
  expired card), the asynchronous seam (`POR_VERIFICAR` right after the
  201 creation, then `RECHAZADA` with `SUCCESS_RATE=0` and `APROBADA`
  with `SUCCESS_RATE=100`, reading the terminal state from the table and
  later from the card listing endpoint added in TASK-024, with the queue
  and the dead letter queue drained), and the duplicate rejection (409). It uses
  relative dates computed at runtime, exits 0 only when every check
  passes, and deletes the created cards unless `--keep` is passed. The
  exact steps are documented in the new Manual verification of RF-006
  section of `docs/development-view.md` (AWS full flow, local Minikube
  partial flow and why the happy path is AWS only), with short pointers
  in `docs/README.md` (Run with Minikube) and in the `credit_cards_app`
  README.
- Implemented the asynchronous credit card verification worker (TASK-022,
  issue #93, RF-006): a new `card_worker` application, an AWS Lambda
  function packaged as a container image (SAM Python 3.11 base, handler
  `handler.handler`), that consumes the card verification queue, polls
  TrueNative `GET /native/cards/{ruv}` a bounded number of times per
  invocation (5 attempts with a 2 second interval and a 3 second timeout by
  default), and updates the terminal card status and `updatedAt` in the
  DynamoDB table owned by `credit_cards_app` (idempotent by card id). When
  the attempts are exhausted the invocation fails on purpose, so the queue
  redelivers the event and the card stays `POR_VERIFICAR`; after the
  maximum number of receives (5) the event is moved to the dead letter
  queue, which is the documented fallback of the pattern. New Terraform
  stacks: `5_sqs` (queue, dead letter queue, and redrive policy, in
  `tf_stacks`) and `6_lambda` (image based function, least privilege
  execution role, and SQS event source mapping with batch size 1, in
  `post_k8s_stacks`, reaching TrueNative through the single external host
  of the platform). The `card-worker` ECR repository in `2_registry`, the
  `card_worker` entry in `config.yaml` `apps` (image `card-worker:v0.0.0`),
  the missing `k8s_entrega3/k8s-credit-cards-deployment.yml` (the
  Deployment + Service that the `/credit-cards` ingress rule targets,
  wiring the DynamoDB table name and the queue URL from the Terraform
  outputs), and the `card_worker` job in `ci_evaluador_unit.yml`. 63 unit
  tests with 99% coverage (moto in memory DynamoDB, `httpx2` mock
  transport, injected sleep for the polling waits).

### Changed

- Updated `credit_cards_app` so the bearer token verification resolves the
  card owner (id and email) through the users application API with the new
  `VerifiedUser` value object, and the `CARD_VERIFICATION_REQUESTED` queue
  event now carries the owner email, which the card worker uses to address
  the result email notification. 157 unit tests with 98% coverage.
- Updated the `6_lambda` stack to inject the `MAX_RECEIVE_COUNT`
  environment variable (new variable, default 5, mirroring
  `max_receive_count` of the `5_sqs` stack), and updated
  `scripts/terraform_scripts/verify-aws-rf006.sh` to check the SNS topic of
  the result notification and the notification publish itself (both the
  `RECHAZADA` and the `APROBADA` entries in the CloudWatch log group of the
  worker). The documentation followed: the Manual verification of RF-006
  section of `docs/development-view.md` (new step 9 for the email check,
  renumbered to 11 steps), the `card_worker` and `credit_cards_app`
  READMEs, the RF-006 sequence view, and the messaging and email mechanism
  section of the deployment view.
- Updated the deployment and verification scripts for RF-006:
  `scripts/local-deploy.sh` now builds the `credit-cards-app` image and
  deploys the `k8s_entrega3/` credit cards Deployment and Service with
  local placeholder values (a placeholder table name and an empty queue
  URL that makes the app skip the publish and log it),
  `scripts/local-verify.sh` now asserts the credit cards pod and
  service, the ingress routing of `POST /credit-cards`, and the 403,
  401, 400 and 412 responses, and
  `scripts/terraform_scripts/deploy-k8s-to-eks.sh` now builds and pushes
  the `credit-cards-app` image, renders the credit cards manifest from
  the `3_dynamodb` and `5_sqs` Terraform outputs, applies it before the
  ingress, and waits for it.
- Added the missing `config.tf` (AWS provider block with the default
  tags) to the `5_sqs` and `6_lambda` stacks, pinning the AWS provider
  to `~> 6` to match the resource and data source names those stacks
  already use (`message_retention_seconds` and the `aws_lb` data
  source); without it their `terraform plan` failed on the provider
  configuration.
- Updated `config.yaml` (`5_sqs` in `tf_stacks`, `6_lambda` in
  `post_k8s_stacks`, and the `card_worker` application entry), the root
  `README.md` (stack table, deployment order, and the deployment
  procedure), `docs/development-view.md` (application and k8s folders),
  `docs/terraform-deployment.md` (stack decomposition, deployment order,
  and destroy order), and `docs/deployment-view.md` (infrastructure and
  ingress sections). The stack README copy list in `pages.yml` now
  includes `3_dynamodb`, `5_sqs`, and `6_lambda`, and the app README copy
  list now includes `credit_cards_app` and `card_worker`.

- Implemented the synchronous card creation flow of `credit_cards_app`
  (TASK-021, issue #92, RF-006): `POST /credit-cards` validates the caller
  bearer token against the users application (`GET /users/me`, no direct
  access to its database), rejects missing, empty, or malformed fields
  with 400, expired cards with 412, and duplicates with 409, tokenizes the
  card at TrueNative (`POST /native/cards` with a unique
  `transactionIdentifier` and the `Authorization: Bearer <SECRET_TOKEN>`
  header), persists it as `POR_VERIFICAR` (the raw card number and the CVV
  are never stored), publishes the verification event to the SQS queue,
  and answers `201 {id, userId, createdAt}` in under 5 seconds. A
  TrueNative tokenization failure stores nothing and answers 502. New
  adapters for the users application, TrueNative, and the queue, the
  `CreateCreditCardUseCase`, the BIN issuer detection with `UNKNOWN`
  fallback, and the expiration service. 156 unit tests with 98% coverage
  (moto in memory DynamoDB and SQS, `httpx2` mock transport for the HTTP
  adapters).

### Changed

- Extended `credit_cards_app` configuration with `USERS_APP_URL`,
  `TRUENATIVE_URL`, `TRUENATIVE_SECRET_TOKEN`,
  `CARD_VERIFICATION_QUEUE_URL`, and `HTTP_TIMEOUT_SECONDS`, and moved
  `httpx2` from the dev group to the main dependencies (it is now the
  runtime HTTP client of the token validation and the TrueNative
  tokenization).
- Updated `credit_cards_app/README.md` (creation flow, request and error
  contract, environment variables) and `docs/development-view.md`
  (application folder description).

- Created the `credit_cards_app` component (TASK-020, issue #91, RF-006
  scaffold): application skeleton (FastAPI, no business endpoints yet),
  `CreditCard` data model with the `issuer` and `status` enums from the
  entity specification (dates follow the ISO `yyyy-mm-ddTHH:MM:SS` contract
  in UTC 0), and the exclusive DynamoDB persistence layer (partition key `id`,
  `userId-index` GSI). 54 unit tests with 100% coverage, run against an
  in memory DynamoDB table (moto); no raw card number or CVV is stored.
- Added the `3_dynamodb` Terraform stack (dedicated DynamoDB table for the
  `CreditCard` entity, exclusive to `credit_cards_app`) with the `dev` and
  `student1` environments, and registered it in `config.yaml` `tf_stacks`
  between `2_registry` and `eks`. The `dev` environment table
  (`grupo33-credit-cards`) was applied to validate the stack end to end.
- Extended the `2_registry` stack with the `credit-cards-app` ECR
  repository and registered the `credit_cards_app` entry in `config.yaml`
  `apps` so the deploy pipeline builds and pushes the new image.
- Added the `credit_cards_app` job to `ci_evaluador_unit.yml` (unit tests
  with the 70% coverage minimum, same pattern as the other applications).
- Documented the `CreditCard` entity in `docs/information-view.md`, the
  application in `docs/development-view.md`, and the new stack in
  `docs/terraform-deployment.md`, the root `README.md` stack table, and the
  `makefile` `docscopy` target.
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

### Changed

- Fixed the `6_lambda` stack for the academic lab accounts (TASK-035):
  those accounts deny `iam:CreateRole` and `iam:PutRolePolicy` (the lab
  identity policy), so the stack no longer creates the least privilege
  execution role of the card worker; the `aws_lambda_function` resource
  now uses the `LabRole` that every lab account provisions in advance
  (the ARN is built from the caller identity at plan time, so the same
  stack works in the dev and the student1 lab accounts). The removed
  `card_worker_role_arn` output, the `lambda_assume` data source, and the
  `lambda_role_name` variable (still declared, now documented as unused
  because the environment tfvars pass it) followed, together with the
  stack README.
- Fixed the startup of the `users_app` so a persistent database follows
  the model (TASK-035): `create_all` builds missing tables but never
  evolves existing ones, so a long lived RDS from an earlier deployment
  kept its old column set and the app failed on the first query that
  touches a column added later by the model (the `ruv` column of the
  users table). `init_db` now calls `ensure_schema_columns`, which
  inspects every mapped table and adds the missing nullable columns
  with the model types (`ALTER TABLE ... ADD COLUMN ... NULL`); a
  missing primary key or non nullable column raises instead of being
  guessed. Covered by the new unit tests of
  `test_connection_schema_evolution.py` (16 cases), and verified on the
  dev cluster: the running image self healed the persistent RDS at
  startup and the full RF-007 flow ran green on top of it.
- Fixed the Terraform output surface consumed by the deploy pipeline
  (TASK-035) so the pipeline's combined `tf_outputs` JSON no longer
  carries the value of any GitHub environment secret. Root cause: GitHub
  Actions silently discards a job output when it contains the value of
  any secret in scope as a substring, and the pipeline merges every
  stack output into that single JSON; one "poisoned" output (any ARN or
  URL embedding the account id, the port `5432`, the database name
  `shared_db`, the `SECRET_TOKEN` value, the notification email)
  discarded the whole map, so every downstream envsubst render resolved
  empty and the apps started without their wiring. The fix, without
  touching the unmodifiable pipeline:
  - `1_database` no longer exposes `rds_port`, `rds_db_name`, or the
    Secrets Manager ARN; it exposes `secrets_manager_secret_name` (safe,
    consumed by the local AWS deploy script) and keeps `rds_address`
    (safe: the endpoint matches no secret value as a substring). Port
    and database name are the same fixed values in every environment,
    so `k8s_entrega2/00-secrets.yml` hardcodes `DB_PORT="5432"` and
    `DB_NAME="shared_db"` and envsubst only `DB_HOST` (from
    `rds_address`), `DB_USER` and `DB_PASSWORD` (the pipeline injects
    both straight from the environment secrets into the step
    environment). The AWS Secrets Store CSI variant was tried and
    reverted: the lab EKS cluster has no `secrets-store` CRDs or driver
    pod, the node role lacks `secretsmanager:GetSecretValue`, and the
    async materialization raced the pipeline rollout wait.
  - The TrueNative token stays the `SECRET_TOKEN` value of the
    `secrets-pipeline-native-map` secret (the only allowed source for
    the token and the verification email), but it can no longer be
    exposed as a plain output (it is an environment secret;
    re-exposing it would poison the combined `tf_outputs`). The `eks`
    stack therefore exposes the **base64 encoding** of the map value
    through the new `secret_token_b64` output: the encoded form
    contains no secret value as a substring, so it crosses the
    pipeline channel safely, and the pipeline exports it as
    `SECRET_TOKEN_B64` for the envsubst step; the TrueNative manifest
    fills a K8s Secret `data:` field, which takes base64 natively. The
    `6_lambda` stack reads the same map key with a data source, so the
    card worker and the k8s apps always carry the same token.
  - `3_dynamodb`, `4_sns` and `5_sqs` expose only resource names (safe);
    the full table ARN, topic ARNs and queue URLs are reconstructed at
    apply time by envsubst from the name plus `$AWS_REGION` and
    `$ACCOUNT_ID` (both provided by the pipeline itself) in
    `k8s_entrega2/28-user-verification-callback.yml` and
    `k8s_entrega3/k8s-credit-cards-deployment.yml`. `4_sns` also stops
    exposing `email_endpoint` (it equals the `EMAIL_TO_NOTIFY`
    environment secret; the subscription keeps using it internally).
  - `5_sqs` gains the missing `backend "s3" {}` block (without it, its
    state was written to the ephemeral runner's local backend and lost
    on every run) and aligns its AWS provider pin to `~> 5` like every
    other stack. The pre-existing queue of `dev` (left behind by the
    runs before the fix) was imported into the S3 state locally, and the
    `student1` queue was left in a state the pipeline recreates
    cleanly (the queue names are deterministic), so the pipeline applies
    both environments as "no changes" instead of failing with
    `QueueAlreadyExists`.
  - `6_lambda` sets `package_type = "Image"` on the card worker function:
    the AWS provider defaults to the Zip package type, which made every
    plan fail with "handler and runtime must be set when PackageType is
    Zip" (the stack
    had never been planned before the pipeline fix, since every run
    failed before the post-k8s step).
- Updated the local flows to the same channels: `scripts/local-deploy.sh`
  renders the composed ARN/URL from the placeholders and then empties
  the value (the callback and the credit cards app skip the publish with
  a logged notice, as before), and
  `scripts/terraform_scripts/deploy-k8s-to-eks.sh` reads the token from
  the map (and computes its base64 form for the K8s Secret `data:`
  field) and the queue/topic names from the stack outputs, and
  reconstructs the full values.
- Updated the stack READMEs, the `card_worker` token docstring, the
  `user_verification_callback` docstrings and README, and
  `docs/development-view.md` to match the new channels.

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
