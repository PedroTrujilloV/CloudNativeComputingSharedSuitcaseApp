"""
Contract tests for POST /posts, matching the payloads the delivery's Postman
collection sends.
"""
from datetime import datetime, timedelta


ROUTE_ID = "11111111-1111-4111-8111-111111111111"
USER_ID = "22222222-2222-4222-8222-222222222222"


def future_iso_utc():
    """An expireAt exactly as Date.toISOString() produces it."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def payload(**overrides):
    body = {
        "routeId": ROUTE_ID,
        "userId": USER_ID,
        "expireAt": (datetime.utcnow() + timedelta(days=7)).isoformat(),
    }
    body.update(overrides)
    return body


class TestExpireAtTimezone:
    """expireAt arrives offset-aware; it must not be compared while aware."""

    def test_offset_aware_expire_at_is_accepted(self, client):
        expire_at = (
            (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()
            + "Z"
        )

        response = client.post("/posts", json=payload(expireAt=expire_at))

        assert response.status_code == 201

    def test_offset_aware_expire_at_in_the_past_returns_412(self, client):
        response = client.post(
            "/posts", json=payload(expireAt="2022-08-01T21:20:53.214Z")
        )

        assert response.status_code == 412
        assert response.json() == {"msg": "La fecha expiración no es válida"}

    def test_explicit_offset_is_accepted(self, client):
        expire_at = (
            (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()
            + "+00:00"
        )

        response = client.post("/posts", json=payload(expireAt=expire_at))

        assert response.status_code == 201


class TestIdentifierValidation:
    """routeId and userId must be uuid strings."""

    def test_malformed_route_id_returns_400(self, client):
        assert client.post("/posts", json=payload(routeId="invalidId")).status_code == 400

    def test_malformed_user_id_returns_400(self, client):
        assert client.post("/posts", json=payload(userId="invalidId")).status_code == 400

    def test_malformed_identifier_does_not_persist_the_post(self, client):
        client.post("/posts", json=payload(routeId="invalidId"))

        assert client.get("/posts/count").json() == {"count": 0}

    def test_valid_identifiers_are_accepted(self, client):
        assert client.post("/posts", json=payload()).status_code == 201


class TestTimestampRoundTrip:
    """Timestamps go back out carrying the timezone they were sent with."""

    def test_expire_at_round_trips_through_get_by_id(self, client):
        sent = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0)
        expire_at = sent.isoformat() + "Z"
        post_id = client.post("/posts", json=payload(expireAt=expire_at)).json()["id"]

        body = client.get(f"/posts/{post_id}").json()

        assert body["expireAt"] == expire_at

    def test_timestamps_are_designated_utc(self, client):
        post_id = client.post("/posts", json=payload()).json()["id"]

        body = client.get(f"/posts/{post_id}").json()

        assert body["expireAt"].endswith("Z")
        assert body["createdAt"].endswith("Z")
        assert datetime.fromisoformat(body["expireAt"]).tzinfo is not None

    def test_created_at_is_designated_utc_on_create(self, client):
        body = client.post("/posts", json=payload()).json()

        assert body["createdAt"].endswith("Z")

    def test_list_timestamps_are_designated_utc(self, client):
        client.post("/posts", json=payload())

        body = client.get("/posts").json()[0]

        assert body["expireAt"].endswith("Z")
        assert body["createdAt"].endswith("Z")


class TestMissingFields:
    """Missing required fields keep returning 400."""

    def test_missing_route_id_returns_400(self, client):
        body = payload()
        del body["routeId"]

        assert client.post("/posts", json=body).status_code == 400

    def test_missing_expire_at_returns_400(self, client):
        body = payload()
        del body["expireAt"]

        assert client.post("/posts", json=body).status_code == 400

    def test_malformed_expire_at_returns_400(self, client):
        assert client.post("/posts", json=payload(expireAt="not-a-date")).status_code == 400
