# Posts App (Publicaciones)

Posts microservice for the Shared Suitcase delivery platform. It exposes the Posts REST API and owns its data store.

## Requirements

- Python 3.11
- Poetry 2.1.1
- PostgreSQL is the production default (see persistence below); set `DB_DRIVER=sqlite` for local runs without a database

## Project structure

```text
.
├── src/
│   ├── adapters/database/   # SQLAlchemy models, connection helpers, and PublicationRepository
│   ├── domain/               # Ports and use cases (added in later tasks)
│   ├── entrypoints/api/      # FastAPI application and routers
│   └── config.py             # Environment-based settings
├── tests/unit/                # Unit tests
├── pyproject.toml
└── README.md
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application name | `posts_app` |
| `LOG_LEVEL` | Log level | `INFO` |
| `DB_DRIVER` | `postgresql` (default) or `sqlite` (local only) | `postgresql` |
| `DATABASE_URL` | Full SQLAlchemy URL (overrides driver) | _(unset)_ |
| `SQLITE_URL` | SQLite URL when `DB_DRIVER=sqlite` | `sqlite://` (in-memory) |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `posts_db` |
| `DB_USER` | Database user | `posts_user` |
| `DB_PASSWORD` | Database password | _(empty)_ |

No secrets are hardcoded in source. Provide credentials through environment variables.

**PostgreSQL (default):** the service targets its own `posts-db` container, as the deployment diagram specifies. `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` build the URL; tables are created on startup via `init_db()`, so the database has to be reachable before the app starts or the startup lifespan fails.

```bash
$env:DB_HOST = "posts-db"
$env:DB_PASSWORD = "..."
# or bypass the driver vars entirely:
$env:DATABASE_URL = "postgresql+psycopg://posts_user:...@posts-db:5432/posts_db"
```

**SQLite (local / Postman smoke tests):** set `DB_DRIVER=sqlite` to fall back to shared in-memory SQLite with no server involved. Data lasts only while the process is running. Unit tests pin this driver through `pyproject.toml`.

```bash
$env:DB_DRIVER = "sqlite"
```

## Install dependencies

```bash
cd posts_app
poetry install
```

If `poetry.lock` is missing, run `poetry lock` first.

## Run locally

PowerShell:

```bash
cd posts_app
$env:PYTHONPATH = "$(Get-Location)\src"
poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

Unix:

```bash
cd posts_app
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

API base URL: `http://localhost:8000`

## Docker

Image name/tag must match `config.yaml` (`posts_app` / `v0.0.0`).

```bash
cd posts_app
docker build -t posts_app:v0.0.0 .
```

The container defaults to PostgreSQL, so it needs a reachable database. Against a `posts-db` container on a shared network, matching `docs/diagrams/deployment.puml`:

```bash
docker network create posts-net

docker run -d --name posts-db --network posts-net \
  -e POSTGRES_DB=posts_db \
  -e POSTGRES_USER=posts_user \
  -e POSTGRES_PASSWORD=posts_pass \
  -v posts-db-volumen:/var/lib/postgresql/data \
  postgres:16-alpine

docker run --rm -p 8000:8000 --network posts-net \
  -e DB_HOST=posts-db \
  -e DB_NAME=posts_db \
  -e DB_USER=posts_user \
  -e DB_PASSWORD=posts_pass \
  posts_app:v0.0.0
```

Without a database, override the driver to keep the old serverless behaviour:

```bash
docker run --rm -p 8000:8000 -e DB_DRIVER=sqlite posts_app:v0.0.0
```

Hardened run (recommended when the process does not need writes or extra capabilities):

```bash
docker run --rm -p 8000:8000 \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  posts_app:v0.0.0
```

Note: `--read-only` suits in-memory SQLite and a remote PostgreSQL alike, since neither writes to the container filesystem. If you need temp files on disk, drop `--read-only` or add a writable `--tmpfs`.

Health check (manual):

```bash
curl http://localhost:8000/posts/ping
```

Expected: `pong` (HTTP 200). The image also declares a `HEALTHCHECK` against the same path.

## Run with Kubernetes (Minikube)

The Kubernetes manifests live at the repository root under `k8s/`.

| File | Purpose |
|---|---|
| `k8s/posts-app.yaml` | posts-app Deployment + NodePort, posts-db Deployment + ClusterIP, emptyDir |
| `k8s/posts-network-policy.yaml` | Only posts-app can reach posts-db on TCP 5432 |

NodePort `30001` matches the deployment/network diagrams. Image `posts_app:v0.0.0` matches `config.yaml`.

```bash
minikube start --cni=calico
eval $(minikube docker-env)
cd posts_app
docker build -t posts_app:v0.0.0 .
cd ..
kubectl apply -f k8s/posts-app.yaml
kubectl get pods -w
minikube service posts-app-service --url
curl $(minikube service posts-app-service --url)/posts/ping
# → pong
```

`emptyDir` is ephemeral: data survives container restarts but is deleted when the DB pod is deleted.

On Windows PowerShell, `eval $(minikube docker-env)` is not available; use Minikube's documented PowerShell equivalent (`minikube docker-env | Invoke-Expression`) or run the apply from a Unix environment.

### Network policy: posts-db isolation

A `NetworkPolicy` allows ingress to `posts-db` **only** from pods labeled `app: posts-app`, on TCP port `5432`. Other apps cannot reach `posts_db`.

File: `k8s/posts-network-policy.yaml` (namespace `default`, same labels as `posts-app.yaml`).

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
cd posts_app
docker build -t posts_app:v0.0.0 .
cd ..
kubectl apply -f k8s/posts-app.yaml
kubectl apply -f k8s/posts-network-policy.yaml
kubectl get networkpolicy
```

Allowed (pod labeled `posts-app`):

```bash
kubectl run -i --tty test-posts-app --rm --image postgres:16-alpine --restart=Never \
  --labels=app=posts-app -- sh -c \
  "PGPASSWORD=posts_pass psql -h posts-db-service -p 5432 -U posts_user -d posts_db -c 'SELECT 1;'"
```

Blocked (no `posts-app` label):

```bash
kubectl run -i --tty test-blocked --rm --image postgres:16-alpine --restart=Never -- sh -c \
  "PGPASSWORD=posts_pass psql -h posts-db-service -p 5432 -U posts_user -d posts_db -c 'SELECT 1;'"
```

Expected: allowed query returns `1`; blocked call times out or is refused. If the blocked call succeeds, Calico is not enforcing policies.

## Current endpoints

- `GET /posts/ping` → `pong` (`200`): implemented (Issue #1)
- `POST /posts` → create publication: planned (Issue #3)
- `GET /posts` → list publications with optional filters: planned (Issue #4)
- `GET /posts/{id}` → get a publication by ID: planned (Issue #4)
- `DELETE /posts/{id}` → delete a publication: planned (Issue #4)
- `GET /posts/count` → count publications: planned (Issue #4)
- `POST /posts/reset` → reset all publications (testing): planned (Issue #4)

## Domain and persistence (issue #2)

- Domain model: `src/adapters/database/models.py` (`Publication`) — `id` (UUID, auto-generated), `route_id`, `user_id`, `expire_at`, `created_at` (auto-generated)
- Repository: `src/adapters/database/repository.py` (`PublicationRepository`) — `create`, `get_by_id`, `list`, `delete`, `count`, `delete_all`
- Repository port: N/A (repository is used directly; no port abstraction yet)
- Validation: `create` rejects an `expire_at` that is not strictly in the future
- Filtering: `list` supports `route_id`, `user_id`, and expiration status (`expired` / `not_expired`), combined with AND semantics

`init_db()` runs automatically on application startup (`main.py` lifespan).

## Tests

```bash
cd posts_app
poetry run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing
```

From the repository root (same command used by the makefile):

```bash
make unittest DIR=posts_app
```

Current result: 51 passed, 97% coverage.

- Ping endpoint tests (2)
- Repository CRUD tests (16)
- Connection tests (3)
- Config tests (21)
- Model tests (3)
- Edge case tests (6)

## Author

- Juan Roncancio — `j.roncancioc@uniandes.edu.co`
