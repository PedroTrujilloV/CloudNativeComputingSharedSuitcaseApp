"""Unit tests for the RF-004 router: auth + validation gate and offer creation flow."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from domain.models.post import PostInfo
from domain.models.route import RouteInfo
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.create_offer_use_case import CreateOfferUseCase
from domain.use_cases.offer_preconditions_use_case import OfferPreconditionsUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from entrypoints.api.deps import (
    get_create_offer_use_case,
    get_offer_preconditions_use_case,
    get_validate_token_use_case,
)
from entrypoints.api.main import app
from errors import (
    OffersServiceUnavailableError,
    PostsServiceUnavailableError,
    RoutesServiceUnavailableError,
    ScoresServiceUnavailableError,
    UsersServiceUnavailableError,
)
from tests.conftest import FakePosts, valid_payload, valid_post

AUTH = {"Authorization": "Bearer valid-token"}
POST_ID = "post-1"
URL = f"/rf004/posts/{POST_ID}/offers"


class UnavailableValidation:
    """Fake port simulating an unreachable Users service."""

    def validate_token(self, token: str) -> AuthenticatedUser:
        raise UsersServiceUnavailableError("down")


class FailingPosts(FakePosts):
    """Posts fake that raises the given error on get_post."""

    def __init__(self, error: Exception, **kwargs):
        super().__init__(**kwargs)
        self._error = error

    def get_post(self, post_id: str) -> PostInfo:
        raise self._error


def test_ping_returns_200_pong(client: TestClient):
    """The health-check endpoint returns 200 with a plain-text body."""
    response = client.get("/rf004/ping")

    assert response.status_code == 200
    assert response.text == "pong"


def test_valid_request_returns_201(client: TestClient):
    """A request that passes every gate creates the offer and returns 201."""
    stored_post = valid_post()
    client.fake_posts.posts[POST_ID] = stored_post

    mock_offers = MagicMock()
    mock_offers.create_offer.return_value = {
        "id": "offer-1",
        "userId": client.fake_users.user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    mock_routes = MagicMock()
    mock_routes.get_route.return_value = RouteInfo(id="route-1", bagCost=10000.0)
    mock_scores = MagicMock()
    mock_scores.upsert_score.return_value = {"offerId": "offer-1", "score": 45000.0}

    fake_use_case = CreateOfferUseCase(
        offers=mock_offers, routes=mock_routes, scores=mock_scores
    )

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=client.fake_users)
    )
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(posts=client.fake_posts)
    )
    app.dependency_overrides[get_create_offer_use_case] = (
        lambda: fake_use_case
    )

    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)
        app.dependency_overrides.pop(get_offer_preconditions_use_case, None)
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 201
    body = response.json()
    assert "data" in body
    assert "msg" in body
    assert body["data"]["id"] == "offer-1"
    assert body["data"]["postId"] == stored_post.id
    assert body["msg"]
    mock_offers.create_offer.assert_called_once()
    mock_routes.get_route.assert_called_once_with(stored_post.routeId)
    mock_scores.upsert_score.assert_called_once_with(offer_id="offer-1", score_value=45000.0)


def test_scores_service_unavailable_compensates_and_returns_503(client: TestClient):
    """When the Scores service is unavailable after the offer was created, the offer is deleted (compensating action) and the endpoint returns 503 with the standard message."""
    stored_post = valid_post()
    client.fake_posts.posts[POST_ID] = stored_post

    mock_offers = MagicMock()
    mock_offers.create_offer.return_value = {
        "id": "offer-2",
        "userId": client.fake_users.user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    mock_routes = MagicMock()
    mock_routes.get_route.return_value = RouteInfo(id="route-1", bagCost=10000.0)

    class FailingScores:
        upsert_calls = []
        def upsert_score(self, offer_id, score_value):
            raise ScoresServiceUnavailableError("down")

    mock_scores = FailingScores()

    fake_use_case = CreateOfferUseCase(
        offers=mock_offers, routes=mock_routes, scores=mock_scores
    )

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=client.fake_users)
    )
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(posts=client.fake_posts)
    )
    app.dependency_overrides[get_create_offer_use_case] = (
        lambda: fake_use_case
    )

    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)
        app.dependency_overrides.pop(get_offer_preconditions_use_case, None)
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }
    # The offer was created and then compensated (deleted): no orphan remains.
    mock_offers.create_offer.assert_called_once()
    mock_offers.delete_offer.assert_called_once_with("offer-2")


def test_valid_request_reaches_offer_stage_placeholder(client: TestClient):
    """A request that passes every gate creates the offer and returns 201 with success message."""
    client.fake_posts.posts[POST_ID] = valid_post()

    mock_offers = MagicMock()
    mock_offers.create_offer.return_value = {
        "id": "offer-3",
        "userId": client.fake_users.user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    mock_routes = MagicMock()
    mock_routes.get_route.return_value = RouteInfo(id="route-1", bagCost=10000.0)
    mock_scores = MagicMock()
    mock_scores.upsert_score.return_value = {"offerId": "offer-3", "score": 45000.0}

    fake_use_case = CreateOfferUseCase(
        offers=mock_offers, routes=mock_routes, scores=mock_scores
    )

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=client.fake_users)
    )
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(posts=client.fake_posts)
    )
    app.dependency_overrides[get_create_offer_use_case] = (
        lambda: fake_use_case
    )

    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)
        app.dependency_overrides.pop(get_offer_preconditions_use_case, None)
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 201
    body = response.json()
    assert "Oferta creada exitosamente" in body["msg"]
    assert body["data"]["id"] == "offer-3"
    assert client.fake_users.calls == ["valid-token"]
    assert client.fake_posts.get_calls == [POST_ID]


def test_missing_authorization_header_returns_403(client: TestClient):
    """No Authorization header is a 403 (empty body), before any downstream call."""
    response = client.post(URL, json=valid_payload())

    assert response.status_code == 403
    assert response.text == ""
    assert client.fake_users.calls == []
    assert client.fake_posts.get_calls == []


def test_empty_bearer_token_returns_403(client: TestClient):
    """An empty Bearer token is a 403 (empty body), before any downstream call."""
    response = client.post(
        URL, json=valid_payload(), headers={"Authorization": "Bearer "}
    )

    assert response.status_code == 403
    assert response.text == ""
    assert client.fake_users.calls == []
    assert client.fake_posts.get_calls == []


def test_invalid_token_returns_401(client: TestClient):
    """A token the Users service rejects is a 401 (empty body), before any post call."""
    response = client.post(
        URL, json=valid_payload(), headers={"Authorization": "Bearer expired-token"}
    )

    assert response.status_code == 401
    assert response.text == ""
    assert client.fake_users.calls == ["expired-token"]
    assert client.fake_posts.get_calls == []


def test_users_service_unavailable_returns_503(client: TestClient):
    """An unreachable Users service is a 503 with the standard message."""
    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=UnavailableValidation())
    )
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }
    assert client.fake_posts.get_calls == []


def test_missing_required_field_returns_400(client: TestClient):
    """Each required field missing is a 400 (empty body)."""
    for missing in ("description", "size", "fragile", "offer"):
        payload = valid_payload()
        del payload[missing]
        response = client.post(URL, json=payload, headers=AUTH)
        assert response.status_code == 400, missing
        assert response.text == ""


def test_malformed_field_returns_400(client: TestClient):
    """Malformed field values are a 400 (empty body)."""
    bad_bodies = [
        valid_payload(description=""),
        valid_payload(size="XL"),
        valid_payload(size="medium"),
        valid_payload(fragile="notabool"),
        valid_payload(offer=-1),
        valid_payload(offer="cheap"),
    ]
    for body in bad_bodies:
        response = client.post(URL, json=body, headers=AUTH)
        assert response.status_code == 400
        assert response.text == ""


def test_no_body_returns_400(client: TestClient):
    """A request without a JSON body is a 400 (empty body)."""
    response = client.post(URL, headers=AUTH)

    assert response.status_code == 400
    assert response.text == ""


def test_unknown_post_returns_404_empty_body(client: TestClient):
    """A post the Posts service does not know about is a 404 (empty body)."""
    response = client.post(URL, json=valid_payload(), headers=AUTH)

    assert response.status_code == 404
    assert response.text == ""
    assert client.fake_posts.get_calls == [POST_ID]


def test_own_post_returns_412_empty_body(client: TestClient):
    """A post owned by the caller is a 412 (empty body)."""
    client.fake_posts.posts[POST_ID] = valid_post(userId=client.fake_users.user_id)

    response = client.post(URL, json=valid_payload(), headers=AUTH)

    assert response.status_code == 412
    assert response.text == ""


def test_expired_post_returns_412_empty_body(client: TestClient):
    """A post whose expireAt is in the past is a 412 (empty body)."""
    client.fake_posts.posts[POST_ID] = valid_post(
        expireAt=datetime.now(timezone.utc) - timedelta(seconds=10)
    )

    response = client.post(URL, json=valid_payload(), headers=AUTH)

    assert response.status_code == 412
    assert response.text == ""


def test_posts_service_unavailable_returns_503(client: TestClient):
    """An unreachable Posts service is a 503 with the standard message."""
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(
            posts=FailingPosts(PostsServiceUnavailableError("down"))
        )
    )
    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_offer_preconditions_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }


def test_offers_service_unavailable_returns_503(client: TestClient):
    """An unreachable Offers service is a 503 with the standard message."""
    client.fake_posts.posts[POST_ID] = valid_post()

    class FailingOffers:
        def create_offer(self, **kwargs):
            raise OffersServiceUnavailableError("down")

    mock_routes = MagicMock()
    mock_routes.get_route.return_value = RouteInfo(id="route-1", bagCost=10000.0)

    fake_use_case = CreateOfferUseCase(
        offers=FailingOffers(), routes=mock_routes, scores=MagicMock()
    )

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=client.fake_users)
    )
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(posts=client.fake_posts)
    )
    app.dependency_overrides[get_create_offer_use_case] = (
        lambda: fake_use_case
    )

    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)
        app.dependency_overrides.pop(get_offer_preconditions_use_case, None)
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }


def test_routes_service_unavailable_returns_503(client: TestClient):
    """An unreachable Routes service is a 503 with the standard message."""
    client.fake_posts.posts[POST_ID] = valid_post()

    class FailingRoutes:
        def get_route(self, route_id):
            raise RoutesServiceUnavailableError("down")

    fake_use_case = CreateOfferUseCase(
        offers=MagicMock(), routes=FailingRoutes(), scores=MagicMock()
    )

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=client.fake_users)
    )
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(posts=client.fake_posts)
    )
    app.dependency_overrides[get_create_offer_use_case] = (
        lambda: fake_use_case
    )

    try:
        response = client.post(URL, json=valid_payload(), headers=AUTH)
    finally:
        app.dependency_overrides.pop(get_validate_token_use_case, None)
        app.dependency_overrides.pop(get_offer_preconditions_use_case, None)
        app.dependency_overrides.pop(get_create_offer_use_case, None)

    assert response.status_code == 503
    assert response.json() == {
        "msg": "El servicio está temporalmente fuera de servicio."
    }
