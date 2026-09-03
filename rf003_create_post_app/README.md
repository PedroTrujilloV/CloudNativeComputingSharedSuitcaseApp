# RF-003 Create Post App (Orchestrator)

The RF-003 orchestrator for the Shared Suitcase delivery platform: it exposes
the client-facing `POST /rf003/posts` endpoint that creates a post by
coordinating the Routes and Posts services (with the Users service for
authentication).

> **Status: complete.** The full RF-003 flow is in place: bearer-token
> validation against the Users service (security gate: "solo un usuario
> autenticado puede realizar esta operación"), request-body validation,
> route find-or-create in `routes_app`, `expireAt` validation, duplicate-post
> rule, post creation in `posts_app`, and **saga compensation + 503
> error handling** for mid-flow downstream failures (see *Consistency and
> error handling* below).

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
only talks to other services over HTTP (existing public APIs no direct DB
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
│       ├── routes_service_client.py     # Routes-service client (find/create)
│       └── posts_service_client.py      # Posts-service client (check/create)
├── domain/
│   ├── models/
│   │   ├── route.py                     # RouteInfo (frozen dataclass)
│   │   ├── schemas.py                   # RF003CreatePostRequest / Airport
│   │   └── user.py                      # AuthenticatedUser
│   ├── ports/
│   │   ├── posts_port.py                # Posts contract + CreatedPost
│   │   ├── routes_port.py               # Routes contract (find/create)
│   │   └── user_validation_port.py      # Token validation contract (port)
│   └── use_cases/
│       ├── create_post_use_case.py      # Core RF-003 orchestration
│       └── validate_token_use_case.py   # Auth gate use case
└── entrypoints/
    └── api/
        ├── main.py                      # FastAPI app + 400 validation handler
        ├── deps.py                      # Dependency providers (clients, use cases)
        └── routers/
            └── rf003_router.py          # POST /rf003/posts + /rf003/ping
```

### Orchestration flow

`CreatePostUseCase.execute` (wired via `deps.get_create_post_use_case`):

1. **Resolve the route by `flightId`** `GET /routes?flight=` against the
   Routes service. If a route already exists it is **reused as-is** (the
   submitted route fields are discarded); otherwise the route is created
   with the submitted values (`POST /routes`, airport codes uppercased to
   satisfy the Routes service's `^[A-Z]{3}$` rule). A `412` from the Routes
   service (invalid route dates) is surfaced as `412
   {"msg": "Las fechas del trayecto no son válidas"}`.
2. **Validate `expireAt`** it must be strictly in the future
   (`expireAt > now`) **and** on or before the route's
   `plannedStartDate` (`expireAt <= plannedStartDate`), otherwise `412
   {"msg": "La fecha expiración no es válida"}`.
3. **Check the duplicate rule** `GET /posts?route=&owner=` against the
   Posts service; if the user already has a post for this route, `412
   {"msg": "El usuario ya tiene una publicación para la misma fecha"}`.
4. **Create the post** `POST /posts` with `routeId`, `userId`, `expireAt`.
   A `412` from the Posts service (for example `expireAt` no longer in the future)
   is surfaced with the same message as step 2.
5. **Shape the success response** `201` with `data` + `msg` (sibling keys).

If step 4 fails with an *integration* error (Posts service unreachable or
unexpected status) and the route was **created by this request** (step 1),
the orchestrator runs the **compensating action** (step 6) before answering
the client.

### Consistency and error handling (saga compensation)

The flow writes to two independently owned stores (Routes, Posts) with no
distributed transaction. The documented consistency strategy
(`docs/solution-patterns.md`, RF-003) is: **either both writes exist or
neither does** a failed request must not leave an *orphaned* route.

| Failure during the flow | Client sees | Data left behind |
|---|---|---|
| Route stage: business 412 (bad dates / duplicate flightId) | `412` with the route-dates message | none (no route created) |
| Route stage: integration failure | `503` with the standard message | none |
| Post stage: business 412 (`expireAt` / duplicate) | `412` with the matching message | the new route **remains** (legitimate, reusable the next request for the same `flightId` reuses it) |
| Post stage: integration failure, route **created by this request** | `503` with the standard message | **none** the route is deleted via `DELETE /routes/{id}` (compensating action) |
| Post stage: integration failure, route **pre-existed** (reused by `flightId`) | `503` with the standard message | the shared route **remains** (it is not this request's to delete) |
| Compensation itself fails (Routes service also down) | `503` with the standard message (original error wins) | a safe orphan may remain until the Routes service recovers; it is a valid route the next request reuses, and the event is logged at ERROR |

Implementation notes:

- **Distinguishing error classes** happens in the HTTP clients
  (`src/adapters/http/`): a `412` from a downstream service is mapped to the
  matching business error (`RouteDatesInvalidError`, `ExpireAtInvalidError`,
  `DuplicatePostError` → 412 pass-through), while network errors / timeouts /
  unexpected statuses are mapped to `*ServiceUnavailableError` (→ 503 with
  the exact message `{"msg": "El servicio está temporalmente fuera de
  servicio."}`).
- The compensation lives in `CreatePostUseCase._compensate_route`
  (`src/domain/use_cases/create_post_use_case.py`): it tracks whether the
  route was created by the current request and only then calls
  `RoutesPort.delete_route` (new in this task, `src/domain/ports/routes_port.py`
  + `src/adapters/http/routes_service_client.py`). A compensation failure is
  swallowed (logged at ERROR) so the original 503 always reaches the client.
- **Observability:** route resolution (created vs reused), integration
  failures, the compensating action and its outcome are logged
  (`INFO`/`WARNING`/`ERROR`), for example `RF003: post creation failed for
  user=... flightId=...; compensating by deleting newly created route ...` 
  inspect them with `docker logs <container>` or `kubectl logs <pod>` during
  grading/demo.

### Token validation (reused, not duplicated)

The orchestrator does **not** store or verify tokens itself. It calls the
existing Users service endpoint `GET /users/me` with the bearer token and
reuses its contract as-is (Entrega 1 apps are not modified):

| Users service answers | Orchestrator returns |
|-----------------------|----------------------|
| `403` (no Authorization header) | `403` (empty body) |
| `401` (invalid or expired token) | `401` (empty body) |
| `200` (valid token) | proceeds to orchestration |
| unreachable / `5xx` | `503` `{"msg": "El servicio está temporalmente fuera de servicio."}` |

Validation happens in a FastAPI dependency, so **no downstream business
service (Routes/Posts) is called unless the token is valid and the body is
well-formed**.

## API endpoints

| Method | Path          | Auth   | Description                                                              |
|--------|---------------|--------|--------------------------------------------------------------------------|
| `POST` | `/rf003/posts`| Bearer | Creates a post (RF-003): validates token + body, resolves/creates the route, validates dates, checks duplicates, creates the post. |
| `GET`  | `/rf003/ping` | none   | Health check (`pong`, used by the container `HEALTHCHECK`).              |

### `POST /rf003/posts` contract

Request body (all fields required; camelCase, matching `routes_app`'s route
creation fields plus the post `expireAt`):

```json
{
  "flightId": "AA001",
  "expireAt": "2026-09-15T10:00:00",
  "plannedStartDate": "2026-10-01T10:00:00",
  "plannedEndDate": "2026-10-02T10:00:00",
  "origin": { "airportCode": "BOG", "country": "Colombia" },
  "destiny": { "airportCode": "MAD", "country": "Spain" },
  "bagCost": 350
}
```

Success response (`201`):

```json
{
  "data": {
    "id": "<post id>",
    "userId": "<user id>",
    "createdAt": "2026-09-02T16:59:40.338035+00:00",
    "expireAt": "2026-09-15T10:00:00",
    "route": { "id": "<route id>", "createdAt": "<route createdAt | null>" }
  },
  "msg": "Publicación creada exitosamente."
}
```

| Status | When                                                                 | Body            |
|--------|----------------------------------------------------------------------|-----------------|
| `403`  | `Authorization: Bearer <token>` header missing or empty              | empty           |
| `401`  | Users service rejected the token (invalid or expired)                | empty           |
| `400`  | Any required field missing or malformed (no body / bad types)        | empty           |
| `412`  | Route dates invalid (enforced by the Routes service)                 | `{"msg": "Las fechas del trayecto no son válidas"}` |
| `412`  | `expireAt` not after `now` or after the route's `plannedStartDate`   | `{"msg": "La fecha expiración no es válida"}` |
| `412`  | The user already has a post for the same route                       | `{"msg": "El usuario ya tiene una publicación para la misma fecha"}` |
| `503`  | Users, Routes or Posts service unreachable (network error or `5xx`)  | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `500`  | Unexpected internal error                                            | empty           |

Validation rules (mirroring `routes_app`'s `RouteCreateRequest`):
`flightId` non-empty string; `expireAt`/`plannedStartDate`/`plannedEndDate`
ISO-8601 datetimes; `origin.airportCode`/`destiny.airportCode` 3-letter IATA
codes; `origin.country`/`destiny.country` non-empty strings; `bagCost`
integer `>= 0`.

## Environment variables

| Variable              | Description                                  | Default                 |
|-----------------------|----------------------------------------------|-------------------------|
| `APP_NAME`            | Application name (FastAPI title)             | `rf003_create_post_app` |
| `LOG_LEVEL`           | Log level                                    | `DEBUG`                 |
| `USERS_SERVICE_URL`   | Base URL of the Users service                | `http://localhost:8000` |
| `ROUTES_SERVICE_URL`  | Base URL of the Routes service               | `http://localhost:8001` |
| `POSTS_SERVICE_URL`   | Base URL of the Posts service                | `http://localhost:8002` |
| `HTTP_TIMEOUT`        | Downstream HTTP timeout (seconds)            | `5`                     |

In Minikube/EKS the services are reachable through their cluster DNS names
(for example `http://users-app-service:8000`, `http://routes-app-service:8000`,
`http://posts-app-service:8000`); set the variables accordingly.

## Run locally

```bash
cd rf003_create_post_app
poetry install
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8001
```

API base URL: `http://localhost:8001`. The full flow needs the three
downstream services running (their READMEs cover starting them, for example
`users_app` on port `8000` with `DB_DRIVER=sqlite` for quick local runs,
`routes_app` on `8001`… note: pick non-clashing ports and point
`USERS_SERVICE_URL` / `ROUTES_SERVICE_URL` / `POSTS_SERVICE_URL` at them).

## Run tests

```bash
poetry run pytest --cov=src --cov-fail-under=70
```

- **Unit tests** (mocked downstream services) cover the Users/Routes/Posts
  HTTP clients (success / 412 / 4xx / 5xx / network error, including the
  `DELETE /routes/{id}` compensating call), the auth-gate use case, the
  `CreatePostUseCase` (happy path, route reuse, date rules, duplicate rule,
  error surfacing, and the saga compensation: newly created route deleted on
  post-stage 503, pre-existing route preserved, compensation failure not
  masking the 503, business 412 not compensated) and the router
  (403/401/400/412/503/201 paths, including 503-with-rollback).
- **Integration tests** (`tests/api/test_integration_rf003.py`) exercise the
  orchestrator against the **real** Users/Routes/Posts services in Docker;
  they are skipped automatically when the services are not reachable
  (`/rf003/ping` probe).
- A Postman collection for manual verification lives in
  `tests/api/evaluate_rf003.json`.

## Run with Docker

```bash
docker build -t rf003-create-post-app:v0.0.0 .
docker run --rm -p 8001:8000 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e ROUTES_SERVICE_URL=http://routes-app-service:8000 \
  -e POSTS_SERVICE_URL=http://posts-app-service:8000 \
  rf003-create-post-app:v0.0.0
```

The image name `rf003-create-post-app:v0.0.0` matches `config.yaml`
(`image_name: rf003-create-post-app`, `image_tag: v0.0.0`), so it is ready for
ECR publication. The `HEALTHCHECK` probes `GET /rf003/ping`.

## Manual verification (curl)

Prerequisites: the three downstream services running (Users on `8000`,
Routes on `8002`, Posts on `8003` any ports work, just export the
matching `*_SERVICE_URL` values) and this orchestrator on `8001`.

**Note**: If when running any app service, you encounter any issue with any apps database connection and don't care the database provider use:
```bash
DB_DRIVER=sqlite PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port <REPLACE WITH APP DESIGNATED PORT>
```

```bash
# 0. Create a user and obtain a token (Users service)
curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"rf003tester","password":"Secret123!","email":"rf003tester@example.com","dni":"12345678","fullName":"RF003 Tester","phoneNumber":"3001112233"}'
# -> 201 {"id": "..."}

TOKEN=$(curl -s -X POST http://localhost:8000/users/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"rf003tester","password":"Secret123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Use a unique flightId per run so the happy path is repeatable
FLIGHT="PM$(date +%s)"
BODY="{\"flightId\":\"$FLIGHT\",\"expireAt\":\"2026-09-15T10:00:00\",\"plannedStartDate\":\"2026-10-01T10:00:00\",\"plannedEndDate\":\"2026-10-02T10:00:00\",\"origin\":{\"airportCode\":\"BOG\",\"country\":\"Colombia\"},\"destiny\":{\"airportCode\":\"MAD\",\"country\":\"Spain\"},\"bagCost\":350}"

# 1. Health check
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/rf003/ping
# -> 200

# 2. Missing token -> 403 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -d "$BODY"
# -> 403

# 3. Invalid token -> 401 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer not-a-valid-token" -d "$BODY"
# -> 401

# 4. Missing required field (no flightId) -> 400 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"expireAt":"2026-09-15T10:00:00","plannedStartDate":"2026-10-01T10:00:00","plannedEndDate":"2026-10-02T10:00:00","origin":{"airportCode":"BOG","country":"Colombia"},"destiny":{"airportCode":"MAD","country":"Spain"},"bagCost":350}'
# -> 400

# 5. Malformed field (bad date + bad airport code + negative bagCost) -> 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d "{\"flightId\":\"$FLIGHT\",\"expireAt\":\"not-a-date\",\"plannedStartDate\":\"2026-10-01T10:00:00\",\"plannedEndDate\":\"2026-10-02T10:00:00\",\"origin\":{\"airportCode\":\"B\",\"country\":\"Colombia\"},\"destiny\":{\"airportCode\":\"MAD\",\"country\":\"Spain\"},\"bagCost\":-5}"
# -> 400

# 6. No body -> 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Authorization: Bearer $TOKEN"
# -> 400

# 7. Valid token + valid body -> 201 (route + post created)
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 201 {"data": {"id": "...", "userId": "...", "createdAt": "...",
#        "expireAt": "2026-09-15T10:00:00",
#        "route": {"id": "...", "createdAt": "..."}},
#        "msg": "Publicación creada exitosamente."}

# 8. Duplicate (same user + same flightId) -> 412
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 412 {"msg": "El usuario ya tiene una publicación para la misma fecha"}

# 9. expireAt after plannedStartDate -> 412
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d "{\"flightId\":\"$FLIGHT\",\"expireAt\":\"2026-10-02T00:00:00\",\"plannedStartDate\":\"2026-10-01T10:00:00\",\"plannedEndDate\":\"2026-10-02T10:00:00\",\"origin\":{\"airportCode\":\"BOG\",\"country\":\"Colombia\"},\"destiny\":{\"airportCode\":\"MAD\",\"country\":\"Spain\"},\"bagCost\":350}"
# -> 412 {"msg": "La fecha expiración no es válida"}

# 10. Route dates in the past -> 412 (enforced by the Routes service)
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"flightId":"PAST1","expireAt":"2026-09-15T10:00:00","plannedStartDate":"2020-01-01T10:00:00","plannedEndDate":"2020-01-02T10:00:00","origin":{"airportCode":"BOG","country":"Colombia"},"destiny":{"airportCode":"MAD","country":"Spain"},"bagCost":350}'
# -> 412 {"msg": "Las fechas del trayecto no son válidas"}

# 11. Downstream service down -> 503 (stop one service first, for example:
#     docker stop posts-app-service, then repeat scenario 7)
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}
```

### Manual verification: consistency / rollback on a mid-flow outage

This proves the two acceptance criteria: a mid-flow downstream outage returns
the documented 503 **and** leaves no orphaned route.

**Option A local (no cluster needed).** Point the Posts client at a dead
port so the post stage fails *after* the route stage succeeded:

```bash
# 1. Start Users (8000) and Routes (8002) as usual (see "Run locally"), then
#    start the orchestrator with POSTS_SERVICE_URL pointing at a dead port:
cd rf003_create_post_app
USERS_SERVICE_URL=http://localhost:8000 \
ROUTES_SERVICE_URL=http://localhost:8002 \
POSTS_SERVICE_URL=http://localhost:9999 \
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8001

# 2. Create user + token (same as step 0 above), then fire a NEW flightId:
FLIGHT="CB$(date +%s)"
BODY="{\"flightId\":\"$FLIGHT\",\"expireAt\":\"2026-09-15T10:00:00\",\"plannedStartDate\":\"2026-10-01T10:00:00\",\"plannedEndDate\":\"2026-10-02T10:00:00\",\"origin\":{\"airportCode\":\"BOG\",\"country\":\"Colombia\"},\"destiny\":{\"airportCode\":\"MAD\",\"country\":\"Spain\"},\"bagCost\":350}"
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}

# 3. Verify NO orphaned route remains for that flightId:
curl -s "http://localhost:8002/routes?flight=$FLIGHT"
# -> []  (the route created in step 2 was compensated/deleted)

# 4. Verify the orchestrator logs show the compensation (tail the uvicorn
#    output or `docker logs <container>`):
#    RF003: created new route <id> for flightId=CB...
#    RF003: post creation failed for user=... flightId=CB...;
#           compensating by deleting newly created route <id>
#    RF003: compensation succeeded, route <id> deleted

# 5. Restart the Posts service on 8002 and repeat step 2 with a new
#    flightId -> 201 again (the flow works after the outage).
```

**Option B Minikube/EKS (as deployed).** Scale the Posts deployment to
zero mid-flow and watch the compensation in the orchestrator pod logs:

```bash
kubectl scale deployment posts-app --replicas=0

# fire a request with a NEW flightId (ingress or node port of rf003):
curl -s -w "\n%{http_code}\n" -X POST http://localhost:<RF003_PORT>/rf003/posts \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}

# compensation is visible in the orchestrator logs:
kubectl logs -l app=rf003-create-post-app --tail=20

# and the route is gone (query the routes service for the flightId):
kubectl exec deploy/routes-app -- \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/routes?flight=$FLIGHT').read().decode())"
# -> []

# restore the service:
kubectl scale deployment posts-app --replicas=1
```

The Postman collection also includes the 503 request
(`(Optional) Downstream service down -> 503 (stop posts-app first)`) run it
with `posts-app` scaled to zero / stopped, then check the routes service for
the flightId to confirm the rollback.

### Manual verification with Postman

Import `tests/api/evaluate_rf003.json`. A collection-level pre-request
script generates a unique `flightId` (and `pastFlightId`) per run. Set the
collection variables if needed (`baseUrl` = orchestrator URL,
`usersUrl` = Users service URL), run the **Setup** folder (creates the user
and stores the token), then run the gate requests (403 / 401 / 400) and the
**Orchestration** folder (201, duplicate 412, `expireAt` 412, route-dates
412, and the optional 503 with a downstream service stopped) each request
asserts its expected status code and message. For the 503 request, stop
`posts-app` first and afterwards query the Routes service for the flightId
to confirm the compensating deletion (see *Manual verification: consistency
/ rollback on a mid-flow outage* above).
