"""Test suite for the RF-005 endpoint."""

import pytest
from fastapi.testclient import TestClient

from entrypoints.api.main import app
from domain.models import PostInfo
from domain.ports.user_validation_port import (
    AuthenticatedUser,
    UserValidationPort,
)
from domain.use_cases import ValidateTokenUseCase
from domain.use_cases.ownership_gate_use_case import OwnershipGateUseCase
from domain.use_cases.query_post_use_case import QueryPostUseCase
from errors import (
    InvalidTokenError,
    PostNotFoundError,
    PostsServiceUnavailableError,
    TokenMissingError,
    UsersServiceUnavailableError,
    UserNotOwnerError,
)
from tests.conftest import FakePosts, FakeUserValidation


@pytest.fixture
def client(fake_user_validation: FakeUserValidation, fake_posts: FakePosts):
    """Provide a TestClient with injected fake services via use cases."""
    from entrypoints.api import deps
    from adapters.http.routes_service_client import RoutesServiceClient
    from adapters.http.offers_service_client import OffersServiceClient
    from adapters.http.scores_service_client import ScoresServiceClient

    def fake_validate_token_use_case():
        return ValidateTokenUseCase(user_validation=fake_user_validation)

    def fake_ownership_gate_use_case():
        return OwnershipGateUseCase(posts=fake_posts)

    class FakeQueryPostUseCase:
        """Fake aggregation use case that returns mock data."""
        def execute(self, *, post, post_id: str, route_id: str | None):
            from domain.models import QueryPostResponse
            return QueryPostResponse(data={
                "id": post.id,
                "expireAt": post.expireAt,
                "plannedStartDate": post.plannedStartDate,
                "plannedEndDate": post.plannedEndDate,
                "createdAt": post.createdAt,
                "route": {
                    "id": route_id or "",
                    "flightId": route_id or "",
                    "origin": {"airportCode": "BOG", "country": "Colombia"},
                    "destiny": {"airportCode": "MIA", "country": "USA"},
                    "bagCost": 25.0,
                    "plannedStartDate": None,
                    "plannedEndDate": None,
                },
                "offers": [],
            })

    def fake_query_post_use_case():
        return FakeQueryPostUseCase()

    app.dependency_overrides[deps.get_validate_token_use_case] = (
        fake_validate_token_use_case
    )
    app.dependency_overrides[deps.get_ownership_gate_use_case] = (
        fake_ownership_gate_use_case
    )
    app.dependency_overrides[deps.get_query_post_use_case] = (
        fake_query_post_use_case
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_missing_bearer_token_returns_403(client: TestClient):
    """GET without Authorization header responds with HTTP 403."""
    response = client.get("/rf005/posts/post1")
    assert response.status_code == 403
    assert response.text == ""


def test_invalid_bearer_token_returns_401(client: TestClient):
    """GET with invalid bearer token responds with HTTP 401."""
    response = client.get(
        "/rf005/posts/post1",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401
    assert response.text == ""


def test_nonexistent_post_returns_404(client: TestClient):
    """GET with valid token but non-existent post responds with HTTP 404."""
    response = client.get(
        "/rf005/posts/nonexistent",
        headers={"Authorization": "Bearer valid_token"},
    )
    assert response.status_code == 404
    assert response.text == ""


def test_non_owner_returns_403(client: TestClient):
    """GET with valid token but user is not the post owner responds with HTTP 403."""
    response = client.get(
        "/rf005/posts/post2",
        headers={"Authorization": "Bearer valid_token"},
    )
    assert response.status_code == 403
    assert response.text == ""


def test_owner_proceeds(client: TestClient):
    """GET with valid token and user is the post owner now returns 200 with aggregated data."""
    response = client.get(
        "/rf005/posts/post1",
        headers={"Authorization": "Bearer valid_token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "route" in data["data"]
    assert "offers" in data["data"]


def test_users_service_unavailable_returns_503(
    client: TestClient, fake_user_validation: FakeUserValidation
):
    """GET with Users service down returns HTTP 503."""
    fake_user_validation.unreachable = True
    response = client.get(
        "/rf005/posts/post1",
        headers={"Authorization": "Bearer valid_token"},
    )
    assert response.status_code == 503
    assert "El servicio está temporalmente fuera de servicio" in response.text


def test_posts_service_unavailable_returns_503(
    client: TestClient, fake_posts: FakePosts
):
    """GET with Posts service down returns HTTP 503."""
    fake_posts.unreachable = True
    response = client.get(
        "/rf005/posts/post1",
        headers={"Authorization": "Bearer valid_token"},
    )
    assert response.status_code == 503
    assert "El servicio está temporalmente fuera de servicio" in response.text


def test_healthcheck_endpoint_responds(client: TestClient):
    """GET /rf005/ping responds with 200 and 'pong'."""
    response = client.get("/rf005/ping")
    assert response.status_code == 200
    assert response.text == "pong"


def test_owner_response_contains_post_fields_and_null_score(
    client: TestClient, fake_posts: FakePosts
):
    """The 200 body carries the post fields and a null score per offer.

    Simulates the RF-005 resilience requirement end to end at the
    router level: the Score service is down, so every offer is
    returned with ``score: null`` while the request still succeeds
    with 200 and the full documented data shape.
    """
    fake_posts.posts_by_id["post1"] = PostInfo(
        id="post1",
        userId="user1",
        routeId="r1",
        expireAt="2026-07-01T10:00:00Z",
        plannedStartDate="2026-06-01T10:00:00Z",
        plannedEndDate="2026-06-10T18:00:00Z",
        createdAt="2026-05-01T09:00:00Z",
    )

    from entrypoints.api import deps

    class ScoreOutageQueryPostUseCase:
        """Returns the full shape with every offer score set to null."""

        def execute(self, *, post, post_id: str, route_id: str | None):
            from domain.models import QueryPostResponse

            return QueryPostResponse(
                data={
                    "id": post.id,
                    "expireAt": post.expireAt,
                    "plannedStartDate": post.plannedStartDate,
                    "plannedEndDate": post.plannedEndDate,
                    "createdAt": post.createdAt,
                    "route": {
                        "id": route_id or "",
                        "flightId": "FL100",
                        "origin": {"airportCode": "BOG", "country": "Colombia"},
                        "destiny": {"airportCode": "MIA", "country": "USA"},
                        "bagCost": 25.0,
                        "plannedStartDate": "2026-06-01T10:00:00Z",
                        "plannedEndDate": "2026-06-10T18:00:00Z",
                    },
                    "offers": [
                        {
                            "id": "o1",
                            "userId": "user1",
                            "description": "Bag 23kg",
                            "size": 2,
                            "fragile": False,
                            "offer": 150.0,
                            "score": None,
                            "createdAt": "2026-05-01T10:00:00Z",
                        },
                    ],
                }
            )

    app.dependency_overrides[deps.get_query_post_use_case] = (
        lambda: ScoreOutageQueryPostUseCase()
    )
    try:
        response = client.get(
            "/rf005/posts/post1",
            headers={"Authorization": "Bearer valid_token"},
        )
    finally:
        app.dependency_overrides.pop(deps.get_query_post_use_case, None)

    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    # Post-level fields.
    assert data["id"] == "post1"
    assert data["expireAt"] == "2026-07-01T10:00:00Z"
    assert data["plannedStartDate"] == "2026-06-01T10:00:00Z"
    assert data["plannedEndDate"] == "2026-06-10T18:00:00Z"
    assert data["createdAt"] == "2026-05-01T09:00:00Z"
    # Route present.
    assert data["route"]["id"] == "r1"
    # The affected offer is returned with score null, not an error.
    assert data["offers"][0]["score"] is None
    assert data["offers"][0]["id"] == "o1"


def test_missing_route_record_returns_503(
    client: TestClient, fake_posts: FakePosts
):
    """A route that does not exist fails the request with the 503 body.

    Per the RF-005 sequence view, the Routes service is a hard
    dependency of the aggregation: a missing route record is surfaced
    with the documented 503 message, not with a 404 or an empty view.
    """
    from entrypoints.api import deps
    from errors import RouteNotFoundError

    class MissingRouteQueryPostUseCase:
        def execute(self, *, post, post_id: str, route_id: str | None):
            raise RouteNotFoundError(f"Route {route_id} does not exist")

    app.dependency_overrides[deps.get_query_post_use_case] = (
        lambda: MissingRouteQueryPostUseCase()
    )
    try:
        response = client.get(
            "/rf005/posts/post1",
            headers={"Authorization": "Bearer valid_token"},
        )
    finally:
        app.dependency_overrides.pop(deps.get_query_post_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }
