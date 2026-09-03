"""Unit tests for the RF-003 router: auth gate + core orchestration."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from domain.models.route import RouteInfo
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.create_post_use_case import CreatePostUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from entrypoints.api.deps import (
    get_create_post_use_case,
    get_validate_token_use_case,
)
from entrypoints.api.main import app
from errors import (
    ExpireAtInvalidError,
    PostsServiceUnavailableError,
    RouteDatesInvalidError,
    RoutesServiceUnavailableError,
    UsersServiceUnavailableError,
)
from tests.conftest import FakePosts, FakeRoutes, valid_payload

AUTH = {"Authorization": "Bearer valid-token"}


class UnavailableValidation:
    """Fake port simulating an unreachable Users service."""

    def validate_token(self, token: str) -> AuthenticatedUser:
        raise UsersServiceUnavailableError("down")


class FailingRoutes(FakeRoutes):
    """Routes fake that raises the given error on create."""

    def __init__(self, error: Exception, **kwargs):
        super().__init__(**kwargs)
        self._error = error

    def create_route(self, **kwargs) -> RouteInfo:
        raise self._error


class FailingPosts(FakePosts):
    """Posts fake that raises the given error on create."""

    def __init__(self, error: Exception, **kwargs):
        super().__init__(**kwargs)
        self._error = error

    def create_post(self, **kwargs):
        raise self._error


def test_ping_returns_200_pong(client: TestClient):
    """The health-check endpoint returns 200 with a plain-text body."""
    response = client.get("/rf003/ping")

    assert response.status_code == 200
    assert response.text == "pong"


def test_missing_authorization_header_returns_403(client: TestClient):
    """No Authorization header is a 403, before any downstream call."""
    response = client.post("/rf003/posts", json=valid_payload())

    assert response.status_code == 403
    assert response.text == ""
    assert client.fake_users.calls == []


def test_empty_bearer_token_returns_403(client: TestClient):
    """An empty Bearer token is a 403, before any downstream call."""
    response = client.post(
        "/rf003/posts", json=valid_payload(), headers={"Authorization": "Bearer "}
    )

    assert response.status_code == 403
    assert client.fake_users.calls == []


def test_invalid_token_returns_401(client: TestClient):
    """A token the Users service rejects is a 401, before any downstream call."""
    response = client.post(
        "/rf003/posts",
        json=valid_payload(),
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.text == ""
    assert client.fake_users.calls == ["expired-token"]


def test_users_service_unavailable_returns_503(client: TestClient):
    """An unreachable Users service is a 503 with the standard message."""
    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=UnavailableValidation())
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }


def test_missing_required_field_returns_400(client: TestClient):
    """Each required field missing is a 400 (no body), auth still checked first."""
    for missing in (
        "flightId",
        "expireAt",
        "plannedStartDate",
        "plannedEndDate",
        "origin",
        "destiny",
        "bagCost",
    ):
        payload = valid_payload()
        del payload[missing]
        response = client.post("/rf003/posts", json=payload, headers=AUTH)
        assert response.status_code == 400, missing
        assert response.text == ""


def test_malformed_field_returns_400(client: TestClient):
    """Malformed field values are 400 (no body)."""
    bad_bodies = [
        valid_payload(flightId=""),
        valid_payload(bagCost=-5),
        valid_payload(bagCost="cheap"),
        valid_payload(expireAt="not-a-date"),
        valid_payload(origin={"airportCode": "B", "country": "Colombia"}),
        valid_payload(origin={"country": "Colombia"}),
        valid_payload(destiny={"airportCode": "MAD"}),
        valid_payload(origin="BOG"),
    ]
    for body in bad_bodies:
        response = client.post("/rf003/posts", json=body, headers=AUTH)
        assert response.status_code == 400
        assert response.text == ""


def test_no_body_returns_400(client: TestClient):
    """A request without a JSON body is a 400."""
    response = client.post("/rf003/posts", headers=AUTH)

    assert response.status_code == 400
    assert response.text == ""


def test_valid_token_and_body_creates_route_and_post(client: TestClient):
    """Happy path: route is created, post is created, 201 documented shape."""
    response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"data", "msg"}
    data = body["data"]
    assert set(data) == {"id", "userId", "createdAt", "expireAt", "route"}
    assert data["userId"] == client.fake_users.user_id
    assert data["expireAt"] == "2026-09-15T10:00:00"
    assert set(data["route"]) == {"id", "createdAt"}
    # One route created with the submitted values, one post for the user.
    assert len(client.fake_routes.created) == 1
    assert client.fake_routes.created[0]["flightId"] == "AA001"
    assert len(client.fake_posts.created) == 1
    assert client.fake_posts.created[0]["userId"] == client.fake_users.user_id


def test_existing_route_is_reused(client: TestClient):
    """When the flightId already has a route, it is reused as-is."""
    existing = RouteInfo(
        id="route-1",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
        createdAt=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    client.fake_routes.existing_route = existing

    response = client.post(
        "/rf003/posts",
        json=valid_payload(
            bagCost=999, origin={"airportCode": "MAD", "country": "Spain"}
        ),
        headers=AUTH,
    )

    assert response.status_code == 201
    # The submitted route values are discarded; the existing route is reused.
    assert client.fake_routes.created == []
    assert response.json()["data"]["route"]["id"] == "route-1"
    assert client.fake_posts.created[0]["routeId"] == "route-1"


def test_route_dates_invalid_returns_412(client: TestClient):
    """A 412 from the Routes service is surfaced with the exact message."""
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=FailingRoutes(RouteDatesInvalidError("down")),
        posts=client.fake_posts,
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 412
    assert response.json() == {"msg": "Las fechas del trayecto no son válidas"}
    assert client.fake_posts.created == []


def test_routes_service_unavailable_returns_503(client: TestClient):
    """An unreachable Routes service is a 503 with the standard message."""
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=FailingRoutes(RoutesServiceUnavailableError("down")),
        posts=client.fake_posts,
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }


def test_expire_at_not_in_future_returns_412(client: TestClient):
    """expireAt in the past is rejected before any post call."""
    response = client.post(
        "/rf003/posts",
        json=valid_payload(expireAt="2020-01-01T00:00:00"),
        headers=AUTH,
    )

    assert response.status_code == 412
    assert response.json() == {"msg": "La fecha expiración no es válida"}
    assert client.fake_posts.created == []


def test_expire_at_after_planned_start_returns_412(client: TestClient):
    """expireAt after plannedStartDate is rejected before any post call."""
    response = client.post(
        "/rf003/posts",
        json=valid_payload(expireAt="2026-10-02T00:00:00"),
        headers=AUTH,
    )

    assert response.status_code == 412
    assert response.json() == {"msg": "La fecha expiración no es válida"}
    assert client.fake_posts.created == []


def test_duplicate_post_returns_412(client: TestClient):
    """An existing post for the route/user is a 412 with the exact message."""
    client.fake_posts.existing_posts = [
        {"routeId": "r1", "userId": client.fake_users.user_id}
    ]
    # The duplicate must be detected on the resolved (existing) route.
    client.fake_routes.existing_route = RouteInfo(
        id="r1",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
    )

    response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)

    assert response.status_code == 412
    assert response.json() == {
        "msg": "El usuario ya tiene una publicación para la misma fecha"
    }
    assert client.fake_posts.created == []


def test_posts_service_unavailable_returns_503(client: TestClient):
    """An unreachable Posts service is a 503 with the standard message."""
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=client.fake_routes,
        posts=FailingPosts(PostsServiceUnavailableError("down")),
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }


def test_posts_service_unavailable_compensates_new_route(client: TestClient):
    """Mid-flow outage: the newly created route is deleted (no orphan)."""
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=client.fake_routes,
        posts=FailingPosts(PostsServiceUnavailableError("down")),
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 503
    # A route was created by this request and then compensated (no orphan).
    assert len(client.fake_routes.created) == 1
    assert client.fake_routes.deleted == client.fake_routes.created_ids
    assert client.fake_posts.created == []


def test_posts_service_unavailable_keeps_preexisting_route(client: TestClient):
    """Mid-flow outage with a reused route: the shared route must survive."""
    existing = RouteInfo(
        id="route-pre",
        flightId="AA001",
        plannedStartDate=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
    )
    client.fake_routes.existing_route = existing
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=client.fake_routes,
        posts=FailingPosts(PostsServiceUnavailableError("down")),
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 503
    assert client.fake_routes.created == []
    assert client.fake_routes.deleted == []


def test_posts_service_412_is_surfaced(client: TestClient):
    """A 412 from the Posts service is surfaced with the exact message."""
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=client.fake_routes,
        posts=FailingPosts(ExpireAtInvalidError("down")),
    )
    try:
        response = client.post("/rf003/posts", json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 412
    assert response.json() == {"msg": "La fecha expiración no es válida"}
