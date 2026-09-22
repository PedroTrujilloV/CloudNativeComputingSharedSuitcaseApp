# Solution Patterns per Requirement

The following table documents the architectural pattern applied to each functional requirement, per the required format. All three requirements share the same core pattern (orchestration via a dedicated per requirement service, exposed through a single Ingress entry point), but are broken out individually since each has distinct trade-offs given its own failure modes and consistency needs.

| Requerimiento | Patrón utilizado | Justificación | Atributos de calidad favorecidos | Atributos de calidad desfavorecidos | Componentes involucrados |
|---|---|---|---|---|---|
| **RF-003** (create a post) | Orchestrator / Saga (choreographed via a dedicated orchestrating service), fronted by an API Gateway / Ingress routing pattern | The client must make exactly one HTTP request to create a post, but the operation coordinates two independently owned services (Routes, Posts) that cannot be merged or directly coupled without violating the "each app owns its data" constraint. A dedicated orchestrator service composes these calls server-side, so the client never sees the underlying multi-service sequence. Because the operation spans two data stores with no distributed transaction available, a saga-style approach (proceed sequentially, compensate on partial completion) keeps the system consistent without requiring a shared database transaction across services. | Modifiability (Routes/Posts can evolve independently without touching the client contract); Deployability (each service still ships independently); Simplicity for the client (one request, one response, no client-side orchestration logic); Testability (the orchestration logic is isolated and independently testable from the underlying services) | Availability (the request now depends on the availability of two downstream services instead of one, so one link failing fails the whole operation, mitigated by returning 503 rather than silently succeeding); Latency (sequential calls to Routes then Posts add round-trip time compared to a single local write); Consistency complexity (without a distributed transaction, a partial failure requires explicit compensating logic, adding design and testing burden) | `rf003_create_post_app` (RF003App), `users_app`, `routes_app`, `posts_app`, `ingress` (Ingress) |
| **RF-004** (create an offer and persist its score) | Orchestrator / Saga (choreographed via a dedicated orchestrating service) with a compensating action for the Score stage and hard dependency propagation for the rest of the flow | Creating an offer coordinates three services (Posts for validation, Offers for persistence, Scores for the calculated utility value) behind one client request. The operation spans two data stores (Offers, Scores) with no distributed transaction available, and the project document requires that in every error case the databases are consistent when the flow ends. A saga-style approach is therefore used: the writes proceed sequentially (offer first, score second, because the score references the offer id), and when any stage after the offer write fails (the route fetch, the score persistence, or a missing route) the orchestrator runs the compensating action (delete the just created offer) so the system ends consistent. The remaining downstream calls (Users, Posts, Offers) are hard dependencies: when any of them is unreachable or errors unexpectedly, the request cannot be completed and the orchestrator answers 503, with no write left behind because the failure happens before or at the first write. | Consistency (a failed request never leaves an orphaned offer without its score); Simplicity for the client (one request, one response, and the documented 503 body when the flow cannot be completed); Modifiability (Offers and Scores can evolve independently behind their ports) | Availability of the primary use case (an offer can no longer be created when the Scores service is down, because the consistency requirement forces the rollback instead of a soft fail); Latency (four sequential downstream calls plus a local score computation step add round-trip time); Complexity (the orchestrator must distinguish integration failures, which trigger the compensating action and a 503, from business rejections such as 404/412, which pass through unchanged and never compensate) | `rf004_create_offer_app` (RF004App), `users_app`, `posts_app`, `routes_app`, `offers_app`, `scores_app` (ScoresApp), `ingress` (Ingress) |
| **RF-005** (query a post with its route and offers sorted by score) | Orchestrator / API Composition pattern, with a per-item resilience/fallback pattern applied to the Score lookups | Querying a post aggregates data from four services (Users for authorization, Posts, Routes, Offers) into one response, plus a Score lookup per offer. This is a read-side composition, not a write-side saga: there is no state to roll back, only data to gather and merge. The per-offer fallback (returning `null` for an individual offer's score rather than failing the whole response) is required explicitly by the project document and is implemented as a per-item resilience pattern within the composition, so a single unavailable score never blocks the rest of the response. | Resilience (the response degrades gracefully at the level of an individual offer rather than failing entirely); Usability (the client always gets the post and its offers, even under partial backend degradation); Separation of concerns (each underlying service remains solely responsible for its own data; the composition logic lives only in the orchestrator, not duplicated elsewhere) | Latency (the highest fan-out of the three requirements, with one call each to Users, Posts, Routes, Offers plus one Score call per offer, which makes this the slowest of the three endpoints, especially as the number of offers on a post grows); Availability under multiple simultaneous outages (unlike Score, Posts/Routes/Offers are treated as hard dependencies here, so if any of them is down the whole request fails, since there is no meaningful "partial post" to return); Complexity of ordering (sorting offers descending by a value that may be `null` for some entries requires an explicit, documented tie-breaking rule) | `rf005_query_post_app` (RF005App), `users_app`, `posts_app`, `routes_app`, `offers_app`, `scores_app` (ScoresApp), `ingress` (Ingress) |
| **RF-006** (store a credit card and notify the owner of the verification result) | Single entry point / API Gateway routing, asynchronous event driven decoupling through the SQS queue, bounded polling with at least once delivery and a dead letter queue fallback, and SNS email notification | Storing a card coordinates authentication, validation, TrueNative tokenization, persistence, and a slow verification (up to 30 seconds) behind one client request that must answer in less than 5 seconds. The synchronous phase does only the fast work, the queue hands the slow verification to a separate serverless worker that polls TrueNative until the terminal state, and the email is published to the SNS topics for every outcome. Each pattern addresses one of the stated design constraints: the single host, the 5 second response against the 30 second TrueNative SLA, the growing demand, and the mandatory notification. | Responsiveness (the client never waits for the verification); Scalability (the queue buffers events under demand spikes and the serverless worker scales with the queue depth); Decoupling (the web service, the worker, and the email mechanism evolve and deploy independently); Usability (one request, one host, and a mandatory email for every outcome) | Latency of the final status (the card status only changes after the worker polls TrueNative to a terminal state); Eventual consistency (the client sees `POR_VERIFICAR` first and the final status arrives later); At least once delivery (a redelivered event forces the consumer to be idempotent); Operational step (the SNS subscription must be confirmed once before any email is delivered) | `ingress` (Ingress), `credit_cards_app` (CreditCardsApp), `users_app` (UsersApp), `truenative` (TrueNative), `credit_cards_db` (CreditCardsDb), `card_verification_queue` (CardQueue), `card_worker` (CardWorker), `sns_topics` (SnsTopics) |
| **RF-007** (verify the identity of a user when the user is created) | Single entry point / API Gateway routing, asynchronous event driven callback (the TrueNative webhook) to a dedicated callback component, an integrity check (SHA256 over the secret token, the RUV, and the score) as the only authorization of the public endpoint, a status based token block in `users_app`, and SNS email notification | The requirement is triggered by user creation, so `users_app` stores the user as `POR_VERIFICAR` and sends the verification request to TrueNative without waiting for the result: TrueNative commits to deliver the answer in no more than 120 seconds through the webhook, and the user must not be able to obtain a token until the status is `VERIFICADO`. The result arrives through a public `PATCH` callback handled by a separate deployable (`user_verification_callback`) that verifies the SHA256 integrity of the message, updates the user through the `users_app` API (preserving the data ownership rule), and publishes the mandatory email. Each pattern addresses one of the stated design constraints: the single host, the 120 second provider commitment, the public and unauthenticated webhook, the rule that only verified users can use the platform, and the mandatory notification. | Responsiveness (the creation request does not wait for the 120 second verification); Scalability (the callback is a stateless web component that scales with the callback volume, and `users_app` never holds a request while waiting for TrueNative); Security of the public endpoint (the SHA256 check discards any message that does not come from a client that knows the secret token); Decoupling (the callback, the user domain, and the email mechanism deploy and evolve independently); Usability (one request to one host, and a mandatory email for every outcome) | Eventual consistency (the user is `POR_VERIFICAR` until the callback arrives, up to 120 seconds after the creation); Availability of the final status (if the callback is lost or fails the integrity check, the user stays `POR_VERIFICAR` until the result is redelivered or fixed); Coupling to the provider contract (the public webhook has no authorization mechanism, so the integrity check must evolve with the TrueNative contract); Operational step (the SNS subscription must be confirmed once before any email is delivered) | `ingress` (Ingress), `users_app` (UsersApp), `truenative` (TrueNative), `user_verification_callback` (UserVerificationCallback), `shared_db` (SharedDb), `sns_topics` (SnsTopics) |

## RF-003


#### RF-003 Consistency Strategy (documented per Epic H)

The RF-003 flow performs two writes on two independently owned stores
(Routes, Posts) with no distributed transaction. The team's definition of
**"the databases are consistent"** after the flow is:

> Either both writes exist (route + post) or neither does. A failed request
> must not leave behind an *orphaned* route that is a route created by that
> request that has no post because the post creation failed mid-flow.

The team chose the **compensating action** option (saga compensation) over a
"no orphaned state possible" redesign, because the route find or create
order (route first, post second) is dictated by the data dependency (a post
references a route id) and the Routes service already exposes
`DELETE /routes/{id}` as its public API so compensation reuses the owning
service's own contract (no cross-app DB access, no new endpoint).

Rules implemented in `rf003_create_post_app`:

1. **Only integration failures (503-class) trigger compensation.** When the
   post stage fails because a downstream service is unreachable or errors
   unexpectedly *and* the route was **created by this same request**, the
   orchestrator deletes that route (`DELETE /routes/{routeId}`) before
   answering the client with `503 {"msg": "El servicio está temporalmente
   fuera de servicio."}`.
2. **Pre-existing routes are never compensated.** A route reused by `flightId`
   is shared state: a failed post attempt must not destroy data other
   requests (and users) depend on.
3. **Business rejections (412) are not compensated.** An `expireAt` or
   duplicate rejection passes through untouched; the newly created route
   remains because it is a legitimate, reusable entity the next request
   with the same `flightId` finds and reuses it (the documented happy path).
4. **A failed compensation is logged, not fatal.** If the Routes service is
   also down, the compensating delete cannot be confirmed; the original 503
   is still returned, and the event is logged (see Observability below). The
   residual orphan is *safe*: it is a valid route that the next request for
   the same `flightId` will reuse, so it self-heals without data corruption.

**Observability:** the orchestrator logs, at INFO/WARNING/ERROR levels: route
resolution (created vs reused), post-stage integration failures, the
compensating action and its outcome, and compensation failures so a partial
failure during grading/demo can be traced from the container logs
(`docker logs <rf003 container>` or `kubectl logs <pod>`).

## RF-004

#### RF-004 Consistency Strategy (documented per Epic H)

The RF-004 flow performs two writes on two independently owned stores
(Offers, Scores) with no distributed transaction. The team's definition of
**"the databases are consistent"** after the flow is:

> Either both writes exist (offer + score) or neither does. A failed
> request must not leave behind an *orphaned* offer that has no score
> because the score persistence failed mid-flow.

The team chose the **compensating action** option (saga compensation) over
a "no orphaned state possible" redesign, because the offer first, score
second order is dictated by the data dependency (a score references the
offer id) and the Offers service already exposes `DELETE /offers/{id}` as
its public API so compensation reuses the owning service's own contract
(no cross-app DB access, no new endpoint).

Rules implemented in `rf004_create_offer_app`:

1. **The offer is the first write, so every failure after it triggers
   compensation.** The flow order is: create the offer, then fetch the
   route and calculate the score, then persist the score. When the route
   fetch fails (unreachable Routes service, 503) or the score stage
   fails (unreachable Scores service, 503), the orchestrator deletes the
   offer created by this same request (`DELETE /offers/{offerId}`)
   before answering the client with `503
1. **The offer is the first write, so every failure after it triggers
   compensation.** The flow order is: create the offer, then fetch the
   route and calculate the score, then persist the score. When the route
   fetch fails (unreachable Routes service, 503) or the score stage
   fails (unreachable Scores service, 503), the orchestrator deletes the
   offer created by this same request (`DELETE /offers/{offerId}`)
   before answering the client with `503
   {"msg": "El servicio está temporalmente fuera de servicio."}`.
2. **A missing route (business 404) is also compensated, and the 404
   still reaches the client.** A post whose `routeId` does not exist
   cannot be scored, so the offer created by the request is deleted
   before the documented 404 (empty body) is answered: the business
   contract is preserved and no orphaned offer remains.
3. **Failures before the first write leave nothing behind.** An
   unreachable Users or Posts service happens before the offer is
   created, so the 503 answer needs no compensation. An unreachable
   Offers service means the write never happened either.
4. **Business rejections in the gates (400/404/412) are never
   compensated.** A missing post, an own post, an expired post, or a
   malformed body passes through untouched; no write was performed at
   that point, so nothing to roll back.
5. **A failed compensation is logged, not fatal.** If the Offers service
   is also down, the compensating delete cannot be confirmed; the
   original error is still returned (503, or 404 for a missing route),
   and the event is logged at ERROR (see Observability below). The
   residual orphan is *null-safe*: an offer without a score simply reads
   as `null` in RF-005 until the data is repaired, so it does not
   corrupt any query.
2. **A missing route (business 404) is also compensated, and the 404
   still reaches the client.** A post whose `routeId` does not exist
   cannot be scored, so the offer created by the request is deleted
   before the documented 404 (empty body) is answered: the business
   contract is preserved and no orphaned offer remains.
3. **Failures before the first write leave nothing behind.** An
   unreachable Users or Posts service happens before the offer is
   created, so the 503 answer needs no compensation. An unreachable
   Offers service means the write never happened either.
4. **Business rejections in the gates (400/404/412) are never
   compensated.** A missing post, an own post, an expired post, or a
   malformed body passes through untouched; no write was performed at
   that point, so nothing to roll back.
5. **A failed compensation is logged, not fatal.** If the Offers service
   is also down, the compensating delete cannot be confirmed; the
   original error is still returned (503, or 404 for a missing route),
   and the event is logged at ERROR (see Observability below). The
   residual orphan is *null-safe*: an offer without a score simply reads
   as `null` in RF-005 until the data is repaired, so it does not
   corrupt any query.

**Distinguishing the error classes** happens in the HTTP clients
(`src/adapters/http/`): network errors, timeouts, and unexpected statuses
are mapped to the matching `*ServiceUnavailableError` (503 with the exact
message), while the documented business statuses (404, 412) are mapped to
the matching business errors that pass through unchanged.

**Observability:** the orchestrator logs, at INFO/WARNING/ERROR levels:
the score stage integration failure, the compensating action and its
outcome, and compensation failures so a partial failure during grading or
demo can be traced from the container logs (`docker logs <rf004
container>` or `kubectl logs <pod>`).

## RF-005

**Distinguishing the error classes:** RF005 distinguishes between business errors, required-service failures, and optional-service failures. Business errors such as missing or invalid authentication, a non-existent post, or a user who is not the owner preserve their corresponding HTTP status codes (403, 401, 404, and 403). Failures of required dependencies such as Users, Posts, Routes, or Offers are propagated as 503 with the standard service-unavailable message. In contrast, Scores is treated as a soft dependency: when the Score service is unavailable or an offer has no persisted score, RF005 does not return an error and instead sets the corresponding score to null while returning 200.

**Observability:** RF005 provides observability of degraded Score dependencies through warning logs. When the Score service is unavailable for an offer, the orchestrator records a WARNING indicating that the Score service is unavailable for that offer, while continuing the aggregation with score: null. This allows the system to maintain availability for the client while making the underlying dependency failure visible to operators.

## RF-006

The RF-006 flow has two phases: a synchronous phase inside the request (auth, validation, TrueNative tokenization, persistence, event publish, answer) and an asynchronous phase after the response (queue delivery, polling of TrueNative, status update, email). The patterns below are broken out individually because each one addresses a different stated design constraint: the single host, the 5 second response against the 30 second TrueNative SLA, the growing demand, the decoupling rule, and the mandatory email for every outcome.

### Single entry point / API Gateway routing

| Requerimiento | RF-006 (store a credit card and notify the owner of the verification result) |
|---|---|
| **Patrón utilizado** | Single entry point / API Gateway routing |
| **Justificación** | The client makes exactly one HTTP request to one host. The Ingress routes the request by path prefix to `credit_cards_app`, and that service coordinates the rest of the flow server side: it validates the bearer token through `users_app`, validates the request, tokenizes the card at TrueNative, persists it, publishes the verification event, and answers the client. The client never sees the underlying multi component sequence, which is what the single host and one request per requirement constraint requires. |
| **Atributos de calidad favorecidos** | Usability (one host and one request per requirement); Modifiability (the internal flow can evolve without changing the client contract); Deployability (each component behind the route deploys independently). |
| **Atributos de calidad desfavorecidos** | Availability (the request depends on the availability of several components, so one failing link fails the whole request); Latency (the synchronous path performs the token validation, the TrueNative call, and the database write in sequence); Complexity of the routing layer (a routing mistake in the Ingress breaks the requirement that every endpoint group is reachable). |
| **Componentes involucrados** | `ingress` (Ingress), `credit_cards_app` (CreditCardsApp), `users_app` (UsersApp), `truenative` (TrueNative). |

### Asynchronous event driven decoupling (SQS queue)

| Requerimiento | RF-006 (store a credit card and notify the owner of the verification result) |
|---|---|
| **Patrón utilizado** | Asynchronous event driven decoupling through the `card_verification_queue` (SQS) |
| **Justificación** | The initial response must return in less than 5 seconds, while TrueNative commits to up to 30 seconds for the card verification. `credit_cards_app` therefore stores the card with status `POR_VERIFICAR`, publishes the verification event (card id and RUV) to the queue, and answers the client without waiting for TrueNative. `card_worker` is the consumer that completes the verification afterwards. The queue is the single asynchronous seam of the flow, and it is what makes the event driven pattern explicit in the architecture. It also buffers events when TrueNative is slow or when demand spikes, so the web service never blocks on the external platform. |
| **Atributos de calidad favorecidos** | Responsiveness (the client never waits for the verification); Scalability (demand spikes are absorbed by the queue, and the serverless consumer scales with the queue depth); Availability (the web service stays responsive even when TrueNative is slow); Decoupling (the producer and the consumer deploy and evolve independently). |
| **Atributos de calidad desfavorecidos** | Eventual consistency (the client sees `POR_VERIFICAR` first, and the final status arrives later); At least once delivery (a redelivered event forces the consumer to be idempotent, which adds a design constraint on the worker); Operational overhead (the queue, its permissions, and its dead letter policy must be provisioned and monitored). |
| **Componentes involucrados** | `credit_cards_app` (CreditCardsApp), `card_verification_queue` (CardQueue), `card_worker` (CardWorker). |

### Bounded polling with at least once delivery and a dead letter queue fallback

| Requerimiento | RF-006 (store a credit card and notify the owner of the verification result) |
|---|---|
| **Patrón utilizado** | Bounded polling of `GET /native/cards/{ruv}` with at least once delivery and a dead letter queue fallback (team decision) |
| **Justificación** | TrueNative exposes a polling model for cards (no webhook), so the worker polls `GET /native/cards/{ruv}` with the secret token header. A `202` means the verification is still in progress, so the worker waits and retries within a bounded number of attempts. When TrueNative answers `200`, the worker reads the final status and updates the card by id, which is idempotent under the at least once delivery of the queue. If no terminal state is reached within the budget, the worker gives up on that invocation and the queue redelivers the event, so the card stays `POR_VERIFICAR`; after the maximum number of retries the event is moved to the dead letter queue and the owner is still notified by email with the `POR_VERIFICAR` status and the RUV, so the user is never left without the mandatory notification. This fallback is a team decision because the project document does not specify what happens in that case. |
| **Atributos de calidad favorecidos** | Resilience (a transient TrueNative error does not lose the event, the redelivery retries it); Simplicity (the polling loop is a plain sequential loop inside a synchronous function invoked by the event, so the restriction that forbids background tasks, threads, and asyncio in the web components is respected); Guaranteed notification (every outcome, including the fallback, produces the mandatory email). |
| **Atributos de calidad desfavorecidos** | Latency of the final status (the status only changes when the worker reaches a terminal state, and a redelivered event adds delay); Idempotency burden (the consumer must be safe under redelivery, which constrains its implementation); Cost of the fallback (a card that never reaches a terminal state stays `POR_VERIFICAR` until an operator inspects the dead letter queue). |
| **Componentes involucrados** | `card_worker` (CardWorker), `truenative` (TrueNative), `credit_cards_db` (CreditCardsDb), `card_verification_queue` (CardQueue). |

### SNS email notification

| Requerimiento | RF-006 (store a credit card and notify the owner of the verification result) |
|---|---|
| **Patrón utilizado** | SNS email notification through the `sns_topics` |
| **Justificación** | The acceptance criteria require that the owner be notified by email for every outcome, approved, rejected, or the pending fallback. `card_worker` publishes the result to the SNS email topics, and the topics deliver the notification to the user. The email contains the process result, the basic card data as stored in the database, and the RUV generated by TrueNative. The subscription address comes from the `EMAIL_TO_NOTIFY` key of the `secrets-pipeline-native-map` secret in AWS Secrets Manager, so no address is hardcoded. The producers only publish a message and never handle SMTP or provider credentials. |
| **Atributos de calidad favorecidos** | Decoupling (the producer is isolated from the email delivery mechanism, so the provider can change without touching the worker); Simplicity (the worker publishes a message and the notification is delivered by the platform); Reliability of the notification (the same mandatory email is produced for every outcome). |
| **Atributos de calidad desfavorecidos** | Availability of the notification (while the subscription is not confirmed, SNS discards the messages, and an SNS outage delays or loses the email); Operational step (the subscription confirmation is a manual step that must be documented and repeated in a new environment); Latency of the notification (the email arrives only after the worker finishes the verification and publishes the message). |
| **Componentes involucrados** | `card_worker` (CardWorker), `sns_topics` (SnsTopics). |

## RF-007

The RF-007 flow has three parts: the user creation (synchronous, inside the request), the identity verification callback (asynchronous, initiated by TrueNative through the public webhook), and the token block that applies while the user is not `VERIFICADO`. The patterns below are broken out individually because each one addresses a different stated design constraint: the single host, the 120 second provider commitment, the public and unauthenticated webhook, the rule that only verified users can use the platform, and the mandatory email for every outcome.

### Single entry point / API Gateway routing

| Requerimiento | RF-007 (verify the identity of a user when the user is created) |
|---|---|
| **Patrón utilizado** | Single entry point / API Gateway routing |
| **Justificación** | The client makes exactly one HTTP request to one host. The Ingress routes the request by path prefix to `users_app` for the user creation and for the authentication, and to `user_verification_callback` for the public callback path that TrueNative uses to deliver the result. The client never sees the underlying multi component sequence, which is what the single host and one request per requirement constraint requires. No extra external entry point is introduced: the callback reaches the callback component through the same single host. |
| **Atributos de calidad favorecidos** | Usability (one host and one request per requirement); Modifiability (the internal flow can evolve without changing the client contract); Deployability (each component behind the route deploys independently). |
| **Atributos de calidad desfavorecidos** | Availability (the flow depends on the availability of several components, so one failing link fails the whole flow); Complexity of the routing layer (a routing mistake in the Ingress breaks the requirement that every endpoint group is reachable); Public surface (the callback path is public by design, so the routing must expose it without authentication, which enlarges the attack surface of the host). |
| **Componentes involucrados** | `ingress` (Ingress), `users_app` (UsersApp), `user_verification_callback` (UserVerificationCallback). |

### Asynchronous event driven callback (TrueNative webhook)

| Requerimiento | RF-007 (verify the identity of a user when the user is created) |
|---|---|
| **Patrón utilizado** | Asynchronous event driven callback: the TrueNative webhook (`PATCH` to the public callback path) handled by the dedicated `user_verification_callback` component |
| **Justificación** | TrueNative commits to deliver the identity verification result in no more than 120 seconds through the webhook, and the user creation must not wait for that result: `users_app` stores the user with `status = POR_VERIFICAR`, sends the `POST /native/verify` request with the `user` object, the `userIdentifier`, the `transactionIdentifier`, and the `userWebhook`, stores the returned RUV, and answers `201`. The result arrives later as a `PATCH` initiated by TrueNative. The callback is handled by a separate deployable (`user_verification_callback`) so that `users_app` does not expose an unauthenticated public route and does not mix the webhook verification logic with the user domain rules. The `transactionIdentifier` and the RUV are the correlation keys that the callback uses to resolve the user. The component answers `200` to TrueNative on receipt, as the TrueNative contract requires. This is the event driven seam of the flow: the provider pushes the result, and no component polls or waits. |
| **Atributos de calidad favorecidos** | Responsiveness (the creation request does not wait for the 120 second verification); Scalability (the callback is a stateless web component that scales with the callback volume, and `users_app` never holds a request while waiting for TrueNative); Decoupling (the callback component, the user domain, and the provider evolve and deploy independently); Simplicity (no polling loop, no queue, and no background work in the web components, so the restriction that forbids asyncio, threads, and background tasks in the users web component is respected). |
| **Atributos de calidad desfavorecidos** | Eventual consistency (the user is `POR_VERIFICAR` until the callback arrives, up to 120 seconds after the creation); Availability of the final status (if the callback is lost or fails the integrity check, the user stays `POR_VERIFICAR` until the result is redelivered or fixed); Coupling to the provider contract (the callback body and the `PATCH` method are dictated by TrueNative, so the callback component must evolve with that contract); Complexity (an extra deployable, an extra Ingress route, and a correlation key are introduced to handle one asynchronous step). |
| **Componentes involucrados** | `users_app` (UsersApp), `truenative` (TrueNative), `user_verification_callback` (UserVerificationCallback). |

### Integrity check (SHA256) as the only authorization of the public webhook

| Requerimiento | RF-007 (verify the identity of a user when the user is created) |
|---|---|
| **Patrón utilizado** | Integrity check: the callback verifies that `verifyToken` equals `sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")`, and a message that fails the check is discarded |
| **Justificación** | The webhook is public by design: TrueNative has no authorization mechanism for callbacks, and the endpoint must process `PATCH` and answer `200`. The SHA256 over the secret token, the RUV, and the score is therefore the only protection of the endpoint: it certifies that the message comes from a client that uses the same secret token configured in TrueNative and that it has not been altered. The check is applied before any status change, so a forged or altered message cannot move a user to `VERIFICADO`. The `SECRET_TOKEN` value is stored as a Kubernetes Secret (the `truenative-secret` object, referenced by the manifest through `secretKeyRef`) and is never committed in plaintext; the value is substituted at apply time in both environments. The same check is what the TrueNative documentation recommends for this public webhook. |
| **Atributos de calidad favorecidos** | Security (a message whose token does not match is discarded and no status change is applied, so the public endpoint cannot be abused to verify users); Integrity (the check covers the RUV and the score, so an altered score or a mismatched RUV is detected); Simplicity (the check is a single hash comparison, with no extra infrastructure). |
| **Atributos de calidad desfavorecidos** | Shared secret (the protection depends on a single secret token shared by every client of TrueNative, so a leak of that token weakens every callback); No replay protection (the check certifies the origin and the content, but it does not expire the message, so a captured valid message can in principle be resent); Coupling to the provider contract (the format of the token is dictated by TrueNative, so the check must evolve with that contract). |
| **Componentes involucrados** | `user_verification_callback` (UserVerificationCallback), `truenative` (TrueNative). |

### Data ownership through the users API (no direct database access)

| Requerimiento | RF-007 (verify the identity of a user when the user is created) |
|---|---|
| **Patrón utilizado** | Data ownership through the owning API: the callback updates the user status through the `users_app` API, never through the database |
| **Justificación** | The data ownership rule requires that each application is the exclusive owner of its data and that no other application accesses its storage directly. The callback needs to apply the result of the verification (the status `VERIFICADO` when the score is greater than 60, `NO_VERIFICADO` when the score is 60 or lower, per the team decision documented in the [RF-007 Sequence View](./rf007-sequence-view.md), and the refreshed `updatedAt`), but it does not own the user data. It therefore calls the internal endpoint that `users_app` exposes for this update, so the user record stays in the shared database under the `users_app` schema and the status mapping rule lives in one place. The callback answers `200` to TrueNative only when the update is applied; when the user cannot be resolved by the transaction identifier, the message is discarded and the callback still answers `200`, so TrueNative does not retry a message that will never apply. |
| **Atributos de calidad favorecidos** | Cohesion (the user domain rules, including the score to status mapping, live in a single component); Modifiability (the callback can change without touching the user schema or the user storage); Data consistency (the update goes through the same API that the rest of the system uses, so there is one write path to the user record). |
| **Atributos de calidad desfavorecidos** | Latency (the callback performs an extra HTTP call to `users_app` before it can answer TrueNative); Availability (the callback cannot apply the result when `users_app` is down, and the user stays `POR_VERIFICAR` until the result is redelivered or fixed); Coupling (the callback depends on the internal endpoint contract of `users_app`, which is a new surface between the two components). |
| **Componentes involucrados** | `user_verification_callback` (UserVerificationCallback), `users_app` (UsersApp), `shared_db` (SharedDb). |

### Status based token block in `users_app`

| Requerimiento | RF-007 (verify the identity of a user when the user is created) |
|---|---|
| **Patrón utilizado** | Status based token block: `users_app` no longer generates nor verifies tokens when the user is not in the `VERIFICADO` status |
| **Justificación** | The acceptance criteria require that a user in `POR_VERIFICAR` cannot access the system and that a user in `NO_VERIFICADO` cannot enter the platform, while a user in `VERIFICADO` can use it. The block is implemented in the only component that issues and verifies tokens: `users_app`. A `POST /users/auth` by a user in `POR_VERIFICAR` or `NO_VERIFICADO` is rejected with the existing authentication behavior for credentials it does not accept (`404`), so no token is ever issued to a blocked user. The token verification paths also reject tokens that belong to users who are no longer `VERIFICADO`, so a blocked user cannot keep working with a previously issued token. This is the only modification to `users_app` in this delivery, as the project document allows, and it is what makes the asynchronous result have a real consequence on the platform: the status produced by the callback gates every access. |
| **Atributos de calidad favorecidos** | Security (a user that is not verified cannot obtain a token, and a token issued before a status downgrade stops working); Simplicity (the rule is enforced in a single component, at the point where tokens are issued and verified, without a check in every downstream service); Consistency with the requirement (the three statuses map one to one to the access rule: `POR_VERIFICAR` and `NO_VERIFICADO` are blocked, `VERIFICADO` is allowed). |
| **Atributos de calidad desfavorecidos** | Behavior change for existing clients (the authentication answer for a blocked user is a `404` from the existing behavior, which does not say explicitly that the user is not verified, so the client cannot distinguish a wrong password from a blocked user); Coupling of the access rule to the status (every access to the platform now depends on the verification status, so a callback outage delays the access of new users); Testing burden (the rule must be covered by the unit tests of `users_app`, which are validated by the pipeline with the minimum coverage requirement). |
| **Componentes involucrados** | `users_app` (UsersApp), `shared_db` (SharedDb). |

### SNS email notification

| Requerimiento | RF-007 (verify the identity of a user when the user is created) |
|---|---|
| **Patrón utilizado** | SNS email notification through the `sns_topics` |
| **Justificación** | The acceptance criteria require that the user be notified by email for every outcome, `VERIFICADO` or `NO_VERIFICADO`, including the outcomes that come from the exception flows of the verification request (a `400`, `401`, `403`, or `409` from TrueNative stores the user as `NO_VERIFICADO` and still produces the notification). `user_verification_callback` publishes the result to the SNS email topics, and the topics deliver the notification to the user. The email contains the final status, the RUV generated by TrueNative, and the user data used in the verification process. The subscription address comes from the `EMAIL_TO_NOTIFY` key of the `secrets-pipeline-native-map` secret in AWS Secrets Manager, so no address is hardcoded. The producers only publish a message and never handle SMTP or provider credentials. |
| **Atributos de calidad favorecidos** | Decoupling (the producer is isolated from the email delivery mechanism, so the provider can change without touching the callback); Simplicity (the callback publishes a message and the notification is delivered by the platform); Reliability of the notification (the same mandatory email is produced for every outcome, including the exception flows). |
| **Atributos de calidad desfavorecidos** | Availability of the notification (while the subscription is not confirmed, SNS discards the messages, and an SNS outage delays or loses the email); Operational step (the subscription confirmation is a manual step that must be documented and repeated in a new environment); Latency of the notification (the email arrives only after the callback applies the status and publishes the message). |
| **Componentes involucrados** | `user_verification_callback` (UserVerificationCallback), `sns_topics` (SnsTopics). |

### About the Saga Pattern

The Saga pattern aims to build distributed transactions across multiple microservices and other systems by breaking a given transaction into a sequence of subtransactions and corresponding compensating transactions. All transactions in a Saga either complete successfully, or, in the event of a failure, compensating transactions are executed to roll back all subtransactions.

*Design Patterns for Cloud Native Applications*
*Kasun Indrasiri, Sriskandarajah Suhothayan*