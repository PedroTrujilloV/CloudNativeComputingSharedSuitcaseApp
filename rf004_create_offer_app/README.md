# RF-004 Create Offer App (Orchestrator)

The RF-004 orchestrator for the Shared Suitcase delivery platform: it
exposes the client facing `POST /rf004/posts/{id}/offers` endpoint that
lets an authenticated user create an offer on a post they do not own.

> **Status: complete.** The full gate is in
> place: bearer token validation against the Users service (security
> gate: "solo un usuario autenticado puede realizar esta operación"),
> request body validation (HTTP 400), and the post level preconditions
> through the existing Posts API (post exists, the post is not owned by
> the caller, the post has not expired). A request that passes every
> gate then runs the offer creation stage: the offer is persisted through
> the Offers public API (`POST /offers`), the route is fetched through the
> Routes public API (`GET /routes/{routeId}`) and its utility score is
> calculated from the route `bagCost`, and the score is persisted through
> the Scores public API (`POST /scores`). A fully valid request answers
> `201` with the offer data and a summary message. Consistency (saga
> compensation, see *Consistency and error handling* below): the offer is
> the first write of the flow, so any failure after it (an unreachable
> Routes service, a missing route, or an unreachable Scores service)
> makes the orchestrator delete the just created offer (compensating
> action) before answering the client (`503` with the standard message,
> or the documented `404` for a missing route), so no orphaned offer
> remains. An unreachable Users, Posts, Routes, Offers, or Scores
> service is a hard failure: the endpoint answers `503`.

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
only talks to other services over HTTP (existing public APIs, no direct DB
access). For a request that passes the gates it orchestrates four
downstream calls: Users (token), Posts (post lookup), Offers (offer
creation), and Routes + Scores (score calculation and persistence).

## Architecture

The service follows the same Clean Architecture layout as the other apps:

- `domain`: models, ports (abstractions), and use cases (business rules).
- `adapters`: concrete implementations (outbound HTTP clients).
- `entrypoints`: the API layer (router, schemas wiring, dependency injection).

```
src/
├── assembly.py                          # Dependency injection wiring
├── config.py                            # Settings (env driven)
├── errors.py                            # Custom exceptions (status + msg)
├── adapters/
│   └── http/
│       ├── users_service_client.py      # Users service token validation client
│       ├── posts_service_client.py      # Posts service client (post lookup)
│       ├── offers_service_client.py     # Offers service client (POST /offers)
│       ├── routes_service_client.py     # Routes service client (GET /routes/{id})
│       └── scores_service_client.py     # Scores service client (POST /scores)
├── domain/
│   ├── models/
│   │   ├── post.py                      # PostInfo (frozen dataclass)
│   │   ├── route.py                     # RouteInfo (frozen dataclass)
│   │   └── schemas.py                   # RF004CreateOfferRequest
│   ├── ports/
│   │   ├── posts_port.py                # Posts contract (get_post)
│   │   ├── offers_port.py               # Offers contract (create_offer) + FakeOffers
│   │   ├── routes_port.py               # Routes contract (get_route)
│   │   ├── scores_port.py               # Scores contract (upsert_score) + FakeScores
│   │   └── user_validation_port.py      # Token validation contract + AuthenticatedUser
│   └── use_cases/
│       ├── offer_preconditions_use_case.py  # Post level preconditions
│       ├── validate_token_use_case.py   # Auth gate use case
│       └── create_offer_use_case.py     # Offer creation + score calculation
└── entrypoints/
    └── api/
        ├── main.py                      # FastAPI app + 400 validation handler
        ├── deps.py                      # Dependency providers (clients, use cases)
        └── routers/
            └── rf004_router.py          # POST /rf004/posts/{id}/offers + /rf004/ping
```

### Gate flow

`POST /rf004/posts/{post_id}/offers` runs the gates in this order (mirroring
`docs/diagrams/rf004-sequence.puml`):

1. **Validate the bearer token** against the Users service
   (`GET /users/me`, reused as is). Missing token is `403`, a rejected
   token is `401`, an unreachable Users service is `503`.
2. **Validate the request body** (FastAPI dependency, runs before the
   handler body): all four fields required, `size` must be one of
   `LARGE`, `MEDIUM`, `SMALL`, `offer` must be a number `>= 0`. Any
   failure is `400` with an empty body (handled in `main.py`).
3. **Fetch the post** `GET /posts/{id}` against the Posts service
   (reused as is). A missing post is `404` with an empty body; an
   unreachable Posts service is `503`.
4. **Own post rule** if the post belongs to the authenticated user,
   `412` with an empty body. This check runs first, exactly as the
   sequence diagram documents.
5. **Expiration rule** if the post `expireAt` is not in the future
   (compared in UTC), `412` with an empty body.
6. **Offer creation stage** the request reaches this point only when
   every gate passed. The orchestrator then:
   1. Persists the offer through the Offers service `POST /offers`
      (unreachable Offers service is `503`; the write never happened, so
      nothing is left behind).
   2. Fetches the post route through the Routes service
      `GET /routes/{routeId}` to read its `bagCost` (unreachable Routes
      service is `503`, a missing route is `404`; in both cases the
      offer created in step 1 is first compensated, see *Consistency
      and error handling* below).
   3. Calculates the utility score with the formula
      `utilidad = offer - (bag occupancy % x route bagCost)`, where the
      occupancy is `100%` for `LARGE`, `50%` for `MEDIUM`, and `25%`
      for `SMALL`.
   4. Persists the score through the Scores service `POST /scores`
      (unreachable Scores service is `503` after the compensating
      deletion of the just created offer, see *Consistency and error
      handling* below).

   Steps 1 and 4 are the two writes of the flow and follow the
   **consistency strategy** (saga compensation): either both writes
   exist or neither does. Because the offer is the first write, a
   failure in steps 2 or 4 (an unreachable Routes service, a missing
   route, or an unreachable Scores service) makes the orchestrator run
   the compensating action (delete the offer created in step 1 through
   `DELETE /offers/{id}`) before answering the client (`503` with the
   standard message, or the documented `404` for a missing route). On
   the happy path the summary is `"Oferta creada exitosamente."`.

Because every gate runs in a FastAPI dependency or before the handler
body returns, **no downstream business call is made unless the token is
valid and the body is well formed**.

### Token validation (reused, not duplicated)

The orchestrator does **not** store or verify tokens itself. It calls the
existing Users service endpoint `GET /users/me` with the bearer token and
reuses its contract as is (Entrega 1 apps are not modified):

| Users service answers | Orchestrator returns |
|-----------------------|----------------------|
| `403` (no Authorization header) | `403` (empty body) |
| `401` (invalid or expired token) | `401` (empty body) |
| `200` (valid token) | proceeds to the next gate |
| unreachable / `5xx` | `503` `{"msg": "El servicio está temporalmente fuera de servicio."}` |

### Error mapping

`src/errors.py` declares one exception per contract outcome; each carries
the HTTP status and, when the contract defines an exact body, that
message. Contract bodies marked `N/A` in the spec map to an **empty
body** (no message on the exception):

| Exception | Status | Body |
|-----------|--------|------|
| `TokenMissingError` | `403` | empty |
| `InvalidTokenError` | `401` | empty |
| `PostNotFoundError` | `404` | empty |
| `OwnPostError` | `412` | empty |
| `PostExpiredError` | `412` | empty |
| `UsersServiceUnavailableError` | `503` | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `PostsServiceUnavailableError` | `503` | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `RoutesServiceUnavailableError` | `503` | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `OffersServiceUnavailableError` | `503` | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `ScoresServiceUnavailableError` | `503` | `{"msg": "El servicio está temporalmente fuera de servicio."}` |
| `RouteNotFoundError` | `404` | empty |

A non UUID post id is rejected by the Posts service with `400
{"msg": "El id debe ser un UUID válido"}`; the orchestrator maps that to
`404` (for the caller the post simply does not exist), since the spec
reserves `400` for missing or malformed request body fields.

### Consistency and error handling (saga compensation)

The flow writes to two independently owned stores (Offers, Scores) with no
distributed transaction. The documented consistency strategy
(`docs/solution-patterns.md`, RF-004) is: **either both writes exist or
neither does** a failed request must not leave an *orphaned* offer without
its score.

| Failure during the flow | Client sees | Data left behind |
|---|---|---|
| Gate stage: business 400/404/412 (body, missing post, own post, expired post) | the matching status with the documented body | none (no write performed) |
| Gate stage: integration failure (Users or Posts unreachable) | `503` with the standard message | none (the failure happens before the offer is created) |
| Offer stage: integration failure (Offers unreachable) | `503` with the standard message | none (the write never happened) |
| Route stage (after the offer write): Routes unreachable | `503` with the standard message | **none** the offer is deleted via `DELETE /offers/{id}` (compensating action) |
| Route stage (after the offer write): the route does not exist | `404` with an empty body | **none** the offer is deleted via `DELETE /offers/{id}` (compensating action) |
| Score stage: integration failure (Scores unreachable) | `503` with the standard message | **none** the offer is deleted via `DELETE /offers/{id}` (compensating action) |
| Route or score stage: the compensation also fails (Offers also down) | the original error wins (`503` with the standard message, or `404` for a missing route) | a null safe orphan may remain until the Offers service recovers (an offer without a score reads as `null` in RF-005); the event is logged at ERROR |

Implementation notes:

- **Distinguishing error classes** happens in the HTTP clients
  (`src/adapters/http/`): network errors, timeouts, and unexpected
  statuses are mapped to the matching `*ServiceUnavailableError` (503
  with the exact message `{"msg": "El servicio está temporalmente fuera
  de servicio."}`), while the documented business statuses (404, 412) are
  mapped to the matching business errors that pass through unchanged and
  never trigger compensation.
- The compensation lives in
  `CreateOfferUseCase._compensate_offer`
  (`src/domain/use_cases/create_offer_use_case.py`): when the route fetch
  raises `RoutesServiceUnavailableError` or `RouteNotFoundError`, or the
  score stage raises `ScoresServiceUnavailableError`, the use case calls
  `OffersPort.delete_offer` (the Offers service `DELETE /offers/{id}`
  endpoint, reused as is) and then re raises the original error so the
  router answers with the original status (503, or 404 for a missing
  route). A compensation failure is swallowed (logged at ERROR) so the
  original error always reaches the client.
- **Observability:** the score stage integration failure, the
  compensating action and its outcome are logged (`INFO`/`WARNING`/
  `ERROR`), for example `RF004: score persistence failed; compensating by
  deleting newly created offer ...` inspect them with
  `docker logs <container>` or `kubectl logs <pod>` during grading/demo.

## API endpoints

| Method | Path                          | Auth   | Description                                                              |
|--------|-------------------------------|--------|--------------------------------------------------------------------------|
| `POST` | `/rf004/posts/{post_id}/offers` | Bearer | Creates an offer (RF-004): validates token + body + post preconditions, then persists the offer and its score. |
| `GET`  | `/rf004/ping`                 | none   | Health check (`pong`, used by the container `HEALTHCHECK`).              |

### `POST /rf004/posts/{post_id}/offers` contract

Request body (all fields required):

```json
{
  "description": "Space for one medium bag",
  "size": "MEDIUM",
  "fragile": false,
  "offer": 50000
}
```

- `description`: non empty string.
- `size`: `LARGE`, `MEDIUM` or `SMALL` (case sensitive, matching the
  `offers_app` `PackageSize` values).
- `fragile`: boolean.
- `offer`: number `>= 0`.

Success response (`201`), returned when the offer is created and its
score is persisted:

```json
{
  "data": {
    "id": "<offer id>",
    "userId": "<user id>",
    "createdAt": "<timestamp>",
    "postId": "<post id>"
  },
  "msg": "Oferta creada exitosamente."
}
```

There is no other 201 variant: when the score stage fails after the offer
was created, the orchestrator compensates (deletes the offer) and answers
`503` instead (see *Consistency and error handling* below).

| Status | When                                                                 | Body            |
|--------|----------------------------------------------------------------------|-----------------|
| `403`  | `Authorization: Bearer <token>` header missing or empty              | empty           |
| `401`  | Users service rejected the token (invalid or expired)                | empty           |
| `400`  | Any required field missing or malformed (no body / bad types / bad size) | empty      |
| `404`  | The post does not exist (or its id is not a valid UUID, or its route is missing) | empty |
| `412`  | The post belongs to the authenticated user                           | empty           |
| `412`  | The post has already expired (`expireAt` not in the future)          | empty           |
| `201`  | The offer was created and its score persisted                        | see response body above |
| `503`  | Users, Posts, Routes, Offers, or Scores service unreachable (network error or `5xx`; when the failure happens after the offer was created, the offer is first compensated) | `{"msg": "El servicio está temporalmente fuera de servicio."}` |

## Environment variables

| Variable              | Description                                  | Default                 |
|-----------------------|----------------------------------------------|-------------------------|
| `APP_NAME`            | Application name (FastAPI title)             | `rf004_create_offer_app` |
| `LOG_LEVEL`           | Log level                                    | `DEBUG`                 |
| `USERS_SERVICE_URL`   | Base URL of the Users service                | `http://localhost:8000` |
| `POSTS_SERVICE_URL`   | Base URL of the Posts service                | `http://localhost:8003` |
| `ROUTES_SERVICE_URL`  | Base URL of the Routes service               | `http://localhost:8002` |
| `OFFERS_SERVICE_URL`  | Base URL of the Offers service               | `http://localhost:8004` |
| `SCORES_SERVICE_URL`  | Base URL of the Scores service               | `http://localhost:8005` |
| `HTTP_TIMEOUT`        | Downstream HTTP timeout (seconds)            | `5`                     |

In Minikube/EKS the services are reachable through their cluster DNS names
(for example `http://users-app-service:8000`,
`http://posts-app-service:8000`); set the variables accordingly.

## Run locally

```bash
cd rf004_create_offer_app
poetry install
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8001
```

API base URL: `http://localhost:8001`. The gate needs the downstream
services running (their READMEs cover starting them, for example
`users_app` on port `8000` with `DB_DRIVER=sqlite` for quick local runs,
`posts_app` on port `8003` with `DB_DRIVER=sqlite`, `routes_app` on port
`8002`, `offers_app` on port `8004`, and `scores_app` on port `8005`);
pick non clashing ports and point `USERS_SERVICE_URL`,
`POSTS_SERVICE_URL`, `ROUTES_SERVICE_URL`, `OFFERS_SERVICE_URL`, and
`SCORES_SERVICE_URL` at them.

## Run tests

```bash
poetry run pytest --cov=src --cov-fail-under=70
```

- **Unit tests** (mocked downstream services) cover the Users, Posts,
  Offers (create and delete), Routes, and Scores HTTP clients (success /
  4xx / 5xx / network error), the auth gate use case, the preconditions
  use case (unknown post, own post, expired post, own post before
  expiry, naive `expireAt` treated as UTC, valid post), the create offer
  use case (score formula for the three sizes, compensation and
  propagation when Routes is unavailable or its route is missing after
  the offer was created, compensation and propagation when Scores is
  unavailable after the offer was created, and the swallowed
  compensation failure when Offers is also down) and the router
  (403/401/400/404/412/503/201 paths, including the missing route 404
  and the assertions that no downstream call is made when the token or
  the body is invalid).
- **Consistency integration tests**
  (`tests/unit/adapters/http/test_rf004_consistency_integration.py`)
  exercise the full request path with the real HTTP clients over a mock
  transport: a Scores outage mid flow answers 503 and the created offer
  is deleted (no orphan remains), a missing route answers 404 (empty
  body) and the created offer is deleted (no orphan remains), an Offers
  outage answers 503 with no write at all, and the happy path persists
  both the offer and the score.
- A Postman collection for manual verification lives in
  `tests/api/evaluate_rf004.json`, and a dedicated consistency collection
  lives in `tests/api/evaluate_rf004_consistency.json`.

## Run with Docker

```bash
docker build -t rf004-create-offer-app:v0.0.0 .
docker run --rm -p 8001:8000 \
  -e USERS_SERVICE_URL=http://users-app-service:8000 \
  -e POSTS_SERVICE_URL=http://posts-app-service:8000 \
  -e ROUTES_SERVICE_URL=http://routes-app-service:8002 \
  -e OFFERS_SERVICE_URL=http://offers-app-service:8004 \
  -e SCORES_SERVICE_URL=http://scores-app-service:8005 \
  rf004-create-offer-app:v0.0.0
```

The image name `rf004-create-offer-app:v0.0.0` matches `config.yaml`
(`image_name: rf004-create-offer-app`, `image_tag: v0.0.0`), so it is ready
for ECR publication. The `HEALTHCHECK` probes `GET /rf004/ping`.

### Deployment (Minikube/EKS)

The orchestrator deploys like the other stateless apps: build and push the
image to ECR, then create the Deployment + Service (name
`rf004-create-offer-service`, port `8000`) with the
`USERS_SERVICE_URL` / `POSTS_SERVICE_URL` / `ROUTES_SERVICE_URL` /
`OFFERS_SERVICE_URL` / `SCORES_SERVICE_URL` environment variables pointing
at the cluster DNS names of each downstream service, and expose it through
the ingress path `/rf004/posts/{id}/offers` (see `docs/deployment-view.md`). Verify after
deploying:

```bash
kubectl get pods -l app=rf004-create-offer-app
# -> 1/1 Running (the HEALTHCHECK on /rf004/ping gates readiness)

kubectl logs -l app=rf004-create-offer-app --tail=20
# -> uvicorn startup lines, no import or configuration errors

curl -s http://<INGRESS_HOST>/rf004/ping
# -> pong
```

## Manual verification (curl)

Prerequisites: the five downstream services running (Users on `8000`,
Routes on `8002`, Posts on `8003`, Offers on `8004`, Scores on `8005`;
any ports work, just export the matching `*_SERVICE_URL` values) and this
orchestrator on `8001`.

**Note**: If when running any app service, you encounter any issue with
any apps database connection and don't care the database provider use:
```bash
DB_DRIVER=sqlite PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port <REPLACE WITH APP DESIGNATED PORT>
```

```bash
# 0a. Create the post owner and a second user (Users service)
curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"rf004owner","password":"Secret123!","email":"rf004owner@example.com","dni":"12345678","fullName":"RF004 Owner","phoneNumber":"3001112233"}'
# -> 201 {"id": "<OWNER_ID>"}

curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"rf004caller","password":"Secret123!","email":"rf004caller@example.com","dni":"87654321","fullName":"RF004 Caller","phoneNumber":"3004445566"}'
# -> 201 {"id": "..."}

# 0b. Obtain both tokens
TOKEN=$(curl -s -X POST http://localhost:8000/users/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"rf004caller","password":"Secret123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

OWNER_TOKEN=$(curl -s -X POST http://localhost:8000/users/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"rf004owner","password":"Secret123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 0c. The owner creates a real route (Routes service, no auth needed).
#     The posts below reference this route so the offer creation stage
#     can fetch it and calculate the score.
ROUTE_ID=$(curl -s -X POST http://localhost:8002/routes \
  -H "Content-Type: application/json" \
  -d '{"flightId":"RF004-MAN-BOG","sourceAirportCode":"MAN","sourceCountry":"Spain","destinyAirportCode":"BOG","destinyCountry":"Colombia","bagCost":10000,"plannedStartDate":"2026-10-01T00:00:00Z","plannedEndDate":"2026-10-08T00:00:00Z"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 0d. The owner creates two posts (Posts service, no auth needed):
#     one valid (far future) and one short lived (expires in ~5 seconds,
#     used for the expired post scenario; the Posts API rejects past
#     expireAt values, so a short future date is the way to get one).
OWNER_ID=<paste the owner id from 0a>
FUTURE=$(date -u -v+1H +%Y-%m-%dT%H:%M:%SZ)        # macOS; on Linux: date -u -d '+1 hour'
SOON=$(date -u -v+5S +%Y-%m-%dT%H:%M:%SZ)          # macOS; on Linux: date -u -d '+5 seconds'

POST_ID=$(curl -s -X POST http://localhost:8003/posts \
  -H "Content-Type: application/json" \
  -d "{\"routeId\":\"$ROUTE_ID\",\"userId\":\"$OWNER_ID\",\"expireAt\":\"$FUTURE\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

EXPIRED_POST_ID=$(curl -s -X POST http://localhost:8003/posts \
  -H "Content-Type: application/json" \
  -d "{\"routeId\":\"$ROUTE_ID\",\"userId\":\"$OWNER_ID\",\"expireAt\":\"$SOON\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

BODY='{"description":"Space for one medium bag","size":"MEDIUM","fragile":false,"offer":50000}'

# 1. Health check
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/rf004/ping
# -> 200

# 2. Missing token -> 403 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -d "$BODY"
# -> 403

# 3. Invalid token -> 401 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer not-a-valid-token" -d "$BODY"
# -> 401

# 4. Missing required field (no offer) -> 400 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"description":"Space for one medium bag","size":"MEDIUM","fragile":false}'
# -> 400

# 5. Malformed field (bad size) -> 400 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"description":"Space for one medium bag","size":"XL","fragile":false,"offer":50000}'
# -> 400

# 6. No body -> 400 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Authorization: Bearer $TOKEN"
# -> 400

# 7. Unknown post -> 404 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/00000000-0000-4000-8000-000000000000/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 404

# 8. Own post (owner's token on the owner's post) -> 412 (empty body)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $OWNER_TOKEN" -d "$BODY"
# -> 412

# 9. Expired post (wait ~6 seconds after step 0c, then) -> 412 (empty body)
sleep 6
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$EXPIRED_POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 412

# 10. Valid token + valid body + valid post -> 201 (the gate passes and
#     the orchestrator creates the offer, fetches the route, calculates
#     the score for a MEDIUM bag as 50000 - 0.5 * 10000 = 45000, and
#     persists it through the Scores service)
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 201 {"data": {"id": "...", "userId": "...", "createdAt": "...", "postId": "..."}, "msg": "Oferta creada exitosamente."}

# 11. Scores service down -> 503 with the standard message, and the
#     offer created mid flow is compensated (stop the Scores service
#     first, for example kill its uvicorn process, then repeat scenario
#     10 with a fresh valid post, and afterwards query the Offers
#     service: the offer from the failed request is not in the list)
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}

# 12. Downstream service down -> 503 with the standard message (stop the
#     Posts or the Offers service first, for example kill its uvicorn
#     process, then repeat scenario 10; no write happened so there is
#     nothing to compensate)
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}

# 13. Routes service down -> 503 with the standard message, and the
#     offer created mid flow is compensated (stop the Routes service
#     first, then repeat scenario 10 with a fresh valid post, and
#     afterwards query the Offers service: the offer from the failed
#     request is not in the list)
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}
```

### Manual verification: consistency / rollback on a mid flow outage

This proves the two acceptance criteria: a mid flow downstream outage
returns the documented 503 **and** leaves no orphaned offer.

```bash
# 1. Start Users (8000), Routes (8002), Posts (8003), and Offers (8004)
#    as usual (see "Run locally"), but leave the Scores service STOPPED
#    (or start it on a dead port and point SCORES_SERVICE_URL there):
#    SCORES_SERVICE_URL=http://localhost:9999

# 2. Run steps 0a to 0d above (users, tokens, route, post) and fire a
#    valid offer request (scenario 10):
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8001/rf004/posts/$POST_ID/offers \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY"
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}

# 3. Verify NO orphaned offer remains for that post (the offer created
#    mid flow was compensated/deleted before the 503 was answered):
curl -s "http://localhost:8004/offers?post=$POST_ID&owner=<CALLER_ID>"
# -> []  (the caller has no offers on that post)

# 4. Verify the orchestrator logs show the compensation (tail the
#    uvicorn output or `docker logs <container>`):
#    RF004: score persistence failed; compensating by deleting
#           newly created offer <id>
#    RF004: compensation succeeded, offer <id> deleted

# 5. Restart the Scores service on 8005 and repeat scenario 10 with a
#    fresh valid post -> 201 again (the flow works after the outage).

# 6. The same mid flow guarantee holds for the route stage: stop the
#    Routes service (or point the post at a nonexistent routeId, which
#    answers 404) and repeat scenario 10 with a fresh valid post. The
#    offer created mid flow is compensated in both cases, so the
#    Offers count for that post stays 0:
curl -s "http://localhost:8004/offers/count"
# -> {"count": 0}
```

On Minikube/EKS the same check uses `kubectl scale deployment
scores-app --replicas=0` instead of stopping the process, `kubectl logs
-l app=rf004-create-offer-app --tail=20` to read the compensation lines,
and `kubectl scale deployment scores-app --replicas=1` to restore the
service.

### Manual verification with Postman

Import `tests/api/evaluate_rf004.json`. Set the collection variables if
needed (`baseUrl` = orchestrator URL, `usersUrl` = Users service URL,
`postsUrl` = Posts service URL, `routesUrl` = Routes service URL,
`scoresUrl` = Scores service URL), then run the **Setup** folder: it
creates the owner and the caller, stores both tokens, creates a route,
and creates an owner post (valid) plus a short lived owner post that
expires about 2 seconds after creation. Run the remaining requests in
order: by the time the **Expired post** request runs, the short lived
post has expired. Each request asserts its expected status code and
empty body, except the last one (**Valid request -> 201**), which asserts
the `201` status and the `data` body with the new offer id, the caller
id, the creation timestamp, and the post id.

For the consistency acceptance criteria, import
`tests/api/evaluate_rf004_consistency.json` (same collection variables).
Its **Setup** folder creates a fresh owner and caller, stores the caller
token, and creates a route plus a valid post. Stop the Scores service
first, then run the **Consistency** folder: **Offer request with Scores
down** asserts the `503` status and the exact standard message, and
**Verify no orphaned offer remains** queries the Offers service for the
offers of that post owned by the caller and asserts the list is empty
(the offer created mid flow was compensated). Restart the Scores
service, then run **Offer request after recovery** to confirm the flow
answers `201` again.

### Manual verification with Postman (consistency collection, newman)

The consistency acceptance criteria are covered by
`tests/api/evaluate_rf004_consistency.json` (the same file the grader
runs). It needs a single environment variable, `BASE_PATH`, pointing at
the URL prefix that routes to the apps (the ingress path in the cluster,
or a local fan out proxy on `http://127.0.0.1:9001` for local runs). Each
outage scenario follows the same three steps: run the **Reset** folder,
stop (or scale to zero) one downstream service, run the scenario folder,
then restore the service and run **Verificar Consistencia** to assert the
offers count is zero.

```bash
# Scenario 1: Users down (auth gate, no writes possible)
newman run tests/api/evaluate_rf004_consistency.json -e env.json --folder "Reset"
# stop users-app (kill the process, or kubectl scale deployment users-app --replicas=0)
newman run tests/api/evaluate_rf004_consistency.json -e env.json \
  --env-var USER_TOKEN=FAKETOKEN \
  --env-var POST_ID=bf8792d2-3097-11ee-be56-0242ac120002 \
  --folder "Test RF-004"
# -> 503 {"msg": "El servicio está temporalmente fuera de servicio."}
# restore users-app, then:
newman run tests/api/evaluate_rf004_consistency.json -e env.json --folder "Verificar Consistencia"
# -> offers/count == 0

# Scenario 2: Offers down (the offer write never happens)
newman run tests/api/evaluate_rf004_consistency.json -e env.json --folder "Reset"
# stop offers-app
newman run tests/api/evaluate_rf004_consistency.json -e env.json --folder "RF-004 Crear oferta"
# -> 503 with the standard message
# restore offers-app, then run "Verificar Consistencia" (offers/count == 0)

# Scenario 3: Posts down (the post lookup gate fails, no writes possible)
newman run tests/api/evaluate_rf004_consistency.json -e env.json --folder "Reset"
newman run tests/api/evaluate_rf004_consistency.json -e env.json --folder "Crear Recursos"
# stop posts-app
newman run tests/api/evaluate_rf004_consistency.json -e env.json \
  --env-var POST_ID=bf8792d2-3097-11ee-be56-0242ac120002 \
  --folder "Sesion & RF-004"
# -> 503 with the standard message
# restore posts-app, then run "Verificar Consistencia" (offers/count == 0)
```

`env.json` is a newman environment file with the variables the collection
uses (at minimum `BASE_PATH`, plus the user credentials and the post
`expireAt`). Note that in the Offers down scenario the collection creates
the post with a random (nonexistent) `routeId`: the offer write is
attempted first, so with the Offers service down the request fails with
the documented 503 before the route is ever fetched, and no write
happens (there is nothing to compensate). The grader runs exactly these
folders against the deployed cluster, so a green local run with the same
folder order is the manual equivalent of the graded check.
