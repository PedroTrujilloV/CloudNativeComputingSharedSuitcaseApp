"""Integration tests for RF-003 against the real downstream services.

These tests exercise the full HTTP stack (orchestrator -> Users/Routes/Posts
services) and are intended to run in a local/CI environment where the three
services are reachable. They are skipped automatically when the services are
not up, so the unit suite stays green in isolation.

Required environment (defaults match the local docker-compose-style layout):
  - RF003_INTEGRATION_BASE   orchestrator URL  (default http://localhost:8001)
  - RF003_USERS_BASE         users service URL (default http://localhost:8000)
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

RF003_BASE = os.getenv("RF003_INTEGRATION_BASE", "http://localhost:8001")
USERS_BASE = os.getenv("RF003_USERS_BASE", "http://localhost:8000")


def _service_reachable(base: str) -> bool:
    """Return True when the service answers its /ping endpoint."""
    try:
        r = httpx.get(f"{base}/rf003/ping", timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def _users_reachable(base: str) -> bool:
    try:
        r = httpx.get(f"{base}/users/ping", timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


requires_services = pytest.mark.skipif(
    not (_service_reachable(RF003_BASE) and _users_reachable(USERS_BASE)),
    reason="RF-003 downstream services are not reachable; skipping integration tests",
)


def _future_payload(flight_id: str, **overrides) -> dict:
    """A payload whose dates are always in the future (relative to now)."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=10)
    end = now + timedelta(days=11)
    expire = now + timedelta(days=5)
    payload = {
        "flightId": flight_id,
        "expireAt": expire.isoformat(),
        "plannedStartDate": start.isoformat(),
        "plannedEndDate": end.isoformat(),
        "origin": {"airportCode": "BOG", "country": "Colombia"},
        "destiny": {"airportCode": "MAD", "country": "Spain"},
        "bagCost": 350,
    }
    payload.update(overrides)
    return payload


def _create_user_and_token(base: str) -> str:
    """Create a fresh user and return a valid bearer token."""
    username = f"rf003_it_{uuid.uuid4().hex[:10]}"
    email = f"{username}@example.com"
    r = httpx.post(
        f"{base}/users",
        json={
            "username": username,
            "password": "Secret123!",
            "email": email,
            "dni": "123456789",
            "fullName": "Integration Tester",
            "phoneNumber": "3001234567",
        },
        timeout=5,
    )
    assert r.status_code == 201, r.text
    r = httpx.post(
        f"{base}/users/auth",
        json={"username": username, "password": "Secret123!"},
        timeout=5,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@requires_services
def test_full_happy_path_creates_route_and_post():
    """A valid request resolves a new route, creates a post, returns 201."""
    token = _create_user_and_token(USERS_BASE)
    flight = f"IT{uuid.uuid4().hex[:6].upper()}"

    r = httpx.post(
        f"{RF003_BASE}/rf003/posts",
        json=_future_payload(flight),
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"data", "msg"}
    data = body["data"]
    assert data["route"]["id"]
    assert data["id"]
    assert data["userId"]


@requires_services
def test_reusing_flight_id_does_not_fail():
    """The same flightId used twice: the second request reuses the route."""
    token = _create_user_and_token(USERS_BASE)
    flight = f"IT{uuid.uuid4().hex[:6].upper()}"

    first = httpx.post(
        f"{RF003_BASE}/rf003/posts",
        json=_future_payload(flight),
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["route"]["id"]

    second = httpx.post(
        f"{RF003_BASE}/rf003/posts",
        json=_future_payload(flight),
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    # The route is reused, but the user already has a post for it -> 412.
    assert second.status_code == 412, second.text
    assert second.json() == {
        "msg": "El usuario ya tiene una publicación para la misma fecha"
    }


@requires_services
def test_missing_token_returns_403():
    flight = f"IT{uuid.uuid4().hex[:6].upper()}"
    r = httpx.post(
        f"{RF003_BASE}/rf003/posts", json=_future_payload(flight), timeout=10
    )
    assert r.status_code == 403
    assert r.text == ""


@requires_services
def test_invalid_token_returns_401():
    flight = f"IT{uuid.uuid4().hex[:6].upper()}"
    r = httpx.post(
        f"{RF003_BASE}/rf003/posts",
        json=_future_payload(flight),
        headers={"Authorization": "Bearer not-a-real-token"},
        timeout=10,
    )
    assert r.status_code == 401
    assert r.text == ""


@requires_services
def test_missing_field_returns_400():
    token = _create_user_and_token(USERS_BASE)
    flight = f"IT{uuid.uuid4().hex[:6].upper()}"
    payload = _future_payload(flight)
    del payload["flightId"]
    r = httpx.post(
        f"{RF003_BASE}/rf003/posts",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code == 400
    assert r.text == ""


@requires_services
def test_expire_at_after_planned_start_returns_412():
    token = _create_user_and_token(USERS_BASE)
    flight = f"IT{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=10)
    payload = _future_payload(flight, expireAt=(start + timedelta(days=1)).isoformat())
    r = httpx.post(
        f"{RF003_BASE}/rf003/posts",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code == 412, r.text
    assert r.json() == {"msg": "La fecha expiración no es válida"}
