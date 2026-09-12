# RF-003 Sequence View

Back to the [documentation home](./README.md). The pattern and trade-offs behind this flow are documented in the [Solution Patterns section](./solution-patterns.md#rf-003).

![Sequence View](./diagrams/rf003-sequence.png "Sequence View")

## Flow Description

`rf003_create_post_app` exposes `POST /rf003/posts` as a single client facing request. The orchestrator runs the following steps in order:

1. **Auth**: validate the bearer token against `users_app`.
2. **Route resolution**: call `routes_app` to find the route by `flightId`. If it does not exist, the orchestrator creates it and marks it as created by this request (this flag drives the compensation decision later).
3. **Post creation**: call `posts_app` to create the post referencing the route.
4. **Answer**: return the created post to the client.

The route is resolved before the post because of the data dependency (a post references a route id).

## Exception Flow Summary

| Stage | Failure | Orchestrator behavior |
|---|---|---|
| Auth (users_app) | Unreachable or unexpected error | Answer 503, no write performed, no compensation needed |
| Auth (users_app) | 400, 401, 403 | Pass through unchanged |
| Route resolution (routes_app) | Unreachable or unexpected error | Answer 503, no write performed, no compensation needed |
| Route resolution (routes_app) | 400, 412 | Pass through unchanged |
| Post creation (posts_app) | 400, 401, 403, 412 | Pass through unchanged; the created route is kept (it is legitimate, reusable state) |
| Post creation (posts_app) | Unreachable or unexpected error (503 class) | **Compensation**: if the route was created by this request, delete it via `DELETE /routes/{id}`, then answer 503 |

Key rules (see the [RF-003 Consistency Strategy](./solution-patterns.md#rf-003)):

- Only integration failures (503 class) trigger compensation.
- Pre-existing routes (reused by `flightId`) are never compensated, because they are shared state.
- Business rejections (412 for example) pass through unchanged and never trigger compensation.
- A failed compensation is logged and not fatal: the residual orphan route is safe, because the next request with the same `flightId` reuses it.

