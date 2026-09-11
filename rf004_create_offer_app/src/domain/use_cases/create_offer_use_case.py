"""Create offer use case for RF-004.

Orchestrates the full offer creation flow:
1. Call POST /offers to persist the offer (hard dependency; an
   unreachable service propagates as a 503 with no write behind it).
2. Fetch route data (via Routes service) and calculate the score using
   the confirmed formula.
3. Persist the score via POST /scores.

Consistency (saga compensation, see ``docs/solution-patterns.md``):
  The flow performs two writes on two independently owned stores (Offers,
  Scores) with no distributed transaction. Because the offer is the first
  write, every failure that happens after it (an unreachable Routes
  service, a missing route, or an unreachable Scores service) triggers
  the compensating action (delete the just created offer) so the system
  ends consistent: either both writes exist or neither does. The original
  error still reaches the client (503 with the standard message, or the
  documented 404 for a missing route). A failed compensation is logged,
  not fatal: the original error is what the client receives.
"""

import logging

from domain.models.post import PostInfo
from domain.models.route import RouteInfo
from domain.models.schemas import RF004CreateOfferRequest
from domain.ports.offers_port import OffersPort
from domain.ports.routes_port import RoutesPort
from domain.ports.scores_port import ScoresPort
from errors import (
    OffersServiceUnavailableError,
    RouteNotFoundError,
    RoutesServiceUnavailableError,
    ScoresServiceUnavailableError,
)

logger = logging.getLogger("rf004_create_offer_app")

# Bag occupancy percentage by package size (Entrega 1 glossary).
_BAG_OCCUPANCY = {
    "LARGE": 1.0,
    "MEDIUM": 0.5,
    "SMALL": 0.25,
}


def _calculate_score(offer_amount: float, size: str, bag_cost: float) -> float:
    """Calculate the utility score for an offer.

    Formula (Entrega 1 glossary):
        utilidad = offer amount - (bag occupancy % x route bagCost)

    Args:
        offer_amount: The offered price from the request.
        size: Package size (LARGE, MEDIUM, SMALL).
        bag_cost: The route's bag cost.

    Returns:
        The computed utility score.
    """
    occupancy = _BAG_OCCUPANCY[size]
    return offer_amount - (occupancy * bag_cost)


class CreateOfferUseCase:
    """Orchestrate the full RF-004 offer creation flow."""

    def __init__(
        self,
        offers: OffersPort,
        routes: RoutesPort | None = None,
        scores: ScoresPort | None = None,
    ):
        self.offers = offers
        self.routes = routes
        self.scores = scores

    def execute(
        self,
        post: PostInfo,
        user_id: str,
        payload: RF004CreateOfferRequest,
    ) -> dict:
        """Execute the full offer creation flow.

        1. Create the offer via POST /offers (through OffersPort).
        2. Fetch route data for score calculation (if routes port
           available) and calculate the score value.
        3. Persist the score via ScoresPort.

        Offers is a hard dependency: its unavailable error propagates to
        the router (503) and no write has happened yet, so nothing is
        left behind. The route fetch and the score stage run AFTER the
        offer was persisted, so when either of them fails with an
        integration error the orchestrator compensates (deletes the just
        created offer) before propagating the original error: the flow
        ends consistent (either both writes exist or neither does). A
        missing route (business 404) is compensated the same way and the
        404 still reaches the client, so the documented contract is
        preserved.

        Returns:
            A dict with keys: id, userId, createdAt, postId,
            score_persisted.
        """
        # Step 1: Create the offer through the Offers service API. When
        # the Offers service is unreachable the error propagates to the
        # router (503) and the write never happened: nothing to
        # compensate.
        result = self.offers.create_offer(
            postId=post.id,
            userId=user_id,
            description=payload.description,
            size=payload.size,
            fragile=payload.fragile,
            offer=payload.offer,
        )

        offer_id = result["id"]
        user_id_result = result["userId"]
        created_at = result["createdAt"]

        score_value = None

        if self.routes is not None:
            # Step 2: fetch the route data and calculate the score. This
            # runs after the offer was persisted, so a failure here
            # (integration or business) is compensated: the just created
            # offer is deleted and the original error propagates to the
            # router (503 for an unreachable Routes service, 404 for a
            # missing route).
            try:
                route_info = self.routes.get_route(post.routeId)
            except (RoutesServiceUnavailableError, RouteNotFoundError):
                self._compensate_offer(offer_id)
                raise

            score_value = _calculate_score(
                offer_amount=payload.offer,
                size=payload.size,
                bag_cost=route_info.bagCost,
            )

        score_persisted = False

        # Step 3: Persist the score. An integration failure here is
        # compensated: the just created offer is deleted so the flow ends
        # consistent (either both writes exist or neither does), and the
        # original error propagates to the router (503).
        if self.scores is not None and score_value is not None:
            try:
                self.scores.upsert_score(
                    offer_id=offer_id,
                    score_value=score_value,
                )
                score_persisted = True
            except ScoresServiceUnavailableError:
                self._compensate_offer(offer_id)
                raise

        return {
            "id": offer_id,
            "userId": user_id_result,
            "createdAt": created_at,
            "postId": post.id,
            "score_persisted": score_persisted,
        }

    def _compensate_offer(self, offer_id: str) -> None:
        """Compensate a partial failure after the offer was persisted.

        The offer created by this request is deleted through the Offers
        service public API (``DELETE /offers/{id}``), reusing the owning
        service's own contract. It is called when the route fetch or the
        score stage fails after the offer write. A compensation failure
        is logged (the Offers service is down too) and swallowed: the
        original error (503, or the documented 404 for a missing route)
        is what the client receives.
        """
        logger.warning(
            "RF004: score persistence failed; compensating by deleting "
            "newly created offer %s",
            offer_id,
        )
        try:
            self.offers.delete_offer(offer_id)
        except OffersServiceUnavailableError:
            logger.error(
                "RF004: compensation FAILED for offer %s: the Offers "
                "service is unreachable; an orphaned offer may remain "
                "until the service recovers (it is null-safe in RF-005: "
                "a score-less offer simply reads as null)",
                offer_id,
            )
        else:
            logger.info("RF004: compensation succeeded, offer %s deleted", offer_id)
