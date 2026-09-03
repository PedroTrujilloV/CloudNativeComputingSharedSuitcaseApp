"""Unit tests for the CreatePostUseCase orchestration."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.models.route import RouteInfo
from domain.models.schemas import Airport, RF003CreatePostRequest
from domain.ports.posts_port import CreatedPost
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.create_post_use_case import CreatePostUseCase
from errors import (
    DuplicatePostError,
    ExpireAtInvalidError,
    PostsServiceUnavailableError,
    RouteDatesInvalidError,
    RoutesServiceUnavailableError,
)


def make_payload(**overrides) -> RF003CreatePostRequest:
    data = {
        "flightId": "AA001",
        "expireAt": datetime(2026, 9, 15, 10, 0),
        "plannedStartDate": datetime(2026, 10, 1, 10, 0),
        "plannedEndDate": datetime(2026, 10, 2, 10, 0),
        "origin": Airport(airportCode="BOG", country="Colombia"),
        "destiny": Airport(airportCode="MAD", country="Spain"),
        "bagCost": 350,
    }
    data.update(overrides)
    return RF003CreatePostRequest(**data)


class StubRoutes:
    def __init__(
        self,
        existing=None,
        created=None,
        find_error=None,
        create_error=None,
        delete_error=None,
    ):
        self.existing = existing
        self.created = created
        self.find_error = find_error
        self.create_error = create_error
        self.delete_error = delete_error
        self.find_calls: list[str] = []
        self.create_calls: list[dict] = []
        self.delete_calls: list[str] = []

    def find_by_flight_id(self, flight_id: str) -> RouteInfo | None:
        self.find_calls.append(flight_id)
        if self.find_error:
            raise self.find_error
        return self.existing

    def create_route(self, **kwargs) -> RouteInfo:
        self.create_calls.append(kwargs)
        if self.create_error:
            raise self.create_error
        return self.created

    def delete_route(self, route_id: str) -> None:
        self.delete_calls.append(route_id)
        if self.delete_error:
            raise self.delete_error


class StubPosts:
    def __init__(
        self, has_post=False, created=None, check_error=None, create_error=None
    ):
        self.has_post = has_post
        self.created = created
        self.check_error = check_error
        self.create_error = create_error
        self.check_calls: list[tuple[str, str]] = []
        self.create_calls: list[dict] = []

    def has_post_for_route_and_owner(self, route_id: str, owner_id: str) -> bool:
        self.check_calls.append((route_id, owner_id))
        if self.check_error:
            raise self.check_error
        return self.has_post

    def create_post(self, **kwargs) -> CreatedPost:
        self.create_calls.append(kwargs)
        if self.create_error:
            raise self.create_error
        return self.created


def make_user() -> AuthenticatedUser:
    return AuthenticatedUser(id=str(uuid4()), username="tester")


def test_creates_route_then_post_and_shapes_response():
    route = RouteInfo(
        id="route-1",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0),
        createdAt=datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc),
    )
    created = CreatedPost(
        id="post-1",
        userId="u-1",
        createdAt=datetime(2026, 9, 2, 9, 5, tzinfo=timezone.utc),
    )
    routes = StubRoutes(created=route)
    posts = StubPosts(created=created)
    user = AuthenticatedUser(id="u-1", username="t")
    payload = make_payload()

    result = CreatePostUseCase(routes=routes, posts=posts).execute(user, payload)

    assert result["msg"] == "Publicación creada exitosamente."
    assert result["data"] == {
        "id": "post-1",
        "userId": "u-1",
        "createdAt": "2026-09-02T09:05:00+00:00",
        "expireAt": "2026-09-15T10:00:00",
        "route": {"id": "route-1", "createdAt": "2026-09-02T09:00:00+00:00"},
    }
    # The route was created with the submitted values.
    assert routes.find_calls == ["AA001"]
    assert routes.create_calls[0]["source_airport_code"] == "BOG"
    assert routes.create_calls[0]["bag_cost"] == 350
    # The post was created for the resolved route and the authenticated user.
    assert posts.check_calls == [("route-1", "u-1")]
    assert posts.create_calls[0]["route_id"] == "route-1"
    assert posts.create_calls[0]["user_id"] == "u-1"
    assert posts.create_calls[0]["expire_at"] == payload.expireAt


def test_reuses_existing_route_and_discards_submitted_values():
    existing = RouteInfo(
        id="route-9",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0),
        createdAt=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    created = CreatedPost(
        id="post-2", userId="u-1", createdAt=datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    routes = StubRoutes(existing=existing)
    posts = StubPosts(created=created)
    user = AuthenticatedUser(id="u-1", username="t")
    payload = make_payload(bagCost=999, origin=Airport(airportCode="MAD", country="X"))

    result = CreatePostUseCase(routes=routes, posts=posts).execute(user, payload)

    assert routes.create_calls == []  # no route creation
    assert posts.create_calls[0]["route_id"] == "route-9"
    assert result["data"]["route"]["id"] == "route-9"
    assert result["data"]["route"]["createdAt"] == "2026-08-01T00:00:00+00:00"


def test_route_dates_invalid_is_surfaced():
    routes = StubRoutes(create_error=RouteDatesInvalidError("x"))
    posts = StubPosts()

    with pytest.raises(RouteDatesInvalidError):
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )

    assert posts.check_calls == []
    assert posts.create_calls == []


def test_routes_find_unavailable_is_surfaced():
    routes = StubRoutes(find_error=RoutesServiceUnavailableError("x"))
    posts = StubPosts()

    with pytest.raises(RoutesServiceUnavailableError):
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )

    assert posts.create_calls == []


def test_expire_at_in_past_is_rejected():
    routes = StubRoutes(
        created=RouteInfo(
            id="r1",
            flightId="AA001",
            plannedStartDate=datetime(2026, 10, 1, 10, 0),
        )
    )
    posts = StubPosts()
    payload = make_payload(expireAt=datetime(2020, 1, 1))

    with pytest.raises(ExpireAtInvalidError):
        CreatePostUseCase(routes=routes, posts=posts).execute(make_user(), payload)

    assert posts.create_calls == []


def test_expire_at_after_planned_start_is_rejected():
    routes = StubRoutes(
        created=RouteInfo(
            id="r1",
            flightId="AA001",
            plannedStartDate=datetime(2026, 10, 1, 10, 0),
        )
    )
    posts = StubPosts()
    payload = make_payload(expireAt=datetime(2026, 10, 2, 0, 0))

    with pytest.raises(ExpireAtInvalidError):
        CreatePostUseCase(routes=routes, posts=posts).execute(make_user(), payload)

    assert posts.create_calls == []


def test_expire_at_equal_to_planned_start_is_accepted():
    route = RouteInfo(
        id="r1",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0),
    )
    created = CreatedPost(
        id="p1", userId="u-1", createdAt=datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    routes = StubRoutes(created=route)
    posts = StubPosts(created=created)
    payload = make_payload(expireAt=datetime(2026, 10, 1, 10, 0))

    CreatePostUseCase(routes=routes, posts=posts).execute(make_user(), payload)

    assert posts.create_calls[0]["expire_at"] == datetime(2026, 10, 1, 10, 0)


def test_expire_at_equal_to_now_is_rejected():
    """``expireAt <= now`` is rejected: capturing "now" before the call makes
    the comparison deterministic (the check runs strictly after it)."""
    fixed_now = datetime.now(timezone.utc).replace(tzinfo=None)
    route = RouteInfo(
        id="r1",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0),
    )
    routes = StubRoutes(created=route)
    posts = StubPosts()
    payload = make_payload(expireAt=fixed_now)

    with pytest.raises(ExpireAtInvalidError):
        CreatePostUseCase(routes=routes, posts=posts).execute(make_user(), payload)


def test_duplicate_post_is_rejected_before_creation():
    routes = StubRoutes(
        created=RouteInfo(
            id="r1",
            flightId="AA001",
            plannedStartDate=datetime(2026, 10, 1, 10, 0),
        )
    )
    posts = StubPosts(has_post=True)

    with pytest.raises(DuplicatePostError):
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )

    assert posts.create_calls == []


def test_posts_create_unavailable_is_surfaced():
    routes = StubRoutes(
        created=RouteInfo(
            id="r1",
            flightId="AA001",
            plannedStartDate=datetime(2026, 10, 1, 10, 0),
        )
    )
    posts = StubPosts(create_error=PostsServiceUnavailableError("x"))

    with pytest.raises(PostsServiceUnavailableError):
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )


def test_posts_create_unavailable_compensates_newly_created_route():
    """Saga compensation: a new route + failed post leaves no orphan."""
    routes = StubRoutes(
        created=RouteInfo(
            id="route-new",
            flightId="AA001",
            plannedStartDate=datetime(2026, 10, 1, 10, 0),
        )
    )
    posts = StubPosts(create_error=PostsServiceUnavailableError("x"))

    with pytest.raises(PostsServiceUnavailableError):
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )

    # The route was created by this request, so it must be compensated.
    assert routes.delete_calls == ["route-new"]


def test_posts_create_unavailable_does_not_compensate_preexisting_route():
    """A pre-existing (shared) route must survive a failed post attempt."""
    existing = RouteInfo(
        id="route-old",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0),
    )
    routes = StubRoutes(existing=existing)
    posts = StubPosts(create_error=PostsServiceUnavailableError("x"))

    with pytest.raises(PostsServiceUnavailableError):
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )

    assert routes.create_calls == []
    assert routes.delete_calls == []


def test_compensation_failure_does_not_mask_the_503():
    """If the compensating delete also fails, the original 503 still wins."""
    routes = StubRoutes(
        created=RouteInfo(
            id="route-new",
            flightId="AA001",
            plannedStartDate=datetime(2026, 10, 1, 10, 0),
        ),
        delete_error=RoutesServiceUnavailableError("routes also down"),
    )
    posts = StubPosts(create_error=PostsServiceUnavailableError("x"))

    with pytest.raises(PostsServiceUnavailableError) as exc_info:
        CreatePostUseCase(routes=routes, posts=posts).execute(
            make_user(), make_payload()
        )

    # The client still sees the post-stage failure, not the compensation one.
    assert "x" in str(exc_info.value)
    assert routes.delete_calls == ["route-new"]


def test_business_rejections_are_not_compensated():
    """412s (expireAt / duplicate) pass through without touching the route."""
    for error in (
        ExpireAtInvalidError("x"),
        DuplicatePostError("x"),
    ):
        routes = StubRoutes(
            created=RouteInfo(
                id="route-new",
                flightId="AA001",
                plannedStartDate=datetime(2026, 10, 1, 10, 0),
            )
        )
        posts = StubPosts(create_error=error)

        with pytest.raises(error.__class__):
            CreatePostUseCase(routes=routes, posts=posts).execute(
                make_user(), make_payload()
            )

        assert routes.delete_calls == []
