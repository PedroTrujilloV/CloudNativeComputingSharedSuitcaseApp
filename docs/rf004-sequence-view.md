# RF-004 Sequence View

Back to the [documentation home](./README.md). The pattern and trade-offs behind this flow are documented in the [Solution Patterns section](./solution-patterns.md#rf-004).

![Sequence View](./diagrams/rf004-sequence.png "Sequence View")

## Flow Description

`rf004_create_offer_app` exposes `POST /rf004/posts/{id}/offers` as a single client facing request. The orchestrator runs the following steps in order:

1. **Request validation**: reject a malformed body with 400.
2. **Auth**: validate the bearer token against `users_app`.
3. **Post validation**: call `posts_app` to fetch the post, then reject with 412 if the post belongs to the authenticated user or is already expired.
4. **Offer creation (first write)**: call `offers_app` to create the offer.
5. **Route fetch**: call `routes_app` to get the `bagCost` needed for the score calculation.
6. **Score calculation and persistence**: compute the score locally (offer amount, size occupancy, `bagCost`) and persist it via `scores_app`.
7. **Answer**: return the created offer to the client.

The offer is written before the score because of the data dependency (a score references an offer id). This order makes the offer the first write, so every failure after it triggers the compensating action.

## Exception Flow Summary

| Stage | Failure | Orchestrator behavior |
|---|---|---|
| Request validation | Missing or malformed field | Answer 400, no write performed |
| Auth (users_app) | 401, 403 | Pass through unchanged |
| Auth (users_app) | Unreachable or unexpected error | Answer 503, no write performed |
| Post validation (posts_app) | 404 (post does not exist) | Pass through unchanged |
| Post validation (posts_app) | 412 (own post or expired post) | Pass through unchanged |
| Post validation (posts_app) | Unreachable or unexpected error | Answer 503, no write performed |
| Offer creation (offers_app) | Unreachable or unexpected error | Answer 503, no write performed (the write never happened) |
| Route fetch (routes_app) | 404 (route does not exist) | **Compensation**: delete the just created offer via `DELETE /offers/{id}`, then answer 404 (empty body) |
| Route fetch (routes_app) | Unreachable or unexpected error | **Compensation**: delete the just created offer via `DELETE /offers/{id}`, then answer 503 |
| Score persistence (scores_app) | Unreachable or unexpected error | **Compensation**: delete the just created offer via `DELETE /offers/{id}`, then answer 503 |

Key rules (see the [RF-004 Consistency Strategy](./solution-patterns.md#rf-004)):

- The offer is the first write, so every failure after it triggers compensation. The consistency guarantee is: either both writes exist (offer + score) or neither does.
- Business rejections in the gates (400/404/412) are never compensated, because no write was performed at that point.
- Failures before the first write (Users, Posts, Offers unreachable) leave nothing behind.
- A failed compensation is logged and not fatal: the original error is still returned, and the residual orphan offer is null safe, because an offer without a score simply reads as `null` in RF-005.

