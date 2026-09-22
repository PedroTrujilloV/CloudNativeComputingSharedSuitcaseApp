# Routes App (Trayectos)

Routes microservice for the Shared Suitcase delivery platform. It exposes the Routes REST API and owns its data store.

## Requirements

- Python 3.11
- Poetry 2.1.1
- PostgreSQL 16+ (production) or SQLite (local development)

## Persistence

### Production

Routes service uses **PostgreSQL** as its default persistence driver. The deployment
architecture provisions a separate `routes-db` container (PostgreSQL 16).

### Local Development

For local development without PostgreSQL, set `DB_DRIVER=sqlite` to use SQLite:

```bash
DB_DRIVER=sqlite PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

## Project structure

```text
.
├── src/
│   ├── adapters/database/   # SQLAlchemy connection helpers
│   ├── entrypoints/api/     # FastAPI application and routers
│   ├── assembly.py          # Dependency injection wiring (TBD)
│   ├── config.py            # Environment-based settings
│   └── errors.py            # Custom exceptions
├── tests/unit/              # Unit tests (TBD)
├── pyproject.toml
└── README.md
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application name | `routes_app` |
| `LOG_LEVEL` | Log level | `DEBUG` |
| `DB_DRIVER` | `postgresql` (production) or `sqlite` (local) | `postgresql` |
| `DATABASE_URL` | Full SQLAlchemy URL (overrides driver) | _(unset)_ |
| `SQLITE_URL` | SQLite URL when `DB_DRIVER=sqlite` | `sqlite://` (in-memory) |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `routes_db` |
| `DB_USER` | Database user | `routes_user` |
| `DB_PASSWORD` | Database password | _(empty)_ |

No secrets are hardcoded in source. Provide credentials through environment variables.

**PostgreSQL (production default):** the app connects to a PostgreSQL database using the
`postgresql+psycopg` driver. All database credentials are provided via environment
variables.

**SQLite (local development fallback):** Set `DB_DRIVER=sqlite` to use an in-memory
SQLite database. Tables are created on startup via `init_db()`. No Postgres required for
`GET /routes/ping` smoke tests. Data lasts only while the process is running.

**Overriding all driver settings:** Set `DATABASE_URL` to a full SQLAlchemy URL to bypass
all driver variables:

```bash
DATABASE_URL=postgresql://user:pass@db_host:5432/routes_db
```

## Run with Docker Compose

Create a temporary docker-compose.yml for manual verification:

```yaml
services:
  routes-app:
    image: routes_app:v0.0.0
    build: .
    ports:
      - "8000:8000"
    environment:
      DB_DRIVER: postgresql
      DB_HOST: routes-db
      DB_PORT: "5432"
      DB_NAME: routes_db
      DB_USER: routes_user
      DB_PASSWORD: routes_password
    depends_on:
      routes-db:
        condition: service_healthy

  routes-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: routes_db
      POSTGRES_USER: routes_user
      POSTGRES_PASSWORD: routes_password
```

```bash
cd routes_app
docker compose up -d
curl http://localhost:8000/routes/ping
docker compose down
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
- [x] Routes app is reachable externally via its NodePort service
- [x] PostgreSQL DB is reachable only internally via ClusterIP
- [x] `ci_evaluador_entrega1_k8s.yml` passes unmodified

### Deploy to Minikube

**1. Build the Docker image in minikube's daemon:**

```bash
minikube start
eval $(minikube docker-env)
cd routes_app
docker build -t routes_app:v0.0.0 .
```

**2. Apply the Kubernetes manifests (from project root):**

> **Note:** All k8s manifests live in the project root `k8s/` directory. Run all `kubectl apply` commands from there.

```bash
kubectl apply -f k8s/routes-app.yaml
kubectl get pods -w  # wait for both pods to show Running
```

**3. Access the app:**

```bash
minikube service routes-app-service --url
curl $(minikube service routes-app-service --url)/routes/ping
# → pong
```

**4. Restore your local Docker environment (optional):**

```bash
eval $(minikube docker-env -u)
```

### Kubernetes Manifests

| File | Purpose |
|---|-|
| `k8s/routes-app.yaml` | All resources: app Deployment, app Service, DB Deployment, DB Service |
| `k8s/routes-network-policy.yaml` | Network isolation rules: only routes-app can reach routes-db |

The manifest contains four resources:

1. **routes-app Deployment**: FastAPI app with liveness/readiness probes at `/routes/ping`, resource limits (500m CPU, 256Mi memory)
2. **routes-app-service (NodePort 30002)**: External access to the app
3. **routes-db Deployment**: PostgreSQL 16 with ephemeral `emptyDir` storage, liveness/readiness probes via `pg_isready`
4. **routes-db-service (ClusterIP)**: Internal-only database access

All database credentials are passed via environment variables (no secrets hardcoded).

## Network Policy: routes-db Isolation

A Kubernetes `NetworkPolicy` enforces that **only `routes-app` pods can connect to `routes-db` on port 5432**. All other ingress traffic to `routes-db` is denied.

### Manifest

File: `k8s/routes-network-policy.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: routes-network
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: routes-db
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: routes-app
      ports:
        - protocol: TCP
          port: 5432
```

**Key points:**
- `podSelector` targets pods labeled `app: routes-db`
- `policyTypes: [Ingress]` means only the rules listed below apply; anything not matched is denied
- `from.podSelector` allows traffic only from pods labeled `app: routes-app`
- The `ports` block restricts to TCP port 5432 (PostgreSQL)
- Any other application's pods (users-app, posts-app, offers-app) **cannot** connect to routes-db

### Deploy the Network Policy

**⚠️ Prerequisite: NetworkPolicies require a CNI plugin (Calico) to be enforced.**

The default Minikube `docker` driver does **NOT** enforce NetworkPolicies. You MUST enable Calico before deploying this policy:

The official Calico manifest:
```bash
https://raw.githubusercontent.com/projectcalico/calico/v3.32.0/manifests/calico.yaml
```


#### Option A: Use Calico CNI directly (recommended)

```bash
minikube stop
minikube delete
minikube start --cni=calico
```

#### Option B: Enable Calico addon 

```bash
minikube stop
minikube delete
minikube start
minikube addons enable calico
minikube addons list  # verify calico shows [enabled]
```

#### Complete deployment with Calico

```bash
# 1. Ensure Calico is enabled
minikube addons enable calico

# 2. Set Docker environment and build image
eval $(minikube docker-env)
cd routes_app
docker build -t routes_app:v0.0.0 .

# 3. Deploy app, DB, and network policy
cd ../..  # project root
kubectl apply -f k8s/routes-app.yaml
kubectl apply -f k8s/routes-network-policy.yaml

# 4. Verify resources
kubectl get pods -w  # wait for routes-app and routes-db to be Running
kubectl get networkpolicy  # verify routes-network exists
```

### Manual Verification on Minikube

#### 1. Verify allowed connection (routes-app → routes-db)

```bash
# Use a temporary pod with psql client
kubectl run -i --tty test-allowed --rm --image postgres:16-alpine --restart=Never -- sh -c \
  "PGPASSWORD=routes_pass psql -h routes-db-service -p 5432 -U routes_user -d routes_db -c 'SELECT 1;'" 2>&1

# Expected output:
#  ?column?
# ----------
#         1
```

#### 2. Verify blocked connection from unauthorized pod

```bash
# Create a temporary pod WITHOUT the routes-app label
# This should FAIL because the NetworkPolicy only allows routes-app pods
kubectl run -i --tty test-blocked --rm --image postgres:16-alpine --restart=Never -- sh -c \
  "PGPASSWORD=routes_pass psql -h routes-db-service -p 5432 -U routes_user -d routes_db -c 'SELECT 1;'" 2>&1

# Expected: Connection refused or timeout (denied by NetworkPolicy)
# If it succeeds, Calico is not properly enabled — check with: minikube addons list
```

#### 3. Verify routes-app can still access routes-db on port 5432

```bash
kubectl run -i --tty test-routes-app --rm --image postgres:16-alpine --restart=Never \
  --labels=app=routes-app -- sh -c \
  "PGPASSWORD=routes_pass psql -h routes-db-service -p 5432 -U routes_user -d routes_db -c 'SELECT 1;'" 2>&1

# Expected: Query executes successfully (returns 1)
```

#### 4. Cleanup

```bash
kubectl delete -f k8s/routes-network-policy.yaml
kubectl delete -f k8s/routes-app.yaml
eval $(minikube docker-env -u)
minikube addons disable calico
minikube stop
```
kubectl delete -f k8s/routes-network-policy.yaml
kubectl delete -f k8s/routes-app.yaml
eval $(minikube docker-env -u)
minikube stop
```

## Install dependencies

```bash
cd routes_app
poetry install
```

If `poetry.lock` is missing, run `poetry lock` first.

## Run locally

### PostgreSQL (default)

```bash
cd routes_app
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

### SQLite (local development)

```bash
cd routes_app
DB_DRIVER=sqlite PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

API base URL: `http://localhost:8000`

## Docker

Image name/tag must match `config.yaml` (`routes_app` / `v0.0.0`).

### PostgreSQL (production)

```bash
cd routes_app
docker build -t routes_app:v0.0.0 .
docker run --rm -p 8000:8000 \
  -e DB_DRIVER=postgresql \
  -e DB_HOST=routes-db \
  -e DB_PORT=5432 \
  -e DB_NAME=routes_db \
  -e DB_USER=routes_user \
  -e DB_PASSWORD=routes_password \
  routes_app:v0.0.0
```

### SQLite (local development)

```bash
cd routes_app
docker build -t routes_app:v0.0.0 .
docker run --rm -p 8000:8000 -e DB_DRIVER=sqlite routes_app:v0.0.0
```

### Docker Compose (development)

```bash
cd routes_app
docker compose up -d
```

Health check (manual):

```bash
curl http://localhost:8000/routes/ping
```

Expected: `pong` (HTTP 200). The image also declares a `HEALTHCHECK` against the same path.

## Current endpoints

- `GET /routes/ping` → `pong`
- `POST /routes` → Create a new route (see API documentation below)

### API Documentation: POST /routes

Creates a new route (trayecto) for a flight journey.

#### Request

**Method:** `POST`
**Route:** `/routes`
**Content-Type:** `application/json`

**Request Body:**
```json
{
  "flightId": "flight code",
  "sourceAirportCode": "origin airport code",
  "sourceCountry": "origin country name",
  "destinyAirportCode": "destination airport code",
  "destinyCountry": "destination country name",
  "bagCost": 126,
  "plannedStartDate": "2026-08-15T03:01:15.103Z",
  "plannedEndDate": "2026-08-23T03:01:15.103Z"
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flightId` | string | Yes | Flight identifier (for example, AA001 or 937) |
| `sourceAirportCode` | string | Yes | Origin airport IATA code (3 uppercase letters) |
| `sourceCountry` | string | Yes | Country of origin (for example, Colombia) |
| `destinyAirportCode` | string | Yes | Destination airport IATA code (3 uppercase letters) |
| `destinyCountry` | string | Yes | Destination country name (for example, United Kingdom) |
| `bagCost` | integer | Yes | Cost of shipping a suitcase (non-negative integer) |
| `plannedStartDate` | string (ISO datetime) | Yes | Journey start date in ISO format (UTC timezone) |
| `plannedEndDate` | string (ISO datetime) | Yes | Journey end date in ISO format (UTC timezone) |

**Date Format:** `yyyy-mm-ddTHH:MM:SS+00:00` (ISO 8601 with UTC timezone offset). Both `+00:00` and `Z` are accepted.

#### Response Codes

| Code | Description | Response Body |
|------|-------------|------|
| `201` | Route created successfully | `{"id": "<route-id>", "createdAt": "<ISO-UTC-datetime>"}` |
| `400` | Missing or invalid required field | `{"msg": "<validation-error-details>"}` |
| `412` | Duplicate `flightId` | `{"msg": "Route with this flightId already exists"}` |
| `412` | Invalid dates (past or end ≤ start) | `{"msg": "Las fechas del trayecto no son válidas"}` |

**Validation precedence:**
1. Pydantic validates all required fields; invalid or missing fields return **400**.
2. Duplicate `flightId` check returns **412** with `{"msg": "..."}` (not nested under `detail`).
3. Date validity (both in future, end > start) returns **412** with `{"msg": "Las fechas del trayecto no son válidas"}` (not nested under `detail`).

#### Validation Rules

1. **Required fields:** All 8 fields must be present.
2. **flightId:** Non-empty string; must be unique across all routes.
3. **Airport codes:** Exactly 3 uppercase letters (for example, BOG, JFK, LGW).
4. **bagCost:** Non-negative integer (≥ 0).
5. **Date handling:**
   - Accepts ISO 8601 UTC datetimes with `+00:00` or `Z` suffix.
   - Both `plannedStartDate` and `plannedEndDate` must be in the **future**.
   - `plannedEndDate` must be strictly **after** `plannedStartDate`.
   - Past dates or end ≤ start return **412** with `{"detail": {"msg": "Las fechas del trayecto no son válidas"}}`.
6. **Response `createdAt`** is ISO 8601 UTC (for example, `2026-08-15T03:01:15.103+00:00`).

### Coverage

The suite currently reports **90% coverage across 115 tests**, against the 70%
minimum required for the delivery (configured via `--cov-fail-under=70` in
`pyproject.toml`). The run fails if coverage drops below that gate.

> **Note:** The coverage gate was previously only enforced through `makefile` commands.
> `addopts` in `pyproject.toml` has been added so that plain `pytest` also respects the gate.

### Endpoint coverage

Every endpoint is exercised for its happy path and for each error path defined in
the API contract.

| Endpoint | Happy path | Error paths | Tests |
|---|---|---|---|
| `GET /routes/ping` | `200` | — | 1 |
| `POST /routes` | `201` | `400` missing field · `412` duplicate flightId, invalid dates | 7 |
| `GET /routes` | `200` | `200` `[]` for non-existent `flightId` filter (contract-defined) | 4 |
| `GET /routes/{id}` | `200` | `400` invalid UUID · `404` unknown id | 4 |
| `DELETE /routes/{id}` | `200` | `400` invalid UUID · `404` unknown id | 4 |
| `GET /routes/count` | `200` | — | 3 |
| `POST /routes/reset` | `200` | — | 3 |

The remaining 90 tests cover the persistence adapter (`route_repository_adapter.py`,
93% coverage), domain model (`route.py`, 90% coverage), domain validation services
(`route_validation.py`, 97% coverage), environment settings, error handling, and
connection helpers.

## Domain and persistence

- Domain model: ✅ Implemented
- Repository port: ✅ Implemented
- SQLAlchemy model/adapter: ✅ Implemented

`init_db()` runs automatically on application startup (`main.py` lifespan).

## Tests

```bash
cd routes_app
poetry run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing
```

From the repository root (same command used by the makefile):

```bash
make unittest DIR=routes_app
```

## Manual verification

Start the server (Unix):

```bash
cd routes_app
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

### 1. Health check

```bash
curl http://127.0.0.1:8000/routes/ping
# → pong
```

### 2. Valid route creation → 201

```bash
curl -X POST http://127.0.0.1:8000/routes \
  -H 'Content-Type: application/json' \
  -d '{
    "flightId": "872",
    "sourceAirportCode": "BOG",
    "sourceCountry": "Colombia",
    "destinyAirportCode": "LGW",
    "destinyCountry": "United Kingdom",
    "bagCost": 521,
    "plannedStartDate": "2026-08-16T02:54:50.294+00:00",
    "plannedEndDate": "2026-08-24T02:54:50.294+00:00"
  }'
```
Expected response: `201` with `{"id": "...", "createdAt": "..."}` (ISO UTC).

### 3. Missing required field → 400

```bash
curl -X POST http://127.0.0.1:8000/routes \
  -H 'Content-Type: application/json' \
  -d '{"flightId": "872"}'
```
Expected response: `400`.

### 4. Duplicate flightId → 412

Send the same request twice with the same `flightId`.
The second request should return `412`.

### 5. Invalid dates → 412

```bash
curl -X POST http://127.0.0.1:8000/routes \
  -H 'Content-Type: application/json' \
  -d '{
    "flightId": "999",
    "sourceAirportCode": "BOG",
    "sourceCountry": "Colombia",
    "destinyAirportCode": "LGW",
    "destinyCountry": "United Kingdom",
    "bagCost": 100,
    "plannedStartDate": "2020-01-01T00:00:00+00:00",
    "plannedEndDate": "2020-01-05T00:00:00+00:00"
  }'
```
Expected response: `412` with `{"detail": {"msg": "Las fechas del trayecto no son válidas"}}`.

### 6. Get all routes → 200

```bash
curl http://127.0.0.1:8000/routes
```
Expected response: `200` with an array of route objects.

### 7. Get routes by flightId → 200

```bash
curl 'http://127.0.0.1:8000/routes?flight=872'
```
Expected response: `200` with an array of routes matching the flightId.

### 8. Get routes by non-existent flightId → 200

```bash
curl 'http://127.0.0.1:8000/routes?flight=NONEXISTENT'
```
Expected response: `200` with `[]` (empty array).

### 9. Get route by ID → 200

```bash
curl http://127.0.0.1:8000/routes/550e8400-e29b-41d4-a716-446655440000
```
Expected response: `200` with the route object matching the UUID.

### 10. Get route by invalid UUID → 400

```bash
curl http://127.0.0.1:8000/routes/not-a-uuid
```
Expected response: `400` with an empty body.

### 11. Get route by non-existent ID → 404

```bash
curl http://127.0.0.1:8000/routes/00000000-0000-0000-0000-000000000000
```
Expected response: `404` with an empty body.

---

## DELETE /routes/{{id}}: Delete a Route

Deletes a route by its UUID.

### 12. Delete route by valid UUID → 200

```bash
curl -X DELETE http://127.0.0.1:8000/routes/550e8400-e29b-41d4-a716-446655440000
```
Expected response: `200` with `{"msg": "el trayecto fue eliminado"}`.

### 13. Delete route by invalid UUID → 400

```bash
curl -X DELETE http://127.0.0.1:8000/routes/not-a-uuid
```
Expected response: `400` with an empty body.

### 14. Delete route by non-existent ID → 404

```bash
curl -X DELETE http://127.0.0.1:8000/routes/00000000-0000-0000-0000-000000000000
```
Expected response: `404` with an empty body.

### 15. Delete route twice (idempotency check) → 404 on second call

```bash
curl -X DELETE http://127.0.0.1:8000/routes/550e8400-e29b-41d4-a716-446655440000
curl -X DELETE http://127.0.0.1:8000/routes/550e8400-e29b-41d4-a716-446655440000
```
Expected response: First call → `200` with `{"msg": "el trayecto fue eliminado"}`. Second call → `404` with an empty body.

---

## GET /routes/count: Count Routes

Returns the total number of routes stored in the database.

### 16. Count routes with empty database → 200

```bash
curl http://127.0.0.1:8000/routes/count
```
Expected response: `200` with `{"count": 0}`.

### 17. Count routes with existing routes → 200

```bash
curl http://127.0.0.1:8000/routes/count
```
Expected response: `200` with `{"count": <number>}` where `<number>` is the actual count of routes.

### 18. Count routes after deletion → 200 with decremented count

```bash
curl http://127.0.0.1:8000/routes/count
```
Expected response: `200` with `{"count": <number>}` where `<number>` reflects routes after deletion.

---

## POST /routes/reset: Reset All Routes

Deletes all route data from the database.

### 19. Reset routes on empty database → 200

```bash
curl -X POST http://127.0.0.1:8000/routes/reset
```
Expected response: `200` with `{"msg": "Todos los datos fueron eliminados"}`.

### 20. Reset routes with existing data → 200

```bash
curl -X POST http://127.0.0.1:8000/routes/reset
```
Expected response: `200` with `{"msg": "Todos los datos fueron eliminados"}`. Subsequent `GET /routes/count` → `{"count": 0}`.

### 21. Reset routes twice (idempotency check) → 200 both times

```bash
curl -X POST http://127.0.0.1:8000/routes/reset
curl -X POST http://127.0.0.1:8000/routes/reset
```
Expected response: Both calls → `200` with `{"msg": "Todos los datos fueron eliminados"}`.

## Author

- Pedro Trujillo — `pe.trujillo@uniandes.edu.co`
