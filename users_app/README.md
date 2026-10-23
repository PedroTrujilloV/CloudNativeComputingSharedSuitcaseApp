# Users App

Users microservice for the Shared Suitcase delivery platform. It exposes the Users REST API and owns its data store.

## Requirements

- Python 3.11
- Poetry 2.1.1
- PostgreSQL is optional for now (see persistence below)

## Project structure

```text
.
├── src/
│   ├── adapters/database/   # SQLAlchemy connection helpers
│   ├── adapters/truenative/ # TrueNative verification client (RF-007)
│   ├── domain/              # Models, ports, and use cases
│   ├── entrypoints/api/     # FastAPI application and routers
│   ├── assembly.py          # Dependency injection wiring
│   ├── config.py            # Environment-based settings
│   └── errors.py            # Custom exceptions
├── tests/unit/              # Unit tests
├── Dockerfile               # Container image (users_app:v0.0.0)
├── pyproject.toml
└── README.md
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application name | `users_app` |
| `LOG_LEVEL` | Log level | `DEBUG` |
| `DB_DRIVER` | `postgresql` (default) or `sqlite` (local only) | `postgresql` |
| `DATABASE_URL` | Full SQLAlchemy URL (overrides driver) | _(unset)_ |
| `SQLITE_URL` | SQLite URL when `DB_DRIVER=sqlite` | `sqlite://` (in-memory) |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `users_db` |
| `DB_USER` | Database user | `users_user` |
| `DB_PASSWORD` | Database password | _(empty)_ |
| `TRUE_NATIVE_BASE_URL` | Base URL of the TrueNative platform (RF-007) | `http://truenative-service` |
| `SECRET_TOKEN` | Bearer token sent to TrueNative; must match the TrueNative deployment | _(empty)_ |
| `USER_WEBHOOK_URL` | Absolute URL where TrueNative delivers the verification result | `http://user-verification-callback-service:8000/users/verify/callback` |

No secrets are hardcoded in source. Provide credentials through environment variables.

**PostgreSQL (default):** the service targets its own `users-db` container, as the deployment diagram specifies. `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` build the URL; tables are created on startup via `init_db()`, so the database has to be reachable before the app starts or the startup lifespan fails.

```bash
$env:DB_HOST = "users-db"
$env:DB_PASSWORD = "..."
# or bypass the driver vars entirely:
$env:DATABASE_URL = "postgresql+psycopg://users_user:...@users-db:5432/users_db"
```

**SQLite (local / Postman smoke tests):** set `DB_DRIVER=sqlite` to fall back to shared in-memory SQLite with no server involved. Data lasts only while the process is running. Unit tests pin this driver through `pyproject.toml`.

```bash
$env:DB_DRIVER = "sqlite"
```

## Install dependencies

```bash
cd users_app
poetry install
```

If `poetry.lock` is missing, run `poetry lock` first.

## Run locally

```bash
cd users_app
$env:PYTHONPATH = "$(Get-Location)\src"   # PowerShell
poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

Unix:

```bash
cd users_app
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

API base URL: `http://localhost:8000`

## Docker

Image name/tag must match `config.yaml` (`users_app` / `v0.0.0`).

```bash
cd users_app
docker build -t users_app:v0.0.0 .
```

The container defaults to PostgreSQL, so it needs a reachable database. Against a `users-db` container on a shared network:

```bash
docker network create users-net

docker run -d --name users-db --network users-net \
  -e POSTGRES_DB=users_db \
  -e POSTGRES_USER=users_user \
  -e POSTGRES_PASSWORD=users_pass \
  -v users-db-volumen:/var/lib/postgresql/data \
  postgres:16-alpine

docker run --rm -p 8000:8000 --network users-net \
  -e DB_HOST=users-db \
  -e DB_NAME=users_db \
  -e DB_USER=users_user \
  -e DB_PASSWORD=users_pass \
  users_app:v0.0.0
```

Without a database, override the driver to keep the old serverless behaviour:

```bash
docker run --rm -p 8000:8000 -e DB_DRIVER=sqlite users_app:v0.0.0
```

Hardened run (recommended when the process does not need writes or extra capabilities):

```bash
docker run --rm -p 8000:8000 \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  users_app:v0.0.0
```

Note: `--read-only` suits in-memory SQLite and a remote PostgreSQL alike, since neither writes to the container filesystem. If you need temp files on disk, drop `--read-only` or add a writable `--tmpfs`.

Health check (manual):

```bash
curl http://localhost:8000/users/ping
```

Expected: `pong` (HTTP 200). The image also declares a `HEALTHCHECK` against the same path.

## Run with Kubernetes (Minikube)

The Kubernetes manifests live at the repository root under `k8s/`.

| File | Purpose |
|---|---|
| `k8s/users-app.yaml` | users-app Deployment + NodePort, users-db Deployment + ClusterIP, emptyDir |
| `k8s/users-network-policy.yaml` | Only users-app can reach users-db on TCP 5432 |

NodePort `30000` matches the deployment/network diagrams.

```bash
minikube start --cni=calico
eval $(minikube docker-env)
cd users_app
docker build -t users_app:v0.0.0 .
cd ..
kubectl apply -f k8s/users-app.yaml
kubectl get pods -w
minikube service users-app-service --url
curl $(minikube service users-app-service --url)/users/ping
# → pong
```

`emptyDir` is ephemeral: data survives container restarts but is deleted when the DB pod is deleted.

On Windows PowerShell, `eval $(minikube docker-env)` is not available; use Minikube's documented PowerShell equivalent (`minikube docker-env | Invoke-Expression`) or run the apply from a Unix environment.

### Network policy: users-db isolation

A `NetworkPolicy` allows ingress to `users-db` **only** from pods labeled `app: users-app`, on TCP port `5432`. Other apps cannot reach `users_db`.

File: `k8s/users-network-policy.yaml` (namespace `default`, same labels as `users-app.yaml`).

**Prerequisite:** Minikube's default CNI (Kindnet) does not enforce NetworkPolicies. Calico is **not** a Minikube addon on current versions (`minikube addons enable calico` fails). Create the cluster with Calico from the start.

If Minikube is already running without Calico, stop and **delete** the cluster (a plain `minikube stop` / `minikube start --cni=calico` reuses the old profile and does not switch CNI):

```bash
minikube stop
minikube delete
minikube start --cni=calico
```

Wait until `calico-node` is Ready (`kubectl get pods -n kube-system`), then rebuild the image and apply manifests (existing Deployments were wiped by `delete`).

Deploy app, DB, and policy (from the repository root):

```bash
eval $(minikube docker-env)
cd users_app
docker build -t users_app:v0.0.0 .
cd ..
kubectl apply -f k8s/users-app.yaml
kubectl apply -f k8s/users-network-policy.yaml
kubectl get networkpolicy
```

Allowed (pod labeled `users-app`):

```bash
kubectl run -i --tty test-users-app --rm --image postgres:16-alpine --restart=Never \
  --labels=app=users-app -- sh -c \
  "PGPASSWORD=users_pass psql -h users-db-service -p 5432 -U users_user -d users_db -c 'SELECT 1;'"
```

Blocked (no `users-app` label):

```bash
kubectl run -i --tty test-blocked --rm --image postgres:16-alpine --restart=Never -- sh -c \
  "PGPASSWORD=users_pass psql -h users-db-service -p 5432 -U users_user -d users_db -c 'SELECT 1;'"
```

Expected: allowed query returns `1`; blocked call times out or is refused. If the blocked call succeeds, Calico is not enforcing policies.

## Current endpoints

- `GET /users/ping` → `pong`
- `POST /users` → create user and trigger the TrueNative identity verification (`201` with `{id, createdAt}`; `400` validation; `412` duplicate; a rejected or unreachable verification still answers `201` and stores the user as `NO_VERIFICADO`)
- `POST /users/auth` → authenticate (`200` with `{id, token, expireAt}`; `400` validation; `404` invalid credentials; `401` when the user is not `VERIFICADO`, in which case no token is stored)
- `GET /users/me` → current user (`200` profile; `403` missing bearer; `401` invalid or expired token, and also when the token belongs to a user that is not `VERIFICADO`)
- `PATCH /users/{id}` → update public fields (`200` with confirmation msg; `400` empty/invalid; `404` unknown id)
- `GET /users/count` → `{count}` (`200`)
- `POST /users/reset` → delete all users (`200` with confirmation msg)

## Domain and persistence (issue #11)

- Domain model: `src/domain/models/user.py` (`User`, `UserStatus`)
- Repository port: `src/domain/ports/user_repository_port.py`
- SQLAlchemy model/adapter: `src/adapters/database/`
- Password hashing with explicit salt: `src/adapters/security/password_hasher.py`

`init_db()` runs automatically on application startup (`main.py` lifespan).

## TrueNative verification (RF-007)

User creation registers the identity verification with TrueNative as a normal
synchronous request response call, following the RF-007 sequence view:

1. The user is stored with status `POR_VERIFICAR`.
2. The service calls `POST {TRUE_NATIVE_BASE_URL}/native/verify` with a
   `Authorization: Bearer <SECRET_TOKEN>` header, the available user fields
   (`email`, `dni`, `fullName`, `phone`), the local user id as
   `userIdentifier`, a unique `transactionIdentifier` per request, and the
   absolute `USER_WEBHOOK_URL` as `userWebhook`.
3. On `201` the returned RUV is stored on the user record through
   `set_ruv` (status and `updatedAt` are left untouched).
4. On a rejected request (`400`, `401`, `403`, `409`, or any other error
   status) or when the platform cannot be reached, the user is marked
   `NO_VERIFICADO` and the creation still completes with `201`.

Pieces:

- Port: `src/domain/ports/truenative_port.py` (`TrueNativeVerificationPort`)
- Adapter: `src/adapters/truenative/verification_adapter.py`
  (`TrueNativeVerificationAdapter`, `httpx` with a 10 second timeout)
- Use case: `src/domain/use_cases/create_user_use_case.py`
- Errors: `TrueNativeRequestError` and `TrueNativeUnreachableError` in
  `src/errors.py`
- Wiring: `src/entrypoints/api/deps.py` (`get_truenative_verification_provider`)

The webhook callback that marks the user `VERIFICADO` is a separate component
(T012) and is not implemented here. Unit tests exercise the provider through
an in-memory fake (API and use case tests) and through `httpx.MockTransport`
(adapter tests).

## Token gating by verification status (RF-007, T014)

`users_app` is the only component that issues and validates session
tokens. With the RF-007 lifecycle, a token is only valid while the user
that owns it has the status `VERIFICADO`:

- `POST /users/auth` rejects the credentials of a `POR_VERIFICAR` or
  `NO_VERIFICADO` user with `401` and stores no token. Invalid
  credentials still answer `404`, so the endpoint does not reveal
  whether a username exists or what its status is.
- `GET /users/me` rejects with `401` a valid, unexpired token that
  belongs to a user that is no longer `VERIFICADO`. Every service that
  validates tokens (the RF-003, RF-004 and RF-005 orchestrators, and
  the credit cards component of RF-006) calls this endpoint, so the
  gate covers token verification as a whole without touching those
  services.

Both rejections are logged at `WARNING` level with the user and the
status that caused them.

Pieces:

- `src/domain/use_cases/authenticate_user_use_case.py` raises
  `UserNotVerifiedError` (new, in `src/errors.py`), which the router
  maps to `401`.
- `src/domain/use_cases/get_current_user_use_case.py` raises the
  existing `InvalidTokenError`, which the router already maps to `401`.

### Manual verification (reproducible)

This verification runs the real TrueNative platform, the real
`user_verification_callback` component, and this service on the local
machine (no cluster). The SNS topic ARN is not set, so the callback
composes the result email and logs it, and skips the delivery with a
warning; the delivery itself is covered by the T013 verification.

1. Start TrueNative on port 3000 with the testing variables (success
   rate 0 means the verification will end in `NO_VERIFICADO`):

   ```bash
   docker run -d --name t014-truenative -p 3000:3000 \
     -e SECRET_TOKEN=<secret> -e SUCCESS_RATE=0 \
     -e MAX_WEBHOOK_DELAY=5 -e MAX_POLL_DELAY=2 \
     ghcr.io/misw-4301-desarrollo-apps-en-la-nube/true-native:2.0.0
   ```

2. Start this service on port 8100, pointing at TrueNative and at the
   callback (the absolute SQLite URL needs four leading slashes):

   ```bash
   cd users_app
   DB_DRIVER=sqlite SQLITE_URL="sqlite:////tmp/t014-users.sqlite3" \
   TRUE_NATIVE_BASE_URL=http://127.0.0.1:3000 \
   USER_WEBHOOK_URL=http://host.docker.internal:8105/users/verify/callback \
   SECRET_TOKEN=<secret> LOG_LEVEL=INFO \
   PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app \
     --host 0.0.0.0 --port 8100
   ```

3. Start the callback on port 8105:

   ```bash
   cd user_verification_callback
   USERS_SERVICE_URL=http://127.0.0.1:8100 SECRET_TOKEN=<secret> \
   LOG_LEVEL=INFO PYTHONPATH=$(pwd)/src poetry run uvicorn \
     entrypoints.api.main:app --host 0.0.0.0 --port 8105
   ```

4. Create a user and observe the token issuance gate:

   ```bash
   curl -s -X POST http://127.0.0.1:8100/users \
     -H "Content-Type: application/json" \
     -d '{"username":"t014_unverified","password":"Secret123!","email":"t014.unverified@example.com"}'
   # -> 201 {"id": "..."}

   curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8100/users/auth \
     -H "Content-Type: application/json" \
     -d '{"username":"t014_unverified","password":"Secret123!"}'
   # -> 401 while the status is POR_VERIFICAR
   ```

   With `SUCCESS_RATE=0` the webhook marks the user `NO_VERIFICADO`
   (the callback log shows `is now NO_VERIFICADO`). The same login call
   keeps answering `401`, and the record persists no token.

5. Reconfigure TrueNative so the next verification succeeds, and create
   a second user:

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST \
     http://127.0.0.1:3000/native/env \
     -H "Content-Type: application/json" \
     -d '{"SUCCESS_RATE": 100, "MAX_POLL_DELAY": 5, "MAX_WEBHOOK_DELAY": 5}'
   # -> 200

   curl -s -X POST http://127.0.0.1:8100/users \
     -H "Content-Type: application/json" \
     -d '{"username":"t014_verified","password":"Secret123!","email":"t014.verified@example.com"}'
   # -> 201 {"id": "..."}  (keep the id as USER_ID)

   curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8100/users/auth \
     -H "Content-Type: application/json" \
     -d '{"username":"t014_verified","password":"Secret123!"}'
   # -> 401 while the status is POR_VERIFICAR
   ```

6. When the callback log shows `is now VERIFICADO`, obtain and use the
   token:

   ```bash
   curl -s -X POST http://127.0.0.1:8100/users/auth \
     -H "Content-Type: application/json" \
     -d '{"username":"t014_verified","password":"Secret123!"}'
   # -> 200 {"id": "...", "token": "...", "expireAt": "..."}  (keep the token as TOKEN)

   curl -s http://127.0.0.1:8100/users/me \
     -H "Authorization: Bearer <TOKEN>"
   # -> 200 profile with status VERIFICADO
   ```

7. Exercise the token verification gate: move the user out of
   `VERIFICADO` after the token was issued (the callback performs
   exactly this `PATCH`):

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X PATCH \
     http://127.0.0.1:8100/users/<USER_ID> \
     -H "Content-Type: application/json" \
     -d '{"status": "NO_VERIFICADO"}'
   # -> 200

   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8100/users/me \
     -H "Authorization: Bearer <TOKEN>"
   # -> 401, the token stops resolving
   ```

8. Clean up: stop both processes, run `docker rm -f t014-truenative`,
   and delete the SQLite file.

## Tests

Unit tests live in `tests/unit/`, mirroring the `src/` layout. They run against the
default in-memory SQLite database, so no PostgreSQL instance is required.

```bash
cd users_app
poetry run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing
```

From the repository root (same command used by the makefile):

```bash
make unittest DIR=users_app
```

### Coverage

The suite currently reports **94.69% coverage across 102 tests**, against the 70%
minimum required for the delivery. The run fails if coverage drops below that gate.

### Endpoint coverage

Every endpoint is exercised for its happy path and for each error path defined in
the API contract.

| Endpoint | Happy path | Error paths | Tests |
|---|---|---|---|
| `GET /users/ping` | `200` | — | 1 |
| `POST /users` | `201`, stored as `POR_VERIFICAR` with the TrueNative RUV | `400` missing field, malformed email, malformed username · `412` duplicate username, duplicate email · provider rejection (`400`, `401`, `403`, `409`, `500`) or unreachable platform → `201` stored as `NO_VERIFICADO` | 16 |
| `POST /users/auth` | `200` for a `VERIFICADO` user | `400` missing username, missing password · `404` wrong password, unknown username · `401` user is `POR_VERIFICAR` or `NO_VERIFICADO` (correct credentials, no token stored) | 7 |
| `GET /users/me` | `200` | `403` missing bearer · `401` invalid or expired token, token of a user that is not `VERIFICADO` | 4 |
| `PATCH /users/{id}` | `200` | `400` empty body, disallowed fields, invalid status · `404` unknown id | 7 |
| `GET /users/count` | `200` | — | 2 |
| `POST /users/reset` | `200` | — | 2 |

The remaining 63 tests cover the application lifespan, the persistence
adapter, the TrueNative verification adapter, the create user use case, the
authenticate user use case (token issuance gate for both rejected statuses
and the invalid credentials paths), the get current user use case (token
verification gate for the unknown, expired, and unverified user paths),
password hashing and token generation, the domain model, and
environment-based configuration.

## Authors

- Pedro Trujillo - `pe.trujillo@uniandes.edu.co` Entrega 2 and 3
- Student 1 — `student1@uniandes.edu.co` Entrega 1
