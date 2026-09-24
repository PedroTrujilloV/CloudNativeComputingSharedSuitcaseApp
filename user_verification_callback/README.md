# User Verification Callback App

The public callback receiver for RF-007 (user identity verification): it
exposes the unauthenticated `PATCH /users/verify/callback` endpoint that
TrueNative calls with the verification result, verifies the message
signature, updates the user status through the Users service API, and
publishes the result email to the RF-007 SNS topic.

> **Status: complete.** The endpoint verifies `verifyToken` as
> `sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")`, maps the score to the user
> status (`VERIFICADO` when the score is greater than 60,
> `NO_VERIFICADO` when it is 60 or lower), applies the change
> synchronously inside the request, and publishes the result email
> (both outcomes) to the SNS email topic provisioned by the `4_sns`
> Terraform stack. It answers `200` to TrueNative on
> receipt in every case (the TrueNative contract only expects a
> `200`), discarding the message without any change when the signature
> does not match or the user is unknown.

## Tech stack

| Concern      | Choice            |
|--------------|-------------------|
| Language     | Python 3.11       |
| Framework    | FastAPI           |
| ASGI server  | Uvicorn           |
| HTTP client  | `httpx`           |
| AWS SDK      | `boto3` (SNS)     |
| Packaging    | Poetry            |
| Tests        | pytest            |

The receiver is **stateless**: it owns no data and has no database. It
updates the user through the Users service API (`PATCH /users/{id}`),
never by writing to the users database directly, so the data ownership
rule is preserved. All the processing is a normal synchronous
request/response inside the callback request (the SNS publish is a
plain synchronous API call as well); there is no background
processing, no threading and no event loop handling (the component must
stay free of those patterns by design).

## Architecture

The service follows the same Clean Architecture layout as the other apps:

- `domain`: the callback payload model, the result email model, the ports (abstractions) and the use case (business rules).
- `adapters`: the concrete outbound HTTP client for the Users service and the SNS email notification publisher.
- `entrypoints`: the API layer (router, dependency injection, app factory).

```
src/
├── assembly.py                          # Dependency injection wiring
├── config.py                            # Settings (env-driven)
├── errors.py                            # Custom exceptions
├── adapters/
│   ├── http/
│   │   └── users_service_client.py      # Users-service status update client
│   └── sns/
│       └── sns_email_notification.py    # Result email publisher (SNS topic)
├── domain/
│   ├── models/
│   │   ├── updated_user_data.py         # User record from the update answer
│   │   ├── verification_callback.py     # TrueNative callback payload (pydantic)
│   │   └── verification_email.py        # Result email content (value object)
│   ├── ports/
│   │   ├── email_notification_port.py   # Email notification contract (port)
│   │   └── user_update_port.py          # Status update contract (port)
│   └── use_cases/
│       └── process_verification_callback_use_case.py  # Signature + threshold + update + email
└── entrypoints/
    └── api/
        ├── main.py                      # FastAPI app + 400 validation handler
        ├── deps.py                      # Dependency providers (client, email, use case)
        └── routers/
            └── callback_router.py       # PATCH /users/verify/callback + ping
```

### Callback flow

`ProcessVerificationCallbackUseCase.execute` (wired via
`deps.get_process_verification_callback_use_case`):

1. **Verify the signature** `verifyToken` must equal
   `sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")` (the exact scheme TrueNative
   uses to sign the message, compared in constant time). The `SCORE`
   appears in the signature material in its exact textual JSON form, so
   the payload keeps the score as the JSON number it arrived as
   (integer or float) and never coerces it.
2. **Map the score to the status** `VERIFICADO` when the score is
   greater than 60, `NO_VERIFICADO` when it is 60 or lower (the team
   decision documented in `docs/rf007-sequence-view.md`). The `status`
   field carried by TrueNative itself is never trusted; the score is the
   only input to the decision.
3. **Apply the change** `PATCH /users/{userIdentifier}` against the Users
   service with the computed status. The Users service refreshes
   `updatedAt` on the change and answers the updated user record. This
   is a normal synchronous call inside the request.
4. **Publish the result email** the email content is built from the
   user record the platform persisted in the update answer (the final
   status, the RUV, and the user data used in the verification
   process: email, DNI, full name and phone number), and it is
   published synchronously to the RF-007 SNS email topic. The email is
   sent for both `VERIFICADO` and `NO_VERIFICADO` outcomes. A
   notification failure never undoes the applied status change (the
   change is already persisted, and the receipt must stay `200`).
5. **Answer `200`** the endpoint always reports receipt to TrueNative,
   whatever the outcome is.

| Callback outcome | Status applied | Result email | Answer to TrueNative |
|------------------|----------------|--------------|----------------------|
| Valid signature, score greater than 60 | `VERIFICADO` | sent | `200` |
| Valid signature, score 60 or lower | `NO_VERIFICADO` | sent | `200` |
| Signature mismatch | none (message discarded) | not sent | `200` |
| User unknown to the Users service (`404`) | none (message discarded) | not sent | `200` |
| Users service unreachable or error | none (change not applied) | not sent | `200` |
| Malformed body (missing or invalid required field) | none | not sent | `400` |

### The result email (SNS)

The email mechanism was provisioned by the `4_sns` Terraform stack
(TASK-003): the topic `grupo33-user-verification-notifications` has one
email subscription, and its endpoint is the `EMAIL_TO_NOTIFY` value
read at plan time from the `secrets-pipeline-native-map` secret in AWS
Secrets Manager (the deploy pipeline populates it from the GitHub
secret of the same name). No recipient address is hardcoded anywhere in
this repository: this service only publishes to the topic, and the
subscription delivers the message.

- The topic ARN is the `user_verification_topic_arn` output of the
  `4_sns` stack; the deploy pipeline exports it as
  `USER_VERIFICATION_TOPIC_ARN` for the envsubst step that applies the
  Kubernetes manifests (the `${USER_VERIFICATION_TOPIC_ARN}`
  placeholder in `k8s_entrega2/28-user-verification-callback.yml`).
- The AWS credentials of the publish call come from the cluster node
  role through the default boto3 chain (the pod runs on the managed
  node group); nothing AWS related is stored in this repository.
- While the subscription is in the `pending` state SNS discards the
  messages: after the deploy, the confirmation email that SNS sends to
  the `EMAIL_TO_NOTIFY` address must be opened and the link clicked
  once (manual step, documented in the repository README,
  Cloud Deployment Procedure, step 3).
- The email content is fixed by the RF-007 acceptance criteria: the
  final status, the RUV generated by TrueNative, and the user data
  used in the verification process. The status and the RUV come from
  the user record the platform persisted in the status update answer,
  so the email always states what the platform stores. Absent profile
  fields are shown as `Not provided`.
- When `USER_VERIFICATION_TOPIC_ARN` is empty (local runs without the
  AWS stack) the composed email is still logged and the delivery is
  skipped with a warning, so the flow keeps working end to end.

Observability: the receipt, the signature result, the applied status
and the composed email are logged at `INFO`/`WARNING` level (inspect
them with `docker logs <container>` or `kubectl logs <pod>` during
grading or demo).

## API endpoints

| Method | Path                   | Auth | Description                                                                                     |
|--------|------------------------|------|-------------------------------------------------------------------------------------------------|
| `PATCH`| `/users/verify/callback` | none | Receives the TrueNative verification result, verifies the signature and updates the user status. |
| `GET`  | `/users/verify/ping`   | none | Health check (`pong`, used by the container `HEALTHCHECK` and the Kubernetes probes).           |

### `PATCH /users/verify/callback` contract

Request body (the exact payload TrueNative delivers through its webhook;
`RUV`, `userIdentifier`, `score` and `verifyToken` are required):

```json
{
  "RUV": "dHgtMTpidXNlci0x",
  "userIdentifier": "user-1",
  "transactionIdentifier": "tx-1",
  "createdAt": "2026-09-23T12:00:00",
  "status": "VERIFICADO",
  "score": 92.5,
  "verifyToken": "sha256-hex-of-SECRET_TOKEN:RUV:SCORE"
}
```

Success response (`200`, receipt only, empty body):

```
200 OK
```

| Status | When                                                        | Body  |
|--------|-------------------------------------------------------------|-------|
| `200`  | Well-formed callback received (signature applied or not)    | empty |
| `400`  | Missing or malformed required field (for example no `RUV`)  | empty |
| `405`  | Any method other than `PATCH`                               | empty |

## Environment variables

| Variable                    | Description                                   | Default                          |
|-----------------------------|-----------------------------------------------|----------------------------------|
| `APP_NAME`                  | Application name (FastAPI title)              | `user_verification_callback`     |
| `LOG_LEVEL`                 | Log level                                     | `DEBUG`                          |
| `USERS_SERVICE_URL`         | Base URL of the Users service (update target) | `http://users-app-service:8000`  |
| `SECRET_TOKEN`              | Shared secret for the callback signature      | empty                            |
| `HTTP_TIMEOUT`              | Downstream HTTP timeout (seconds)             | `5`                              |
| `USER_VERIFICATION_TOPIC_ARN` | ARN of the RF-007 SNS email topic (4_sns stack output) | empty                  |
| `AWS_REGION`                | Region for the SNS client                     | `us-east-1`                      |
| `SNS_ENDPOINT_URL`          | Optional SNS endpoint override (local simulation) | empty                        |

`SECRET_TOKEN` must match the `SECRET_TOKEN` environment variable of the
TrueNative deployment (both read the same `truenative-secret` Kubernetes
Secret); it is provided through the environment and never hardcoded in
source.

## Run locally

```bash
cd user_verification_callback
poetry install
SECRET_TOKEN=top-secret PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8005
```

API base URL: `http://localhost:8005`. Point `USERS_SERVICE_URL` at a
running `users_app` instance (for example `http://localhost:8000`, the
usual local port) to make the status update reachable.

## Run tests

```bash
poetry run pytest --cov=src --cov-fail-under=70
```

- **Unit tests** (mocked Users service and SNS client) cover the HTTP
  client (success with the user block parsed, partial and absent user
  block, unknown fields dropped, `404`, other statuses, network error,
  client lifecycle), the SNS adapter (publish to the topic with the
  mandatory content, skip without the topic ARN, provider error,
  composed subject and body, absent fields shown as `Not provided`,
  endpoint override, client lifecycle), the use case (signature match
  and mismatch, wrong secret, tampered score or RUV, exact score text
  form for integer scores, score at or below 60 mapped to
  `NO_VERIFICADO`, score above 60 mapped to `VERIFICADO`, unknown
  user, Users service error, provider status field ignored, email
  content taken from the persisted user record with payload fallback,
  email failure keeping the applied change, skipped email outcome) and
  the router (200 receipt, email sent for both outcomes, no email on
  the discard paths, email failure still 200, unknown user still 200,
  malformed body 400, wrong method 405, plus the full wiring with the
  real use case and the real SNS adapter over mock clients).

## Run with Docker

```bash
docker build -t user-verification-callback:v0.0.0 .
docker run --rm -p 8005:8000 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e SECRET_TOKEN=top-secret \
  user-verification-callback:v0.0.0
```

The image name `user-verification-callback:v0.0.0` matches `config.yaml`
(`image_name: user-verification-callback`, `image_tag: v0.0.0`), so it is
ready for ECR publication. The `HEALTHCHECK` probes
`GET /users/verify/ping`.

## Manual verification (curl)

Prerequisites: `users_app` running (for example on port `8000`) and this
receiver on port `8005` with the same `SECRET_TOKEN` that TrueNative
would use.

```bash
# 0. Create a user (Users service) and keep its id
curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"cbtester","password":"Secret123!","email":"cbtester@example.com"}'
# -> 201 {"id": "..."}   (use that id as USER_ID below)

# 1. Health check
curl -s http://localhost:8005/users/verify/ping
# -> pong

# 2. Build a correctly signed callback (score above 60 means VERIFICADO)
RUV="dGVzdC10eDox"
SCORE=92.5
TOKEN=$(python3 -c "import hashlib; print(hashlib.sha256('top-secret:$RUV:$SCORE'.encode()).hexdigest())")

curl -s -o /dev/null -w "%{http_code}\n" -X PATCH http://localhost:8005/users/verify/callback \
  -H "Content-Type: application/json" \
  -d "{\"RUV\":\"$RUV\",\"userIdentifier\":\"$USER_ID\",\"transactionIdentifier\":\"tx-1\",\"createdAt\":\"2026-09-23T12:00:00\",\"status\":\"VERIFICADO\",\"score\":$SCORE,\"verifyToken\":\"$TOKEN\"}"
# -> 200

# 3. Check the user status on the Users service (through any endpoint or
#    the database) -> VERIFICADO, and updatedAt refreshed.

# 3b. The result email: in the receiver log the composed email is
#     visible (status VERIFICADO, the RUV, and the user data). Without
#     USER_VERIFICATION_TOPIC_ARN the delivery is skipped with a
#     warning; with the topic ARN (for example from a local AWS account
#     after applying the 4_sns stack) it is published to the SNS topic.
#     On the deployed cluster the email arrives in the EMAIL_TO_NOTIFY
#     mailbox after the SNS subscription has been confirmed.

# 4. Bad signature -> 200 receipt, no status change
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH http://localhost:8005/users/verify/callback \
  -H "Content-Type: application/json" \
  -d "{\"RUV\":\"$RUV\",\"userIdentifier\":\"$USER_ID\",\"score\":92.5,\"verifyToken\":\"deadbeef\"}"
# -> 200 (and the status stays the previous one)
```
