# Solution Patterns per Requirement

The following table documents the architectural pattern applied to each functional requirement, per the required format. All three requirements share the same core pattern (orchestration via a dedicated per-requirement service, exposed through a single Ingress entry point), but are broken out individually below since each has distinct trade-offs given its own failure modes and consistency needs.
Here you go:

## RF-003

| Aspect | Details |
|---|---|
| **Pattern Used** | Orchestrator / Saga (choreographed via a dedicated orchestrating service), fronted by an API Gateway / Ingress routing pattern |
| **Justification** | The client must make exactly one HTTP request to create a post, but the operation requires coordinating two independently owned services (Routes, Posts) that cannot be merged or directly coupled without violating the "each app owns its own data" constraint. A dedicated orchestrator service composes these calls server-side, so the client never sees the underlying multi-service sequence. Because the operation spans two data stores with no distributed transaction available, a saga-style approach (proceed sequentially, compensate/report failure on partial completion) is used to keep the system consistent without requiring a shared database transaction across services. |
| **Favored Quality Attributes** | Modifiability (Routes/Posts can evolve independently without touching the client contract); Deployability (each service still ships independently); Simplicity for the client (one request, one response, no client-side orchestration logic); Testability (the orchestration logic is isolated and independently testable from the underlying services) |
| **Disadvantaged Quality Attributes** | Availability (the request now depends on the availability of two downstream services instead of one—one link failing fails the whole operation, mitigated by returning 503 rather than silently succeeding); Latency (sequential calls to Routes then Posts add round-trip time compared to a single local write); Consistency complexity (without a distributed transaction, a partial failure requires explicit compensating logic or a documented acceptance of eventual/best-effort consistency, adding design and testing burden) |
| **Components Involved** | `rf003_create_post_app` (RF003App), `users_app`, `routes_app`, `posts_app`, `ingress` (Ingress) |

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

| Aspect | Details |
|---|---|
| **Pattern Used** | Orchestrator / Saga (choreographed via a dedicated orchestrating service) with a Bulkhead-style resilience pattern applied to the Score dependency |
| **Justification** | Creating an offer requires coordinating three services (Posts for validation, Offers for persistence, Scores for the calculated utility value) behind one client request. The Score value is explicitly documented as potentially unavailable/inconsistent over time, so the orchestrator isolates the Score call from the rest of the flow (a bulkhead)—a Score-service failure does not sink offer creation itself, only leaves the score temporarily undefined, consistent with the explicit resilience requirement in the project document. |
| **Favored Quality Attributes** | Resilience (the core business outcome—the offer existing—survives a Score-service outage); Modifiability (Score can be redesigned, rescaled, or even temporarily disabled without breaking offer creation); Availability of the primary use case (offer creation succeeds independently of a non-critical dependency) |
| **Disadvantaged Quality Attributes** | Consistency (an offer can transiently exist with no associated score, which is an accepted eventual-consistency trade-off rather than strict atomicity); Latency (three sequential downstream calls plus a local score computation step add round-trip time); Complexity (the orchestrator must distinguish "hard" failures that should fail the whole request—for example, Posts/Offers unreachable—from "soft" failures that should degrade gracefully—Scores unreachable—which is more logic than a naive fail-everything approach) |
| **Components Involved** | `rf004_create_offer_app` (RF004App), `users_app`, `posts_app`, `routes_app`, `offers_app`, `scores_app` (ScoresApp), `ingress` (Ingress) |

## RF-005

| Aspect | Details |
|---|---|
| **Pattern Used** | Orchestrator / API Composition pattern, with a per-item resilience/fallback pattern applied to the Score lookups |
| **Justification** | Querying a post requires aggregating data from four services (Users for authorization, Posts, Routes, Offers) into one response, plus a Score lookup per offer. This is a read-side composition, not a write-side saga—there is no state to roll back, only data to gather and merge. The per-offer fallback (returning `null` for an individual offer's score rather than failing the whole response) is required explicitly by the project document and is implemented as a per-item resilience pattern within the composition, so a single unavailable score never blocks the rest of the response. |
| **Favored Quality Attributes** | Resilience (the response degrades gracefully at the level of an individual offer rather than failing entirely); Usability (the client always gets the post and its offers, even under partial backend degradation); Separation of concerns (each underlying service remains solely responsible for its own data; the composition logic lives only in the orchestrator, not duplicated elsewhere) |
| **Disadvantaged Quality Attributes** | Latency (the highest fan-out of the three requirements—one call each to Users, Posts, Routes, Offers, plus one Score call per offer—makes this the slowest of the three endpoints, especially as the number of offers on a post grows); Availability under multiple simultaneous outages (unlike Score, Posts/Routes/Offers are treated as hard dependencies here—if any of them is down, the whole request fails, since there is no meaningful "partial post" to return); Complexity of ordering (sorting offers descending by a value that may be `null` for some entries requires an explicit, documented tie-breaking rule) |
| **Components Involved** | `rf005_query_post_app` (RF005App), `users_app`, `posts_app`, `routes_app`, `offers_app`, `scores_app` (ScoresApp), `ingress` (Ingress) |


### About the Bulkhead Pattern

The Bulkhead pattern is a critical software resilience design pattern that isolates application resources into independent pools or compartments. This structure ensures that if one component fails or becomes overloaded, the remaining parts of the system continue to function normally, effectively preventing a cascading system crash.

[Wikipedia, Bulkhead_pattern](https://en.wikipedia.org/wiki/Bulkhead_pattern)

### About the Saga Pattern

The Saga pattern aims to build distributed transactions across multiple microservices and other systems by breaking a given transaction into a sequence of subtransactions and corresponding compensating transactions. All transactions in a Saga either complete successfully, or, in the event of a failure, compensating transactions are executed to roll back all subtransactions.

*Design Patterns for Cloud Native Applications*
*Kasun Indrasiri, Sriskandarajah Suhothayan*