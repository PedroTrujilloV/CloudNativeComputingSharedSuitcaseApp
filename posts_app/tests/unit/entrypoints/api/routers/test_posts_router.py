"""
Unit tests for Posts Service endpoints.
"""
from datetime import datetime, timedelta


def test_ping_returns_pong(client):
    """Test that GET /posts/ping returns 200 with body 'pong'."""
    response = client.get("/posts/ping")

    assert response.status_code == 200
    assert response.text == "pong"


def test_ping_endpoint_exists(client):
    """Test that /posts/ping endpoint is accessible."""
    response = client.get("/posts/ping")

    assert response.status_code == 200
    assert "pong" in response.text.lower()


class TestCreatePost:
    """Test suite for POST /posts endpoint."""

    def test_create_post_success(self, client):
        """Test successful post creation returns 201."""
        expire_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": expire_at,
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 201
        body = response.json()
        assert "id" in body
        assert body["userId"] == "22222222-2222-4222-8222-222222222222"
        assert "createdAt" in body
        # Verify ISO format
        datetime.fromisoformat(body["createdAt"])

    def test_create_post_missing_route_id(self, client):
        """Test missing routeId returns 400."""
        expire_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        payload = {
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": expire_at,
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 400

    def test_create_post_missing_user_id(self, client):
        """Test missing userId returns 400."""
        expire_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "expireAt": expire_at,
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 400

    def test_create_post_missing_expire_at(self, client):
        """Test missing expireAt returns 400."""
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 400

    def test_create_post_invalid_expire_at_format(self, client):
        """Test invalid expireAt format returns 400."""
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": "not-a-date",
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 400

    def test_create_post_expire_at_in_past(self, client):
        """Test past expireAt returns 412 with message."""
        expire_at = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": expire_at,
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 412
        body = response.json()
        assert body["msg"] == "La fecha expiración no es válida"

    def test_create_post_expire_at_now(self, client):
        """Test current time expireAt returns 412."""
        expire_at = datetime.utcnow().isoformat()
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": expire_at,
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 412
        body = response.json()
        assert body["msg"] == "La fecha expiración no es válida"

    def test_create_post_response_iso_format(self, client):
        """Test createdAt is in ISO format."""
        expire_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": expire_at,
        }

        response = client.post("/posts", json=payload)

        assert response.status_code == 201
        body = response.json()
        # Verify it can be parsed as ISO datetime
        created_at = datetime.fromisoformat(body["createdAt"])
        assert isinstance(created_at, datetime)

    def test_create_post_each_call_gets_unique_id(self, client):
        """Test each post creation gets unique ID."""
        expire_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        payload = {
            "routeId": "11111111-1111-4111-8111-111111111111",
            "userId": "22222222-2222-4222-8222-222222222222",
            "expireAt": expire_at,
        }

        response1 = client.post("/posts", json=payload)
        response2 = client.post("/posts", json=payload)

        id1 = response1.json()["id"]
        id2 = response2.json()["id"]

        assert id1 != id2
