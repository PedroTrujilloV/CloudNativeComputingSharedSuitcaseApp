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

### Network policy — users-db isolation

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
- `POST /users` → create user (`201` with `{id, createdAt}`; `400` validation; `412` duplicate)
- `POST /users/auth` → authenticate (`200` with `{id, token, expireAt}`; `400` validation; `404` invalid credentials)
- `GET /users/me` → current user (`200` profile; `403` missing bearer; `401` invalid/expired token)
- `PATCH /users/{id}` → update public fields (`200` with confirmation msg; `400` empty/invalid; `404` unknown id)
- `GET /users/count` → `{count}` (`200`)
- `POST /users/reset` → delete all users (`200` with confirmation msg)

## Domain and persistence (issue #11)

- Domain model: `src/domain/models/user.py` (`User`, `UserStatus`)
- Repository port: `src/domain/ports/user_repository_port.py`
- SQLAlchemy model/adapter: `src/adapters/database/`
- Password hashing with explicit salt: `src/adapters/security/password_hasher.py`

`init_db()` runs automatically on application startup (`main.py` lifespan).

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

The suite currently reports **93.89% coverage across 46 tests**, against the 70%
minimum required for the delivery. The run fails if coverage drops below that gate.

### Endpoint coverage

Every endpoint is exercised for its happy path and for each error path defined in
the API contract.

| Endpoint | Happy path | Error paths | Tests |
|---|---|---|---|
| `GET /users/ping` | `200` | — | 1 |
| `POST /users` | `201` | `400` missing field, malformed email, malformed username · `412` duplicate username, duplicate email | 7 |
| `POST /users/auth` | `200` | `400` missing username, missing password · `404` wrong password, unknown username | 5 |
| `GET /users/me` | `200` | `403` missing bearer · `401` invalid or expired token | 3 |
| `PATCH /users/{id}` | `200` | `400` empty body, disallowed fields, invalid status · `404` unknown id | 7 |
| `GET /users/count` | `200` | — | 2 |
| `POST /users/reset` | `200` | — | 2 |

The remaining 19 tests cover the persistence adapter, password hashing and token
generation, the domain model, and environment-based configuration.

## Author

- Agustin Serrano — `a.serranor@uniandes.edu.co`
