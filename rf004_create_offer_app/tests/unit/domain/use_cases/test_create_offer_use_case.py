"""Unit tests for the CreateOfferUseCase (RF-004 offer creation stage)."""

from datetime import datetime, timezone

import pytest

from domain.models.post import PostInfo
from domain.models.route import RouteInfo
from domain.models.schemas import RF004CreateOfferRequest
from domain.ports.offers_port import FakeOffers
from domain.ports.routes_port import RoutesPort
from domain.ports.scores_port import FakeScores, ScoresPort
from domain.use_cases.create_offer_use_case import (
    CreateOfferUseCase,
    _calculate_score,
)
from errors import RoutesServiceUnavailableError, ScoresServiceUnavailableError


VALID_PAYLOAD = RF004CreateOfferRequest(
    description="Space for one medium bag",
    size="MEDIUM",
    fragile=False,
    offer=50000.0,
)

VALID_POST = PostInfo(
    id="post-1",
    routeId="route-1",
    userId="owner-1",
    expireAt=datetime.now(timezone.utc).replace(year=2099, tzinfo=timezone.utc),
)


class FakeRoutes:
    """Fake Routes service."""

    def __init__(self, route_info: RouteInfo | None = None):
        self.route_info = route_info or RouteInfo(id="route-1", bagCost=10000.0)
        self.get_calls: list[str] = []

    def get_route(self, route_id: str) -> RouteInfo:
        self.get_calls.append(route_id)
        return self.route_info


def test_calculate_score_large():
    """LARGE: occupancy is 100%."""
    score = _calculate_score(offer_amount=50000.0, size="LARGE", bag_cost=10000.0)
    assert score == 40000.0


def test_calculate_score_medium():
    """MEDIUM: occupancy is 50%."""
    score = _calculate_score(offer_amount=50000.0, size="MEDIUM", bag_cost=10000.0)
    assert score == 45000.0


def test_calculate_score_small():
    """SMALL: occupancy is 25%."""
    score = _calculate_score(offer_amount=50000.0, size="SMALL", bag_cost=10000.0)
    assert score == 47500.0


def test_execute_success_no_routes():
    """When no routes port is provided, the offer is created but score is not calculated."""
    offers = FakeOffers(offer_result={"id": "offer-1", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})
    use_case = CreateOfferUseCase(offers=offers, routes=None, scores=None)

    result = use_case.execute(post=VALID_POST, user_id="user-1", payload=VALID_PAYLOAD)

    assert result["id"] == "offer-1"
    assert result["postId"] == "post-1"
    assert offers.create_calls


def test_execute_success_with_routes_and_scores():
    """Full flow: create offer, calculate score, persist score."""
    offers = FakeOffers(offer_result={"id": "offer-1", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})
    routes = FakeRoutes(route_info=RouteInfo(id="route-1", bagCost=10000.0))
    scores = FakeScores(upsert_result={"offerId": "offer-1", "score": 45000.0})

    use_case = CreateOfferUseCase(offers=offers, routes=routes, scores=scores)

    result = use_case.execute(post=VALID_POST, user_id="user-1", payload=VALID_PAYLOAD)

    assert result["id"] == "offer-1"
    assert offers.create_calls
    assert routes.get_calls == ["route-1"]
    assert scores.upsert_calls == [{"offerId": "offer-1", "score": 45000.0}]


def test_execute_with_large_size_calculates_correct_score():
    """LARGE size with bagCost=10000: score = 50000 - (1.0 * 10000) = 40000."""
    offers = FakeOffers(offer_result={"id": "offer-2", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})
    routes = FakeRoutes(route_info=RouteInfo(id="route-1", bagCost=10000.0))
    scores = FakeScores()

    payload_large = RF004CreateOfferRequest(
        description="Space for one large bag",
        size="LARGE",
        fragile=True,
        offer=50000.0,
    )
    use_case = CreateOfferUseCase(offers=offers, routes=routes, scores=scores)

    result = use_case.execute(post=VALID_POST, user_id="user-1", payload=payload_large)

    assert offers.create_calls
    expected_score = 50000.0 - (1.0 * 10000.0)
    assert scores.upsert_calls == [{"offerId": "offer-2", "score": expected_score}]


def test_execute_small_size_calculates_correct_score():
    """SMALL size with bagCost=10000: score = 50000 - (0.25 * 10000) = 47500."""
    offers = FakeOffers(offer_result={"id": "offer-3", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})
    routes = FakeRoutes(route_info=RouteInfo(id="route-1", bagCost=10000.0))
    scores = FakeScores()

    payload_small = RF004CreateOfferRequest(
        description="Space for one small bag",
        size="SMALL",
        fragile=False,
        offer=50000.0,
    )
    use_case = CreateOfferUseCase(offers=offers, routes=routes, scores=scores)

    result = use_case.execute(post=VALID_POST, user_id="user-1", payload=payload_small)

    expected_score = 50000.0 - (0.25 * 10000.0)
    assert scores.upsert_calls == [{"offerId": "offer-3", "score": expected_score}]


def test_execute_routes_unavailable_hard_fails():
    """When the Routes service is unavailable, the error propagates (the router answers 503)."""
    offers = FakeOffers(offer_result={"id": "offer-4", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})

    class FailingRoutes:
        get_calls = []
        def get_route(self, route_id):
            raise RoutesServiceUnavailableError("down")

    scores = FakeScores()
    use_case = CreateOfferUseCase(offers=offers, routes=FailingRoutes(), scores=scores)

    with pytest.raises(RoutesServiceUnavailableError):
        use_case.execute(post=VALID_POST, user_id="user-1", payload=VALID_PAYLOAD)

    # The offer was never created and no score was persisted.
    assert offers.create_calls == []
    assert scores.upsert_calls == []


def test_execute_scores_unavailable_compensates_and_propagates():
    """When Scores is unavailable after the offer was created, the offer is deleted (compensation) and the error propagates (503 at the router)."""
    offers = FakeOffers(offer_result={"id": "offer-5", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})
    routes = FakeRoutes(route_info=RouteInfo(id="route-1", bagCost=10000.0))

    class FailingScores:
        upsert_calls = []
        def upsert_score(self, offer_id, score_value):
            raise ScoresServiceUnavailableError("down")

    use_case = CreateOfferUseCase(offers=offers, routes=routes, scores=FailingScores())

    with pytest.raises(ScoresServiceUnavailableError):
        use_case.execute(post=VALID_POST, user_id="user-1", payload=VALID_PAYLOAD)

    # The offer was created and then compensated (deleted): no orphan remains.
    assert offers.create_calls
    assert offers.delete_calls == ["offer-5"]


def test_execute_scores_unavailable_compensation_failure_is_swallowed():
    """When both Scores and Offers are down, the compensation failure is swallowed and the original Scores error propagates."""
    from errors import OffersServiceUnavailableError

    class FailingOffers(FakeOffers):
        def delete_offer(self, offer_id):
            self.delete_calls.append(offer_id)
            raise OffersServiceUnavailableError("down")

    offers = FailingOffers(offer_result={"id": "offer-6", "userId": "user-1", "createdAt": datetime.now(timezone.utc).isoformat()})
    routes = FakeRoutes(route_info=RouteInfo(id="route-1", bagCost=10000.0))

    class FailingScores:
        upsert_calls = []
        def upsert_score(self, offer_id, score_value):
            raise ScoresServiceUnavailableError("down")

    use_case = CreateOfferUseCase(offers=offers, routes=routes, scores=FailingScores())

    with pytest.raises(ScoresServiceUnavailableError):
        use_case.execute(post=VALID_POST, user_id="user-1", payload=VALID_PAYLOAD)

    assert offers.create_calls
    assert offers.delete_calls == ["offer-6"]
