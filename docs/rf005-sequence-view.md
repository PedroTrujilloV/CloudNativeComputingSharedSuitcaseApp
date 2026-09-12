# RF-005 Sequence View

Back to the [documentation home](./README.md). The pattern and trade-offs behind this flow are documented in the [Solution Patterns section](./solution-patterns.md#rf-005).

![Sequence View](./diagrams/rf005-sequence.png "Sequence View")

## Flow Description

`rf005_query_post_app` exposes `GET /rf005/posts/{id}` as a single client facing request. The orchestrator runs the following steps in order:

1. **Auth**: validate the bearer token against `users_app`.
2. **Post fetch**: call `posts_app` to fetch the post, then reject with 403 if the authenticated user is not the post owner.
3. **Route fetch**: call `routes_app` to fetch the route details.
4. **Offers fetch**: call `offers_app` to fetch all offers for the post.
5. **Score lookup per offer (resilient loop)**: for each offer, call `scores_app`. If the score is missing or the Scores service is unreachable for that offer, set that offer's score to `null` and continue the loop; the whole request does not fail.
6. **Sort**: sort the offers descending by score, with a documented tie-breaking rule for offers with a `null` score.
7. **Answer**: return the post, its route, and its sorted offers.

## Exception Flow Summary

| Stage | Failure | Orchestrator behavior |
|---|---|---|
| Auth (users_app) | 401 | Pass through unchanged |
| Auth (users_app) | Unreachable or unexpected error | Answer 503 |
| Post fetch (posts_app) | 404 (post does not exist) | Pass through unchanged |
| Post fetch (posts_app) | 403 (user is not the owner) | Answer 403 |
| Post fetch (posts_app) | Unreachable or unexpected error | Answer 503 |
| Route fetch (routes_app) | Unreachable or unexpected error | Answer 503 |
| Offers fetch (offers_app) | Unreachable or unexpected error | Answer 503 |
| Score lookup (scores_app) | Unreachable, 5xx, or 404 for one offer | Set that offer's score to `null` and continue the loop; the request still succeeds |

Key rules (see the [RF-005 Solution Pattern](./solution-patterns.md#rf-005)):

- This is a read-side composition, not a write-side saga: there is no state to roll back, so no compensating action exists in this flow.
- The per-offer fallback is an explicit resilience requirement from the project document: a missing or unavailable score for one offer never fails the whole response.
- Posts, Routes, and Offers are hard dependencies here: if any of them is down, the whole request fails with 503, because there is no meaningful partial post to return.

