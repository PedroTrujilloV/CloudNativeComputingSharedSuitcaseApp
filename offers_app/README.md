# Offers App

Offers microservice for the Shared Suitcase delivery platform. It exposes the Offers REST API and owns its PostgreSQL database.

## Requirements

- Python 3.11
- Poetry 2.1.1

Runtime dependencies (installed via `poetry install`):

- FastAPI — API framework
- SQLAlchemy — ORM and persistence
- Uvicorn — ASGI server
- psycopg (binary) — PostgreSQL driver

Development dependencies (managed in the `dev` dependency group):

- httpx — HTTP test client
- pytest — test runner
- pytest-cov — coverage reporting

Postman API verification requires Node.js with `npx` available to run `newman`.

## Project structure

```text
.
├── src/
│   ├── adapters/database/   # PostgreSQL connection helpers
│   ├── domain/              # Models, ports, and use cases (added in later tasks)
│   ├── entrypoints/api/     # FastAPI application and routers
│   ├── config.py            # Environment-based settings
├── tests/unit/              # Unit tests
├── pyproject.toml
└── README.md
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application name | `offers_app` |
| `LOG_LEVEL` | Log level | `DEBUG` |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `offers_db` |
| `DB_USER` | Database user | `offers_user` |
| `DB_PASSWORD` | Database password | _(empty)_ — requires `trust` auth in `pg_hba.conf` |
| `DATABASE_URL` | Overrides all `DB_*` settings when set | _(unset)_ |

No secrets are hardcoded in source. Provide credentials through environment variables.

> **Note:** `DATABASE_URL` takes precedence over `DB_DRIVER`, `DB_HOST`, `DB_PORT`, `DB_NAME`,
> `DB_USER`, and `DB_PASSWORD`. When `DATABASE_URL` is set, the other `DB_*` variables are ignored.

> **Note:** Unit tests force `DB_DRIVER=sqlite` at runtime in `tests/unit/conftest.py` because
> `pyproject.toml`'s `[tool.pytest.ini_options].env` has no effect without the `pytest-env` plugin.
> Integration tests would be needed to validate PostgreSQL connectivity.

## Install dependencies

```bash
cd offers_app
poetry install
```


## Run locally

```bash
cd offers_app/src
poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

API base URL: `http://localhost:8000`

## Current endpoints

All endpoints live under the `/offers` prefix. Query/body fields use camelCase as defined in the API contract.

### Health

| Method | Route | Description |
|---|---|---|
| `GET` | `/offers/ping` | Health check. Returns `pong`. |

### Create an offer

| Method | Route | Description |
|---|---|---|
| `POST` | `/offers` | Creates an offer. |

Request body:

```json
{
  "postId": "uuid",
  "userId": "uuid",
  "description": "descripción del paquete a llevar",
  "size": "LARGE | MEDIUM | SMALL",
  "fragile": true,
  "offer": 150.50
}
```

Responses:

| Code | Body |
|---|---|
| `201` | `{"id", "userId", "createdAt"}` |
| `400` | A field is missing or malformed (e.g. description > 140 chars, more than 2 decimals) |
| `412` | A value is out of the expected range (e.g. invalid size, negative offer) |

### List and filter offers

| Method | Route | Description |
|---|---|---|
| `GET` | `/offers?post={postId}&owner={userId}` | Lists offers. Both query params are optional and combine with AND semantics. |

Responses:

| Code | Body |
|---|---|
| `200` | Array of full offer objects: `{"id", "postId", "userId", "description", "size", "fragile", "offer", "createdAt"}` |
| `400` | A search field does not have the expected UUID format |

If no filter is provided, the full unfiltered list is returned.

### Get a single offer

| Method | Route | Description |
|---|---|---|
| `GET` | `/offers/{id}` | Returns the offer with the given id. |

Responses:

| Code | Body |
|---|---|
| `200` | Full offer object: `{"id", "postId", "userId", "description", "size", "fragile", "offer", "createdAt"}` |
| `400` | The id is not a string with UUID format |
| `404` | No offer exists with that id |

### Delete an offer

| Method | Route | Description |
|---|---|---|
| `DELETE` | `/offers/{id}` | Deletes the offer with the given id. |

Responses:

| Code | Body |
|---|---|
| `200` | `{"msg": "la oferta fue eliminada"}` |
| `400` | The id is not a string with UUID format |
| `404` | No offer exists with that id |

### Count offers

| Method | Route | Description |
|---|---|---|
| `GET` | `/offers/count` | Returns the number of stored offers. |

Responses:

| Code | Body |
|---|---|
| `200` | `{"count": <non-negative integer>}` |

### Reset the database

| Method | Route | Description |
|---|---|---|
| `POST` | `/offers/reset` | Deletes all stored offers. |

Responses:

| Code | Body |
|---|---|
| `200` | `{"msg": "Todos los datos fueron eliminados"}` |

## Docker

Image name/tag must match `config.yaml` (`offers_app` / `v0.0.0`).

```bash
cd offers_app
docker build -t offers_app:v0.0.0 .
```

## Run with Kubernetes (Minikube)

### Requirements
- [x] Pods/Deployments for the app and PostgreSQL DB
- [x] App Service: NodePort
- [x] DB Service: ClusterIP
- [x] `emptyDir` volumes for the DB (ephemeral, not persistent)
- [x] Namespace: `default`
- [x] Env-based configuration for DB connection strings

### Acceptance Criteria
- [x] `kubectl apply -f k8s/` deploys all 2 workloads successfully on Minikube
- [x] Offers app is reachable externally via its NodePort service
- [x] PostgreSQL DB is reachable only internally via ClusterIP
- [x] `ci_evaluador_entrega1_k8s.yml` passes unmodified

### Deploy to Minikube

**1. Build the Docker image in minikube's daemon:**

```bash
minikube start
eval $(minikube docker-env)
cd offers_app
docker build -t offers_app:v0.0.0 .
```

**2. Apply the Kubernetes manifests (from project root):**

> **Note:** All k8s manifests live in the project root `k8s/` directory. Run all `kubectl apply` commands from there.

```bash
kubectl apply -f k8s/offers-app.yaml
kubectl get pods -w  # wait for both pods to show Running
```

**3. Access the app:**

```bash
minikube service offers-app-service --url
curl $(minikube service offers-app-service --url)/offers/ping
# → pong
```

**4. Test all endpoints on Minikube:**

```bash
# Health check
curl $(minikube service offers-app-service --url)/offers/ping

# Create an offer
curl -s -X POST $(minikube service offers-app-service --url)/offers \
  -H "Content-Type: application/json" \
  -d '{"postId":"550e8400-e29b-41d4-a716-446655440000","userId":"660e8400-e29b-41d4-a716-446655440001","description":"Test offer","size":"SMALL","fragile":false,"offer":100.00}'

# List offers
curl $(minikube service offers-app-service --url)/offers

# Delete an offer
curl -s -X DELETE $(minikube service offers-app-service --url)/offers/<offer-id>
# → {"msg": "la oferta fue eliminada"}

# Reset database
curl -s -X POST $(minikube service offers-app-service --url)/offers/reset
# → {"msg": "Todos los datos fueron eliminados"}
```

**5. Run Postman collection on Minikube:**

```bash
newman run .continue/entrega1_offers.json -e <minikube-env.json>
```

Or export the Minikube URL and run:

```bash
export OFFERS_URL=$(minikube service offers-app-service --url)
newman run .continue/entrega1_offers.json --delay-request 100
```

**6. Restore your local Docker environment (optional):**

```bash
eval $(minikube docker-env -u)
```

### Kubernetes Manifests

| File | Purpose |
|---|-|
| `k8s/offers-app.yaml` | All resources: app Deployment, app Service, DB Deployment, DB Service |

The manifest contains four resources:

1. **offers-app Deployment** — FastAPI app with liveness/readiness probes at `/offers/ping`, resource limits (500m CPU, 256Mi memory)
2. **offers-app-service (NodePort 30003)** — External access to the app
3. **offers-db Deployment** — PostgreSQL 16 with ephemeral `emptyDir` storage, liveness/readiness probes via `pg_isready`
4. **offers-db-service (ClusterIP)** — Internal-only database access

All database credentials are passed via environment variables (no secrets hardcoded).

### Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────┐
│  Minikube Cluster (namespace: default)  │
│                                     │
│  offers-app-service (NodePort 30003) │
│         │                           │
│         ▼                           │
│  offers-app Deployment (pods)        │
│         │                           │
│         ▼                           │
│  offers-db-service (ClusterIP)       │
│         │                           │
│         ▼                           │
│  offers-db Deployment (pods)         │
│  ┌───────────────────┐               │
│  │ PostgreSQL 16     │               │
│  │ emptyDir volume   │               │
│  └───────────────────┘               │
└─────────────────────────────────────┘
```

### Environment Variables

The app receives DB credentials through environment variables:

| Variable | Value | Description |
|---|---|-|
| `DB_DRIVER` | `postgresql` | Production database driver |
| `DB_HOST` | `offers-db-service` | ClusterIP service name |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `offers_db` | Database name |
| `DB_USER` | `offers_user` | Database user |
| `DB_PASSWORD` | `offers_pass` | Database password |

### Resource Limits

| Resource | Limit | Request |
|---|---|-|
| CPU | 500m | 100m |
| Memory | 256Mi | 128Mi |

### Cleanup

```bash
kubectl delete -f k8s/offers-app.yaml
minikube stop
```

**Note:** `emptyDir` is ephemeral: data survives container restarts but is deleted when the DB pod is deleted.

## Network Policy — offers-db Isolation

A Kubernetes `NetworkPolicy` enforces that **only `offers-app` pods can connect to `offers-db` on port 5432**. All other ingress traffic to `offers-db` is denied.

#### Prerequisites — Calico CNI

Minikube's default CNI (Kindnet) does **not** enforce NetworkPolicies. You must create the cluster with Calico from the start:

```bash
minikube stop
minikube delete
minikube start --cni=calico
```

Wait until Calico pods are Ready:

```bash
kubectl get pods -n kube-system -l k8s-app=calico-node
```

All pods should show `1/1` Ready and `Running` status.

#### Deploy the NetworkPolicy

After deploying the app and database (from the repository root):

```bash
kubectl apply -f k8s/offers-app.yaml
kubectl apply -f k8s/offers-network-policy.yaml
kubectl get networkpolicy
```

Expected output:
```
NAME                          POD-SELECTOR   AGE
offers-network                  app=offers-db   <age>
```

#### Manifest

File: `k8s/offers-network-policy.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: offers-network
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: offers-db
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: offers-app
      ports:
        - protocol: TCP
          port: 5432
```

**What this policy does:**

| Rule | Effect |
|---|-|
| `podSelector: app: offers-db` | Applies to all pods with label `app=offers-db` |
| `from: podSelector: app: offers-app` | Allows ingress only from pods with label `app=offers-app` |
| `ports: 5432/TCP` | Only PostgreSQL traffic on port 5432 is allowed |
| Default deny | All other ingress traffic to `offers-db` is denied |



#### Verification — Allowed connections

Verify allowed connection (offers-app -> offers-db)

```bash
# Use a temporary pod with psql client
kubectl run -i --tty test-offers-app --rm --image postgres:16-alpine --restart=Never \
  --labels=app=offers-app -- sh -c \
  "PGPASSWORD=offers_pass psql -h offers-db-service -p 5432 -U offers_user -d offers_db -c 'SELECT 1;'"
```
Expected output:
```bash
 ?column? 
----------
        1
(1 row)
```

#### Verification — Blocked connections

Verify blocked connection from unauthorized pod

```bash
# Create a temporary pod WITHOUT the offers-app label
# This should FAIL because the NetworkPolicy only allows offers-app pods
kubectl run -i --tty test-blocked --rm --image postgres:16-alpine --restart=Never -- sh -c \
  "PGPASSWORD=offers_pass psql -h offers-db-service -p 5432 -U offers_user -d offers_db -c 'SELECT 1;'"

# Expected: Connection refused or timeout (denied by NetworkPolicy)
# If it succeeds, Calico is not properly enabled — check with: minikube addons list
```

Expected similar output:

```bash
All commands and output from this session will be recorded in container logs, including credentials and sensitive information passed through the command prompt.
If you don't see a command prompt, try pressing enter.
psql: error: connection to server at "offers-db-service" (10.103.92.125), port 5432 failed: Operation timed out
	Is the server running on that host and accepting TCP/IP connections?
Session ended, resume using 'kubectl attach test-blocked -c test-blocked -n default -i -t' command
pod "test-blocked" deleted from default namespace
pod default/test-blocked terminated (Error)
```

**Note:** In a real scenario, other applications (`users-app`, `routes-app`, `posts-app`) cannot reach `offers-db`. This policy ensures explicit cohesion between `offers-app` and `offers-db` only.

#### Cleanup

To remove the network policy:

```bash
kubectl delete -f k8s/offers-network-policy.yaml
```

To remove all resources:

```bash
kubectl delete -f k8s/offers-network-policy.yaml
kubectl delete -f k8s/offers-app.yaml
minikube stop
```

## Testing

### Unit tests

Unit tests use an in-memory SQLite database (forced at runtime in `tests/unit/conftest.py`). No PostgreSQL server is required.

```bash
cd offers_app
poetry run pytest --cov=src --cov-fail-under=70 -v
```

**Results**: 45 tests pass with 93.66% coverage.

> **Note:** `pyproject.toml`'s `[tool.pytest.ini_options].env` has no effect without the `pytest-env` plugin. `conftest.py` sets `DB_DRIVER=sqlite` explicitly at runtime instead.

### Integration testing (Postman)

Verify the API against the Postman collection with Newman:

```bash
cd ..
newman run .continue/entrega1_offers.json
```

**Results**: 72 assertions pass with 0 failures.

To validate PostgreSQL connectivity, run integration tests against a real PostgreSQL container:

1. Start a PostgreSQL container (see the Docker section above).
2. Launch the app with `DB_DRIVER=postgresql` and `DATABASE_URL=postgresql+psycopg://offers_user:offers_pass@localhost:5432/offers_db`.
3. Hit `GET /offers/ping` — it should return `pong` with HTTP 200.

## Manual Verification

### 1. Build the Docker image

```bash
cd offers_app
docker build -t offers_app:v0.0.0 .
```

Expected: `Successfully tagged offers_app:v0.0.0`

### 2. Start PostgreSQL

```bash
docker run -d --name offers-db --network offers-net \
  -e POSTGRES_DB=offers_db \
  -e POSTGRES_USER=offers_user \
  -e POSTGRES_PASSWORD=offers_pass \
  -v offers-db-volumen:/var/lib/postgresql/data \
  postgres:16-alpine
```

Expected: a container ID printed to stdout

### 3. Start the app

```bash
docker run --rm -p 8000:8000 --network offers-net \
  -e DB_HOST=offers-db \
  -e DB_NAME=offers_db \
  -e DB_USER=offers_user \
  -e DB_PASSWORD=offers_pass \
  offers_app:v0.0.0
```

### 4. Verify health endpoint

```bash
curl -s http://localhost:8000/offers/ping
```

Expected output: `pong`

### 5. Create an offer

```bash
curl -s -X POST http://localhost:8000/offers \
  -H "Content-Type: application/json" \
  -d '{"postId":"550e8400-e29b-41d4-a716-446655440000","userId":"660e8400-e29b-41d4-a716-446655440001","description":"Test offer","size":"SMALL","fragile":false,"offer":100.00}'
```

Expected: HTTP 201 with `{"id":"...","userId":"...","createdAt":"..."}`

### 6. Clean up

```bash
docker stop offers-db && docker rm offers-db
```

The container defaults to PostgreSQL, so it needs a reachable database. Against an `offers-db` container on a shared network:

```bash
docker network create offers-net

docker run -d --name offers-db --network offers-net \
  -e POSTGRES_DB=offers_db \
  -e POSTGRES_USER=offers_user \
  -e POSTGRES_PASSWORD=offers_pass \
  -v offers-db-volumen:/var/lib/postgresql/data \
  postgres:16-alpine

docker run --rm -p 8000:8000 --network offers-net \
  -e DB_HOST=offers-db \
  -e DB_NAME=offers_db \
  -e DB_USER=offers_user \
  -e DB_PASSWORD=offers_pass \
  offers_app:v0.0.0
```

Without a database, override the driver to keep the old serverless behaviour:

```bash
docker run --rm -p 8000:8000 -e DB_DRIVER=sqlite offers_app:v0.0.0
```

Hardened run (recommended when the process does not need writes or extra capabilities):

```bash
docker run --rm -p 8000:8000 \
  --read-only \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  offers_app:v0.0.0
```

Note: `--read-only` suits in-memory SQLite and a remote PostgreSQL alike, since neither writes to the container filesystem. If you need temp files on disk, drop `--read-only` or add a writable `--tmpfs`.

Health check (manual):

```bash
curl http://localhost:8000/offers/ping
```

Expected: `pong` (HTTP 200). The image also declares a `HEALTHCHECK` against the same path.

## Domain and persistence (issue #11)

- Domain model: `src/domain/models/offer.py`
- Repository port: `src/domain/ports/offer_repository_port.py`
- SQLAlchemy model/adapter: `src/adapters/database/`
- Password hashing with explicit salt: `src/adapters/security/password_hasher.py`

Call `init_db()` (from `adapters.database.connection`) before using the repository against PostgreSQL.

## Tests

Unit tests (with coverage ≥70%):

```bash
cd offers_app
poetry run pytest --cov=src --cov-fail-under=70
```

Postman collection (run the server first, then):

```bash
cd offers_app
npx newman run tests/api/offers.postman_collection.json
```

## Author

- Camilo Daza — `ca.dazab1@uniandes.edu.co`
