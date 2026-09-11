"""Integration tests for RF-005 Score resilience (graded requirement).

These tests exercise the real RF-005 FastAPI application end to end
(router + ownership gate + aggregation use case + the real Routes and
Offers HTTP clients) while the Score service is simulated as down, to
prove the RF-005 resilience requirement:

  * an offer without a persisted score is returned with ``score: null``
    and the request still answers 200;
  * a Score service outage (connection refused) degrades to
    ``score: null`` per offer, never to a failed request;
  * offers keep their documented order (score descending, nulls last,
    ties broken by ``createdAt`` descending);
  * business rejections from prior stages (401/403/404) pass through
    unchanged while the Score service is down.

The tests run against the real downstream services (Users, Posts,
Routes, Offers) and the real Score client pointed at a dead port,
so the Score outage is simulated at the network level (connection
refused), exactly like a down Score service. They are skipped
automatically when the downstream services are not up, keeping the
unit suite green in isolation.

Required environment (defaults match the local layout):
  - RF005_USERS_BASE    users service URL   (default http://localhost:8000)
  - RF005_POSTS_BASE    posts service URL   (default http://localhost:8002)
  - RF005_ROUTES_BASE   routes service URL  (default http://localhost:8006)
  - RF005_OFFERS_BASE   offers service URL  (default http://localhost:8003)
  - RF005_SCORES_DEAD_PORT  dead port used to simulate the Score
    service outage (default 9, the discard port: connection refused)
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from entrypoints.api.main import app

USERS_BASE = os.getenv("RF005_USERS_BASE", "http://localhost:8000")
POSTS_BASE = os.getenv("RF005_POSTS_BASE", "http://localhost:8002")
ROUTES_BASE = os.getenv("RF005_ROUTES_BASE", "http://localhost:8006")
OFFERS_BASE = os.getenv("RF005_OFFERS_BASE", "http://localhost:8003")
SCORES_DEAD_PORT = os.getenv("RF005_SCORES_DEAD_PORT", "9")


_PING_PATHS = {
    "users": "/users/ping",
    "posts": "/posts/ping",
    "routes": "/routes/ping",
    "offers": "/offers/ping",
    "scores": "/scores/ping",
}


def _reachable(base: str, name: str) -> bool:
    """Return True when the service answers its own ping endpoint."""
    try:
        r = httpx.get(base + _PING_PATHS[name], timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


requires_services = pytest.mark.skipif(
    not (
        _reachable(USERS_BASE, "users")
        and _reachable(POSTS_BASE, "posts")
        and _reachable(ROUTES_BASE, "routes")
        and _reachable(OFFERS_BASE, "offers")
    ),
    reason="RF-005 downstream services are not reachable; skipping integration tests",
)


@pytest.fixture(autouse=True)
def point_app_at_local_services(monkeypatch):
    """Point the app's Settings at the local services for this module.

    The Settings properties read the environment at request time, so
    patching the variables here is enough. The Score service URL is
    pointed at a dead port (connection refused), which simulates a
    Score service outage through the real HTTP client.
    """
    monkeypatch.setenv("USERS_SERVICE_URL", USERS_BASE)
    monkeypatch.setenv("POSTS_SERVICE_URL", POSTS_BASE)
    monkeypatch.setenv("ROUTES_SERVICE_URL", ROUTES_BASE)
    monkeypatch.setenv("OFFERS_SERVICE_URL", OFFERS_BASE)
    monkeypatch.setenv("SCORES_SERVICE_URL", f"http://127.0.0.1:{SCORES_DEAD_PORT}")


@pytest.fixture
def http_client():
    """Provide a TestClient for the real RF-005 application."""
    yield TestClient(app)


def _create_user_and_token() -> tuple[str, str]:
    """Create a fresh user in the Users service and return (id, token)."""
    username = f"rf005_it_{uuid.uuid4().hex[:10]}"
    r = httpx.post(
        f"{USERS_BASE}/users",
        json={
            "username": username,
            "password": "Secret123!",
            "email": f"{username}@example.com",
            "dni": str(uuid.uuid4().int % 10**8),
            "fullName": "RF005 Integration Tester",
            "phoneNumber": "3001234567",
        },
        timeout=5,
    )
    assert r.status_code == 201, r.text
    r = httpx.post(
        f"{USERS_BASE}/users/auth",
        json={"username": username, "password": "Secret123!"},
        timeout=5,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["id"], body["token"]


def _create_route() -> str:
    """Create a fresh route in the Routes service and return its id."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=10)
    end = now + timedelta(days=11)
    r = httpx.post(
        f"{ROUTES_BASE}/routes",
        json={
            "flightId": f"IT{uuid.uuid4().hex[:6].upper()}",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "MAD",
            "destinyCountry": "Spain",
            "bagCost": 350,
            "plannedStartDate": start.isoformat(),
            "plannedEndDate": end.isoformat(),
        },
        timeout=5,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_post(user_id: str, route_id: str) -> str:
    """Create a post owned by user_id and return its id."""
    expire = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    r = httpx.post(
        f"{POSTS_BASE}/posts",
        json={"routeId": route_id, "userId": user_id, "expireAt": expire},
        timeout=5,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_offer(post_id: str, user_id: str, offer_amount: float) -> str:
    """Create an offer for the post and return its id."""
    r = httpx.post(
        f"{OFFERS_BASE}/offers",
        json={
            "postId": post_id,
            "userId": user_id,
            "description": f"rf005 it offer {uuid.uuid4().hex[:8]}",
            "size": "MEDIUM",
            "fragile": False,
            "offer": offer_amount,
        },
        timeout=5,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@requires_services
def test_score_outage_returns_200_with_null_scores(http_client: TestClient):
    """Score service down: the request still succeeds with score null.

    Acceptance criteria:
      * status is 200 (not 503) while the Score service is down;
      * every offer is returned with ``score: null``;
      * the rest of the documented payload (post fields, route, offer
        fields) is unaffected.
    """
    user_id, token = _create_user_and_token()
    route_id = _create_route()
    post_id = _create_post(user_id, route_id)
    _create_offer(post_id, user_id, 150.0)
    _create_offer(post_id, user_id, 160.0)

    response = http_client.get(
        f"/rf005/posts/{post_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # Post-level fields are present and come from the Posts service.
    assert data["id"] == post_id
    assert data["expireAt"]
    assert data["createdAt"]
    # The route was resolved from the Routes service.
    assert data["route"]["id"] == route_id
    assert data["route"]["flightId"]
    # Both offers are present, and both carry a null score.
    offers = data["offers"]
    assert len(offers) == 2
    for offer in offers:
        assert offer["score"] is None
        assert offer["id"]
        assert offer["userId"] == user_id
        assert offer["description"]
        assert offer["size"]
        assert offer["fragile"] is False
        assert offer["offer"]
        assert offer["createdAt"]


@requires_services
def test_offer_without_persisted_score_returns_null_score(http_client: TestClient):
    """An offer with no persisted score appears with score null.

    This is the per-offer case (no outage at all would give the same
    result; here the outage guarantees the null), and the request
    still returns 200.
    """
    user_id, token = _create_user_and_token()
    route_id = _create_route()
    post_id = _create_post(user_id, route_id)
    _create_offer(post_id, user_id, 120.0)

    response = http_client.get(
        f"/rf005/posts/{post_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    offers = response.json()["data"]["offers"]
    assert len(offers) == 1
    assert offers[0]["score"] is None


@requires_services
def test_sorting_stays_correct_with_null_scores(http_client: TestClient):
    """Offers keep their documented order when scores are null.

    With the Score service down every offer has a null score, so the
    documented tie-break applies: ``createdAt`` descending (most
    recent offer first). The request still returns 200.
    """
    user_id, token = _create_user_and_token()
    route_id = _create_route()
    post_id = _create_post(user_id, route_id)
    _create_offer(post_id, user_id, 110.0)
    _create_offer(post_id, user_id, 120.0)
    _create_offer(post_id, user_id, 130.0)

    response = http_client.get(
        f"/rf005/posts/{post_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    offers = response.json()["data"]["offers"]
    assert len(offers) == 3
    assert all(o["score"] is None for o in offers)
    # Ties (all nulls) are broken by createdAt descending.
    created_at = [o["createdAt"] for o in offers]
    assert created_at == sorted(created_at, reverse=True)


@requires_services
def test_business_rejections_pass_through_with_score_down(http_client: TestClient):
    """401/403/404 from prior stages are unchanged while Score is down."""
    user_id, token = _create_user_and_token()
    route_id = _create_route()
    post_id = _create_post(user_id, route_id)

    # Missing token: 403 with an empty body.
    response = http_client.get(f"/rf005/posts/{post_id}")
    assert response.status_code == 403
    assert response.text == ""

    # Invalid token: 401 with an empty body.
    response = http_client.get(
        f"/rf005/posts/{post_id}",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert response.text == ""

    # Unknown post: 404 with an empty body.
    response = http_client.get(
        f"/rf005/posts/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.text == ""

    # Non-owner: 403 with an empty body.
    stranger_id, stranger_token = _create_user_and_token()
    assert stranger_id != user_id
    response = http_client.get(
        f"/rf005/posts/{post_id}",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert response.status_code == 403
    assert response.text == ""
