"""Aggregation use case for RF-005 Query Post endpoint.

After all auth/authorization gates pass, this orchestrator fetches the
post's route, its offers and the scores for each offer, then returns
a data structure shaped exactly per the API contract:

    200 OK: {
      "data": {
        "id": "...", "expireAt": "...",
        "plannedStartDate": "...", "plannedEndDate": "...",
        "createdAt": "...",
        "route": {"id": "...", "flightId": "...",
                   "origin": {"airportCode": "...", "country": "..."},
                   "destiny": {"airportCode": "...", "country": "..."},
                   "bagCost": ..., "plannedStartDate": "...",
                   "plannedEndDate": "..."}},
        "offers": [
          {"id": "...", "userId": "...", "description": "...",
           "size": 2, "fragile": false, "offer": 150.0,
           "score": 4.8, "createdAt": "..."},
        ]
      }
    }

Resilience (explicit RF-005 requirement): the Score service "puede no
ser consistente en el tiempo", so a score that is missing or whose
lookup fails (service down, timeout, 5xx) is reported as
``"score": null`` for that offer only. The request still returns 200
and the rest of the response is unaffected.

Sorting choice (documented team decision): offers are sorted
descending by score; offers with a null score are always ordered after
offers with a score, and ties (same score, or multiple nulls) are
broken by ``createdAt`` descending (most recent offer first).
"""

from domain.models import (
    OfferInfo,
    Point,
    PostInfo,
    QueryPostResponse,
    RouteInfo,
)
from domain.ports.offers_port import OffersPort
from domain.ports.routes_port import RoutesPort
from domain.ports.scores_port import ScoresPort
from errors import OffersServiceUnavailableError

import logging

logger = logging.getLogger("rf005_query_post_app")


class QueryPostUseCase:
    """Aggregate post + route + offers (with scores) for RF-005."""

    def __init__(
        self,
        routes: RoutesPort,
        offers: OffersPort,
        scores: ScoresPort,
    ):
        self._routes = routes
        self._offers = offers
        self._scores = scores

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self, *, post: PostInfo, post_id: str, route_id: str | None
    ) -> QueryPostResponse:
        """Aggregate the full response for the post identified by *post_id*.

        Steps:
          1. Fetch route from Routes service (hard dependency → 503 on
             network failure; a missing route also fails the request
             with 503, per the RF-005 sequence view: the Routes service
             is a hard dependency of the aggregation).
          2. Fetch offers for `post_id` via OffersPort (hard dependency
             → 503 on network failure).
          3. For each offer, fetch its score (per-item resilience → None
             on failure, so one bad score never blocks the response).
          4. Sort descending by score (nulls last), ties by createdAt desc.
          5. Build and return the shaped response dict.

        Raises:
            RoutesServiceUnavailableError: Routes service unreachable or
                the referenced route does not exist (503).
            OffersServiceUnavailableError: Offers service unreachable (503).
        """
        # 0. Resolve route info from Routes service (hard dependency:
        #    an unreachable Routes service, or a route that does not
        #    exist, fails the request with 503 per the RF-005 contract).
        route_info = self._routes.get_route(route_id) if route_id else RouteInfo(
            id="",
            flightId="",
            origin=Point(airportCode="", country=""),
            destiny=Point(airportCode="", country=""),
            bagCost=0,
            plannedStartDate="",
            plannedEndDate="",
        )

        # 1. Fetch offers (hard dependency: unreachable → 503).
        try:
            offers_raw = self._offers.get_offers(post_id)
        except OffersServiceUnavailableError:
            raise

        # 2. Fetch scores per offer (per-item resilience → None per-offer).
        # The Scores port contract already degrades every failure to
        # None; the broad catch here is defense in depth, so that NO
        # score-related failure can ever escape the per-offer loop and
        # fail the whole request (RF-005 resilience requirement).
        enriched: list[OfferInfo] = []
        for off in offers_raw:
            try:
                score_value = self._scores.get_score(off["id"])
            except Exception as exc:
                logger.warning(
                    "Score unavailable for offer %s: %s. "
                    "Returning score null for this offer.",
                    off["id"],
                    exc,
                )
                score_value = None
            offer_info = OfferInfo(
                id=str(off["id"]),
                userId=str(off["userId"]),
                description=off["description"],
                size=off["size"],
                fragile=bool(off.get("fragile", False)),
                offer=float(off["offer"]),
                score=score_value,
                createdAt=off.get("createdAt"),
            )
            enriched.append(offer_info)

        # 3. Sort descending by score (nulls last), ties by createdAt desc.
        enriched = self._sort_offers(enriched)

        # 4. Build the shaped response dict (exactly per contract).
        # The post-level fields (id, expireAt, plannedStartDate,
        # plannedEndDate, createdAt) come from the Posts service view
        # resolved by the ownership gate.
        data = {
            "id": post.id,
            "expireAt": post.expireAt,
            "plannedStartDate": post.plannedStartDate,
            "plannedEndDate": post.plannedEndDate,
            "createdAt": post.createdAt,
        }

        route_data = {
            "id": route_info.id,
            "flightId": route_info.flightId,
            "origin": {
                "airportCode": route_info.origin.airportCode,
                "country": route_info.origin.country,
            },
            "destiny": {
                "airportCode": route_info.destiny.airportCode,
                "country": route_info.destiny.country,
            },
            "bagCost": route_info.bagCost,
            "plannedStartDate": route_info.plannedStartDate,
            "plannedEndDate": route_info.plannedEndDate,
        }

        offers_data = [self._offer_to_dict(off) for off in enriched]

        data["route"] = route_data
        data["offers"] = offers_data

        return QueryPostResponse(data=data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_offers(offers: list[OfferInfo]) -> list[OfferInfo]:
        """Sort descending by score (nulls last), ties by createdAt desc."""
        # Use a two-step stable sort: first by createdAt desc,
        # then by score descending.
        sorted_offers = sorted(
            offers,
            key=lambda o: o.createdAt or "",
            reverse=True,  # ties broken by most recent createdAt first
        )
        sorted_offers = sorted(
            sorted_offers,
            key=lambda o: float("inf") if o.score is None else -o.score,
        )
        return sorted_offers

    @staticmethod
    def _offer_to_dict(offer: OfferInfo) -> dict:
        """Convert an OfferInfo domain model into the response dict."""
        return {
            "id": offer.id,
            "userId": offer.userId,
            "description": offer.description,
            "size": offer.size,
            "fragile": offer.fragile,
            "offer": offer.offer,
            "score": offer.score,
            "createdAt": offer.createdAt,
        }
