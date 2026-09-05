"""Consistency integration tests for RF-004 (Consistencia Requerimiento RF004).

These tests exercise the full request path (router + use case + real HTTP
clients over a mock transport, no fake ports) to prove the documented
consistency strategy: when a downstream service fails *mid-flow* (after the
offer was already persisted), the orchestrator runs the compensating
action (delete the just created offer) so no orphaned record remains, and
the client receives the documented 503 with the exact message.

Business rejections (404/412) are NOT integration failures and pass
through unchanged, with no compensating action.
"""

import httpx
from fastapi.testclient import TestClient

from adapters.http.offers_service_client import OffersServiceClient
from adapters.http.routes_service_client import RoutesServiceClient
from adapters.http.scores_service_client import ScoresServiceClient
from domain.use_cases.create_offer_use_case import CreateOfferUseCase
from entrypoints.api.deps import get_create_offer_use_case
from entrypoints.api.main import app
from tests.conftest import valid_payload, valid_post

AUTH = {"Authorization": "Bearer valid-token"}
POST_ID = "post-1"
URL = f"/rf004/posts/{POST_ID}/offers"
STANDARD_503 = {"msg": "El servicio está temporalmente fuera de servicio."}

OFFERS_BASE = "http://offers.test"
ROUTES_BASE = "http://routes.test"
SCORES_BASE = "http://scores.test"


def _route_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"id": "route-1", "bagCost": 10000})


def _offers_up_handler(offers_state: dict):
    """Mock transport handler for a healthy Offers service.

    Records the offer lifecycle in ``offers_state``: a POST /offers marks
    the offer as created, a DELETE /offers/{id} marks it as compensated.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            offers_state["state"] = "created"
            return httpx.Response(
                201,
                json={
                    "id": "offer-int-1",
                    "userId": "user-1",
                    "createdAt": "2026-09-01T10:00:00Z",
                },
            )
        if request.method == "DELETE":
            offers_state["state"] = "compensated"
            return httpx.Response(200, json={"msg": "la oferta fue eliminada"})
        return httpx.Response(500)

    return handler


def _down_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def _make_scores_ok_handler(score_calls: list):
    def handler(request: httpx.Request) -> httpx.Response:
        score_calls.append("upsert")
        return httpx.Response(
            201, json={"offerId": "offer-int-1", "score": 45000.0}
        )

    return handler


def _build_use_case(
    offers_state: dict,
    score_calls: list,
    scores_down: bool = False,
    offers_down: bool = False,
) -> CreateOfferUseCase:
    """Build the real use case with real HTTP clients over mock transports."""
    offers_client = OffersServiceClient(
        client=httpx.Client(
            base_url=OFFERS_BASE,
            transport=httpx.MockTransport(
                _down_handler if offers_down else _offers_up_handler(offers_state)
            ),
        )
    )
    routes_client = RoutesServiceClient(
        client=httpx.Client(
            base_url=ROUTES_BASE,
            transport=httpx.MockTransport(_route_handler),
        )
    )
    scores_client = ScoresServiceClient(
        client=httpx.Client(
            base_url=SCORES_BASE,
            transport=httpx.MockTransport(
                _down_handler
                if scores_down
                else (lambda request: score_calls.append("upsert") or httpx.Response(201, json={"offerId": "offer-int-1", "score": 45000.0}))
            ),
        )
    )
    return CreateOfferUseCase(
        offers=offers_client, routes=routes_client, scores=scores_client
    )


def test_scores_outage_mid_flow_compensates_and_returns_503(client: TestClient):
    """Scores unreachable after the offer was created: 503 + offer deleted, no orphan remains."""
    client.fake_posts.posts[POST_ID] = valid_post()
    offers_state: dict = {}
    score_calls: list = []
    use_case = _build_use_case(offers_state, score_calls, scores_down=True)

    app.dependency_overrides[get_create_offer_use_case] = lambda: use_case
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    # The documented 503 with the exact specified message.
    assert response.status_code == 503
    assert response.json() == STANDARD_503
    # The offer was created mid-flow, then compensated (deleted): the
    # final state is the compensated (deleted) offer, no orphan remains.
    assert offers_state.get("state") == "compensated"
    # The score was never persisted.
    assert score_calls == []


def test_offers_outage_returns_503_with_no_writes(client: TestClient):
    """Offers unreachable: 503 and no write happened at all (nothing to compensate)."""
    client.fake_posts.posts[POST_ID] = valid_post()
    offers_state: dict = {}
    use_case = _build_use_case(offers_state, [], offers_down=True)

    app.dependency_overrides[get_create_offer_use_case] = lambda: use_case
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 503
    assert response.json() == STANDARD_503
    assert offers_state.get("state") is None  # create was never accepted


def test_happy_path_persists_offer_and_score(client: TestClient):
    """All services up: 201 with the offer data and the score persisted."""
    stored_post = valid_post()
    client.fake_posts.posts[POST_ID] = stored_post
    offers_state: dict = {}
    score_calls: list = []
    use_case = _build_use_case(offers_state, score_calls)

    app.dependency_overrides[get_create_offer_use_case] = lambda: use_case
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 201
    body = response.json()
    assert body["msg"] == "Oferta creada exitosamente."
    assert body["data"]["id"] == "offer-int-1"
    assert body["data"]["postId"] == stored_post.id
    assert score_calls == ["upsert"]
