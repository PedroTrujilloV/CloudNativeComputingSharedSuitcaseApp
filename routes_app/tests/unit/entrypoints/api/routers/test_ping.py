import pytest
from fastapi.testclient import TestClient
from entrypoints.api.main import app
from errors import RouteNotFoundError, RouteAlreadyExistsError


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_ping_returns_pong(client):
    """Test that /routes/ping returns pong."""
    response = client.get("/routes/ping")
    assert response.status_code == 200
    assert response.content.decode("utf-8") == "pong"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"