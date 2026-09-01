# Scores App

The Scores microservice for the Shared Suitcase delivery platform.

The project document (Entrega 2) mandates a dedicated Score (Utilidad) service
that **persists** a score value per offer: it must not be a calculate-only or
stateless component, and it must remain resilient to a missing or undefined
score for a given offer (callers treat a missing score as `score: null` rather
than as an error).

> **Status: API contract implemented.** The Score (Utilidad) domain model,
> repository port, SQLAlchemy adapter, and the full HTTP API (create/update,
> per-offer and per-id retrieval, count, reset, health check) are in place.
> Scores can be created/updated per offer and queried null-safely, so the
> orchestration layer can create/update a score (RF-004) and query a score
> (RF-005).

## Tech stack

| Concern      | Choice            |
|--------------|-------------------|
| Language     | Python 3.11       |
| Framework    | FastAPI           |
| ASGI server  | Uvicorn           |
| ORM          | SQLAlchemy 2.x    |
| DB driver    | `psycopg` (v3)    |
| Database     | PostgreSQL 16     |
| Packaging    | Poetry            |
| Tests        | pytest            |

This matches the stack used by `users_app`, `routes_app`, `posts_app`, and
`offers_app`, so the service can be maintained and deployed with the same tooling.

## Architecture

The service follows the same Clean Architecture layout as the other apps:

- `domain`: entities, ports (abstractions), and use cases (business rules).
- `adapters`: concrete implementations (database adapter).
- `entrypoints`: the API layer (routers, schemas, dependency wiring).

```
src/
├── assembly.py                  # Dependency injection wiring
├── config.py                    # Settings (env-driven)
├── errors.py                    # Custom exceptions
├── adapters/
│   └── database/
│       ├── connection.py        # Engine, session factory, connection probe
│       ├── models.py            # ORM models (ScoreModel, declarative Base)
│       └── score_repository_adapter.py  # SQLAlchemy ScoreRepository adapter
├── domain/
│   ├── models/
│   │   └── score.py             # Score (Utilidad) domain model
│   ├── ports/
│   │   └── score_repository_port.py   # Persistence contract (port)
│   └── use_cases/
│       ├── base_use_case.py               # Use case contract
│       ├── upsert_score_use_case.py       # Create/update (RF-004)
│       ├── get_score_by_offer_use_case.py # Null-safe query (RF-005)
│       ├── get_score_use_case.py          # Query by id
│       ├── count_scores_use_case.py       # Count
│       └── reset_scores_use_case.py       # Delete all
└── entrypoints/
    └── api/
        ├── main.py              # FastAPI app + lifespan
        ├── deps.py              # Dependency providers (session, repository, use cases)
        └── routers/
            └── score_router.py  # Score API endpoints
```

## Data model

The `Score` (Utilidad) entity is persisted so its value can be retrieved later
even if it changes over time. A missing score for an offer is represented by
the **absence of a row**, which callers read as `score: null`.

| Column      | Type    | Notes                                |
|-------------|---------|--------------------------------------|
| `id`        | string  | Primary key (UUID)                   |
| `offerId`   | string  | The offer this score belongs to (unique, indexed) |
| `value`     | float   | The computed utility value           |
| `createdAt` | datetime| Creation timestamp (timezone-aware UTC) |
| `updatedAt` | datetime| Last update timestamp (timezone-aware UTC) |

### Schema design (team decision)

One **current score row per offer**: `offerId` is unique, so each offer has at
most one persisted score. Updating a score replaces the existing row's value
in place (no history table). This keeps a single source of truth per offer and
makes `get_by_offer_id` a simple, null-safe lookup.

### Repository API

The persistence layer exposes `ScoreRepositoryPort`
(`src/domain/ports/score_repository_port.py`), implemented by
`SQLAlchemyScoreRepositoryAdapter`
(`src/adapters/database/score_repository_adapter.py`) and wired through
`get_score_repository` in `src/entrypoints/api/deps.py`:

| Method              | Description                                                        |
|---------------------|--------------------------------------------------------------------|
| `upsert(score)`     | Creates the score for an offer, or updates its value in place       |
| `get_by_id(score_id)` | Returns the `Score` by its id, or `None` when absent               |
| `get_by_offer_id(offer_id)` | Returns the `Score`, or `None` when the offer has no score (never raises) |
| `delete(offer_id)`  | Deletes the score for an offer; returns `False` when absent         |
| `count()`           | Number of persisted scores                                          |
| `delete_all()`      | Removes every persisted score; returns the number of rows removed   |

### Score calculation formula (Entrega 1 glossary)

The persisted `value` is the **utilidad** computed by the RF-004 orchestrator
(reuse recommended, pending tutor confirmation):

```text
utilidad = offer amount - (bag occupancy % x route bagCost)
```

with bag occupancy by package size: `LARGE = 100%`, `MEDIUM = 50%`,
`SMALL = 25%`. This service only stores the resulting number; it does not
perform the calculation itself.

## Database and environment

Database connection parameters are read **only** from environment variables
(never hardcoded). Defaults target the single shared PostgreSQL instance used
in Entrega 2, with per-app schema isolation.

| Variable         | Description                                  | Default     |
|------------------|----------------------------------------------|-------------|
| `APP_NAME`       | Application name                             | `scores_app`|
| `LOG_LEVEL`      | Logging level                                | `DEBUG`     |
| `DB_DRIVER`      | `postgresql` (default) or `sqlite` (local)   | `postgresql`|
| `DB_HOST`        | Database host                                | `localhost` |
| `DB_PORT`        | Database port                                | `5432`      |
| `DB_NAME`        | Database name                                | `scores-db` |
| `DB_USER`        | Database user                                | `scores_user`|
| `DB_PASSWORD`    | Database password                            | `scores_password`   |
| `DATABASE_URL`   | Full SQLAlchemy URL; overrides all `DB_*`    | _(unset)_   |
| `SQLITE_URL`     | SQLite URL when `DB_DRIVER=sqlite`           | `sqlite://` |

## Endpoints

| Method | Path            | Description                                                            | Success | Errors |
|--------|-----------------|------------------------------------------------------------------------|---------|--------|
| `POST` | `/scores`       | Create/update the score for an offer (idempotent by `offerId`)          | `201` (created) / `200` (updated) | `400` (missing/malformed `offerId` or `score`) |
| `GET`  | `/scores?offerId={offerId}` | Query the score for an offer (null-safe)                  | `200` | `400` (missing/non-UUID `offerId`) |
| `GET`  | `/scores/{id}`  | Retrieve a score by its id                                             | `200` | `400` (non-UUID id), `404` (not found) |
| `GET`  | `/scores/count` | Number of persisted scores                                             | `200` | — |
| `GET`  | `/scores/ping`  | Health check                                                           | `200` | — |
| `POST` | `/scores/reset` | Delete all stored scores                                               | `200` | — |

### Request / response shapes

`POST /scores` request body:

```json
{ "offerId": "550e8400-e29b-41d4-a716-446655440000", "score": 150.5 }
```

- First write for an offer → `201` with `{ "id", "offerId", "score", "createdAt" }`.
- Subsequent write for the same offer → `200` with `{ "id", "offerId", "score", "updatedAt" }` (same `id`, updated value).

`GET /scores?offerId={offerId}`:

- Score exists → `200` with `{ "id", "offerId", "score", "createdAt" }`.
- No score yet (expected case, **not** an error) → `200` with `{ "offerId", "score": null }`.

`GET /scores/{id}` → `200` with `{ "id", "offerId", "score", "createdAt", "updatedAt" }`.

`GET /scores/count` → `200` with `{ "count": <int> }`.

`POST /scores/reset` → `200` with `{ "msg": "All data was deleted" }`.

All `400`/`404` error responses have an empty body. The service is
internal-only (ClusterIP); no external exposure is required.

## Getting started

### Prerequisites

- Python 3.11
- [Poetry](https://python-poetry.org/docs/#installation)

### Install dependencies

```bash
cd scores_app
poetry install
```

### Run the API locally (SQLite, no external database)

```bash
DB_DRIVER=sqlite PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

### Run against PostgreSQL

**Step 1 - Start a local PostgreSQL instance** (skip if you already have one
running on port 5432 with the matching database/user):

```bash
  docker run -d --name scores-db -p 5432:5432 \
  -e POSTGRES_DB=scores_db \
  -e POSTGRES_USER=scores_user \
  -e POSTGRES_PASSWORD=scores_password \
  postgres:16-alpine
```

Wait a few seconds for the container to initialise, then verify:

```bash
docker exec scores_db pg_isready
```

**Step 2 - Start the application** (from inside `scores_app/`):

```bash
PYTHONPATH=$(pwd)/src \
  DB_HOST=localhost DB_PORT=5432 \
  DB_NAME=scores_db DB_USER=scores_user DB_PASSWORD=scores_password \
  poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
```

> **Note:** The application's lifespan hook retries the database connection
> up to 30 times (2 s interval). If Postgres is not ready yet, the app will
> keep retrying until it succeeds or the retries are exhausted.

### Health check

```bash
curl -i http://localhost:8000/scores/ping
```

Expected: `HTTP/1.1 200 OK` with a plain-text body `pong`.

## Running tests

Unit tests run against an in-memory SQLite database (see `pyproject.toml`
`pytest-env`), so no external database is required.

```bash
poetry run pytest
```

To capture coverage:

```bash
poetry run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing
```

**Results**: 41 tests pass with 93.68% coverage (gate: `--cov-fail-under=70`).

### Integration tests (real database, optional)

The integration suite in `tests/integration/` runs the repository against the
engine of your choice. By default it uses in-process SQLite; to run it against
a real PostgreSQL instance, set `SCORES_INTEGRATION_DATABASE_URL`:

```bash
SCORES_INTEGRATION_DATABASE_URL=postgresql+psycopg://scores_user:***@localhost:5432/scores_db \
  poetry run pytest tests/integration -v
```

## Docker

A multi-stage image is provided that builds with Poetry and ships a lean
runtime with a non-root user. The image name/tag matches `config.yaml`'s
`scores_app` entry: `image_name: scores-app`, `image_tag: v0.0.0`
(i.e. `scores-app:v0.0.0`), ready for ECR publication.

```bash
docker build -t scores-app:v0.0.0 . # Create the scores-app image
docker network create scores-net # Create the network for scores containers communication

# Run and create container scores-db (PostgreSQL) on the network scores-net
docker run -d --name scores-db --network scores-net -p 5432:5432 \
  -e POSTGRES_DB=scores_db \
  -e POSTGRES_USER=scores_user \
  -e POSTGRES_PASSWORD=scores_password \
  postgres:16-alpine

# Run and create container scores_app on the network scores-net with db = scores-db on port 5432
docker run --rm -p 8000:8000 --network scores-net \
  -e DB_HOST=scores-db \
  -e DB_PORT=5432 \
  -e DB_NAME=scores_db \
  -e DB_USER=scores_user \
  -e DB_PASSWORD=scores_password \
  scores-app:v0.0.0
```

### Image name and ECR readiness

The image name/tag must match the `scores_app` entry in `config.yaml`:

| `config.yaml` field | Value       |
|---------------------|-------------|
| `image_name`        | `scores-app`|
| `image_tag`         | `v0.0.0`    |

So the image is built and published as `scores-app:v0.0.0`. The CI deploy
pipeline (`ci_entrega2_deploy.yml`) builds every app listed under `apps:` in
`config.yaml` and pushes it to ECR before applying the `k8s/` manifests, so
no further change is needed to make this image publishable:

```bash
# Build (from scores_app/)
docker build -t scores-app:v0.0.0 .

# Optional: tag for the ECR repository and push (done by the pipeline)
docker tag scores-app:v0.0.0 <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/scores-app:v0.0.0
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/scores-app:v0.0.0
```

## Manual Verification

Follow these steps to verify the API end-to-end against a real PostgreSQL
container. All commands were executed successfully on this setup.

### 1. Build the Docker image

```bash
cd scores_app
docker build -t scores-app:v0.0.0 .
```

Expected: `Successfully tagged scores-app:v0.0.0`. The name/tag matches
`config.yaml`'s `scores_app` entry (`image_name: scores-app`,
`image_tag: v0.0.0`).

### 2. Create the network and start PostgreSQL

```bash
docker network create scores-net

docker run -d --name scores-db --network scores-net \
  -e POSTGRES_DB=scores_db \
  -e POSTGRES_USER=scores_user \
  -e POSTGRES_PASSWORD=scores_password \
  postgres:16-alpine
```

Expected: a container ID printed to stdout.

> **Note:** Do not reuse a named volume or an existing cluster for
> `scores-db`: `POSTGRES_PASSWORD` is only applied at first initialization.
> If the container does not connect, remove both containers and the image and
> recreate everything fresh:
> `docker rm -f scores-db && docker rmi scores-app:v0.0.0`.

### 3. Start the app

```bash
docker run --rm -p 8000:8000 --network scores-net \
  -e DB_HOST=scores-db \
  -e DB_NAME=scores_db \
  -e DB_USER=scores_user \
  -e DB_PASSWORD=scores_password \
  scores-app:v0.0.0
```

Expected logs:

```text
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 4. Verify the health endpoint

```bash
curl -s http://localhost:8000/scores/ping
```

Expected output: `pong` (HTTP 200).

### 5. Verify the `scores` table was created in PostgreSQL

```bash
docker exec scores-db psql -U scores_user -d scores_db -c "\dt"
```

Expected output includes:

```text
           List of relations
 Schema |  Name   | Type |    Owner
--------+---------+------+--------------
 public | scores  | table | scores_user
```

### 6. Verify the API endpoints (create, update, null-safe query, errors)

```bash
# 6a. Create a score for an offer → 201 with id, offerId, score, createdAt
curl -s -w " [%{http_code}]\n" -X POST http://localhost:8000/scores \
  -H "Content-Type: application/json" \
  -d '{"offerId": "550e8400-e29b-41d4-a716-446655440000", "score": 150.5}'

# 6b. Update the same offer over time → 200 with the same id and updatedAt
curl -s -w " [%{http_code}]\n" -X POST http://localhost:8000/scores \
  -H "Content-Type: application/json" \
  -d '{"offerId": "550e8400-e29b-41d4-a716-446655440000", "score": 999.25}'

# 6c. Query the score for the offer → 200 with id, offerId, score, createdAt
curl -s -w " [%{http_code}]\n" \
  "http://localhost:8000/scores?offerId=550e8400-e29b-41d4-a716-446655440000"

# 6d. Query an offer with no score → 200 with {"offerId": ..., "score": null}
curl -s -w " [%{http_code}]\n" \
  "http://localhost:8000/scores?offerId=550e8400-e29b-41d4-a716-446655440001"

# 6e. Missing offerId → 400 (empty body)
curl -s -w " [%{http_code}]\n" "http://localhost:8000/scores"

# 6f. Malformed offerId → 400 (empty body)
curl -s -w " [%{http_code}]\n" "http://localhost:8000/scores?offerId=not-a-uuid"

# 6g. Retrieve by id (use the id from 6a) → 200 with all five fields
curl -s -w " [%{http_code}]\n" \
  "http://localhost:8000/scores/<id-from-6a>"

# 6h. Malformed id → 400; unknown id → 404 (both empty body)
curl -s -w " [%{http_code}]\n" "http://localhost:8000/scores/not-a-uuid"
curl -s -w " [%{http_code}]\n" \
  "http://localhost:8000/scores/550e8400-e29b-41d4-a716-446655440009"

# 6i. Count → 200 with {"count": 1}
curl -s -w " [%{http_code}]\n" "http://localhost:8000/scores/count"

# 6j. Reset → 200 with {"msg": "All data was deleted"}
curl -s -w " [%{http_code}]\n" -X POST "http://localhost:8000/scores/reset"

# 6k. Missing/malformed POST fields → 400 (empty body)
curl -s -w " [%{http_code}]\n" -X POST http://localhost:8000/scores \
  -H "Content-Type: application/json" -d '{"score": 10}'
curl -s -w " [%{http_code}]\n" -X POST http://localhost:8000/scores \
  -H "Content-Type: application/json" -d '{"offerId": "550e8400-e29b-41d4-a716-446655440000"}'
curl -s -w " [%{http_code}]\n" -X POST http://localhost:8000/scores \
  -H "Content-Type: application/json" \
  -d '{"offerId": "550e8400-e29b-41d4-a716-446655440000", "score": "abc"}'
```

Expected: `6a` returns `201`, `6b` returns `200` with the same `id`, `6c`
returns the updated score, `6d` returns `200` with `score: null` (not 404),
`6e`/`6f`/`6h`/`6k` return `400`/`404` with an empty body, `6i` returns
`{"count": 1}`, and `6j` returns the reset message.

### 7. Clean up

```bash
docker stop scores-db && docker rm scores-db
docker network rm scores-net
```

## Project configuration

| File               | Purpose                                    |
|--------------------|--------------------------------------------|
| `pyproject.toml`   | Dependencies and tool configuration        |
| `Dockerfile`       | Multi-stage image build                    |
| `.dockerignore`    | Excludes local artifacts from the image    |

## Linters and formatters

Configured in `pyproject.toml`: `black` (formatting), `ruff` (linting,
Google pydocstyle convention), `isort` (import sorting), `bandit`
(security), and `pydoclint` (docstring correctness).
