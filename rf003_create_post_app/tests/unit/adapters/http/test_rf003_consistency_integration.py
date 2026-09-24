"""Consistency integration tests for RF-003 (Consistencia Requerimiento RF003).

These tests exercise the full request path (router + use case + real HTTP
clients over a mock transport, no fake ports) to prove the documented
consistency strategy: when a downstream service fails *mid-flow* (after the
route was already created), the orchestrator runs the compensating action
(delete the just created route) so no orphaned record remains, and the
client receives the documented 503 with the exact message.

Business rejections (412) are NOT integration failures and pass through
unchanged, with no compensating action.
"""

from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient

from adapters.http.posts_service_client import PostsServiceClient
from adapters.http.routes_service_client import RoutesServiceClient
from domain.use_cases.create_post_use_case import CreatePostUseCase
from entrypoints.api.deps import get_create_post_use_case
from entrypoints.api.main import app
from tests.conftest import valid_payload

AUTH = {"Authorization": "Bearer valid-token"}
URL = "/rf003/posts"
STANDARD_503 = {"msg": "El servicio está temporalmente fuera de servicio."}

ROUTES_BASE = "http://routes.test"
POSTS_BASE = "http://posts.test"

# Far-in-the-future (yet) anchor for mocked route views, computed once at
# import time so the date-rule invariants never fall behind the real clock.
FUTURE_START = (
    datetime.now(timezone.utc)
    .replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=None)
    + timedelta(days=30)
)


def _down_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def _routes_handler(routes_state: dict):
    """Mock transport handler for a healthy Routes service.

    Records the route lifecycle in ``routes_state``: a POST /routes marks
    the route as created, a DELETE /routes/{id} marks it as compensated.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            if routes_state.get("existing"):
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "route-existing-1",
                            "flightId": "EXISTING",
                            "plannedStartDate": FUTURE_START.isoformat(),
                            "createdAt": "2026-09-01T09:00:00",
                        }
                    ],
                )
            return httpx.Response(200, json=[])
        if request.method == "POST":
            routes_state["state"] = "created"
            return httpx.Response(
                201,
                json={
                    "id": "route-int-1",
                    "createdAt": "2026-09-01T10:00:00",
                },
            )
        if request.method == "DELETE":
            routes_state["state"] = "compensated"
            return httpx.Response(200, json={"msg": "la ruta fue eliminada"})
        return httpx.Response(500)

    return handler


def _posts_handler(posts_state: dict):
    """Mock transport handler for a healthy Posts service."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "POST":
            posts_state["state"] = "created"
            return httpx.Response(
                201,
                json={
                    "id": "post-int-1",
                    "userId": "user-1",
                    "createdAt": "2026-09-01T10:00:00",
                },
            )
        return httpx.Response(500)

    return handler


def _build_use_case(
    routes_state: dict,
    posts_state: dict,
    posts_down: bool = False,
    routes_down: bool = False,
) -> CreatePostUseCase:
    """Build the real use case with real HTTP clients over mock transports."""
    routes_client = RoutesServiceClient(
        client=httpx.Client(
            base_url=ROUTES_BASE,
            transport=httpx.MockTransport(
                _down_handler if routes_down else _routes_handler(routes_state)
            ),
        )
    )
    posts_client = PostsServiceClient(
        client=httpx.Client(
            base_url=POSTS_BASE,
            transport=httpx.MockTransport(
                _down_handler if posts_down else _posts_handler(posts_state)
            ),
        )
    )
    return CreatePostUseCase(routes=routes_client, posts=posts_client)


def test_posts_outage_mid_flow_compensates_and_returns_503(client: TestClient):
    """Posts unreachable after the route was created: 503 + route deleted, no orphan remains."""
    routes_state: dict = {}
    posts_state: dict = {}
    use_case = _build_use_case(routes_state, posts_state, posts_down=True)

    app.dependency_overrides[get_create_post_use_case] = lambda: use_case
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    # The documented 503 with the exact specified message.
    assert response.status_code == 503
    assert response.json() == STANDARD_503
    # The route was created mid-flow, then compensated (deleted): the
    # final state is the compensated (deleted) route, no orphan remains.
    assert routes_state.get("state") == "compensated"
    # The post was never created.
    assert posts_state.get("state") is None


def test_routes_outage_returns_503_with_no_writes(client: TestClient):
    """Routes unreachable: 503 and no write happened at all (nothing to compensate)."""
    routes_state: dict = {}
    posts_state: dict = {}
    use_case = _build_use_case(routes_state, posts_state, routes_down=True)

    app.dependency_overrides[get_create_post_use_case] = lambda: use_case
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 503
    assert response.json() == STANDARD_503
    assert routes_state.get("state") is None  # create was never accepted
    assert posts_state.get("state") is None


def test_happy_path_creates_route_and_post(client: TestClient):
    """All services up: 201 with the post data and the route id."""
    routes_state: dict = {}
    posts_state: dict = {}
    use_case = _build_use_case(routes_state, posts_state)

    app.dependency_overrides[get_create_post_use_case] = lambda: use_case
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 201
    body = response.json()
    assert body["msg"] == "Publicación creada exitosamente."
    assert body["data"]["id"] == "post-int-1"
    assert body["data"]["route"]["id"] == "route-int-1"
    assert routes_state.get("state") == "created"
    assert posts_state.get("state") == "created"


def test_pre_existing_route_is_preserved_on_posts_outage(client: TestClient):
    """Posts unreachable with a reused (pre-existing) route: 503 and the shared route survives."""
    routes_state: dict = {"existing": True}
    posts_state: dict = {}
    use_case = _build_use_case(routes_state, posts_state, posts_down=True)

    app.dependency_overrides[get_create_post_use_case] = lambda: use_case
    try:
        response = client.post(
            URL, json=valid_payload(flightId="EXISTING"), headers=AUTH
        )
    finally:
        app.dependency_overrides.pop(get_create_post_use_case, None)

    assert response.status_code == 503
    assert response.json() == STANDARD_503
    # The pre-existing route is shared state: it is not deleted.
    assert routes_state.get("state") is None
    assert posts_state.get("state") is None
