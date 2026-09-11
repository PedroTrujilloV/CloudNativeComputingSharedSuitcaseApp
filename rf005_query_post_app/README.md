# RF-005 Query Post Orchestrator

The RF-005 orchestrator for the Shared Suitcase delivery platform: it exposes
the client-facing `GET /rf005/posts/{id}` endpoint that queries a post by
validating a bearer token against the Users service and verifying that the
requesting user is the owner of the post via the Posts service.

> **Status:** complete. The authentication gate, authorization gate, full data aggregation (route + offers + scores via API Composition), and the RF-005 score resilience behavior (a missing score or a down Score service degrades to `"score": null` per offer instead of failing the request) are implemented. All 57 tests passing (53 unit + 4 integration).

## Tech stack

| Concern      | Choice            |
|--------------|-------------------|
| Language     | Python 3.11       |
| Framework    | FastAPI           |
| ASGI server  | Uvicorn           |
| HTTP client  | `httpx`           |
| Packaging    | Poetry            |
| Tests        | pytest            |

The orchestrator is **stateless**: it owns no data and has no database. It
only talks to other services over HTTP (existing public APIs; no direct DB
access).

## Architecture

The service follows the same Clean Architecture layout as the other apps:

- `domain`: models, ports (abstractions), and use cases (business rules).
- `adapters`: concrete implementations (outbound HTTP clients).
- `entrypoints`: the API layer (router, schemas wiring, dependency injection).

```
src/
├── assembly.py                          # Dependency injection wiring
├── config.py                            # Settings (env-driven)
├── errors.py                            # Custom exceptions (status + msg)
├── adapters/
│   └── http/
│       ├── users_service_client.py      # Users-service token validation client
│       ├── posts_service_client.py      # Posts-service client (get post by id)
│       ├── routes_service_client.py     # Routes-service client (get route by id)
│       ├── offers_service_client.py     # Offers-service client (list offers by post)
│       └── scores_service_client.py     # Score-service client (get score per offer, null-safe)
├── domain/
│   ├── models/
│   │   ├── __init__.py                  # PostInfo (frozen dataclass)
│   │   ├── offer.py                     # OfferInfo (offer + nullable score)
│   │   ├── route.py                     # RouteInfo + Point
│   │   ├── score.py                     # ScoreInfo
│   │   └── response.py                  # QueryPostResponse (shaped 200 body)
│   ├── ports/
│   │   ├── posts_port.py                # Posts contract (get_post)
│   │   ├── user_validation_port.py      # Token validation contract (port)
│   │   ├── routes_port.py               # Routes contract (get_route)
│   │   ├── offers_port.py               # Offers contract (get_offers)
│   │   └── scores_port.py               # Score contract (get_score, never raises)
│   └── use_cases/
│       ├── validate_token_use_case.py   # Auth gate use case
│       ├── ownership_gate_use_case.py   # Post-level ownership check
│       └── query_post_use_case.py       # Aggregation (route + offers + scores, resilient)
└── entrypoints/
    └── api/
        ├── main.py                      # FastAPI app
        ├── deps.py                      # Dependency providers (clients, use cases)
        └── routers/
            └── rf005_router.py          # GET /rf005/posts/{id} + /rf005/ping
```

### Orchestration flow

`query_post` (wired via `deps.get_validate_token_use_case` and
`deps.get_ownership_gate_use_case`):

1. **Validate the bearer token** `GET /users/me` against the Users service.
   If the token is missing (no Authorization header) the gate raises
   `TokenMissingError`; if the Users service returns `401` it raises
   `InvalidTokenError`. Both stop orchestration immediately.
2. **Fetch the post** `GET /posts/{id}` via the Posts service port. A `404` or
   `400` from the Posts service (unknown id) is surfaced as
   `PostNotFoundError`.
3. **Check ownership** the authenticated user's id must match the post's
   `userId`. If not, raise `UserNotOwnerError`.
4. **Aggregate the response** by calling Routes, Offers, and Scores services (API Composition). For each offer the use case fetches its score and applies the RF-005 resilience rule (see below). Offers are sorted descending by score, offers with a null score always come after offers with a score, and ties are broken by `createdAt` descending (most recent offer first). Returns `200` with the full JSON structure shown above.

If step 1 or 2 fails due to an *integration* error (Users or Posts service
unreachable, network timeout, `5xx`), the orchestrator answers with `503`.

### Score resilience (RF-005 explicit requirement)

The requirements document states that the Score "puede no ser consistente en
el tiempo" (may not be consistent over time) and that the implementation must
be resilient to offers that have no defined Score. The orchestrator therefore
never fails the whole request because of the Score service:

| Score situation | Offer in the response | Request outcome |
|-----------------|-----------------------|-----------------|
| Score exists | `"score": 4.8` (float) | `200` |
| No score persisted for the offer | `"score": null` | `200` |
| Score service temporarily down (connection error, timeout, `5xx`, malformed payload) | `"score": null` for that offer | `200` |

Each score lookup is isolated to its own offer: a failure for one offer can
never affect the scores of the other offers, and the rest of the response
(route, post fields, offer fields) is unaffected. Unavailability events are
logged at `WARNING` level by the Score client and the use case (for example
`"Score service unavailable for offer ..."`), so they can be tracked during
grading without changing the client response.

The Score service is the only soft dependency of the aggregation. The other
services stay hard dependencies: if Users, Posts, Routes, or Offers cannot be
reached (or the referenced route does not exist) the request still fails with
the documented `503` body. Business rejections from prior stages (`403` /
`401` / `404`) pass through unchanged while the Score service is down.

Sorting choice with null scores (documented team decision): offers are sorted
descending by score; offers with a null score are always ordered after offers
with a score; ties (same score, or multiple nulls) are broken by `createdAt`
descending (most recent offer first).

### Token validation (reused, not duplicated)

The orchestrator does **not** store or verify tokens itself. It calls the
existing Users service endpoint `GET /users/me` with the bearer token and
reuses its contract as-is (Entrega 1 apps are not modified):

| Users service answers | Orchestrator returns |
|-----------------------|----------------------|
| No `Authorization` header (`403`) | `403` (empty body) |
| `401` (invalid or expired token) | `401` (empty body) |
| `200` (valid token) | proceeds to ownership check |
| unreachable / `5xx` | `503` `{"msg": "El servicio está temporalmente fuera de servicio."}` |

Validation happens in a FastAPI dependency, so **no downstream business
service (Posts) is called unless the token is valid**.

## API endpoints

| Method | Path               | Auth   | Description                                                              |
|--------|--------------------|--------|--------------------------------------------------------------------------|
| `GET`  | `/rf005/posts/{id}`| bearer | Query a post (RF-005): validates token, checks ownership, returns aggregated data (post + route + offers + scores). |
| `GET`  | `/rf005/ping`      | none   | Health check (`pong`, used by the container `HEALTHCHECK`).              |

### `GET /rf005/posts/{id}` contract

Path parameter:

```
id  (string, required): the post identifier (UUID)
```

Success response (owner of a valid post, with aggregated data and offers sorted by score):

```json
{
  "data": {
    "route": { "id": "r1", "flightId": "FL100", ... },
    "offers": [
      { "id": "o1", "score": 4.8, "offer": 150.0, ... }
    ]
  }
}
```

| Status | When                                                | Body                                             |
|--------|-----------------------------------------------------|--------------------------------------------------|
| `403`  | No `Authorization` header (missing bearer token)    | empty                                            |
| `401`  | Users service rejected the token (invalid or expired)| empty                                           |
| `404`  | The post does not exist                             | empty                                            |
| `403`  | Authenticated user is not the post owner            | empty                                            |
| `503`  | Users, Posts, Routes, or Offers service unreachable (network error or `5xx`), or the referenced route does not exist | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `200`  | Token valid + post exists + caller is the owner (aggregated data with route, offers sorted by score, null scores last). A missing score or a down Score service never changes this status: the affected offer simply carries `"score": null`. | `{"data": {...}}` |

## Environment variables

| Variable              | Description                                  | Default                       |
|-----------------------|----------------------------------------------|-------------------------------|
| `APP_NAME`            | Application name (FastAPI title)             | `rf005_query_post_app`        |
| `LOG_LEVEL`           | Log level                                    | `DEBUG`                       |
| `USERS_SERVICE_URL`   | Base URL of the Users service                | `http://localhost:8000`       |
| `POSTS_SERVICE_URL`   | Base URL of the Posts service                | `http://localhost:8002`       |
| `ROUTES_SERVICE_URL`  | Base URL of the Routes service               | `http://localhost:8006`       |
| `OFFERS_SERVICE_URL`  | Base URL of the Offers service               | `http://localhost:8003`       |
| `SCORES_SERVICE_URL`  | Base URL of the Scores service               | `http://localhost:8004`       |
| `HTTP_TIMEOUT`        | Downstream HTTP timeout (seconds)            | `5`                           |

In Minikube/EKS the services are reachable through their cluster DNS names
(for example `http://users-app-service:8000`, `http://posts-app-service:8002`);
set the variables accordingly.

## Run locally

```bash
cd rf005_query_post_app
poetry install
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8005
```

API base URL: `http://localhost:8005`. The full flow needs the five
downstream services running (their READMEs cover starting them; for quick
local runs use `DB_DRIVER=sqlite` with a file-backed `SQLITE_URL`):

| Service      | Port | Notes                                             |
|--------------|------|---------------------------------------------------|
| `users_app`  | 8000 | `DB_DRIVER=sqlite`                                |
| `posts_app`  | 8002 | `DB_DRIVER=sqlite`                                |
| `routes_app` | 8006 | `DB_DRIVER=sqlite` (8001 is taken by the RF-003 app) |
| `offers_app` | 8003 | `DB_DRIVER=sqlite`                                |
| `scores_app` | 8004 | `DB_DRIVER=sqlite`                                |

Point `USERS_SERVICE_URL` / `POSTS_SERVICE_URL` / `ROUTES_SERVICE_URL` /
`OFFERS_SERVICE_URL` / `SCORES_SERVICE_URL` at the ports above.

## Run tests

```bash
poetry run pytest --cov=src --cov-fail-under=70
```

- **Unit tests** (mocked downstream services) cover the Users/Posts HTTP
  clients (success / 4xx / 5xx / network error), the token-validation use case
  (valid, missing, empty, whitespace-only tokens), the ownership-gate use case
  (existing post owned by caller, existing post not owned, service down), the
  Score client (present score, missing score, connection error, timeout, `5xx`,
  malformed payload), the aggregation use case (per-offer score isolation,
  service outage degrading to null per offer, score-descending sorting with
  nulls last and `createdAt` tie-breaks), and the router (403/401/404/503/200
  paths).
- **Integration tests** (`tests/api/test_integration_rf005_score_outage.py`)
  exercise the real FastAPI app against the real downstream services with the
  Score service simulated as down through a dead port (connection refused),
  proving the graded RF-005 consistency requirement end to end: a score outage
  returns `200` with `"score": null` per offer, sorting stays correct with
  nulls present, and the 403/401/404 business rejections pass through
  unchanged. They are skipped automatically when the downstream services are
  not running. Point them at your own ports if needed:
  `RF005_USERS_BASE`, `RF005_POSTS_BASE`, `RF005_ROUTES_BASE`,
  `RF005_OFFERS_BASE`, `RF005_SCORES_DEAD_PORT`.
- **Automated manual verification** lives in
  `scripts/rf005_automations/rf005_manual_verification.sh` (see below) and
  exercises the real services end to end.
- The graded Postman collections live in
  `scripts/rf005_automations/evaluate_rf005.json` and
  `scripts/rf005_automations/evaluate_rf005_consistency.json` (see "Manual
  verification with Postman" below).

## Automated manual verification

`scripts/rf005_automations/rf005_manual_verification.sh` runs the whole manual-verification
flow against the real services and asserts every documented status code and
body (empty bodies for 403/401/404, the exact `503` message, and the full
`200` payload: route fields, both offers, scores, and the
score-descending / nulls-last ordering):

```bash
# 1. Start the five business services (sqlite, file-backed) + RF-003 + RF-005
#    (see "Run locally" for ports; every service uses DB_DRIVER=sqlite):
bash scripts/rf005_automations/start_rf005_services.sh
# 2. Run the script (idempotent, safe to re-run):
bash scripts/rf005_automations/rf005_manual_verification.sh
```

After changing `rf005_query_post_app` source code, reload the running
orchestrator with `bash scripts/rf005_automations/restart_rf005.sh` (the other
services keep running).

The script is idempotent: it reuses the `rf005owner` / `rf005stranger` users
(a `412` on create counts as success), and every run creates a fresh
flight/post/offer pair with dates computed dynamically (RF-003 requires
`now < expireAt <= plannedStartDate`), so stale data never breaks the
assertions. It also starts a temporary RF-005 instance whose
`POSTS_SERVICE_URL` points at a dead port to prove the `503` contract, and
shuts that instance down afterwards.

All service URLs, ports, and the dead port are overridable through
environment variables (`USERS_URL`, `ROUTES_URL`, `POSTS_URL`, `OFFERS_URL`,
`SCORES_URL`, `RF003_URL`, `RF005_URL`, `DEAD_PORT`).

Expected output on a healthy environment:

```
Total: 18 | Passed: 18 | Failed: 0
All tests PASSED ✓
```

## Run with Docker

```bash
docker build -t rf005-query-post-app:v0.0.0 .
docker run --rm -p 8005:8005 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e POSTS_SERVICE_URL=http://posts-app-service:8002 \
  rf005-query-post-app:v0.0.0
```

The image name `rf005-query-post-app:v0.0.0` matches `config.yaml` (`image_name:
rf005-query-post-app`, `image_tag: v0.0.0`), so it is ready for ECR
publication. The `HEALTHCHECK` probes `GET /rf005/ping`.

## Manual verification (curl)

**Prerequisites** for all steps below:

1. **Users service** running on port `8000` (`users_app`)
2. **Posts service** running on port `8002` (`posts_app`)
3. **Routes service** running on port `8006` (`routes_app`)
4. **Offers service** running on port `8003` (`offers_app`)
5. **Scores service** running on port `8004` (`scores_app`)
6. **RF-003 app** running on port `8001` (`rf003_create_post_app`), needed
   for step 0 to create test posts
7. This orchestrator running on port `8005`

**Note on Bearer tokens**: The system automatically masks `Bearer <token>` values
in documentation files (the same behavior as rf003). For manual verification,
you must first obtain a real token from the Users service by creating a user and
logging in. Then use that token when sending curl commands with Authorization
headers, then replace any masked value with your actual obtained token.

**Note on tokens**: the Users service stores **one token per user**: every
call to `POST /users/auth` invalidates the previous token. Always use the
token from the most recent auth call (and read the user `id` from that same
response if you need it).

**Note on database connections**: If you encounter any issues with a database
provider for any app service, you can use SQLite as a workaround:

```bash
DB_DRIVER=sqlite PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port <REPLACE WITH APP DESIGNATED PORT>
```

```bash
# 0. Setup: Create users, obtain tokens, and create a test post (via RF-003)

# Step A: Create owner user and get token
curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005owner","password":"Secret123!","email":"rf005owner@example.com","dni":"12345678","fullName":"RF005 Owner","phoneNumber":"3001112233"}'
# -> 201 {"id": "...", "username": "rf005owner", ...}

TOKEN_OWNER=$(curl -s -X POST http://localhost:8000/users/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005owner","password":"Secret123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Step B: Create stranger user and get token (for non-owner tests)
curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005stranger","password":"Secret123!","email":"rf005stranger@example.com","dni":"87654321","fullName":"RF005 Stranger","phoneNumber":"3009998877"}'
# -> 201 {"id": "...", "username": "rf005stranger", ...}

TOKEN_STRANGER=$(curl -s -X POST http://localhost:8000/users/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"rf005stranger","password":"Secret123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Step C: Create a test post (owned by rf005owner) via the RF-003 app
# RF-003 requires now < expireAt <= plannedStartDate and a future journey,
# so the dates are computed dynamically (do not hard-code them).
cd ../rf003_create_post_app

read -r EXPIRE_AT START_AT END_AT <<< "$(python3 -c "
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc).replace(microsecond=0)
print((now + timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%S'),
      (now + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S'),
      (now + timedelta(days=32)).strftime('%Y-%m-%dT%H:%M:%S'))")

FLIGHT="PM$(date +%s)"
BODY="{\"flightId\":\"$FLIGHT\",\"expireAt\":\"$EXPIRE_AT\",\"plannedStartDate\":\"$START_AT\",\"plannedEndDate\":\"$END_AT\",\"origin\":{\"airportCode\":\"BOG\",\"country\":\"Colombia\"},\"destiny\":{\"airportCode\":\"MAD\",\"country\":\"Spain\"},\"bagCost\":350}"

POST_RESPONSE=$(curl -s -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN_OWNER" -d "$BODY")

POST_ID=$(echo "$POST_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
cd ../rf005_query_post_app

# 1. Health check (no auth needed)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8005/rf005/ping
# -> 200

# 2. Missing Authorization header -> 403 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X GET http://localhost:8005/rf005/posts/$POST_ID
# -> 403

# 3. Invalid token -> 401 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X GET http://localhost:8005/rf005/posts/$POST_ID \
  -H "Authorization: Bearer sk_test_rf005_invalid_xyz789"
# -> 401

# 4. Non-existent post (with valid token) -> 404 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X GET http://localhost:8005/rf005/posts/00000000-0000-0000-0000-000000000000 \
  -H "Authorization: Bearer $TOKEN_OWNER"
# -> 404

# 5. Non-owner access (stranger tries to view owner's post) -> 403 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X GET http://localhost:8005/rf005/posts/$POST_ID \
  -H "Authorization: Bearer $TOKEN_STRANGER"
# -> 403

# 6. Owner access (rf005owner queries their own post) -> 200 with aggregated data
curl -s -w "\n%{http_code}\n" -X GET http://localhost:8005/rf005/posts/$POST_ID \
  -H "Authorization: Bearer $TOKEN_OWNER"
# -> 200 {"data": {"route": {...}, "offers": [...]}}
```

### Manual verification with Postman

Two collections cover the endpoint end to end. Both use a single `BASE_PATH`
collection variable (default `http://localhost:9000`), which in the cluster is
the ingress and locally can be any port or IP that routes to the services
(for example the fan-out proxy described in "Local fan-out proxy for the
collections" below).

1. **`scripts/rf005_automations/evaluate_rf005.json`** (happy path and gates):
   resets the services, creates users, a route, a post and an offer, then runs
   the gate requests (no token `403`, invalid token `401`, unknown post `404`,
   non-owner `403`) and the owner request. The owner request asserts the full
   `200` shape and that the offer carries a null score value (the collection
   runs with the Score service down, so the null score is the expected
   resilient outcome).
2. **`scripts/rf005_automations/evaluate_rf005_consistency.json`** (graded
   consistency check): creates a post whose `routeId` does not exist (a
   dangling route) and asserts that the aggregation answers `503` with the
   exact body `{"msg": "El servicio está temporalmente fuera de servicio."}`.
   This
   proves the hard-dependency behavior that complements the score resilience:
   only the Score service is a soft dependency.

Run them with Newman (or import them into Postman and run the folders in
order):

```bash
newman run scripts/rf005_automations/evaluate_rf005.json
newman run scripts/rf005_automations/evaluate_rf005_consistency.json
```

Expected result: every assertion passes (for example `31 assertions` and
`2 assertions` with `0 failed` in the two collections respectively).

### Local fan-out proxy for the collections

The graded collections use a single `BASE_PATH` (the ingress in the cluster).
Locally, the services run on different ports, so a small fan-out proxy can
expose them under one port. For example, a Python script that listens on
`127.0.0.1:9000` and forwards each path prefix to its service:

```
/users*  -> 127.0.0.1:8000 (users_app)
/posts*  -> 127.0.0.1:8002 (posts_app)
/offers* -> 127.0.0.1:8003 (offers_app)
/routes* -> 127.0.0.1:8006 (routes_app)
/scores* -> 127.0.0.1:8004 (scores_app)
/rf005*  -> 127.0.0.1:8005 (this orchestrator)
```

Then run the collections with `BASE_PATH=http://localhost:9000` (the
default). You can also point `BASE_PATH` directly at any port or IP that
reaches the orchestrator and its downstream services.

### Manual verification of the score resilience (curl)

These steps prove the two graded behaviors by hand. Start from the state
created by the curl flow above (owner token, post, and at least one offer).

1. **Score service down (outage).** Stop the Scores service (or point
   `SCORES_SERVICE_URL` at a dead port, for example `http://127.0.0.1:9`),
   then query the post as the owner:

   ```bash
   curl -s -w "\n%{http_code}\n" http://localhost:8005/rf005/posts/$POST_ID \
     -H "Authorization: Bearer $TOKEN_OWNER"
   # -> 200, and every offer in data.offers carries "score": null
   ```

   Expected: the request still returns `200` (not `503`) and each offer
   appears with `"score": null`. The orchestrator logs a `WARNING` line per
   offer, for example `Score service unavailable for offer <id>`.

2. **Offer without a persisted score (service up).** Restart the Scores
   service and do not create a score for the offer, then query the post:

   ```bash
   curl -s http://localhost:8005/rf005/posts/$POST_ID \
     -H "Authorization: Bearer $TOKEN_OWNER"
   # -> 200, and the offer appears with "score": null
   ```

   Expected: the offer without a persisted score appears with
   `"score": null` and the request still returns `200`.

3. **Sorting with null scores.** Create a second offer for the same post,
   keep both scores null, and check the order:

   ```bash
   curl -s http://localhost:8005/rf005/posts/$POST_ID \
     -H "Authorization: Bearer $TOKEN_OWNER" | python3 -c "import sys,json; print([o['createdAt'] for o in json.load(sys.stdin)['data']['offers']])"
   ```

   Expected: with all scores null the offers are ordered by `createdAt`
   descending (most recent first), per the documented team choice.

4. **Business rejections pass through.** With the Score service still down,
   repeat steps 2 to 5 of the curl flow above. Expected: `403` (no token),
   `401` (invalid token), `404` (unknown post), and `403` (non-owner) are
   all unchanged.

### Error classes

| Error class                    | HTTP status | Body                                             |
|--------------------------------|-------------|--------------------------------------------------|
| `TokenMissingError`            | `403`       | empty                                            |
| `InvalidTokenError`            | `401`       | empty                                            |
| `PostNotFoundError`            | `404`       | empty                                            |
| `UserNotOwnerError`            | `403`       | empty                                            |
| `UsersServiceUnavailableError` | `503`       | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `PostsServiceUnavailableError` | `503`       | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `RoutesServiceUnavailableError` | `503`      | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `OffersServiceUnavailableError` | `503`      | `{"msg": "El servicio está temporalmente fuera de servicio."}` |

All errors are mapped to HTTP responses through the error class hierarchy in
`src/errors.py`. Subclasses declare their HTTP status code and, when a message
body is required (integration failures), the exact message string. Note that
`ScoresServiceUnavailableError` exists for completeness but is never returned
to the client: per the RF-005 resilience requirement, Score unavailability is
absorbed by the Score client and the aggregation use case, which degrade it to
`"score": null` for the affected offer while the request still answers `200`.
