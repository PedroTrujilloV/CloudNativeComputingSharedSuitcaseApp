"""Unit tests for QueryPostUseCase."""

import pytest

from domain.models import (
    Point,
    PostInfo,
    RouteInfo,
)
from domain.use_cases.query_post_use_case import QueryPostUseCase
from errors import (
    OffersServiceUnavailableError,
    RouteNotFoundError,
    RoutesServiceUnavailableError,
)


class MockRoutesPort:
    """Mock Routes service that returns a fixed route."""

    def __init__(self, route_info: RouteInfo | None = None, fail: bool = False):
        self.route_info = route_info or RouteInfo(
            id="r1",
            flightId="FL100",
            origin=Point(airportCode="BOG", country="Colombia"),
            destiny=Point(airportCode="MIA", country="United States"),
            bagCost=25.0,
            plannedStartDate="2026-06-01T10:00:00Z",
            plannedEndDate="2026-06-10T18:00:00Z",
        )
        self.fail = fail

    def get_route(self, route_id: str) -> RouteInfo:
        if self.fail:
            raise RoutesServiceUnavailableError("Routes service down")
        return self.route_info


class MockOffersPort:
    """Mock Offers service that returns offers."""

    def __init__(self, offers: list[dict] | None = None, fail: bool = False):
        self.offers = offers if offers is not None else [
            {
                "id": "o1",
                "userId": "user1",
                "description": "Luggage 23kg",
                "size": 2,
                "fragile": False,
                "offer": 150.0,
                "createdAt": "2026-05-01T10:00:00Z",
            },
        ]
        self.fail = fail

    def get_offers(self, post_id: str) -> list[dict]:
        if self.fail:
            raise OffersServiceUnavailableError("Offers service down")
        return self.offers


class MockScoresPort:
    """Mock Score service that returns configured scores.

    ``raise_for`` simulates a Score service outage: every lookup for
    those offer ids raises, as the real port would when the service is
    temporarily down.
    """

    def __init__(
        self,
        scores: dict[str, float | None] | None = None,
        raise_for: set[str] | None = None,
    ):
        self.scores = scores if scores is not None else {"o1": 4.8}
        self.raise_for = raise_for or set()

    def get_score(self, offer_id: str) -> float | None:
        if offer_id in self.raise_for:
            raise RuntimeError("simulated score service outage")
        return self.scores.get(offer_id)


def make_post(**overrides) -> PostInfo:
    """Build a PostInfo with sensible defaults for the tests."""
    defaults = {
        "id": "post1",
        "userId": "user1",
        "routeId": "r1",
        "expireAt": "2026-07-01T10:00:00Z",
        "plannedStartDate": "2026-06-01T10:00:00Z",
        "plannedEndDate": "2026-06-10T18:00:00Z",
        "createdAt": "2026-05-01T09:00:00Z",
    }
    defaults.update(overrides)
    return PostInfo(**defaults)


def make_offer(oid: str, created_at: str = "2026-05-01T10:00:00Z", **kw) -> dict:
    base = {
        "id": oid,
        "userId": "user1",
        "description": f"Offer {oid}",
        "size": 2,
        "fragile": False,
        "offer": 150.0,
        "createdAt": created_at,
    }
    base.update(kw)
    return base


class TestQueryPostUseCase:
    """Test suite for QueryPostUseCase execute method."""

    def test_execute_returns_correct_response_shape(self):
        """The response must match the documented 200 shape exactly."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(),
            scores=MockScoresPort(),
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )
        data = result.data if hasattr(result, "data") else result
        # Post-level fields from the Posts service view.
        assert data["id"] == "post1"
        assert data["expireAt"] == "2026-07-01T10:00:00Z"
        assert data["plannedStartDate"] == "2026-06-01T10:00:00Z"
        assert data["plannedEndDate"] == "2026-06-10T18:00:00Z"
        assert data["createdAt"] == "2026-05-01T09:00:00Z"
        # Route and offers.
        assert "route" in data
        assert "offers" in data
        assert data["route"]["id"] == "r1"
        assert data["route"]["flightId"] == "FL100"
        assert len(data["offers"]) == 1
        offer = data["offers"][0]
        assert offer["id"] == "o1"
        assert offer["score"] == 4.8
        for key in ("id", "userId", "description", "size", "fragile",
                    "offer", "score", "createdAt"):
            assert key in offer

    def test_execute_with_null_scores_returns_none_for_score(self):
        """When the score service returns no score, the offer's score should be None."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(),
            scores=MockScoresPort(scores={}),  # No score for o1
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )

        data = result.data if hasattr(result, "data") else result
        assert len(data["offers"]) == 1
        assert data["offers"][0]["score"] is None

    def test_score_service_outage_degrades_to_null_per_offer(self):
        """A down Score service must not fail the request.

        Every offer of the response is returned with ``score: null``
        and the rest of the payload (route, post fields, offer fields)
        is unaffected.
        """
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(
                offers=[make_offer("o1"), make_offer("o2")]
            ),
            scores=MockScoresPort(raise_for={"o1", "o2"}),
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )
        data = result.data
        assert data["route"]["id"] == "r1"
        assert [o["score"] for o in data["offers"]] == [None, None]
        assert len(data["offers"]) == 2

    def test_score_failure_isolated_to_single_offer(self):
        """One failing score must not affect the scores of other offers."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(
                offers=[make_offer("o1"), make_offer("o2")]
            ),
            scores=MockScoresPort(
                scores={"o2": 3.2}, raise_for={"o1"}
            ),
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )
        by_id = {o["id"]: o for o in result.data["offers"]}
        assert by_id["o1"]["score"] is None
        assert by_id["o2"]["score"] == 3.2

    def test_execute_sorts_offers_descending_by_score(self):
        """Offers should be sorted descending by score (nulls last)."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(
                offers=[
                    make_offer("o1", created_at="2026-05-01T10:00:00Z"),
                    make_offer("o2", created_at="2026-05-02T10:00:00Z"),
                ]
            ),
            scores=MockScoresPort(scores={"o1": 4.8, "o2": 3.2}),
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )

        data = result.data if hasattr(result, "data") else result
        assert len(data["offers"]) == 2
        # o1 should come first (higher score 4.8 > 3.2)
        assert data["offers"][0]["id"] == "o1"
        assert data["offers"][0]["score"] == 4.8

    def test_execute_with_empty_offers_returns_empty_list(self):
        """When no offers exist, the response should have an empty offers list."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(offers=[]),
            scores=MockScoresPort(),
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )

        data = result.data if hasattr(result, "data") else result
        assert len(data["offers"]) == 0
        # Route should still be present
        assert data["route"]["id"] == "r1"

    def test_execute_sorts_null_scores_last(self):
        """Offers with null scores should appear after those with valid scores."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(
                offers=[
                    make_offer(
                        "o1",
                        created_at="2026-05-01T10:00:00Z",
                        description="Has score",
                    ),
                    make_offer(
                        "o2",
                        created_at="2026-05-02T10:00:00Z",
                        description="No score",
                    ),
                ]
            ),
            scores=MockScoresPort(scores={"o1": 4.8}),  # o2 has no score
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )

        data = result.data if hasattr(result, "data") else result
        assert data["offers"][0]["id"] == "o1"  # Has score comes first
        assert data["offers"][1]["id"] == "o2"  # No score comes last
        assert data["offers"][1]["score"] is None

    def test_sort_ties_broken_by_created_at_descending(self):
        """Offers with equal scores (or equal nulls) sort by createdAt desc."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(
                offers=[
                    make_offer("o_old", created_at="2026-05-01T10:00:00Z"),
                    make_offer("o_new", created_at="2026-05-02T10:00:00Z"),
                ]
            ),
            scores=MockScoresPort(scores={}),  # both null
        )
        result = use_case.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )
        assert [o["id"] for o in result.data["offers"]] == ["o_new", "o_old"]

        use_case2 = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(
                offers=[
                    make_offer("o_old", created_at="2026-05-01T10:00:00Z"),
                    make_offer("o_new", created_at="2026-05-02T10:00:00Z"),
                ]
            ),
            scores=MockScoresPort(scores={"o_old": 4.0, "o_new": 4.0}),
        )
        result2 = use_case2.execute(
            post=make_post(), post_id="post1", route_id="r1"
        )
        assert [o["id"] for o in result2.data["offers"]] == ["o_new", "o_old"]

    def test_routes_service_down_raises_unavailable(self):
        """An unreachable Routes service fails the request (503 upstream)."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(fail=True),
            offers=MockOffersPort(),
            scores=MockScoresPort(),
        )
        with pytest.raises(RoutesServiceUnavailableError):
            use_case.execute(post=make_post(), post_id="post1", route_id="r1")

    def test_missing_route_record_fails_request(self):
        """A route that does not exist is a hard dependency failure (503 upstream)."""

        class MissingRoutesPort(MockRoutesPort):
            def get_route(self, route_id: str) -> RouteInfo:
                raise RouteNotFoundError(f"Route {route_id} does not exist")

        use_case = QueryPostUseCase(
            routes=MissingRoutesPort(),
            offers=MockOffersPort(),
            scores=MockScoresPort(),
        )
        with pytest.raises(RouteNotFoundError):
            use_case.execute(post=make_post(), post_id="post1", route_id="missing")

    def test_offers_service_down_raises_unavailable(self):
        """An unreachable Offers service fails the request (503 upstream)."""
        use_case = QueryPostUseCase(
            routes=MockRoutesPort(),
            offers=MockOffersPort(fail=True),
            scores=MockScoresPort(),
        )
        with pytest.raises(OffersServiceUnavailableError):
            use_case.execute(post=make_post(), post_id="post1", route_id="r1")
